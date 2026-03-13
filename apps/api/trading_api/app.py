"""Application router for trading API endpoints."""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from .dependencies import (
    get_camelot_provider,
    get_polygon_provider,
    get_schwab_provider,
    get_supabase_provider,
)
from .schemas import (
    BarsResponse,
    CamelotIngestResponse,
    IndicatorResponse,
    OrderCreate,
    OrdersResponse,
    PositionsResponse,
    QuoteResponse,
    SessionCreate,
    SessionResponse,
    WatchlistMutation,
    WatchlistResponse,
)


def create_app() -> FastAPI:
    app = FastAPI(title="Alpha-Kite Trading API", version="0.1.0")

    @app.get("/health")
    def health(
        polygon=Depends(get_polygon_provider),
        supabase=Depends(get_supabase_provider),
        schwab=Depends(get_schwab_provider),
        camelot=Depends(get_camelot_provider),
    ):
        return {
            "status": "ok",
            "providers": {
                "polygon": polygon.metadata.mode,
                "supabase": supabase.metadata.mode,
                "schwab": schwab.metadata.mode,
                "camelot": camelot.metadata.mode,
            },
        }

    @app.get("/market/quote", response_model=QuoteResponse)
    def market_quote(symbol: str, polygon=Depends(get_polygon_provider)):
        price, as_of = polygon.quote(symbol)
        return QuoteResponse(symbol=symbol.upper(), price=price, as_of=as_of, provider_mode=polygon.metadata.mode)

    @app.get("/market/bars", response_model=BarsResponse)
    def market_bars(symbol: str, timespan: str = "day", limit: int = 30, polygon=Depends(get_polygon_provider)):
        if limit < 1 or limit > 365:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 365")
        bars = polygon.bars(symbol=symbol, timespan=timespan, limit=limit)
        return BarsResponse(symbol=symbol.upper(), bars=bars, provider_mode=polygon.metadata.mode)

    @app.get("/market/indicators", response_model=IndicatorResponse)
    def market_indicators(symbol: str, timespan: str = "day", limit: int = 30, polygon=Depends(get_polygon_provider)):
        bars = polygon.bars(symbol=symbol, timespan=timespan, limit=limit)
        sma, ema, rsi, macd = polygon.indicators(symbol=symbol, bars=bars)
        return IndicatorResponse(symbol=symbol.upper(), sma=sma, ema=ema, rsi=rsi, macd=macd, provider_mode=polygon.metadata.mode)

    @app.get("/watchlists/{user_id}", response_model=WatchlistResponse)
    def get_watchlist(user_id: str, supabase=Depends(get_supabase_provider)):
        return WatchlistResponse(user_id=user_id, symbols=supabase.list_watchlist(user_id), provider_mode=supabase.metadata.mode)

    @app.post("/watchlists/{user_id}", response_model=WatchlistResponse)
    def add_watchlist_symbol(user_id: str, body: WatchlistMutation, supabase=Depends(get_supabase_provider)):
        symbols = supabase.add_watchlist_symbol(user_id=user_id, symbol=body.symbol)
        return WatchlistResponse(user_id=user_id, symbols=symbols, provider_mode=supabase.metadata.mode)

    @app.delete("/watchlists/{user_id}/{symbol}", response_model=WatchlistResponse)
    def delete_watchlist_symbol(user_id: str, symbol: str, supabase=Depends(get_supabase_provider)):
        symbols = supabase.remove_watchlist_symbol(user_id=user_id, symbol=symbol)
        return WatchlistResponse(user_id=user_id, symbols=symbols, provider_mode=supabase.metadata.mode)

    @app.post("/auth/session", response_model=SessionResponse)
    def create_session(body: SessionCreate, supabase=Depends(get_supabase_provider)):
        return supabase.create_session(user_id=body.user_id, email=body.email)

    @app.get("/auth/session/{token}", response_model=SessionResponse)
    def get_session(token: str, supabase=Depends(get_supabase_provider)):
        session = supabase.get_session(token)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    @app.get("/positions/{user_id}", response_model=PositionsResponse)
    def get_positions(user_id: str, schwab=Depends(get_schwab_provider)):
        return PositionsResponse(user_id=user_id, positions=schwab.positions(user_id), provider_mode=schwab.metadata.mode)

    @app.get("/orders/{user_id}", response_model=OrdersResponse)
    def get_orders(user_id: str, schwab=Depends(get_schwab_provider)):
        return OrdersResponse(user_id=user_id, orders=schwab.orders(user_id), provider_mode=schwab.metadata.mode)

    @app.post("/orders/{user_id}", response_model=OrdersResponse)
    def create_order(user_id: str, body: OrderCreate, schwab=Depends(get_schwab_provider)):
        try:
            schwab.place_order(user_id=user_id, order=body)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return OrdersResponse(user_id=user_id, orders=schwab.orders(user_id), provider_mode=schwab.metadata.mode)

    @app.post("/ingest/camelot", response_model=CamelotIngestResponse)
    def ingest_camelot(camelot=Depends(get_camelot_provider)):
        try:
            count, source = camelot.ingest_reference_data()
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return CamelotIngestResponse(records_ingested=count, source=source, provider_mode=camelot.metadata.mode)

    return app
