from __future__ import annotations

import json
from datetime import datetime, timezone
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
from .demo_data import load_all_demo_payloads, load_demo_json
from .matching import compute_match
from .models import Match, RoleQuery, Student
from .openai_client import OpenAIHelper
from .schemas import (
    CandidateCardResponse,
    CrustDataSmokeResponse,
    DemoCachedResponse,
    HealthResponse,
    InterviewQuestionsResponse,
    MarketSnapshotResponse,
    MatchItem,
    RoleCreateRequest,
    RoleCreateResponse,
    RoleMatchesResponse,
    StudentCreatedResponse,
    StudentInterviewRequest,
    StudentInterviewResponse,
)

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


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True, service="edgematch-backend")


@app.get("/market/snapshot", response_model=MarketSnapshotResponse)
def market_snapshot(
    region: str = Query(default="US"),
    role_cluster: str = Query(default="data_analyst"),
    days: int = Query(default=7, ge=1, le=30),
) -> MarketSnapshotResponse:
    if settings.demo_mode:
        cached = load_demo_json("market_snapshot.json")
        return MarketSnapshotResponse(
            region=region,
            role_cluster=role_cluster,
            days=days,
            source="demo",
            companies=cached.get("companies", []),
            news=cached.get("news", []),
        )

    client = get_crustdata_client()

    try:
        filters = [
            {"type": "REGION", "op": "in", "value": [region]},
            {"type": "JOB_OPPORTUNITIES", "op": "in", "value": ["Hiring"]},
            {"type": "KEYWORD", "op": "in", "value": [role_cluster.replace("_", " ")]},
        ]
        company_search = client.post_company_search(filters=filters, page=1)
        web_search = client.post_web_search(
            query=f"{role_cluster.replace('_', ' ')} hiring in {region}",
            geolocation=region,
            sources=["news", "web"],
            fetch_content=False,
        )

        return MarketSnapshotResponse(
            region=region,
            role_cluster=role_cluster,
            days=days,
            source="live",
            companies=company_search.get("companies", [])[:10],
            news=web_search.get("results", [])[:8],
        )
    except CrustDataError:
        cached = load_demo_json("market_snapshot.json")
        return MarketSnapshotResponse(
            region=region,
            role_cluster=role_cluster,
            days=days,
            source="fallback-demo",
            companies=cached.get("companies", []),
            news=cached.get("news", []),
        )


@app.get("/students/interview-questions", response_model=InterviewQuestionsResponse)
def interview_questions() -> InterviewQuestionsResponse:
    cached = load_demo_json("interview_questions.json")
    questions = cached.get("questions", [])
    return InterviewQuestionsResponse(questions=questions)


@app.post("/students", response_model=StudentCreatedResponse)
def create_student(
    full_name: str = Form(...),
    email: str | None = Form(default=None),
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

    student = Student(
        full_name=full_name,
        email=email,
        location=location,
        grad_year=grad_year,
        skills_csv=skills or "",
        cv_filename=cv.filename,
        cv_text=cv_text,
        updated_at=datetime.now(timezone.utc),
    )
    session.add(student)
    session.commit()
    session.refresh(student)

    return StudentCreatedResponse(id=student.id or 0, full_name=student.full_name, created_at=student.created_at)


@app.post("/students/{student_id}/interview", response_model=StudentInterviewResponse)
def save_interview(
    student_id: int,
    payload: StudentInterviewRequest,
    session: Session = Depends(get_session),
) -> StudentInterviewResponse:
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    chunks = [answer.strip() for answer in payload.answers if answer.strip()]
    if payload.notes and payload.notes.strip():
        chunks.append(payload.notes.strip())
    notes = "\n".join(chunks)

    student.interview_notes = notes
    student.updated_at = datetime.now(timezone.utc)
    session.add(student)
    session.commit()

    return StudentInterviewResponse(id=student_id, interview_notes=student.interview_notes)


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

    card = generate_candidate_card(student, openai_helper)
    student.card_json = serialize_card(card)
    student.updated_at = datetime.now(timezone.utc)
    session.add(student)
    session.commit()

    return CandidateCardResponse(id=student_id, card=card)


@app.post("/roles", response_model=RoleCreateResponse)
def create_role(payload: RoleCreateRequest, session: Session = Depends(get_session)) -> RoleCreateResponse:
    role = RoleQuery(
        title=payload.title,
        description=payload.description,
        location=payload.location,
        must_have_skills_csv=",".join(payload.must_have_skills),
        min_grad_year=payload.min_grad_year,
    )
    session.add(role)
    session.commit()
    session.refresh(role)

    return RoleCreateResponse(id=role.id or 0, title=role.title)


@app.get("/roles/{role_id}/matches", response_model=RoleMatchesResponse)
def role_matches(
    role_id: int,
    limit: int = Query(default=20, ge=1, le=100),
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
            select(Match).where(Match.role_id == role_id).where(Match.student_id == (student.id or -1))
        ).first()
        if not existing:
            existing = Match(role_id=role_id, student_id=student.id or 0)

        existing.score = computed.score
        existing.hard_filter_passed = computed.hard_filter_passed
        existing.rationale = computed.rationale
        session.add(existing)

        if include_failed or computed.hard_filter_passed:
            response_items.append(
                MatchItem(
                    student_id=student.id or 0,
                    student_name=student.full_name,
                    score=computed.score,
                    hard_filter_passed=computed.hard_filter_passed,
                    rationale=computed.rationale,
                )
            )

    session.commit()

    ordered = sorted(response_items, key=lambda item: (item.hard_filter_passed, item.score), reverse=True)[:limit]
    return RoleMatchesResponse(role_id=role_id, total=len(ordered), matches=ordered)


@app.get("/demo/cached", response_model=DemoCachedResponse)
def demo_cached() -> DemoCachedResponse:
    return DemoCachedResponse(payloads=load_all_demo_payloads())


@app.get("/crustdata/smoke-auth", response_model=CrustDataSmokeResponse)
def crustdata_smoke_auth() -> CrustDataSmokeResponse:
    if settings.demo_mode:
        return CrustDataSmokeResponse(
            ok=True,
            mode="demo",
            details=load_demo_json("crustdata_smoke_auth.json"),
        )

    client = get_crustdata_client()
    payload: dict[str, Any] = client.get_company_enrich(
        company_domain="openai.com",
        fields=["company_name", "industry", "company_website_domain"],
    )

    details = {
        "status": "authenticated",
        "keys": sorted(list(payload.keys()))[:8],
    }
    return CrustDataSmokeResponse(ok=True, mode="live", details=details)
