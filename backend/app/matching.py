from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import RoleQuery, Student
from .openai_client import OpenAIHelper


@dataclass
class MatchComputation:
    score: float
    hard_filter_passed: bool
    rationale: str


def _split_csv(value: str) -> list[str]:
    return [chunk.strip().lower() for chunk in value.split(",") if chunk.strip()]


def _normalize(text: str | None) -> str:
    return (text or "").strip().lower()


def _student_skill_set(student: Student) -> set[str]:
    skills = set(_split_csv(student.skills_csv))
    cv_text = _normalize(student.cv_text)
    for skill in list(skills):
        if skill in cv_text:
            continue
    return skills


def _hard_filter_failures(role: RoleQuery, student: Student) -> list[str]:
    failures: list[str] = []

    role_loc = _normalize(role.location)
    student_loc = _normalize(student.location)
    if role_loc and (not student_loc or (role_loc not in student_loc and student_loc not in role_loc)):
        failures.append("location")

    if role.min_grad_year is not None:
        if student.grad_year is None or student.grad_year < role.min_grad_year:
            failures.append("grad_year")

    required_skills = _split_csv(role.must_have_skills_csv)
    if required_skills:
        student_skills = _student_skill_set(student)
        cv_text = _normalize(student.cv_text)
        missing = [skill for skill in required_skills if skill not in student_skills and skill not in cv_text]
        if missing:
            failures.append(f"must_have_skills:{','.join(missing)}")

    return failures


def _role_text(role: RoleQuery) -> str:
    parts = [role.title, role.description or "", role.location or "", role.must_have_skills_csv]
    return "\n".join(part for part in parts if part)


def _student_text(student: Student) -> str:
    parts = [student.full_name, student.location or "", student.skills_csv, student.cv_text, student.interview_notes]
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


def _template_rationale(overlap: list[str], failures: list[str]) -> str:
    if failures:
        return f"Filtered out due to {', '.join(failures)}."
    if overlap:
        return f"Strong overlap on {', '.join(overlap[:3])}."
    return "General textual similarity match with limited direct skill overlap."


def compute_match(role: RoleQuery, student: Student, openai_helper: OpenAIHelper) -> MatchComputation:
    failures = _hard_filter_failures(role, student)
    hard_filter_passed = not failures

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
        score = 0.0

    role_skills = set(_split_csv(role.must_have_skills_csv))
    student_skills = _student_skill_set(student)
    overlap = sorted(role_skills.intersection(student_skills))

    rationale = openai_helper.generate_rationale(role_text, student_text) if hard_filter_passed else None
    if not rationale:
        rationale = _template_rationale(overlap, failures)

    return MatchComputation(score=round(score, 4), hard_filter_passed=hard_filter_passed, rationale=rationale)
