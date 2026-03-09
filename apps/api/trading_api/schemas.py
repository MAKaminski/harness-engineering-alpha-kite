"""Pydantic schemas used by API endpoints and provider adapters."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Bar(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class QuoteResponse(BaseModel):
    symbol: str
    price: float
    as_of: str
    provider_mode: str


class BarsResponse(BaseModel):
    symbol: str
    bars: list[Bar]
    provider_mode: str


class IndicatorResponse(BaseModel):
    symbol: str
    sma: float
    ema: float
    rsi: float
    macd: float
    provider_mode: str


class WatchlistMutation(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)


class WatchlistResponse(BaseModel):
    user_id: str
    symbols: list[str]
    provider_mode: str


class Position(BaseModel):
    symbol: str
    quantity: float
    average_price: float
    market_price: float


class PositionsResponse(BaseModel):
    user_id: str
    positions: list[Position]
    provider_mode: str


class Order(BaseModel):
    id: str
    symbol: str
    side: str
    quantity: float
    status: str


class OrderCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    side: str = Field(pattern="^(buy|sell)$")
    quantity: float = Field(gt=0)
    order_type: str = Field(default="market", pattern="^(market|limit)$")


class OrdersResponse(BaseModel):
    user_id: str
    orders: list[Order]
    provider_mode: str


class SessionCreate(BaseModel):
    user_id: str = Field(min_length=1)
    email: Optional[str] = None


class SessionResponse(BaseModel):
    token: str
    user_id: str
    email: Optional[str] = None
    provider_mode: str


class CamelotIngestResponse(BaseModel):
    records_ingested: int
    source: str
    provider_mode: str
