# Alpha-Kite Run Checklist

## 1. Required Secrets and Environment

- Linear / Symphony:
  - `LINEAR_API_KEY`
  - `LINEAR_PROJECT_ID` (preferred: `d77c9342-536d-41f4-9526-2fd38e65226c`) or `LINEAR_PROJECT_SLUG`
- Backend:
  - `PROVIDER_MODE` (`auto` default)
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `POLYGON_API_KEY`
  - `SCHWAB_ACCESS_TOKEN`
  - `SCHWAB_ACCOUNT_ID`
  - `SCHWAB_ENABLE_ORDER_PLACEMENT` (`false` default)
  - `CAMELOT_REPO_PATH`
  - `CAMELOT_SOURCE_FILE` (default `data/reference.json`)

## 2. Preflight Commands

```bash
python3 -m pip install -r requirements.txt
npm --prefix apps/web install
python3 -m pytest -q tests/api
node apps/web/scripts/smoke.js
```

## 3. Deployment Tokens (External)

- Vercel CLI token (`vercel login`) for frontend deployment.
- Railway auth token (`railway login`) for backend deployment.
- Supabase project access (`supabase login`) for schema push.

## 4. Per-Issue Completion Evidence

Each issue must have a Linear comment containing:

1. What changed (files/endpoints/features)
2. Verification commands and outcomes
3. Artifacts (URLs, schema scripts, generated files)
4. Blockers (missing credentials/access) if any
