from __future__ import annotations

import asyncio
import os
import pathlib
import sys

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from trading_api.app import create_app
from trading_api.dependencies import (  # noqa: E402
    get_camelot_provider,
    get_polygon_provider,
    get_schwab_provider,
    get_settings,
    get_supabase_provider,
)


def _reset_caches() -> None:
    get_settings.cache_clear()
    get_supabase_provider.cache_clear()
    get_polygon_provider.cache_clear()
    get_schwab_provider.cache_clear()
    get_camelot_provider.cache_clear()


def _mock_client():
    os.environ["PROVIDER_MODE"] = "mock"
    _reset_caches()
    return create_app()


def _request(app, method: str, path: str, **kwargs) -> httpx.Response:
    async def _inner() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_inner())


def test_health_reports_provider_modes() -> None:
    app = _mock_client()
    response = _request(app, "GET", "/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["providers"]["polygon"] == "mock"
    assert payload["providers"]["supabase"] == "mock"


def test_watchlist_crud_flow() -> None:
    app = _mock_client()
    user_id = "test-user"

    added = _request(app, "POST", f"/watchlists/{user_id}", json={"symbol": "aapl"})
    assert added.status_code == 200
    assert added.json()["symbols"] == ["AAPL"]

    fetched = _request(app, "GET", f"/watchlists/{user_id}")
    assert fetched.status_code == 200
    assert fetched.json()["symbols"] == ["AAPL"]

    deleted = _request(app, "DELETE", f"/watchlists/{user_id}/AAPL")
    assert deleted.status_code == 200
    assert deleted.json()["symbols"] == []


def test_market_endpoints_return_data() -> None:
    app = _mock_client()

    quote = _request(app, "GET", "/market/quote", params={"symbol": "MSFT"})
    assert quote.status_code == 200
    assert quote.json()["symbol"] == "MSFT"

    bars = _request(app, "GET", "/market/bars", params={"symbol": "MSFT", "limit": 5})
    assert bars.status_code == 200
    assert len(bars.json()["bars"]) == 5

    indicators = _request(app, "GET", "/market/indicators", params={"symbol": "MSFT", "limit": 8})
    assert indicators.status_code == 200
    assert "sma" in indicators.json()


def test_auth_session_roundtrip() -> None:
    app = _mock_client()

    created = _request(app, "POST", "/auth/session", json={"user_id": "u-1", "email": "user@example.com"})
    assert created.status_code == 200
    token = created.json()["token"]

    fetched = _request(app, "GET", f"/auth/session/{token}")
    assert fetched.status_code == 200
    assert fetched.json()["user_id"] == "u-1"


def test_order_gated_when_disabled() -> None:
    os.environ["PROVIDER_MODE"] = "mock"
    os.environ["SCHWAB_ENABLE_ORDER_PLACEMENT"] = "false"
    _reset_caches()
    app = create_app()

    response = _request(
        app,
        "POST",
        "/orders/u-1",
        json={"symbol": "AAPL", "side": "buy", "quantity": 1, "order_type": "market"},
    )
    assert response.status_code == 403


def test_camelot_ingest_mock_creates_output() -> None:
    output_file = ROOT / "apps" / "api" / "data" / "camelot_test_output.json"
    os.environ["PROVIDER_MODE"] = "mock"
    os.environ["CAMELOT_INGEST_OUTPUT"] = str(output_file)
    _reset_caches()

    app = create_app()
    response = _request(app, "POST", "/ingest/camelot")
    assert response.status_code == 200
    assert response.json()["records_ingested"] >= 1
    assert output_file.exists()
