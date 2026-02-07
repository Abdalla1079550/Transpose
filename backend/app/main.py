from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from .card import generate_candidate_card, serialize_card
from .config import Settings, get_settings
from .crustdata_client import (
    CrustDataAuthError,
    CrustDataClient,
    CrustDataCreditsError,
    CrustDataError,
    CrustDataPermissionError,
)
from .cv_parser import CVParseError, parse_cv
from .db import get_session, init_db
from .demo_data import load_all_demo_payloads, load_demo_json, load_demo_market_snapshot
from .demo_seed import bootstrap_demo_dataset
from .market import build_market_snapshot
from .matching import compute_match
from .models import Match, RoleQuery, Student
from .openai_client import OpenAIHelper
from .schemas import (
    CandidateCardResponse,
    CrustDataSmokeResponse,
    DemoCachedResponse,
    DemoBootstrapResponse,
    HealthResponse,
    InterviewQuestion,
    InterviewQuestionsResponse,
    MarketSnapshotResponse,
    MatchItem,
    RoleCreateRequest,
    RoleCreateResponse,
    RoleMatchesResponse,
    OutreachRequest,
    OutreachResponse,
    StudentCreatedResponse,
    StudentInterviewRequest,
    StudentInterviewResponse,
)
from .text_utils import extract_skills_from_text

settings = get_settings()
openai_helper = OpenAIHelper(
    api_key=settings.openai_api_key,
    chat_model=settings.openai_chat_model,
    embedding_model=settings.openai_embedding_model,
)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_crustdata_client() -> CrustDataClient:
    cfg: Settings = get_settings()
    return CrustDataClient(
        token=cfg.crustdata_token,
        auth_scheme=cfg.crustdata_auth_scheme,
        base_url=cfg.crustdata_base_url,
        timeout_seconds=cfg.crustdata_timeout_seconds,
        ttl_seconds=cfg.crustdata_cache_ttl_seconds,
    )


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.exception_handler(CrustDataAuthError)
async def crustdata_auth_error_handler(_, exc: CrustDataAuthError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(CrustDataPermissionError)
async def crustdata_permission_error_handler(_, exc: CrustDataPermissionError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(CrustDataCreditsError)
async def crustdata_credits_error_handler(_, exc: CrustDataCreditsError) -> JSONResponse:
    return JSONResponse(status_code=402, content={"detail": str(exc)})


@app.exception_handler(CrustDataError)
async def crustdata_generic_error_handler(_, exc: CrustDataError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _now_ms() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)


def _parse_answers(payload: StudentInterviewRequest) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []

    if payload.role_cluster:
        normalized.append({"question": "Target role cluster(s)", "answer": payload.role_cluster})
    if payload.location_preference:
        normalized.append({"question": "Location preference", "answer": payload.location_preference})

    for item in payload.answers:
        if isinstance(item, str):
            text = item.strip()
            if text:
                normalized.append({"question": "response", "answer": text})
        else:
            question = item.question.strip()
            answer = item.answer.strip()
            if question or answer:
                normalized.append({"question": question or "response", "answer": answer})

    if payload.notes and payload.notes.strip():
        normalized.append({"question": "additional_notes", "answer": payload.notes.strip()})

    return normalized


def _role_from_interview(student: Student) -> str:
    try:
        answers = json.loads(student.interview_answers_json)
    except json.JSONDecodeError:
        return "data_analyst"
    if not isinstance(answers, list):
        return "data_analyst"
    for item in answers:
        if isinstance(item, dict) and str(item.get("question", "")).lower().startswith("target role"):
            value = item.get("answer")
            if isinstance(value, str) and value.strip():
                return value.strip().lower().replace(" ", "_")
    return "data_analyst"


def _snapshot_from_demo(region: str, role_cluster: str, days: int, mode: str) -> MarketSnapshotResponse:
    cached = load_demo_market_snapshot(role_cluster)
    cached["region"] = region
    cached["role_cluster"] = role_cluster
    cached["window_days"] = days
    cached["mode"] = mode
    cached["updated_at_epoch_ms"] = _now_ms()
    cached["updated_at"] = _now_iso()
    return MarketSnapshotResponse(**cached)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    live = not settings.demo_mode
    return HealthResponse(
        ok=True,
        service="edgematch-backend",
        mode="live" if live else "demo",
        data_source="Crustdata" if live else "Cached demo payloads",
        updated_at=_now_iso(),
    )


@app.get("/market/snapshot", response_model=MarketSnapshotResponse)
def market_snapshot(
    region: str = Query(default="AE"),
    role_cluster: str = Query(default="data_analyst"),
    days: int = Query(default=7, ge=1, le=30),
) -> MarketSnapshotResponse:
    if settings.demo_mode:
        return _snapshot_from_demo(region=region, role_cluster=role_cluster, days=days, mode="demo")

    client = get_crustdata_client()
    try:
        payload = build_market_snapshot(client=client, region=region, role_cluster=role_cluster, days=days)
        payload["data_source"] = "Crustdata"
        payload["mode"] = "live"
        payload["updated_at_epoch_ms"] = _now_ms()
        payload["updated_at"] = _now_iso()
        return MarketSnapshotResponse(**payload)
    except CrustDataError:
        return _snapshot_from_demo(region=region, role_cluster=role_cluster, days=days, mode="fallback-demo")


@app.get("/students/interview-questions", response_model=InterviewQuestionsResponse)
def interview_questions() -> InterviewQuestionsResponse:
    cached = load_demo_json("interview_questions.json")
    payload = cached.get("questions", [])
    normalized: list[InterviewQuestion] = []
    for index, item in enumerate(payload):
        if isinstance(item, str):
            normalized.append(InterviewQuestion(id=f"q_{index + 1}", prompt=item))
        elif isinstance(item, dict):
            qid = str(item.get("id") or f"q_{index + 1}")
            prompt = str(item.get("prompt") or item.get("question") or "")
            if prompt:
                normalized.append(InterviewQuestion(id=qid, prompt=prompt))
    return InterviewQuestionsResponse(questions=normalized)


@app.post("/students", response_model=StudentCreatedResponse)
def create_student(
    name: str | None = Form(default=None),
    full_name: str | None = Form(default=None),
    email: str | None = Form(default=None),
    region_pref: str | None = Form(default=None),
    location: str | None = Form(default=None),
    grad_year: int | None = Form(default=None),
    skills: str | None = Form(default=None),
    cv: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> StudentCreatedResponse:
    cv_bytes = cv.file.read()
    if not cv_bytes:
        raise HTTPException(status_code=400, detail="CV file is empty.")

    try:
        cv_text = parse_cv(cv.filename or "cv", cv_bytes)
    except CVParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    candidate_name = (name or full_name or "Unnamed Candidate").strip()
    explicit_skills = [item.strip() for item in (skills or "").split(",") if item.strip()]
    inferred = extract_skills_from_text(cv_text, max_items=15)
    merged_skills = list(dict.fromkeys([*explicit_skills, *inferred]))[:15]

    student = Student(
        name=candidate_name,
        email=email,
        region_pref=(region_pref or location),
        grad_year=grad_year,
        cv_text=cv_text,
        skills_json=json.dumps(merged_skills, ensure_ascii=True),
        updated_at=datetime.now(UTC),
    )
    session.add(student)
    session.commit()
    session.refresh(student)

    return StudentCreatedResponse(id=student.id or 0, name=student.name, created_at=student.created_at)


@app.post("/students/{student_id}/interview", response_model=StudentInterviewResponse)
def save_interview(
    student_id: int,
    payload: StudentInterviewRequest,
    session: Session = Depends(get_session),
) -> StudentInterviewResponse:
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    normalized = _parse_answers(payload)
    student.interview_answers_json = json.dumps(normalized, ensure_ascii=True)
    student.updated_at = datetime.now(UTC)
    session.add(student)
    session.commit()

    return StudentInterviewResponse(id=student_id, saved_answers_count=len(normalized))


@app.get("/students/{student_id}/card", response_model=CandidateCardResponse)
def student_card(
    student_id: int,
    refresh: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> CandidateCardResponse:
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    if student.card_json and not refresh:
        try:
            card = json.loads(student.card_json)
            if isinstance(card, dict):
                return CandidateCardResponse(id=student_id, card=card)
        except json.JSONDecodeError:
            pass

    role_cluster = _role_from_interview(student)
    region = student.region_pref or "AE"
    market_ctx: dict[str, Any] | None = None

    if settings.demo_mode:
        market_ctx = load_demo_market_snapshot(role_cluster)
    else:
        client = get_crustdata_client()
        try:
            market_ctx = build_market_snapshot(client=client, region=region, role_cluster=role_cluster, days=7)
        except CrustDataError:
            market_ctx = load_demo_market_snapshot(role_cluster)

    card = generate_candidate_card(student=student, openai_helper=openai_helper, market_snapshot=market_ctx)
    student.card_json = serialize_card(card)
    student.updated_at = datetime.now(UTC)
    session.add(student)
    session.commit()

    return CandidateCardResponse(id=student_id, card=card)


@app.post("/roles", response_model=RoleCreateResponse)
def create_role(payload: RoleCreateRequest, session: Session = Depends(get_session)) -> RoleCreateResponse:
    title = (payload.title or payload.role_title or "Untitled Role").strip()
    skills = payload.skills_must if payload.skills_must else payload.must_have_skills

    role = RoleQuery(
        title=title,
        region=(payload.region or payload.location),
        raw_desc=(payload.raw_desc or payload.description),
        skills_must_json=json.dumps([skill.strip().lower() for skill in skills if skill.strip()], ensure_ascii=True),
        min_grad_year=payload.min_grad_year,
        max_grad_year=payload.max_grad_year,
        source_job_id=payload.job_id,
        source_job_url=payload.job_url,
    )
    session.add(role)
    session.commit()
    session.refresh(role)

    return RoleCreateResponse(id=role.id or 0, title=role.title, region=role.region)


@app.get("/roles/{role_id}/matches", response_model=RoleMatchesResponse)
def role_matches(
    role_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    include_failed: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> RoleMatchesResponse:
    role = session.get(RoleQuery, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")

    students = session.exec(select(Student)).all()
    response_items: list[MatchItem] = []

    for student in students:
        computed = compute_match(role, student, openai_helper)
        existing = session.exec(
            select(Match).where(Match.role_query_id == role_id).where(Match.student_id == (student.id or -1))
        ).first()
        if not existing:
            existing = Match(role_query_id=role_id, student_id=student.id or 0)

        existing.score = computed.score
        existing.hard_filter_passed = computed.hard_filter_passed
        existing.rationale = computed.rationale
        existing.evidence_json = json.dumps(computed.evidence, ensure_ascii=True)
        existing.gap_flags_json = json.dumps(computed.gap_flags, ensure_ascii=True)
        session.add(existing)

        if include_failed or computed.hard_filter_passed:
            response_items.append(
                MatchItem(
                    student_id=student.id or 0,
                    student_name=student.name,
                    score=computed.score,
                    rationale=computed.rationale,
                    evidence=computed.evidence,
                    gap_flags=computed.gap_flags,
                    hard_filter_passed=computed.hard_filter_passed,
                )
            )

    session.commit()

    ordered = sorted(response_items, key=lambda item: (item.hard_filter_passed, item.score), reverse=True)[:limit]
    return RoleMatchesResponse(role_id=role_id, total=len(ordered), matches=ordered)


@app.post("/roles/{role_id}/outreach", response_model=OutreachResponse)
def role_outreach(
    role_id: int,
    payload: OutreachRequest,
    session: Session = Depends(get_session),
) -> OutreachResponse:
    role = session.get(RoleQuery, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")

    student = session.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    match = session.exec(
        select(Match).where(Match.role_query_id == role_id).where(Match.student_id == payload.student_id)
    ).first()
    if not match:
        computed = compute_match(role, student, openai_helper)
        rationale = computed.rationale
        evidence = computed.evidence
    else:
        rationale = match.rationale
        try:
            evidence_raw = json.loads(match.evidence_json or "[]")
            evidence = [str(item) for item in evidence_raw if isinstance(item, str)]
        except json.JSONDecodeError:
            evidence = []

    subject = f"{role.title}: potential fit conversation"
    body = openai_helper.generate_outreach(
        role_title=role.title,
        student_name=student.name,
        rationale=rationale,
        evidence=evidence,
    )
    if not body:
        body = (
            f"Hi {student.name},\n\n"
            f"We reviewed your profile for our {role.title} opening and saw a strong alignment. "
            f"{rationale} "
            f"We would like to schedule a short conversation this week to discuss fit and next steps.\n\n"
            "Best,\nRecruiting Team"
        )

    return OutreachResponse(role_id=role_id, student_id=payload.student_id, subject=subject, body=body)


@app.get("/demo/cached", response_model=DemoCachedResponse)
def demo_cached() -> DemoCachedResponse:
    return DemoCachedResponse(payloads=load_all_demo_payloads())


@app.post("/demo/bootstrap", response_model=DemoBootstrapResponse)
def demo_bootstrap(
    reset: bool = Query(default=True),
    session: Session = Depends(get_session),
) -> DemoBootstrapResponse:
    payload = bootstrap_demo_dataset(session=session, openai_helper=openai_helper, reset=reset)
    return DemoBootstrapResponse(**payload)


@app.get("/crustdata/smoke-auth", response_model=CrustDataSmokeResponse)
def crustdata_smoke_auth() -> CrustDataSmokeResponse:
    if settings.demo_mode:
        details = load_demo_json("crustdata_smoke_auth.json")
        return CrustDataSmokeResponse(
            ok=True,
            mode="demo",
            selected_scheme=str(details.get("selected_scheme") or "mixed"),
            details=details,
        )

    client = get_crustdata_client()
    details = client.smoke_auth_probe()
    selected_scheme = str(details.get("selected_scheme") or settings.crustdata_auth_scheme)
    return CrustDataSmokeResponse(ok=True, mode="live", selected_scheme=selected_scheme, details=details)
