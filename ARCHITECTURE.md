# EdgeMatch MVP Architecture

## Crustdata Docs Notes (Read Before Implementation)

### Base URL
- `https://api.crustdata.com`

### Auth Schemes Observed in Docs
- Company Enrichment (`/screener/company`): `Authorization: Token <token>`
- Web Search (`/screener/web-search`): `Authorization: Token <token>`
- Web Fetch (`/screener/web-fetch`): `Authorization: Token <token>`
- Company Search via Filters (`/screener/company/search`): `Authorization: Bearer <token>`

Because docs show mixed schemes, backend client supports `token|bearer|auto`, probes both via `/crustdata/smoke-auth`, and remembers per-endpoint winning scheme.

### Endpoints Used

1. Company Enrichment
- `GET /screener/company`
- Query params used:
  - `company_domain` (comma-separated domains)
  - `fields` (comma-separated field paths, e.g. `company_name,industry,job_openings,headcount.headcount`)
  - `enrich_realtime` (optional)
- Response fields we rely on (when available):
  - `company_name`, `industry`, `company_id`, `company_website_domain`, `headcount`, `job_openings`, `news_articles`

2. Company Search via Filters
- `POST /screener/company/search`
- Body params used:
  - `filters` (array of filter objects)
  - `page` (integer)
- Filter types we rely on:
  - `REGION` (`in`)
  - `JOB_OPPORTUNITIES` (`in`: `"Hiring"`)
  - `KEYWORD` (`in`, single value)
  - optional `INDUSTRY` (`in`)
- Response fields we rely on:
  - `companies` array
  - `total_display_count`
  - company-level values such as `name`, `website`, `industry`, `location`, `headquarters`

3. Web Search
- `POST /screener/web-search` (optional `?fetch_content=true`)
- Body params used:
  - `query` (required)
  - `geolocation` (ISO alpha-2, optional)
  - `sources` (optional: `news`, `web`)
  - `site`, `startDate`, `endDate` (optional)
- Response fields we rely on:
  - `success`, `results[]` (`title`, `url`, `snippet`, `position`), `metadata.totalResults`
  - `contents[]` when `fetch_content=true`

4. Web Fetch
- `POST /screener/web-fetch`
- Body params used:
  - `urls` (array, max 10)
- Response fields we rely on:
  - per-URL objects with `success`, `url`, `timestamp`, `pageTitle`, `content`, optional `error`

### Error/Limit Behaviors We Handle
- `400`: validation/filter parsing errors
- `401/403`: invalid auth / permission issues
- `402`: insufficient credits
- `500`: upstream/service errors
- Rate/credit protection: local TTL cache (60-120s), request timeouts, fallback to DEMO_MODE sample payloads

### Job Listing API Assumption
- Marketing page confirms live listings with rich fields (description, category, openings, workplace type, date added/updated, location, company context), but direct endpoint docs are not publicly detailed in provided links.
- Implementation assumes no guaranteed direct Jobs endpoint access for this token; uses Company Search + Company Enrichment as primary source, then optional Web Search supplementation.

## System Overview
- `backend/`: FastAPI + SQLite + Crustdata integration + fallback demo data
- `frontend/`: Next.js (TypeScript) minimal high-end UI with three pages
- `shared/`: optional; skipped for speed unless needed

## Key Backend Endpoints
- `GET /health`
- `GET /market/snapshot?region=AE&role_cluster=data_analyst&days=7`
- `GET /students/interview-questions`
- `POST /students` (multipart)
- `POST /students/{id}/interview`
- `GET /students/{id}/card`
- `POST /roles`
- `GET /roles/{id}/matches`
- `POST /roles/{id}/outreach`
- `GET /demo/cached`
- `GET /crustdata/smoke-auth`

## Auth Scheme Chosen
- Runtime mode: `auto` (recommended default)
- Effective behavior after smoke probe:
  - `/screener/company`, `/screener/web-search`, `/screener/web-fetch` => `Token <CRUSTDATA_TOKEN>`
  - `/screener/company/search` => `Bearer <CRUSTDATA_TOKEN>`
- Implementation stores successful scheme per endpoint path to reduce retries.

## Matching & Scoring
1. Hard filters: location, grad year, must-have skills
2. Similarity:
- With OpenAI key: embedding cosine similarity
- Without OpenAI key: TF-IDF cosine similarity
3. Rationale:
- With OpenAI key: short generated rationale
- Without OpenAI key: overlap-based template

## Deployment/Demo Modes
- `DEMO_MODE=0`: live Crustdata first, fallback per-route when upstream unavailable
- `DEMO_MODE=1`: always use cached sample payloads
