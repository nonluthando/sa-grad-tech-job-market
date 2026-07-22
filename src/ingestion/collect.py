"""Command-line entry point for raw Greenhouse ingestion."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.ingestion.config import GreenhouseSource, load_greenhouse_sources
from src.ingestion.greenhouse import GreenhouseClient
from src.ingestion.snapshot import RawSnapshotStore, filename_timestamp


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "sources.json"
DEFAULT_RAW_ROOT = PROJECT_ROOT / "data" / "raw"


@dataclass(frozen=True)
class CollectionResult:
    source_name: str
    source_token: str
    status: str
    job_count: int
    raw_path: str | None
    metadata_path: str | None
    error: str | None


def collect_source(
    source: GreenhouseSource,
    client: GreenhouseClient,
    store: RawSnapshotStore,
    collected_at: datetime,
) -> CollectionResult:
    try:
        response = client.fetch_board(source.token)
        snapshot = store.write_greenhouse_snapshot(
            source_name=source.name,
            response=response,
            collected_at=collected_at,
        )
        return CollectionResult(
            source_name=source.name,
            source_token=source.token,
            status=snapshot.status,
            job_count=response.job_count,
            raw_path=str(snapshot.raw_path),
            metadata_path=str(snapshot.metadata_path),
            error=None,
        )
    except (requests.RequestException, ValueError, OSError) as error:
        return CollectionResult(
            source_name=source.name,
            source_token=source.token,
            status="failed",
            job_count=0,
            raw_path=None,
            metadata_path=None,
            error=str(error),
        )


def write_run_report(
    raw_root: Path,
    collected_at: datetime,
    results: list[CollectionResult],
) -> Path:
    run_directory = raw_root / "_runs"
    run_directory.mkdir(parents=True, exist_ok=True)
    report_path = run_directory / f"{filename_timestamp(collected_at)}.json"
    payload = {
        "collected_at": collected_at.astimezone(timezone.utc).isoformat(),
        "successful_sources": sum(result.status != "failed" for result in results),
        "failed_sources": sum(result.status == "failed" for result in results),
        "total_source_jobs": sum(result.job_count for result in results),
        "results": [asdict(result) for result in results],
    }
    report_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report_path


def print_summary(results: list[CollectionResult], report_path: Path) -> None:
    print("\nGreenhouse raw-ingestion summary")
    print("=" * 80)
    for result in results:
        print(
            f"{result.status.upper():9} | {result.source_name:18} | "
            f"jobs={result.job_count:3} | token={result.source_token}"
        )
        if result.error:
            print(f"           - {result.error}")
    print(f"\nRun report: {report_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect exact raw Greenhouse job-board snapshots."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument(
        "--source-token",
        action="append",
        dest="source_tokens",
        help="Collect only this Greenhouse token. May be supplied more than once.",
    )
    parser.add_argument("--timeout", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    requested_tokens = set(args.source_tokens) if args.source_tokens else None

    try:
        sources = load_greenhouse_sources(args.config, requested_tokens)
        client = GreenhouseClient(timeout_seconds=args.timeout)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    collected_at = datetime.now(timezone.utc)
    store = RawSnapshotStore(args.raw_root)
    results = [
        collect_source(source, client, store, collected_at)
        for source in sources
    ]
    report_path = write_run_report(args.raw_root, collected_at, results)
    print_summary(results, report_path)

    return 1 if any(result.status == "failed" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
