# Alpha-Kite Symphony + Trading Stack

This repository now contains two connected systems:

- `symphony/`: long-running Linear orchestration service for issue-driven agent execution.
- `apps/api` + `apps/web`: trading backend/frontend implementation tracked by Alpha-Kite Linear issues.

## Layout

- `symphony/`: core Symphony service implementation
- `apps/api`: FastAPI backend (Supabase, Polygon, Schwab, Camelot providers)
- `apps/web`: Next.js frontend routed to backend APIs
- `docs/run-checklist.md`: preflight checklist for secrets and execution
- `docs/symphony-issue-protocol.md`: required issue transition/comment protocol
- `apps/api/sql/supabase_schema.sql`: base schema + RLS policy scaffold

## Prerequisites

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
npm --prefix apps/web install
```

## Environment

Copy `.env.example` to `.env` and set required values.

Core values:

- `LINEAR_API_KEY`
- `LINEAR_PROJECT_ID=d77c9342-536d-41f4-9526-2fd38e65226c` (preferred)
- `PROVIDER_MODE=auto|mock|real`
- Provider credentials (`SUPABASE_*`, `POLYGON_*`, `SCHWAB_*`, `CAMELOT_*`)

## Run Symphony

```bash
./scripts/run-symphony.sh
# dashboard/API on http://localhost:8080 when using --port 8080
```

## Run Backend

```bash
python3 apps/api/main.py
```

API surface:

- `GET /health`
- `GET /market/quote`, `GET /market/bars`, `GET /market/indicators`
- `GET/POST/DELETE /watchlists/{user_id}`
- `POST /auth/session`, `GET /auth/session/{token}`
- `GET /positions/{user_id}`, `GET /orders/{user_id}`, `POST /orders/{user_id}`
- `POST /ingest/camelot`

## Run Frontend

```bash
npm --prefix apps/web run dev
```

Set `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`).

## Verification

```bash
python3 -m pytest -q tests/api
node apps/web/scripts/smoke.js
```

## Deployment Notes

- Frontend target: Vercel (`apps/web`)
- Backend target: Railway (`apps/api`)
- Do not commit provider secrets; use platform env settings.

## Add New Linear Tasks For Symphony

1. Create a new issue in Linear under project `Alpha-Kite`.
2. Set state to `Todo`, include clear scope and acceptance criteria, and add dependency links (`blocked by` / `blocks`) when needed.
3. Ensure the issue belongs to team `Alpha-Kite` so it matches `WORKFLOW.md` filters.
4. Run Symphony (`./scripts/run-symphony.sh`) to pick up eligible `Todo`/`In Progress`/`In Review` tasks.
5. During execution, require issue comments with scope, verification, and blockers before moving to `Done`.
