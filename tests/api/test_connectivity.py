from __future__ import annotations

import pathlib
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest

try:
    import requests  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("requests is not installed; connectivity tests require it", allow_module_level=True)

ROOT = pathlib.Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "apps" / "api"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from trading_api.config import Settings  # noqa: E402
from trading_api.providers.camelot_provider import (  # noqa: E402
    MockCamelotProvider,
    RealCamelotProvider,
    build_camelot_provider,
)
from trading_api.providers.polygon_provider import (  # noqa: E402
    MockPolygonProvider,
    RealPolygonProvider,
    build_polygon_provider,
)
from trading_api.providers.schwab_provider import (  # noqa: E402
    MockSchwabProvider,
    RealSchwabProvider,
    build_schwab_provider,
)
from trading_api.providers.supabase_provider import (  # noqa: E402
    MockSupabaseProvider,
    RealSupabaseProvider,
    build_supabase_provider,
)


class _FakeResponse:
    def __init__(self, *, json_payload: Any = None, status_code: int = 200, headers: Dict[str, str] | None = None):
        self._json_payload = json_payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self) -> Any:
        return self._json_payload

    def raise_for_status(self) -> None:
        if not (200 <= self.status_code < 300):
            raise AssertionError(f"HTTP error status: {self.status_code}")


def _base_settings() -> Settings:
    """Return a baseline Settings object that tests can tweak per-provider."""

    return Settings(
        app_env="test",
        api_host="0.0.0.0",
        api_port=8000,
        provider_mode="auto",
        enable_order_placement=False,
        supabase_url=None,
        supabase_service_role_key=None,
        polygon_api_key=None,
        polygon_base_url="https://api.polygon.io",
        schwab_base_url="https://api.schwabapi.com",
        schwab_access_token=None,
        schwab_account_id=None,
        camelot_repo_path=None,
        camelot_source_file="data/reference.json",
        camelot_ingest_output="apps/api/data/camelot_ingested_test.json",
    )


def test_supabase_builds_mock_without_credentials() -> None:
    settings = _base_settings()
    provider = build_supabase_provider(settings)
    assert isinstance(provider, MockSupabaseProvider)
    assert provider.metadata.mode == "mock"


def test_supabase_builds_real_with_credentials() -> None:
    settings = _base_settings()
    settings = Settings(
        **{
            **settings.__dict__,
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "test-key",
        }
    )
    provider = build_supabase_provider(settings)
    assert isinstance(provider, RealSupabaseProvider)
    assert provider.metadata.mode == "real"


def test_polygon_builds_mock_without_api_key() -> None:
    settings = _base_settings()
    provider = build_polygon_provider(settings)
    assert isinstance(provider, MockPolygonProvider)
    assert provider.metadata.mode == "mock"


def test_polygon_builds_real_with_api_key() -> None:
    settings = _base_settings()
    settings = Settings(
        **{
            **settings.__dict__,
            "polygon_api_key": "test-key",
        }
    )
    provider = build_polygon_provider(settings)
    assert isinstance(provider, RealPolygonProvider)
    assert provider.metadata.mode == "real"


def test_schwab_builds_mock_without_credentials() -> None:
    settings = _base_settings()
    provider = build_schwab_provider(settings)
    assert isinstance(provider, MockSchwabProvider)
    assert provider.metadata.mode == "mock"


def test_schwab_builds_real_with_credentials() -> None:
    settings = _base_settings()
    settings = Settings(
        **{
            **settings.__dict__,
            "schwab_access_token": "access",
            "schwab_account_id": "acct-1",
        }
    )
    provider = build_schwab_provider(settings)
    assert isinstance(provider, RealSchwabProvider)
    assert provider.metadata.mode == "real"


def test_camelot_builds_mock_without_repo_path() -> None:
    settings = _base_settings()
    provider = build_camelot_provider(settings)
    assert isinstance(provider, MockCamelotProvider)
    assert provider.metadata.mode == "mock"


def test_camelot_builds_real_with_repo_path() -> None:
    settings = _base_settings()
    settings = Settings(
        **{
            **settings.__dict__,
            "camelot_repo_path": "/tmp/repo",
        }
    )
    provider = build_camelot_provider(settings)
    assert isinstance(provider, RealCamelotProvider)
    assert provider.metadata.mode == "real"


def test_real_supabase_list_watchlist_invokes_expected_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _base_settings()
    settings = Settings(
        **{
            **settings.__dict__,
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "test-key",
        }
    )
    provider = RealSupabaseProvider(settings)

    captured: Dict[str, Any] = {}

    def fake_get(url: str, params: Dict[str, Any], headers: Dict[str, str], timeout: int):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse(json_payload=[{"symbol": "AAPL"}, {"symbol": "msft"}])

    import requests  # type: ignore

    monkeypatch.setattr(requests, "get", fake_get)

    symbols = provider.list_watchlist("user-1")

    assert symbols == ["AAPL", "MSFT"]
    assert captured["url"].endswith("/rest/v1/watchlists")
    assert captured["params"]["user_id"] == "eq.user-1"
    assert captured["headers"]["apikey"] == "test-key"


def test_real_polygon_quote_and_bars_use_expected_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _base_settings()
    settings = Settings(
        **{
            **settings.__dict__,
            "polygon_api_key": "test-key",
        }
    )
    provider = RealPolygonProvider(settings)

    calls: List[Dict[str, Any]] = []

    def fake_get(url: str, params: Dict[str, Any], timeout: int):
        payload: Dict[str, Any]
        if "/v2/last/trade/" in url:
            payload = {"results": {"p": 123.45, "t": int(datetime.now(tz=timezone.utc).timestamp() * 1000)}}
        else:
            now = datetime.now(timezone.utc)
            rows = [
                {
                    "t": int((now - timedelta(days=idx + 1)).timestamp() * 1000),
                    "o": 100 + idx,
                    "h": 101 + idx,
                    "l": 99 + idx,
                    "c": 100 + idx,
                    "v": 1000 + idx,
                }
                for idx in range(3)
            ]
            payload = {"results": rows}

        calls.append({"url": url, "params": params, "timeout": timeout})
        return _FakeResponse(json_payload=payload)

    import requests  # type: ignore

    monkeypatch.setattr(requests, "get", fake_get)

    price, as_of = provider.quote("MSFT")
    assert price == 123.45
    assert "T" in as_of  # isoformat timestamp

    bars = provider.bars("MSFT", timespan="day", limit=3)
    assert len(bars) == 3

    sma, ema, rsi, macd = provider.indicators("MSFT", bars)
    assert sma != 0
    assert ema != 0
    assert rsi != 0

    quote_call = calls[0]
    assert "/v2/last/trade/MSFT" in quote_call["url"]
    assert quote_call["params"]["apiKey"] == "test-key"

    bars_call = calls[1]
    assert "/v2/aggs/ticker/MSFT/range/1/day" in bars_call["url"]
    assert bars_call["params"]["apiKey"] == "test-key"


def test_real_schwab_positions_orders_and_place_order_use_expected_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _base_settings()
    settings = Settings(
        **{
            **settings.__dict__,
            "schwab_access_token": "access-token",
            "schwab_account_id": "acct-123",
            "enable_order_placement": True,
        }
    )
    provider = RealSchwabProvider(settings)

    from trading_api.schemas import OrderCreate  # noqa: E402

    calls: List[Dict[str, Any]] = []

    def fake_get(url: str, params: Dict[str, Any], headers: Dict[str, str], timeout: int):
        calls.append({"method": "GET", "url": url, "params": params, "headers": headers, "timeout": timeout})
        if "positions" in params.get("fields", ""):
            payload = {
                "securitiesAccount": {
                    "positions": [
                        {
                            "instrument": {"symbol": "AAPL"},
                            "longQuantity": 10,
                            "averagePrice": 150,
                            "marketValue": 155,
                        }
                    ]
                }
            }
        else:
            payload = [
                {
                    "orderId": "100",
                    "status": "FILLED",
                    "orderLegCollection": [
                        {"instruction": "BUY", "quantity": 1, "instrument": {"symbol": "MSFT"}},
                    ],
                }
            ]
        return _FakeResponse(json_payload=payload)

    def fake_post(url: str, headers: Dict[str, str], json: Dict[str, Any], timeout: int):
        calls.append({"method": "POST", "url": url, "headers": headers, "json": json, "timeout": timeout})
        return _FakeResponse(headers={"Location": "https://api.schwabapi.com/orders/100"})

    import requests  # type: ignore

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    positions = provider.positions("user-1")
    assert len(positions) == 1
    assert positions[0].symbol == "AAPL"

    orders = provider.orders("user-1")
    assert len(orders) == 1
    assert orders[0].symbol == "MSFT"

    created = provider.place_order(
        "user-1",
        OrderCreate(symbol="MSFT", side="buy", quantity=1, order_type="market"),
    )
    assert created.symbol == "MSFT"
    assert created.status == "accepted"

    get_positions_call = calls[0]
    assert get_positions_call["url"].endswith(f"/trader/v1/accounts/{settings.schwab_account_id}")

    get_orders_call = calls[1]
    assert get_orders_call["url"].endswith(f"/trader/v1/accounts/{settings.schwab_account_id}/orders")

    post_order_call = calls[2]
    assert post_order_call["url"].endswith(f"/trader/v1/accounts/{settings.schwab_account_id}/orders")
    assert post_order_call["json"]["orderLegCollection"][0]["instrument"]["symbol"] == "MSFT"

