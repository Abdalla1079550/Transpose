from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import RoleQuery, Student
from .openai_client import OpenAIHelper
from .text_utils import extract_skills_from_text


@dataclass
class MatchComputation:
    score: float
    hard_filter_passed: bool
    rationale: str
    evidence: list[str]
    gap_flags: list[str]


def _safe_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            result.append(item.strip().lower())
    return [item for item in result if item]


def _normalize(text: str | None) -> str:
    return (text or "").strip().lower()


def _role_skills(role: RoleQuery) -> list[str]:
    return _safe_json_list(role.skills_must_json)


def _student_skills(student: Student) -> set[str]:
    explicit = set(_safe_json_list(student.skills_json))
    inferred = {skill.lower() for skill in extract_skills_from_text(student.cv_text, max_items=30)}
    return explicit.union(inferred)


def _hard_filter_failures(role: RoleQuery, student: Student) -> list[str]:
    failures: list[str] = []

    role_region = _normalize(role.region)
    student_region = _normalize(student.region_pref)
    if role_region and student_region and role_region not in student_region and student_region not in role_region:
        failures.append("location_mismatch")

    if role.min_grad_year is not None:
        if student.grad_year is None or student.grad_year < role.min_grad_year:
            failures.append("grad_year_below_min")

    if role.max_grad_year is not None:
        if student.grad_year is None or student.grad_year > role.max_grad_year:
            failures.append("grad_year_above_max")

    required = _role_skills(role)
    if required:
        student_skills = _student_skills(student)
        cv_lower = _normalize(student.cv_text)
        missing = [skill for skill in required if skill not in student_skills and skill not in cv_lower]
        for skill in missing:
            failures.append(f"missing_skill:{skill}")

    return failures


def _role_text(role: RoleQuery) -> str:
    parts = [role.title, role.raw_desc or "", role.region or "", " ".join(_role_skills(role))]
    return "\n".join(part for part in parts if part)


def _student_text(student: Student) -> str:
    interview = student.interview_answers_json
    parts = [student.name, student.region_pref or "", student.cv_text, interview]
    return "\n".join(part for part in parts if part)


def _cosine_dense(a: Iterable[float], b: Iterable[float]) -> float:
    a_list = list(a)
    b_list = list(b)
    dot = sum(x * y for x, y in zip(a_list, b_list, strict=False))
    mag_a = math.sqrt(sum(x * x for x in a_list))
    mag_b = math.sqrt(sum(y * y for y in b_list))
    if not mag_a or not mag_b:
        return 0.0
    return max(0.0, min(1.0, dot / (mag_a * mag_b)))


def _extract_evidence(role: RoleQuery, student: Student, max_items: int = 3) -> list[str]:
    evidence: list[str] = []
    required = _role_skills(role)

    cv_lines = [line.strip() for line in student.cv_text.splitlines() if line.strip()]
    interview_text = student.interview_answers_json
    interview_lines = [line.strip() for line in interview_text.splitlines() if line.strip()]

    for skill in required:
        for line in cv_lines:
            if skill in line.lower() and len(evidence) < max_items:
                evidence.append(f"CV: {line[:120]}")
                break
        if len(evidence) >= max_items:
            break

    for line in interview_lines:
        if len(evidence) >= max_items:
            break
        if line and line not in evidence:
            evidence.append(f"Interview: {line[:120]}")

    if not evidence:
        evidence.append("Limited explicit evidence in CV/interview text. Needs deeper screening.")
    return evidence[:max_items]


def _template_rationale(gap_flags: list[str], evidence: list[str]) -> str:
    if gap_flags:
        return f"Gap flags: {', '.join(gap_flags[:2])}."
    return f"Matched on role-relevant signals. Evidence includes: {evidence[0][:80]}"


def compute_match(role: RoleQuery, student: Student, openai_helper: OpenAIHelper) -> MatchComputation:
    gap_flags = _hard_filter_failures(role, student)
    hard_filter_passed = not gap_flags

    role_text = _role_text(role)
    student_text = _student_text(student)

    score = 0.0
    vectors = openai_helper.embed_texts([role_text, student_text]) if openai_helper.enabled else None
    if vectors and len(vectors) == 2:
        score = _cosine_dense(vectors[0], vectors[1])
    else:
        tfidf = TfidfVectorizer(stop_words="english")
        matrix = tfidf.fit_transform([role_text, student_text])
        score = float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])

    if not hard_filter_passed:
        score *= 0.2

    evidence = _extract_evidence(role, student)
    rationale = openai_helper.generate_rationale(role_text, student_text) if hard_filter_passed else None
    if not rationale:
        rationale = _template_rationale(gap_flags, evidence)

    return MatchComputation(
        score=round(score, 4),
        hard_filter_passed=hard_filter_passed,
        rationale=rationale,
        evidence=evidence,
        gap_flags=gap_flags,
    )
