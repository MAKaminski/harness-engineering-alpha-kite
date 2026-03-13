from __future__ import annotations

import pathlib
import sys

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[2]
LAUNCHER_ROOT = ROOT / "launcher"
if str(LAUNCHER_ROOT) not in sys.path:
    sys.path.insert(0, str(LAUNCHER_ROOT))

from app import app, PROCESSES  # type: ignore  # noqa: E402


def _request(method: str, path: str, **kwargs) -> httpx.Response:
    async def _inner() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    import asyncio

    return asyncio.run(_inner())


def test_index_serves_html() -> None:
    response = _request("GET", "/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "<!DOCTYPE html" in response.text or "<html" in response.text.lower()


def test_status_defaults_to_all_false() -> None:
    PROCESSES.clear()
    response = _request("GET", "/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"api": False, "web": False, "symphony": False}

