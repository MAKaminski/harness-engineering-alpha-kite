"""Camelot data ingestion provider (real + mock fallback)."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from trading_api.config import Settings
from .base import ProviderMetadata


class MockCamelotProvider:
    metadata = ProviderMetadata(name="camelot", mode="mock")

    def __init__(self, output_file: str):
        self.output_file = output_file

    def ingest_reference_data(self) -> tuple[int, str]:
        sample_records = [
            {"symbol": "AAPL", "sector": "Technology"},
            {"symbol": "MSFT", "sector": "Technology"},
            {"symbol": "SPY", "sector": "ETF"},
        ]
        output = Path(self.output_file)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "source": "mock",
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "records": sample_records,
        }
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return len(sample_records), str(output)


class RealCamelotProvider:
    metadata = ProviderMetadata(name="camelot", mode="real")

    def __init__(self, settings: Settings):
        if not settings.camelot_repo_path:
            raise ValueError("CAMELOT_REPO_PATH is required for real mode")
        self.repo_path = Path(settings.camelot_repo_path)
        self.source_file = settings.camelot_source_file
        self.output_file = settings.camelot_ingest_output

    def ingest_reference_data(self) -> tuple[int, str]:
        source = (self.repo_path / self.source_file).resolve()
        if not source.exists():
            raise FileNotFoundError(f"Camelot source not found: {source}")
        records = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("Camelot source must be a JSON list of records")
        output = Path(self.output_file)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "source": str(source),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "records": records,
        }
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return len(records), str(output)


def build_camelot_provider(settings: Settings):
    mode = settings.normalized_provider_mode
    if mode == "mock":
        return MockCamelotProvider(settings.camelot_ingest_output)
    if mode == "real":
        return RealCamelotProvider(settings)
    if settings.camelot_repo_path:
        return RealCamelotProvider(settings)
    return MockCamelotProvider(settings.camelot_ingest_output)
