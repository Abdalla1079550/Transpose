from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Student(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    full_name: str
    email: str | None = None
    location: str | None = None
    grad_year: int | None = None
    skills_csv: str = ""
    cv_filename: str | None = None
    cv_text: str = ""
    interview_notes: str = ""
    card_json: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RoleQuery(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = None
    location: str | None = None
    must_have_skills_csv: str = ""
    min_grad_year: int | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Match(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    role_id: int = Field(index=True, foreign_key="rolequery.id")
    student_id: int = Field(index=True, foreign_key="student.id")
    score: float = 0.0
    hard_filter_passed: bool = False
    rationale: str = ""
    created_at: datetime = Field(default_factory=utc_now)
