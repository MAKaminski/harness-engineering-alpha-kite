"""Polygon provider implementations (real + mock fallback)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random
import requests

from apps.api.trading_api.config import Settings
from .base import ProviderMetadata
from ..schemas import Bar


class MockPolygonProvider:
    metadata = ProviderMetadata(name="polygon", mode="mock")

    def quote(self, symbol: str) -> tuple[float, str]:
        seed = sum(ord(c) for c in symbol.upper())
        random.seed(seed)
        price = 80 + (random.random() * 220)
        return round(price, 2), datetime.now(timezone.utc).isoformat()

    def bars(self, symbol: str, timespan: str, limit: int) -> list[Bar]:
        del symbol
        del timespan
        now = datetime.now(timezone.utc)
        base = 190.0
        bars: list[Bar] = []
        for idx in range(limit):
            close = base + ((idx % 7) - 3) * 1.25
            bars.append(
                Bar(
                    time=(now - timedelta(days=limit - idx)).isoformat(),
                    open=round(close - 0.8, 2),
                    high=round(close + 1.4, 2),
                    low=round(close - 1.6, 2),
                    close=round(close, 2),
                    volume=1_000_000 + idx * 8_500,
                )
            )
        return bars

    def indicators(self, symbol: str, bars: list[Bar]) -> tuple[float, float, float, float]:
        del symbol
        closes = [b.close for b in bars]
        window = closes[-12:] if len(closes) >= 12 else closes
        sma = sum(window) / len(window)
        ema = (window[-1] * 0.35) + (sma * 0.65)
        rsi = 54.2
        macd = round(window[-1] - sma, 4)
        return round(sma, 4), round(ema, 4), round(rsi, 2), round(macd, 4)


class RealPolygonProvider:
    metadata = ProviderMetadata(name="polygon", mode="real")

    def __init__(self, settings: Settings):
        if not settings.polygon_api_key:
            raise ValueError("POLYGON_API_KEY is required for real mode")
        self.base_url = settings.polygon_base_url.rstrip("/")
        self.api_key = settings.polygon_api_key

    def quote(self, symbol: str) -> tuple[float, str]:
        response = requests.get(
            f"{self.base_url}/v2/last/trade/{symbol.upper()}",
            params={"apiKey": self.api_key},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json() or {}
        result = payload.get("results") or {}
        price = float(result.get("p") or 0)
        ts = result.get("t")
        as_of = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat() if ts else datetime.now(timezone.utc).isoformat()
        return round(price, 4), as_of

    def bars(self, symbol: str, timespan: str, limit: int) -> list[Bar]:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=max(limit * 2, 7))
        response = requests.get(
            f"{self.base_url}/v2/aggs/ticker/{symbol.upper()}/range/1/{timespan}/{start.date().isoformat()}/{now.date().isoformat()}",
            params={"limit": limit, "apiKey": self.api_key, "adjusted": "true", "sort": "asc"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json() or {}
        results = payload.get("results") or []
        bars: list[Bar] = []
        for row in results[-limit:]:
            ts = row.get("t")
            bars.append(
                Bar(
                    time=datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat() if ts else now.isoformat(),
                    open=float(row.get("o") or 0),
                    high=float(row.get("h") or 0),
                    low=float(row.get("l") or 0),
                    close=float(row.get("c") or 0),
                    volume=int(row.get("v") or 0),
                )
            )
        return bars

    def indicators(self, symbol: str, bars: list[Bar]) -> tuple[float, float, float, float]:
        del symbol
        closes = [b.close for b in bars if b.close]
        if not closes:
            return 0.0, 0.0, 0.0, 0.0
        window = closes[-14:] if len(closes) >= 14 else closes
        sma = sum(window) / len(window)
        ema = (window[-1] * 0.4) + (sma * 0.6)
        gains = [max(window[i] - window[i - 1], 0) for i in range(1, len(window))]
        losses = [max(window[i - 1] - window[i], 0) for i in range(1, len(window))]
        avg_gain = (sum(gains) / len(gains)) if gains else 0.0
        avg_loss = (sum(losses) / len(losses)) if losses else 0.0
        rs = (avg_gain / avg_loss) if avg_loss else 100.0
        rsi = 100 - (100 / (1 + rs))
        macd = closes[-1] - ema
        return round(sma, 4), round(ema, 4), round(rsi, 2), round(macd, 4)


def build_polygon_provider(settings: Settings):
    mode = settings.normalized_provider_mode
    if mode == "mock":
        return MockPolygonProvider()
    if mode == "real":
        return RealPolygonProvider(settings)
    if settings.polygon_api_key:
        return RealPolygonProvider(settings)
    return MockPolygonProvider()
