from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

# Demo bootstrap is useful in both live and demo mode.
os.environ.setdefault("DEMO_MODE", "1")

from app.main import app  # noqa: E402


def main() -> None:
    with TestClient(app) as client:
        response = client.post("/demo/bootstrap", params={"reset": "true"})
        if response.status_code != 200:
            raise RuntimeError(f"Bootstrap failed ({response.status_code}): {response.text}")
        payload = response.json()

    print("Demo dataset bootstrapped")
    print(
        {
            "dataset_version": payload.get("dataset_version"),
            "students": len(payload.get("students", [])),
            "roles": len(payload.get("roles", [])),
            "showcase": payload.get("showcase"),
            "outreach_previews": len(payload.get("outreach_previews", [])),
        }
    )


if __name__ == "__main__":
    main()
