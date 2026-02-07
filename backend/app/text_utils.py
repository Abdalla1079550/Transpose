from __future__ import annotations

import re
from collections import Counter

SKILL_DICTIONARY = [
    "python",
    "sql",
    "java",
    "javascript",
    "typescript",
    "react",
    "next.js",
    "node",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "tableau",
    "power bi",
    "excel",
    "pandas",
    "numpy",
    "scikit-learn",
    "machine learning",
    "data analysis",
    "statistics",
    "cybersecurity",
    "network security",
    "product management",
    "figma",
    "fastapi",
    "postgresql",
    "mysql",
    "redis",
    "git",
    "communication",
]


def normalize_space(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def extract_skills_from_text(text: str, max_items: int = 15) -> list[str]:
    lowered = normalize_space(text).lower()
    found: list[str] = []
    for skill in SKILL_DICTIONARY:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, lowered):
            found.append(skill)
    return found[:max_items]


def top_skill_counts(texts: list[str], max_items: int = 10) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for text in texts:
        for skill in extract_skills_from_text(text, max_items=40):
            counter[skill] += 1
    return counter.most_common(max_items)


def parse_csv_skills(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().lower() for item in value.split(",") if item.strip()]
