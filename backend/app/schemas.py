from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    ok: bool
    service: str


class MarketSnapshotResponse(BaseModel):
    region: str
    role_cluster: str
    days: int
    source: str
    companies: list[dict[str, Any]]
    news: list[dict[str, Any]]


class InterviewQuestionsResponse(BaseModel):
    questions: list[str]


class StudentCreatedResponse(BaseModel):
    id: int
    full_name: str
    created_at: datetime


class StudentInterviewRequest(BaseModel):
    answers: list[str] = Field(default_factory=list)
    notes: str | None = None


class StudentInterviewResponse(BaseModel):
    id: int
    interview_notes: str


class CandidateCardResponse(BaseModel):
    id: int
    card: dict[str, Any]


class RoleCreateRequest(BaseModel):
    title: str
    description: str | None = None
    location: str | None = None
    must_have_skills: list[str] = Field(default_factory=list)
    min_grad_year: int | None = None


class RoleCreateResponse(BaseModel):
    id: int
    title: str


class MatchItem(BaseModel):
    student_id: int
    student_name: str
    score: float
    hard_filter_passed: bool
    rationale: str


class RoleMatchesResponse(BaseModel):
    role_id: int
    total: int
    matches: list[MatchItem]


class DemoCachedResponse(BaseModel):
    payloads: dict[str, Any]


class CrustDataSmokeResponse(BaseModel):
    ok: bool
    mode: str
    details: dict[str, Any]
