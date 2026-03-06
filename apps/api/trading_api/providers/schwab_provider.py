"""Schwab provider implementations (real + mock fallback)."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid
import requests

from trading_api.config import Settings
from trading_api.providers.base import ProviderMetadata
from trading_api.schemas import Order, OrderCreate, Position


class MockSchwabProvider:
    metadata = ProviderMetadata(name="schwab", mode="mock")

    def __init__(self, enable_order_placement: bool):
        self.enable_order_placement = enable_order_placement
        self._orders: dict[str, list[Order]] = {}

    def positions(self, user_id: str) -> list[Position]:
        del user_id
        return [
            Position(symbol="AAPL", quantity=12, average_price=184.1, market_price=191.4),
            Position(symbol="MSFT", quantity=5, average_price=390.0, market_price=402.2),
        ]

    def orders(self, user_id: str) -> list[Order]:
        existing = self._orders.get(user_id)
        if existing:
            return existing
        return [Order(id="mock-001", symbol="AAPL", side="buy", quantity=2, status="filled")]

    def place_order(self, user_id: str, order: OrderCreate) -> Order:
        if not self.enable_order_placement:
            raise PermissionError("Order placement disabled. Set SCHWAB_ENABLE_ORDER_PLACEMENT=true.")
        created = Order(
            id=f"mock-{uuid.uuid4().hex[:8]}",
            symbol=order.symbol.upper(),
            side=order.side,
            quantity=order.quantity,
            status="accepted",
        )
        self._orders.setdefault(user_id, []).append(created)
        return created


class RealSchwabProvider:
    metadata = ProviderMetadata(name="schwab", mode="real")

    def __init__(self, settings: Settings):
        if not settings.schwab_access_token or not settings.schwab_account_id:
            raise ValueError("SCHWAB_ACCESS_TOKEN and SCHWAB_ACCOUNT_ID are required for real mode")
        self.base_url = settings.schwab_base_url.rstrip("/")
        self.token = settings.schwab_access_token
        self.account_id = settings.schwab_account_id
        self.enable_order_placement = settings.enable_order_placement

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def positions(self, user_id: str) -> list[Position]:
        del user_id
        response = requests.get(
            f"{self.base_url}/trader/v1/accounts/{self.account_id}",
            params={"fields": "positions"},
            headers=self._headers,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json() or {}
        account = payload.get("securitiesAccount") or payload
        positions = account.get("positions") or []
        mapped: list[Position] = []
        for row in positions:
            instrument = row.get("instrument") or {}
            mapped.append(
                Position(
                    symbol=instrument.get("symbol", "UNKNOWN"),
                    quantity=float(row.get("longQuantity") or row.get("quantity") or 0),
                    average_price=float(row.get("averagePrice") or 0),
                    market_price=float(row.get("marketValue") or 0),
                )
            )
        return mapped

    def orders(self, user_id: str) -> list[Order]:
        del user_id
        today = datetime.now(timezone.utc).date().isoformat()
        response = requests.get(
            f"{self.base_url}/trader/v1/accounts/{self.account_id}/orders",
            params={"fromEnteredTime": today, "toEnteredTime": today},
            headers=self._headers,
            timeout=20,
        )
        response.raise_for_status()
        rows = response.json() or []
        mapped: list[Order] = []
        for row in rows:
            leg = (row.get("orderLegCollection") or [{}])[0]
            inst = (leg.get("instrument") or {})
            mapped.append(
                Order(
                    id=str(row.get("orderId") or row.get("id") or uuid.uuid4().hex[:8]),
                    symbol=inst.get("symbol", "UNKNOWN"),
                    side=str(leg.get("instruction") or "").lower(),
                    quantity=float(leg.get("quantity") or row.get("quantity") or 0),
                    status=str(row.get("status") or "unknown").lower(),
                )
            )
        return mapped

    def place_order(self, user_id: str, order: OrderCreate) -> Order:
        del user_id
        if not self.enable_order_placement:
            raise PermissionError("Order placement disabled. Set SCHWAB_ENABLE_ORDER_PLACEMENT=true.")
        payload = {
            "orderType": order.order_type.upper(),
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "instruction": order.side.upper(),
                    "quantity": order.quantity,
                    "instrument": {
                        "symbol": order.symbol.upper(),
                        "assetType": "EQUITY",
                    },
                }
            ],
        }
        response = requests.post(
            f"{self.base_url}/trader/v1/accounts/{self.account_id}/orders",
            headers=self._headers,
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return Order(
            id=response.headers.get("Location", f"real-{uuid.uuid4().hex[:10]}"),
            symbol=order.symbol.upper(),
            side=order.side,
            quantity=order.quantity,
            status="accepted",
        )


def build_schwab_provider(settings: Settings):
    mode = settings.normalized_provider_mode
    if mode == "mock":
        return MockSchwabProvider(enable_order_placement=settings.enable_order_placement)
    if mode == "real":
        return RealSchwabProvider(settings)
    if settings.schwab_access_token and settings.schwab_account_id:
        return RealSchwabProvider(settings)
    return MockSchwabProvider(enable_order_placement=settings.enable_order_placement)
