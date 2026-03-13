"""Supabase provider implementations (real + mock fallback)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Optional

import requests

from trading_api.config import Settings
from .base import ProviderMetadata
from ..trading_api.schemas import SessionResponse


def _token_for(user_id: str, email: Optional[str]) -> str:
    payload = f"{user_id}:{email or ''}:{datetime.now(timezone.utc).isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


@dataclass
class _InMemorySupabaseStore:
    watchlists: dict[str, set[str]] = field(default_factory=dict)
    sessions: dict[str, SessionResponse] = field(default_factory=dict)


_STORE = _InMemorySupabaseStore()


class MockSupabaseProvider:
    metadata = ProviderMetadata(name="supabase", mode="mock")

    def list_watchlist(self, user_id: str) -> list[str]:
        return sorted(_STORE.watchlists.get(user_id, set()))

    def add_watchlist_symbol(self, user_id: str, symbol: str) -> list[str]:
        normalized = symbol.upper().strip()
        _STORE.watchlists.setdefault(user_id, set()).add(normalized)
        return self.list_watchlist(user_id)

    def remove_watchlist_symbol(self, user_id: str, symbol: str) -> list[str]:
        normalized = symbol.upper().strip()
        _STORE.watchlists.setdefault(user_id, set()).discard(normalized)
        return self.list_watchlist(user_id)

    def create_session(self, user_id: str, email: Optional[str]) -> SessionResponse:
        token = _token_for(user_id, email)
        session = SessionResponse(token=token, user_id=user_id, email=email, provider_mode="mock")
        _STORE.sessions[token] = session
        return session

    def get_session(self, token: str) -> Optional[SessionResponse]:
        return _STORE.sessions.get(token)


class RealSupabaseProvider:
    metadata = ProviderMetadata(name="supabase", mode="real")

    def __init__(self, settings: Settings):
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for real mode")
        self.url = settings.supabase_url.rstrip("/")
        self.key = settings.supabase_service_role_key

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

    def list_watchlist(self, user_id: str) -> list[str]:
        response = requests.get(
            f"{self.url}/rest/v1/watchlists",
            params={"user_id": f"eq.{user_id}", "select": "symbol"},
            headers=self._headers,
            timeout=15,
        )
        response.raise_for_status()
        rows = response.json() or []
        return sorted({row.get("symbol", "").upper() for row in rows if row.get("symbol")})

    def add_watchlist_symbol(self, user_id: str, symbol: str) -> list[str]:
        payload = {"user_id": user_id, "symbol": symbol.upper().strip()}
        response = requests.post(
            f"{self.url}/rest/v1/watchlists",
            headers={**self._headers, "Prefer": "resolution=merge-duplicates"},
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
        return self.list_watchlist(user_id)

    def remove_watchlist_symbol(self, user_id: str, symbol: str) -> list[str]:
        response = requests.delete(
            f"{self.url}/rest/v1/watchlists",
            params={"user_id": f"eq.{user_id}", "symbol": f"eq.{symbol.upper().strip()}"},
            headers=self._headers,
            timeout=15,
        )
        response.raise_for_status()
        return self.list_watchlist(user_id)

    def create_session(self, user_id: str, email: Optional[str]) -> SessionResponse:
        token = _token_for(user_id, email)
        payload = {
            "token": token,
            "user_id": user_id,
            "email": email,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        response = requests.post(f"{self.url}/rest/v1/sessions", headers=self._headers, json=payload, timeout=15)
        response.raise_for_status()
        return SessionResponse(token=token, user_id=user_id, email=email, provider_mode="real")

    def get_session(self, token: str) -> Optional[SessionResponse]:
        response = requests.get(
            f"{self.url}/rest/v1/sessions",
            params={"token": f"eq.{token}", "limit": "1", "select": "token,user_id,email"},
            headers=self._headers,
            timeout=15,
        )
        response.raise_for_status()
        rows = response.json() or []
        if not rows:
            return None
        row = rows[0]
        return SessionResponse(
            token=row.get("token", token),
            user_id=row.get("user_id", ""),
            email=row.get("email"),
            provider_mode="real",
        )


def build_supabase_provider(settings: Settings):
    mode = settings.normalized_provider_mode
    if mode == "mock":
        return MockSupabaseProvider()
    if mode == "real":
        return RealSupabaseProvider(settings)
    if settings.supabase_url and settings.supabase_service_role_key:
        return RealSupabaseProvider(settings)
    return MockSupabaseProvider()
