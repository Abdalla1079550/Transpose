from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Student(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str | None = None
    region_pref: str | None = None
    grad_year: int | None = None
    cv_text: str = ""
    interview_answers_json: str = "[]"
    skills_json: str = "[]"
    card_json: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RoleQuery(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    region: str | None = None
    raw_desc: str | None = None
    skills_must_json: str = "[]"
    min_grad_year: int | None = None
    max_grad_year: int | None = None
    source_job_id: str | None = None
    source_job_url: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Match(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    role_query_id: int = Field(index=True, foreign_key="rolequery.id")
    student_id: int = Field(index=True, foreign_key="student.id")
    score: float = 0.0
    rationale: str = ""
    evidence_json: str = "[]"
    gap_flags_json: str = "[]"
    hard_filter_passed: bool = False
    created_at: datetime = Field(default_factory=utc_now)
