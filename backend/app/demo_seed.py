from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, delete, select

from .card import generate_candidate_card, serialize_card
from .demo_data import load_demo_json, load_demo_market_snapshot
from .matching import compute_match
from .models import Match, RoleQuery, Student
from .openai_client import OpenAIHelper


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _template_outreach(role_title: str, student_name: str, rationale: str) -> tuple[str, str]:
    subject = f"{role_title}: fast-track interview invitation"
    body = (
        f"Hi {student_name},\n\n"
        f"We reviewed your profile for our {role_title} role. {rationale} "
        "Your projects map well to our current team priorities. "
        "Are you available for a 20-minute fit conversation this week?\n\n"
        "Best,\nTalent Team"
    )
    return subject, body


def _safe_list(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _pick_market_snapshot_for_role(role_title: str, role_cluster_hint: str | None = None) -> dict[str, Any]:
    if role_cluster_hint:
        return load_demo_market_snapshot(role_cluster_hint)

    lowered = role_title.lower()
    if "data" in lowered or "analyst" in lowered:
        return load_demo_market_snapshot("data_analyst")
    if "security" in lowered or "cyber" in lowered:
        return load_demo_market_snapshot("cybersecurity")
    if "product" in lowered:
        return load_demo_market_snapshot("product")
    return load_demo_market_snapshot("software_engineer")


def bootstrap_demo_dataset(
    session: Session,
    openai_helper: OpenAIHelper,
    reset: bool = True,
) -> dict[str, Any]:
    scenario = load_demo_json("demo_scenario.json")
    students_payload = _safe_list(scenario.get("students"))
    roles_payload = _safe_list(scenario.get("roles"))

    if reset:
        session.exec(delete(Match))
        session.exec(delete(RoleQuery))
        session.exec(delete(Student))
        session.commit()

    created_students: list[Student] = []
    for item in students_payload:
        skills = [str(skill).strip() for skill in item.get("skills", []) if str(skill).strip()]
        interview_answers = item.get("interview_answers", [])

        student = Student(
            name=str(item.get("name") or "Unnamed Candidate"),
            email=str(item.get("email") or ""),
            region_pref=str(item.get("region_pref") or "AE"),
            grad_year=int(item.get("grad_year") or 2026),
            cv_text=str(item.get("cv_text") or ""),
            interview_answers_json=json.dumps(interview_answers, ensure_ascii=True),
            skills_json=json.dumps(skills, ensure_ascii=True),
            updated_at=datetime.now(UTC),
        )

        market_snapshot = _pick_market_snapshot_for_role(
            role_title=str(item.get("target_role") or "Data Analyst"),
            role_cluster_hint=str(item.get("role_cluster") or "data_analyst"),
        )
        card = generate_candidate_card(student=student, openai_helper=openai_helper, market_snapshot=market_snapshot)
        student.card_json = serialize_card(card)

        session.add(student)
        session.flush()
        created_students.append(student)

    created_roles: list[RoleQuery] = []
    for item in roles_payload:
        must = [str(skill).strip().lower() for skill in item.get("skills_must", []) if str(skill).strip()]
        role = RoleQuery(
            title=str(item.get("title") or "Untitled Role"),
            region=str(item.get("region") or "AE"),
            raw_desc=str(item.get("raw_desc") or ""),
            skills_must_json=json.dumps(must, ensure_ascii=True),
            min_grad_year=int(item.get("min_grad_year") or 2025),
            max_grad_year=int(item.get("max_grad_year") or 2028),
            source_job_id=str(item.get("source_job_id") or ""),
            source_job_url=str(item.get("source_job_url") or ""),
        )
        session.add(role)
        session.flush()
        created_roles.append(role)

    previews: list[dict[str, Any]] = []
    for role in created_roles:
        role_matches: list[tuple[Student, float]] = []
        for student in created_students:
            computed = compute_match(role=role, student=student, openai_helper=openai_helper)
            match = Match(
                role_query_id=role.id or 0,
                student_id=student.id or 0,
                score=computed.score,
                rationale=computed.rationale,
                evidence_json=json.dumps(computed.evidence, ensure_ascii=True),
                gap_flags_json=json.dumps(computed.gap_flags, ensure_ascii=True),
                hard_filter_passed=computed.hard_filter_passed,
            )
            session.add(match)
            role_matches.append((student, computed.score if computed.hard_filter_passed else 0.0))

        role_matches.sort(key=lambda item: item[1], reverse=True)
        if role_matches and role_matches[0][1] > 0:
            top_student = role_matches[0][0]
            top_match = session.exec(
                select(Match)
                .where(Match.role_query_id == (role.id or -1))
                .where(Match.student_id == (top_student.id or -1))
            ).first()
            rationale = top_match.rationale if top_match else "Strong fit"
            evidence = []
            if top_match:
                try:
                    evidence_raw = json.loads(top_match.evidence_json)
                    evidence = [str(line) for line in evidence_raw if isinstance(line, str)]
                except json.JSONDecodeError:
                    evidence = []

            subject, body = _template_outreach(role.title, top_student.name, rationale)
            generated = openai_helper.generate_outreach(role.title, top_student.name, rationale, evidence)
            previews.append(
                {
                    "role_id": role.id or 0,
                    "role_title": role.title,
                    "student_id": top_student.id or 0,
                    "student_name": top_student.name,
                    "subject": subject,
                    "body": generated or body,
                }
            )

    session.commit()

    showcase_region = str(scenario.get("default_region") or "AE")
    showcase_role_cluster = str(scenario.get("default_role_cluster") or "data_analyst")

    first_student = created_students[0] if created_students else None
    first_role = created_roles[0] if created_roles else None

    return {
        "ok": True,
        "dataset_version": str(scenario.get("dataset_version") or "demo-v1"),
        "seeded_at": _now_iso(),
        "students": [
            {"id": student.id or 0, "name": student.name}
            for student in created_students
        ],
        "roles": [
            {"id": role.id or 0, "title": role.title, "region": role.region}
            for role in created_roles
        ],
        "showcase": {
            "student_id": first_student.id if first_student and first_student.id else 0,
            "role_id": first_role.id if first_role and first_role.id else 0,
            "region": showcase_region,
            "role_cluster": showcase_role_cluster,
        },
        "outreach_previews": previews[:3],
    }
