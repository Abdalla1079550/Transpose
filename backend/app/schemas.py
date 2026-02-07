from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class HealthResponse(BaseModel):
    ok: bool
    service: str
    mode: Literal["live", "demo"]
    data_source: str
    updated_at: str


class IndustryCount(BaseModel):
    industry: str
    count: int


class SkillCount(BaseModel):
    skill: str
    count: int


class TrendSummary(BaseModel):
    current_window: int
    previous_window: int
    pct_change: float


class MarketSnapshotResponse(BaseModel):
    role_cluster: str
    region: str
    window_days: int
    total_openings_estimate: int
    listings_or_companies_sample: list[dict[str, Any]]
    trend: TrendSummary
    top_industries: list[IndustryCount]
    top_skills: list[SkillCount]
    data_source: str
    mode: Literal["live", "demo", "fallback-demo"]
    updated_at_epoch_ms: int
    updated_at: str


class InterviewQuestion(BaseModel):
    id: str
    prompt: str


class InterviewQuestionsResponse(BaseModel):
    questions: list[InterviewQuestion]


class StudentCreatedResponse(BaseModel):
    id: int
    name: str
    created_at: datetime


class InterviewAnswer(BaseModel):
    question: str
    answer: str


class StudentInterviewRequest(BaseModel):
    role_cluster: str | None = None
    location_preference: str | None = None
    answers: list[str] | list[InterviewAnswer] = Field(default_factory=list)
    notes: str | None = None


class StudentInterviewResponse(BaseModel):
    id: int
    saved_answers_count: int


class CandidateCardResponse(BaseModel):
    id: int
    card: dict[str, Any]


class RoleCreateRequest(BaseModel):
    title: str | None = None
    role_title: str | None = None
    region: str | None = None
    location: str | None = None
    raw_desc: str | None = None
    description: str | None = None
    skills_must: list[str] = Field(default_factory=list)
    must_have_skills: list[str] = Field(default_factory=list)
    min_grad_year: int | None = None
    max_grad_year: int | None = None
    job_id: str | None = None
    job_url: str | None = None

    @model_validator(mode="after")
    def ensure_title(self) -> "RoleCreateRequest":
        if not (self.title or self.role_title):
            raise ValueError("title is required")
        return self


class RoleCreateResponse(BaseModel):
    id: int
    title: str
    region: str | None = None


class MatchItem(BaseModel):
    student_id: int
    student_name: str
    score: float
    rationale: str
    evidence: list[str]
    gap_flags: list[str]
    hard_filter_passed: bool


class RoleMatchesResponse(BaseModel):
    role_id: int
    total: int
    matches: list[MatchItem]


class OutreachRequest(BaseModel):
    student_id: int
    tone: str = "professional"


class OutreachResponse(BaseModel):
    role_id: int
    student_id: int
    subject: str
    body: str


class DemoCachedResponse(BaseModel):
    payloads: dict[str, Any]


class CrustDataSmokeResponse(BaseModel):
    ok: bool
    mode: str
    selected_scheme: str
    details: dict[str, Any]
