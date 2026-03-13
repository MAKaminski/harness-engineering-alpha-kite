"""Dependency builders shared across API routes and scripts."""
from __future__ import annotations

from functools import lru_cache

from trading_api.config import Settings, load_settings
from .providers.camelot_provider import build_camelot_provider
from .providers.polygon_provider import build_polygon_provider
from .providers.schwab_provider import build_schwab_provider
from .providers.supabase_provider import build_supabase_provider


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


@lru_cache(maxsize=1)
def get_supabase_provider():
    return build_supabase_provider(get_settings())


@lru_cache(maxsize=1)
def get_polygon_provider():
    return build_polygon_provider(get_settings())


@lru_cache(maxsize=1)
def get_schwab_provider():
    return build_schwab_provider(get_settings())


@lru_cache(maxsize=1)
def get_camelot_provider():
    return build_camelot_provider(get_settings())
