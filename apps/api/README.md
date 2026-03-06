# Alpha-Kite API (`apps/api`)

FastAPI service for trading UI backend functionality.

## Endpoints

- `GET /health`
- `GET /market/quote?symbol=AAPL`
- `GET /market/bars?symbol=AAPL&timespan=day&limit=30`
- `GET /market/indicators?symbol=AAPL&timespan=day&limit=30`
- `GET/POST/DELETE /watchlists/{user_id}`
- `POST /auth/session`, `GET /auth/session/{token}`
- `GET /positions/{user_id}`
- `GET /orders/{user_id}`
- `POST /orders/{user_id}` (gated by `SCHWAB_ENABLE_ORDER_PLACEMENT=true`)
- `POST /ingest/camelot`

## Run

```bash
python3 -m pip install -r requirements.txt
python3 apps/api/main.py
```

## Provider Modes

Set `PROVIDER_MODE=mock|real|auto`:

- `mock`: always use mock adapters
- `real`: require credentials and call provider APIs
- `auto`: use real only when required credentials are present

## Camelot Ingestion

```bash
python3 apps/api/scripts/ingest_camelot.py
```

Real mode expects `CAMELOT_REPO_PATH` and a JSON list at `CAMELOT_SOURCE_FILE`.
