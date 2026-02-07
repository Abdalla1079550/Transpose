# EdgeMatch (Hackathon MVP)

EdgeMatch is a demo-first AI + labor market intelligence system with three fast flows:
- `Market Truth`: live demand snapshot from Crustdata (with demo fallback)
- `Student One Profile`: CV upload + mini interview + candidate card
- `Company Shortlist`: role input + ranked candidate matches + outreach draft

## Stack
- Backend: FastAPI + SQLModel + SQLite
- Frontend: Next.js (TypeScript)
- Data backbone: Crustdata APIs

## Repository Layout
- `backend/` FastAPI app, Crustdata client, matching logic, smoke tests, demo payloads
- `frontend/` Next.js UI (`/`, `/student`, `/employer`)
- `ARCHITECTURE.md` API notes, auth behavior, assumptions

## Environment Variables
Create `.env` in repo root (or `backend/.env`) using `.env.example`:

- `CRUSTDATA_TOKEN=...`
- `CRUSTDATA_AUTH_SCHEME=auto|token|bearer`
- `OPENAI_API_KEY=...` (optional)
- `DEMO_MODE=0|1`
- `BACKEND_PORT=8000`
- `FRONTEND_PORT=3000`
- `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`
- `DATABASE_URL=sqlite:///backend/edgematch.db`

## Install
```bash
make install
```

## Run
Terminal 1:
```bash
make backend
```

Terminal 2:
```bash
make frontend
```

Or run both:
```bash
make dev
```

## Backend API
- `GET /health`
- `GET /market/snapshot?region=AE&role_cluster=data_analyst&days=7`
- `GET /students/interview-questions`
- `POST /students` (multipart: `cv` + fields)
- `POST /students/{id}/interview`
- `GET /students/{id}/card`
- `POST /roles`
- `GET /roles/{id}/matches`
- `POST /roles/{id}/outreach`
- `GET /demo/cached`
- `GET /crustdata/smoke-auth`

## Smoke Test
Runs full core flow in `DEMO_MODE=1`:
```bash
cd backend
. .venv/bin/activate
python scripts/smoke_test.py
```

## Demo Mode and Live Mode
- `DEMO_MODE=0`: use live Crustdata first; route-level fallback to cached demo payloads on upstream/auth/credit issues
- `DEMO_MODE=1`: force cached sample payloads from `backend/data/`

UI shows:
- `LIVE/DEMO` indicator
- `Data source: Crustdata`
- `Last updated`

## 3-Minute Demo Script
1. Open `/` and set `region=AE`, `role_cluster=data_analyst`; show hiring estimate, trend, top industries, top skills.
2. Export curriculum gap brief as JSON/CSV from dashboard controls.
3. Open `/student`; upload CV, load questions, submit answers, show generated candidate card tied to market context.
4. Open `/employer`; create role, fetch shortlist, show rationale/evidence/gap flags, click `Generate Outreach`.

## Notes
- Crustdata auth styles differ by endpoint (`Token` vs `Bearer`), so client supports `auto` probing and per-endpoint fallback.
- No secrets are logged or committed.
- Small in-memory TTL caching is used for Crustdata calls to protect credits during demos.
