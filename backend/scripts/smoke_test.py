from __future__ import annotations

import os
import sys
from io import BytesIO
from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient

os.environ.setdefault("DEMO_MODE", "1")
backend_root = Path(__file__).resolve().parents[1]
smoke_db = backend_root / "smoke_test.db"
if smoke_db.exists():
    smoke_db.unlink()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{smoke_db}")

if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.main import app  # noqa: E402


def _assert_ok(response, expected_status: int = 200) -> dict:
    if response.status_code != expected_status:
        raise RuntimeError(f"Expected {expected_status}, got {response.status_code}: {response.text}")
    return response.json()


def _build_docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("Mustafa Ahmed")
    document.add_paragraph("Data analyst candidate with Python, SQL, Tableau, and experimentation skills.")
    document.add_paragraph("Built demand forecasting dashboards and automated KPI reporting pipelines.")
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def main() -> None:
    with TestClient(app) as client:
        health = _assert_ok(client.get("/health"))
        snapshot = _assert_ok(
            client.get(
                "/market/snapshot",
                params={"region": "AE", "role_cluster": "data_analyst", "days": 7},
            )
        )

        questions = _assert_ok(client.get("/students/interview-questions"))

        create_student_resp = _assert_ok(
            client.post(
                "/students",
                data={
                    "name": "Mustafa Ahmed",
                    "email": "mustafa@example.com",
                    "region_pref": "AE",
                    "grad_year": "2026",
                    "skills": "python,sql,tableau,communication",
                },
                files={
                    "cv": (
                        "mustafa_cv.docx",
                        _build_docx_bytes(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        )
        student_id = create_student_resp["id"]

        interview = _assert_ok(
            client.post(
                f"/students/{student_id}/interview",
                json={
                    "role_cluster": "data_analyst",
                    "location_preference": "AE",
                    "answers": [
                        {
                            "question": "Describe your best project",
                            "answer": "Built a churn dashboard in SQL and Tableau reducing manual reporting by 70%.",
                        },
                        {
                            "question": "Hardest bug",
                            "answer": "Fixed a timezone bug in ETL causing daily KPI drift.",
                        },
                    ],
                },
            )
        )

        card = _assert_ok(client.get(f"/students/{student_id}/card"))

        role = _assert_ok(
            client.post(
                "/roles",
                json={
                    "title": "Junior Data Analyst",
                    "region": "AE",
                    "raw_desc": "Support BI reporting, SQL analysis, and dashboard delivery.",
                    "skills_must": ["python", "sql", "tableau"],
                    "min_grad_year": 2025,
                },
            )
        )
        role_id = role["id"]

        matches = _assert_ok(client.get(f"/roles/{role_id}/matches", params={"include_failed": "true"}))
        smoke = _assert_ok(client.get("/crustdata/smoke-auth"))

    print("Smoke test passed")
    print(
        {
            "health_mode": health.get("mode"),
            "market_mode": snapshot.get("mode"),
            "questions_count": len(questions.get("questions", [])),
            "student_id": student_id,
            "saved_answers": interview.get("saved_answers_count"),
            "card_keys": sorted(card.get("card", {}).keys()),
            "role_id": role_id,
            "matches_total": matches.get("total"),
            "smoke_mode": smoke.get("mode"),
        }
    )


if __name__ == "__main__":
    main()
