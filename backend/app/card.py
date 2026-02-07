from __future__ import annotations

import json
import re
from collections import OrderedDict
from typing import Any

from .models import Student
from .openai_client import OpenAIHelper

COMMON_SKILLS = [
    "python",
    "sql",
    "excel",
    "tableau",
    "power bi",
    "pandas",
    "numpy",
    "scikit-learn",
    "machine learning",
    "data analysis",
    "statistics",
    "communication",
    "aws",
    "docker",
    "fastapi",
]


def _split_skills(csv_value: str) -> list[str]:
    return [item.strip() for item in csv_value.split(",") if item.strip()]


def _extract_skills_from_text(text: str) -> list[str]:
    lowered = text.lower()
    found = [skill for skill in COMMON_SKILLS if skill in lowered]
    return list(OrderedDict.fromkeys(found))


def _extract_summary(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "No CV summary available."

    non_contact = [line for line in lines if "@" not in line and not re.search(r"\+?\d[\d\s\-]{7,}", line)]
    summary_source = non_contact if non_contact else lines
    return " ".join(summary_source[:2])[:280]


def build_deterministic_card(student: Student) -> dict[str, Any]:
    explicit_skills = _split_skills(student.skills_csv)
    inferred_skills = _extract_skills_from_text(student.cv_text)
    merged_skills = list(OrderedDict.fromkeys([*explicit_skills, *inferred_skills]))[:8]

    interview_excerpt = student.interview_notes.strip()[:240] or "No interview notes provided yet."
    grad_line = f"Expected graduation: {student.grad_year}." if student.grad_year else "Graduation year not provided."

    return {
        "headline": f"{student.full_name} - Early Career Candidate",
        "summary": _extract_summary(student.cv_text),
        "top_skills": merged_skills,
        "strengths": [
            "Structured communication" if "communication" in {skill.lower() for skill in merged_skills} else "Clear technical focus",
            "Hands-on project exposure from CV",
        ],
        "risks": [
            "Limited interview depth" if len(student.interview_notes) < 50 else "Needs role-specific assessment",
        ],
        "interview_excerpt": interview_excerpt,
        "metadata": {
            "location": student.location,
            "grad_year": student.grad_year,
            "note": grad_line,
        },
    }


def generate_candidate_card(student: Student, openai_helper: OpenAIHelper) -> dict[str, Any]:
    base_card = build_deterministic_card(student)
    if not openai_helper.enabled:
        return base_card

    ai_card = openai_helper.generate_card(
        {
            "name": student.full_name,
            "location": student.location,
            "grad_year": student.grad_year,
            "skills_csv": student.skills_csv,
            "cv_text": student.cv_text[:3500],
            "interview_notes": student.interview_notes[:1200],
            "base_card": base_card,
        }
    )
    if not ai_card:
        return base_card

    merged = dict(base_card)
    for key in ("headline", "summary", "top_skills", "strengths", "risks"):
        value = ai_card.get(key)
        if value:
            merged[key] = value
    return merged


def serialize_card(card: dict[str, Any]) -> str:
    return json.dumps(card, ensure_ascii=True)
