"""Manual Camelot ingestion job for scheduled or ad-hoc execution."""
from __future__ import annotations

from apps.api.trading_api.dependencies import get_camelot_provider


def main() -> int:
    provider = get_camelot_provider()
    try:
        count, source = provider.ingest_reference_data()
    except Exception as exc:  # pragma: no cover - operational script
        print(f"camelot ingestion failed: {exc}")
        return 1

    print(f"camelot ingestion complete: records={count} source={source} mode={provider.metadata.mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
