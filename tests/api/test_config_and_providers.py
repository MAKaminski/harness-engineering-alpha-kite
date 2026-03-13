from __future__ import annotations

import os
import pathlib
import sys
from typing import Any, Dict

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "apps" / "api"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from trading_api.config import Settings, _bool_env, _int_env, load_settings  # noqa: E402
from trading_api.providers.supabase_provider import MockSupabaseProvider, build_supabase_provider  # noqa: E402


def test_bool_env_parsing_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    env_values: Dict[str, str] = {
        "T1": "1",
        "T2": "true",
        "T3": "TRUE",
        "T4": "Yes",
        "F1": "0",
        "F2": "false",
        "F3": "off",
    }

    def fake_getenv(name: str, default: Any | None = None) -> Any:
        del default
        return env_values.get(name)

    monkeypatch.setattr(os, "getenv", fake_getenv)

    assert _bool_env("T1") is True
    assert _bool_env("T2") is True
    assert _bool_env("T3") is True
    assert _bool_env("T4") is True
    assert _bool_env("F1") is False
    assert _bool_env("F2") is False
    assert _bool_env("F3") is False
    assert _bool_env("MISSING", default=True) is True
    assert _bool_env("MISSING", default=False) is False


def test_int_env_valid_and_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    env_values: Dict[str, str] = {
        "PORT_VALID": "9000",
        "PORT_INVALID": "not-an-int",
    }

    def fake_getenv(name: str, default: Any | None = None) -> Any:
        del default
        return env_values.get(name)

    monkeypatch.setattr(os, "getenv", fake_getenv)

    assert _int_env("PORT_VALID", default=8000) == 9000
    assert _int_env("PORT_INVALID", default=8000) == 8000
    assert _int_env("MISSING", default=7000) == 7000


def test_load_settings_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    env_values: Dict[str, str] = {
        "APP_ENV": "production",
        "API_HOST": "127.0.0.1",
        "API_PORT": "1234",
        "PROVIDER_MODE": "real",
        "SCHWAB_ENABLE_ORDER_PLACEMENT": "true",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "key",
        "POLYGON_API_KEY": "poly-key",
        "POLYGON_BASE_URL": "https://polygon.example.test",
        "SCHWAB_BASE_URL": "https://schwab.example.test",
        "SCHWAB_ACCESS_TOKEN": "access",
        "SCHWAB_ACCOUNT_ID": "acct-1",
        "CAMELOT_REPO_PATH": "/tmp/repo",
        "CAMELOT_SOURCE_FILE": "src.json",
        "CAMELOT_INGEST_OUTPUT": "out.json",
    }

    def fake_getenv(name: str, default: Any | None = None) -> Any:
        return env_values.get(name, default)

    monkeypatch.setattr(os, "getenv", fake_getenv)

    settings = load_settings()
    assert isinstance(settings, Settings)
    assert settings.app_env == "production"
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 1234
    assert settings.provider_mode == "real"
    assert settings.enable_order_placement is True
    assert settings.supabase_url == env_values["SUPABASE_URL"]
    assert settings.supabase_service_role_key == env_values["SUPABASE_SERVICE_ROLE_KEY"]
    assert settings.polygon_api_key == env_values["POLYGON_API_KEY"]
    assert settings.polygon_base_url == env_values["POLYGON_BASE_URL"]
    assert settings.schwab_base_url == env_values["SCHWAB_BASE_URL"]
    assert settings.schwab_access_token == env_values["SCHWAB_ACCESS_TOKEN"]
    assert settings.schwab_account_id == env_values["SCHWAB_ACCOUNT_ID"]
    assert settings.camelot_repo_path == env_values["CAMELOT_REPO_PATH"]
    assert settings.camelot_source_file == env_values["CAMELOT_SOURCE_FILE"]
    assert settings.camelot_ingest_output == env_values["CAMELOT_INGEST_OUTPUT"]


def test_build_supabase_provider_respects_provider_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getenv(name: str, default: Any | None = None) -> Any:
        env_map = {
            "PROVIDER_MODE": "mock",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "key",
        }
        return env_map.get(name, default)

    monkeypatch.setattr(os, "getenv", fake_getenv)

    settings = load_settings()
    assert settings.normalized_provider_mode == "mock"
    provider = build_supabase_provider(settings)
    assert isinstance(provider, MockSupabaseProvider)
    assert provider.metadata.mode == "mock"

