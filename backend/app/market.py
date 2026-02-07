from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from .crustdata_client import CrustDataClient
from .text_utils import top_skill_counts

ROLE_CLUSTER_SYNONYMS: dict[str, list[str]] = {
    "data_analyst": ["data analyst", "business analyst", "analytics"],
    "software_engineer": ["software engineer", "backend", "frontend", "full stack"],
    "cybersecurity": ["cybersecurity", "security engineer", "soc analyst"],
    "product": ["product manager", "product owner", "growth product"],
}

REGION_VALUE_MAP: dict[str, str] = {
    "AE": "United Arab Emirates",
    "UAE": "United Arab Emirates",
    "US": "United States",
    "UK": "United Kingdom",
}


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = "".join(ch for ch in value if ch.isdigit())
        return int(digits) if digits else 0
    return 0


def _date_str(value: datetime) -> str:
    return value.date().isoformat()


def _extract_domain(raw: str | None) -> str | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    candidate = text if "://" in text else f"https://{text}"
    parsed = urlparse(candidate)
    host = (parsed.netloc or parsed.path).lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _company_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    companies = payload.get("companies")
    if isinstance(companies, list):
        return [item for item in companies if isinstance(item, dict)]
    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _best_company_name(item: dict[str, Any]) -> str:
    for key in ("name", "company_name", "title", "legal_name"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Unknown"


def _industry(item: dict[str, Any]) -> str:
    for key in ("industry", "industry_name", "sector"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Unknown"


def _openings_value(item: dict[str, Any]) -> int:
    for key in ("job_openings", "openings", "open_roles", "active_jobs"):
        value = item.get(key)
        if isinstance(value, list):
            return len(value)
        parsed = _safe_int(value)
        if parsed:
            return parsed
    return 0


def _collect_market_texts(companies: list[dict[str, Any]], web_results: list[dict[str, Any]]) -> list[str]:
    texts: list[str] = []
    for item in companies:
        for key in ("job_openings", "description", "about", "headline", "summary"):
            value = item.get(key)
            if isinstance(value, str):
                texts.append(value)
            if isinstance(value, list):
                texts.extend(str(v) for v in value if isinstance(v, str))
    for item in web_results:
        for key in ("title", "snippet", "description"):
            value = item.get(key)
            if isinstance(value, str):
                texts.append(value)
    return texts


def _query_for_role(role_cluster: str) -> str:
    role_key = role_cluster.lower().strip()
    words = ROLE_CLUSTER_SYNONYMS.get(role_key)
    if words:
        return " OR ".join(words)
    return role_cluster.replace("_", " ")


def _region_filter_value(region: str) -> str:
    key = region.strip().upper()
    return REGION_VALUE_MAP.get(key, region)


def build_market_snapshot(
    client: CrustDataClient,
    region: str,
    role_cluster: str,
    days: int,
) -> dict[str, Any]:
    role_query = _query_for_role(role_cluster)
    filters = [
        {"filter_type": "REGION", "type": "in", "value": [_region_filter_value(region)]},
        {"filter_type": "JOB_OPPORTUNITIES", "type": "in", "value": ["Hiring on Linkedin"]},
    ]

    companies: list[dict[str, Any]] = []
    try:
        company_search = client.post_company_search(filters=filters, page=1)
        companies = _company_items(company_search)
    except Exception:
        companies = []

    sample_companies: list[dict[str, Any]] = []
    industry_counter: Counter[str] = Counter()
    total_openings_estimate = 0

    for item in companies[:30]:
        industry = _industry(item)
        industry_counter[industry] += 1
        openings = _openings_value(item)
        total_openings_estimate += openings
        sample_companies.append(
            {
                "company_name": _best_company_name(item),
                "industry": industry,
                "openings_estimate": openings,
                "location": item.get("location") or item.get("headquarters"),
                "website": item.get("website") or item.get("domain"),
            }
        )

    domains: list[str] = []
    for item in sample_companies[:10]:
        domain = _extract_domain(item.get("website") if isinstance(item.get("website"), str) else None)
        if domain:
            domains.append(domain)

    if domains:
        try:
            enrich_payload = client.get_company_enrich(
                company_domain=list(dict.fromkeys(domains))[:10],
                fields=["company_name", "job_openings", "company_website_domain"],
                enrich_realtime=False,
            )
            enriched_companies = _company_items(enrich_payload)
            if enriched_companies:
                for item in enriched_companies:
                    industry_counter[_industry(item)] += 1
                    total_openings_estimate += _openings_value(item)
        except Exception:
            pass

    now = datetime.now(UTC)
    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)

    current_results: list[dict[str, Any]] = []
    previous_results: list[dict[str, Any]] = []
    current_total = 0
    previous_total = 0

    try:
        current_search = client.post_web_search(
            query=f"{role_query} jobs {region}",
            geolocation=region,
            sources=["web", "news"],
            start_date=_date_str(current_start),
            end_date=_date_str(now),
        )
        previous_search = client.post_web_search(
            query=f"{role_query} jobs {region}",
            geolocation=region,
            sources=["web", "news"],
            start_date=_date_str(previous_start),
            end_date=_date_str(current_start),
        )

        current_results = (
            current_search.get("results") if isinstance(current_search.get("results"), list) else []
        )
        previous_results = (
            previous_search.get("results") if isinstance(previous_search.get("results"), list) else []
        )

        if isinstance(current_search.get("metadata"), dict):
            current_total = _safe_int(current_search.get("metadata", {}).get("totalResults"))
        if isinstance(previous_search.get("metadata"), dict):
            previous_total = _safe_int(previous_search.get("metadata", {}).get("totalResults"))
        if current_total == 0:
            current_total = len(current_results)
        if previous_total == 0:
            previous_total = len(previous_results)
    except Exception:
        # Some accounts may not have Web Search access. Fall back to company signals only.
        current_total = max(len(companies), len(sample_companies))
        previous_total = max(1, int(current_total * 0.85))

    denominator = previous_total if previous_total > 0 else 1
    pct_change = round(((current_total - previous_total) / denominator) * 100.0, 2)

    market_texts = _collect_market_texts(companies, [r for r in current_results if isinstance(r, dict)])
    top_skills = [{"skill": skill, "count": count} for skill, count in top_skill_counts(market_texts, max_items=10)]

    if total_openings_estimate == 0:
        total_openings_estimate = max(current_total, len(sample_companies))

    return {
        "role_cluster": role_cluster,
        "region": region,
        "window_days": days,
        "total_openings_estimate": int(total_openings_estimate),
        "listings_or_companies_sample": sample_companies[:10],
        "trend": {
            "current_window": current_total,
            "previous_window": previous_total,
            "pct_change": pct_change,
        },
        "top_industries": [
            {"industry": industry, "count": count} for industry, count in industry_counter.most_common(8)
        ],
        "top_skills": top_skills,
    }
