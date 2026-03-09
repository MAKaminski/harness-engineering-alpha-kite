"""Environment-driven settings for trading API providers and service behavior."""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_env: str
    api_host: str
    api_port: int
    provider_mode: str
    enable_order_placement: bool

    supabase_url: Optional[str]
    supabase_service_role_key: Optional[str]

    polygon_api_key: Optional[str]
    polygon_base_url: str

    schwab_base_url: str
    schwab_access_token: Optional[str]
    schwab_account_id: Optional[str]

    camelot_repo_path: Optional[str]
    camelot_source_file: str
    camelot_ingest_output: str


    @property
    def normalized_provider_mode(self) -> str:
        mode = (self.provider_mode or "auto").strip().lower()
        if mode not in {"auto", "real", "mock"}:
            return "auto"
        return mode


def load_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=_int_env("API_PORT", 8000),
        provider_mode=os.getenv("PROVIDER_MODE", "auto"),
        enable_order_placement=_bool_env("SCHWAB_ENABLE_ORDER_PLACEMENT", default=False),
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        polygon_api_key=os.getenv("POLYGON_API_KEY"),
        polygon_base_url=os.getenv("POLYGON_BASE_URL", "https://api.polygon.io"),
        schwab_base_url=os.getenv("SCHWAB_BASE_URL", "https://api.schwabapi.com"),
        schwab_access_token=os.getenv("SCHWAB_ACCESS_TOKEN"),
        schwab_account_id=os.getenv("SCHWAB_ACCOUNT_ID"),
        camelot_repo_path=os.getenv("CAMELOT_REPO_PATH"),
        camelot_source_file=os.getenv("CAMELOT_SOURCE_FILE", "data/reference.json"),
        camelot_ingest_output=os.getenv("CAMELOT_INGEST_OUTPUT", "apps/api/data/camelot_ingested.json"),
    )
