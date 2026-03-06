"""FastAPI entrypoint for the Alpha-Kite trading backend."""
from __future__ import annotations

import uvicorn

from trading_api.app import create_app

app = create_app()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
