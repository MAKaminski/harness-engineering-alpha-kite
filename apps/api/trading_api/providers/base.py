"""Provider interfaces for runtime-pluggable data integrations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from trading_api.schemas import Bar, Order, OrderCreate, Position, SessionResponse


@dataclass(frozen=True)
class ProviderMetadata:
    name: str
    mode: str


class PolygonProvider(Protocol):
    metadata: ProviderMetadata

    def quote(self, symbol: str) -> tuple[float, str]: ...

    def bars(self, symbol: str, timespan: str, limit: int) -> list[Bar]: ...

    def indicators(self, symbol: str, bars: list[Bar]) -> tuple[float, float, float, float]: ...


class SupabaseProvider(Protocol):
    metadata: ProviderMetadata

    def list_watchlist(self, user_id: str) -> list[str]: ...

    def add_watchlist_symbol(self, user_id: str, symbol: str) -> list[str]: ...

    def remove_watchlist_symbol(self, user_id: str, symbol: str) -> list[str]: ...

    def create_session(self, user_id: str, email: str | None) -> SessionResponse: ...

    def get_session(self, token: str) -> SessionResponse | None: ...


class SchwabProvider(Protocol):
    metadata: ProviderMetadata

    def positions(self, user_id: str) -> list[Position]: ...

    def orders(self, user_id: str) -> list[Order]: ...

    def place_order(self, user_id: str, order: OrderCreate) -> Order: ...


class CamelotProvider(Protocol):
    metadata: ProviderMetadata

    def ingest_reference_data(self) -> tuple[int, str]: ...
