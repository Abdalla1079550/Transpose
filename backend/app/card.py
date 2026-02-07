from __future__ import annotations

import json
from collections import OrderedDict
from typing import Any

from .models import Student
from .openai_client import OpenAIHelper
from .text_utils import extract_skills_from_text

ROLE_CLUSTERS = [
    "data_analyst",
    "software_engineer",
    "cybersecurity",
    "product",
    "ml_engineer",
    "qa_engineer",
]


def _safe_json_list(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def _flat_interview_text(answers_json: str) -> str:
    values = _safe_json_list(answers_json)
    chunks: list[str] = []
    for item in values:
        if isinstance(item, str):
            chunks.append(item)
        elif isinstance(item, dict):
            q = item.get("question")
            a = item.get("answer")
            if isinstance(q, str) and isinstance(a, str):
                chunks.append(f"{q}: {a}")
            elif isinstance(a, str):
                chunks.append(a)
    return "\n".join(chunks)


def _role_fit(skills: list[str]) -> list[str]:
    score_map = {role: 0 for role in ROLE_CLUSTERS}
    normalized = {skill.lower() for skill in skills}

    if {"sql", "tableau", "power bi", "excel", "data analysis"}.intersection(normalized):
        score_map["data_analyst"] += 3
    if {"python", "java", "javascript", "typescript", "react", "docker", "fastapi"}.intersection(normalized):
        score_map["software_engineer"] += 3
    if {"cybersecurity", "network security"}.intersection(normalized):
        score_map["cybersecurity"] += 4
    if {"product management", "communication", "figma"}.intersection(normalized):
        score_map["product"] += 3
    if {"machine learning", "scikit-learn", "numpy", "pandas"}.intersection(normalized):
        score_map["ml_engineer"] += 3

    ranked = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
    return [role for role, score in ranked if score > 0][:5] or ["data_analyst"]


def _improvements(skills: list[str], market_skills: list[str]) -> list[str]:
    have = {skill.lower() for skill in skills}
    missing_market = [skill for skill in market_skills if skill.lower() not in have][:3]
    if not missing_market:
        return [
            "Build one measurable capstone project with baseline vs improved KPI impact.",
            "Publish a concise portfolio README with architecture and outcomes.",
            "Practice one mock interview per week using your target role prompts.",
        ]

    return [
        f"Ship a portfolio project that explicitly uses {missing_market[0]} and quantifies outcomes.",
        f"Add a 2-week drill plan on {missing_market[1] if len(missing_market) > 1 else missing_market[0]} with weekly milestones.",
        f"Update CV bullets to include evidence for {missing_market[2] if len(missing_market) > 2 else missing_market[-1]} using metrics.",
    ]


def build_deterministic_card(student: Student, market_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    interview_text = _flat_interview_text(student.interview_answers_json)
    merged_text = "\n".join([student.cv_text, interview_text])

    explicit_skills = [item for item in _safe_json_list(student.skills_json) if isinstance(item, str)]
    inferred_skills = extract_skills_from_text(merged_text, max_items=20)
    all_skills = list(OrderedDict.fromkeys([*explicit_skills, *inferred_skills]))[:15]

    market_top_skills = []
    if market_snapshot:
        for item in market_snapshot.get("top_skills", []):
            if isinstance(item, dict) and isinstance(item.get("skill"), str):
                market_top_skills.append(item["skill"])

    strengths = []
    if all_skills:
        strengths.append(f"Demonstrated skills: {', '.join(all_skills[:4])}")
    strengths.append("Shows practical project delivery evidence from CV/interview content.")

    gaps = []
    skill_set = {skill.lower() for skill in all_skills}
    for market_skill in market_top_skills[:4]:
        if market_skill.lower() not in skill_set:
            gaps.append(f"Market gap: {market_skill}")
    if not gaps:
        gaps.append("Needs stronger quantified impact bullets for recruiter screening.")

    region = student.region_pref or "global"
    role_fit = _role_fit(all_skills)

    card: dict[str, Any] = {
        "candidate": {
            "name": student.name,
            "email": student.email,
            "region_pref": student.region_pref,
            "grad_year": student.grad_year,
        },
        "normalized_skill_list": all_skills,
        "role_fit_suggestions": role_fit[:5],
        "strengths": strengths[:3],
        "gaps": gaps[:3],
        "improvements": _improvements(all_skills, market_top_skills),
        "market_context": {
            "region": region,
            "hiring_now_estimate": market_snapshot.get("total_openings_estimate") if market_snapshot else None,
            "top_market_skills": market_top_skills[:5],
            "citation": f"In {region}, the strongest hiring signals currently favor {', '.join(role_fit[:2])}.",
        },
    }
    return card


def generate_candidate_card(
    student: Student,
    openai_helper: OpenAIHelper,
    market_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = build_deterministic_card(student, market_snapshot=market_snapshot)
    if not openai_helper.enabled:
        return base

    prompt = (
        "Refine this candidate card. Keep factual grounding. "
        "Return JSON with exactly keys: normalized_skill_list, role_fit_suggestions, strengths, gaps, improvements. "
        "Use concise, concrete items."
    )
    payload = openai_helper.generate_json_object(prompt, {"base": base, "market": market_snapshot or {}})
    if not payload:
        return base

    merged = dict(base)
    for key in ("normalized_skill_list", "role_fit_suggestions", "strengths", "gaps", "improvements"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            merged[key] = [str(item) for item in value][: (15 if key == "normalized_skill_list" else 5)]
    return merged


def serialize_card(card: dict[str, Any]) -> str:
    return json.dumps(card, ensure_ascii=True)
