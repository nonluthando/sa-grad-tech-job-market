"""Command-line entry point for raw public job-source ingestion."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import requests

from src.ingestion.config import (
    ConfiguredSource,
    GreenhouseSource,
    LeverSource,
    SuccessFactorsSource,
    WorkdaySource,
    OracleHCMSource,
    WPJobManagerSource,
    load_collection_sources,
)
from src.ingestion.greenhouse import GreenhouseClient
from src.ingestion.lever import LeverClient
from src.ingestion.snapshot import RawSnapshotStore, filename_timestamp
from src.ingestion.successfactors import SuccessFactorsClient
from src.ingestion.workday import WorkdayClient
from src.ingestion.oracle_hcm import OracleHCMClient
from src.ingestion.wp_job_manager import WPJobManagerClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "sources.json"
DEFAULT_RAW_ROOT = PROJECT_ROOT / "data" / "raw"


@dataclass(frozen=True)
class CollectionResult:
    source_name: str
    source_provider: str
    source_token: str
    status: str
    job_count: int
    raw_path: str | None
    metadata_path: str | None
    error: str | None


class GreenhouseFetcher(Protocol):
    def fetch_board(self, board_token: str): ...


class LeverFetcher(Protocol):
    def fetch_site(self, site_token: str): ...


class SuccessFactorsFetcher(Protocol):
    def fetch_source(self, source: SuccessFactorsSource): ...


class WorkdayFetcher(Protocol):
    def fetch_source(self, source: WorkdaySource): ...


class OracleHCMFetcher(Protocol):
    def fetch_source(self, source: OracleHCMSource): ...


class WPJobManagerFetcher(Protocol):
    def fetch_source(self, source: WPJobManagerSource): ...


def _failed_result(source_name: str, provider: str, token: str, error: Exception) -> CollectionResult:
    return CollectionResult(
        source_name=source_name,
        source_provider=provider,
        source_token=token,
        status="failed",
        job_count=0,
        raw_path=None,
        metadata_path=None,
        error=str(error),
    )


def collect_source(
    source: GreenhouseSource,
    client: GreenhouseFetcher,
    store: RawSnapshotStore,
    collected_at: datetime,
) -> CollectionResult:
    """Collect one Greenhouse source.

    This name is retained for backwards compatibility with the Milestone 1 API.
    """

    try:
        response = client.fetch_board(source.token)
        snapshot = store.write_greenhouse_snapshot(
            source_name=source.name,
            response=response,
            collected_at=collected_at,
        )
        return CollectionResult(
            source_name=source.name,
            source_provider="greenhouse",
            source_token=source.token,
            status=snapshot.status,
            job_count=response.job_count,
            raw_path=str(snapshot.raw_path),
            metadata_path=str(snapshot.metadata_path),
            error=None,
        )
    except (requests.RequestException, ValueError, OSError) as error:
        return _failed_result(source.name, "greenhouse", source.token, error)


def collect_lever_source(
    source: LeverSource,
    client: LeverFetcher,
    store: RawSnapshotStore,
    collected_at: datetime,
) -> CollectionResult:
    """Collect one Lever source."""

    try:
        response = client.fetch_site(source.token)
        snapshot = store.write_lever_snapshot(
            source_name=source.name,
            response=response,
            collected_at=collected_at,
        )
        return CollectionResult(
            source_name=source.name,
            source_provider="lever",
            source_token=source.token,
            status=snapshot.status,
            job_count=response.job_count,
            raw_path=str(snapshot.raw_path),
            metadata_path=str(snapshot.metadata_path),
            error=None,
        )
    except (requests.RequestException, ValueError, OSError) as error:
        return _failed_result(source.name, "lever", source.token, error)


def collect_successfactors_source(
    source: SuccessFactorsSource,
    client: SuccessFactorsFetcher,
    store: RawSnapshotStore,
    collected_at: datetime,
) -> CollectionResult:
    """Collect one complete SuccessFactors listing-and-detail bundle."""

    try:
        response = client.fetch_source(source)
        snapshot = store.write_successfactors_snapshot(
            source_name=source.name,
            response=response,
            collected_at=collected_at,
        )
        return CollectionResult(
            source_name=source.name,
            source_provider="successfactors",
            source_token=source.token,
            status=snapshot.status,
            job_count=response.job_count,
            raw_path=str(snapshot.raw_path),
            metadata_path=str(snapshot.metadata_path),
            error=None,
        )
    except (requests.RequestException, ValueError, OSError) as error:
        return _failed_result(source.name, "successfactors", source.token, error)



def collect_workday_source(
    source: WorkdaySource,
    client: WorkdayFetcher,
    store: RawSnapshotStore,
    collected_at: datetime,
) -> CollectionResult:
    """Collect one complete Workday CXS listing-and-detail bundle."""

    try:
        response = client.fetch_source(source)
        snapshot = store.write_workday_snapshot(
            source_name=source.name, response=response, collected_at=collected_at
        )
        return CollectionResult(
            source_name=source.name, source_provider="workday",
            source_token=source.token, status=snapshot.status,
            job_count=response.job_count, raw_path=str(snapshot.raw_path),
            metadata_path=str(snapshot.metadata_path), error=None,
        )
    except (requests.RequestException, ValueError, OSError) as error:
        return _failed_result(source.name, "workday", source.token, error)


def collect_oracle_hcm_source(
    source: OracleHCMSource,
    client: OracleHCMFetcher,
    store: RawSnapshotStore,
    collected_at: datetime,
) -> CollectionResult:
    """Collect one complete Oracle Candidate Experience bundle."""

    try:
        response = client.fetch_source(source)
        snapshot = store.write_oracle_hcm_snapshot(
            source_name=source.name, response=response, collected_at=collected_at
        )
        return CollectionResult(
            source_name=source.name, source_provider="oracle_hcm",
            source_token=source.token, status=snapshot.status,
            job_count=response.job_count, raw_path=str(snapshot.raw_path),
            metadata_path=str(snapshot.metadata_path), error=None,
        )
    except (requests.RequestException, ValueError, OSError) as error:
        return _failed_result(source.name, "oracle_hcm", source.token, error)


def collect_wp_job_manager_source(
    source: WPJobManagerSource,
    client: WPJobManagerFetcher,
    store: RawSnapshotStore,
    collected_at: datetime,
) -> CollectionResult:
    """Collect one complete WP Job Manager bundle."""

    try:
        response = client.fetch_source(source)
        snapshot = store.write_wp_job_manager_snapshot(
            source_name=source.name, response=response, collected_at=collected_at
        )
        return CollectionResult(
            source_name=source.name, source_provider="wp_job_manager",
            source_token=source.token, status=snapshot.status,
            job_count=response.job_count, raw_path=str(snapshot.raw_path),
            metadata_path=str(snapshot.metadata_path), error=None,
        )
    except (requests.RequestException, ValueError, OSError) as error:
        return _failed_result(source.name, "wp_job_manager", source.token, error)

def collect_configured_source(
    source: ConfiguredSource,
    greenhouse_client: GreenhouseFetcher,
    lever_client: LeverFetcher,
    successfactors_client: SuccessFactorsFetcher,
    workday_client: WorkdayFetcher,
    oracle_hcm_client: OracleHCMFetcher,
    wp_job_manager_client: WPJobManagerFetcher,
    store: RawSnapshotStore,
    collected_at: datetime,
) -> CollectionResult:
    if source.provider == "greenhouse":
        return collect_source(
            GreenhouseSource(name=source.name, token=source.token),
            greenhouse_client,
            store,
            collected_at,
        )
    if source.provider == "lever":
        return collect_lever_source(
            LeverSource(name=source.name, token=source.token),
            lever_client,
            store,
            collected_at,
        )
    if source.provider == "successfactors":
        if source.listing_url is None:
            raise ValueError(
                f"SuccessFactors source {source.token} has no listing URL."
            )
        return collect_successfactors_source(
            SuccessFactorsSource(
                name=source.name,
                token=source.token,
                listing_url=source.listing_url,
                page_size=source.page_size,
                max_pages=source.max_pages,
                request_delay_seconds=source.request_delay_seconds,
            ),
            successfactors_client,
            workday_client,
            oracle_hcm_client,
            wp_job_manager_client,
            store,
            collected_at,
        )
    if source.provider == "workday":
        if not source.host or not source.tenant or not source.site:
            raise ValueError(f"Workday source {source.token} is incomplete.")
        return collect_workday_source(
            WorkdaySource(
                name=source.name, token=source.token, host=source.host,
                tenant=source.tenant, site=source.site, page_size=source.page_size,
                max_pages=source.max_pages, request_delay_seconds=source.request_delay_seconds,
            ), workday_client, store, collected_at,
        )
    if source.provider == "oracle_hcm":
        if not source.host or not source.site:
            raise ValueError(f"Oracle HCM source {source.token} is incomplete.")
        return collect_oracle_hcm_source(
            OracleHCMSource(
                name=source.name, token=source.token, host=source.host, site=source.site,
                page_size=source.page_size, max_pages=source.max_pages,
                request_delay_seconds=source.request_delay_seconds,
            ), oracle_hcm_client, store, collected_at,
        )
    if source.provider == "wp_job_manager":
        if not source.listing_url or not source.api_url:
            raise ValueError(f"WP Job Manager source {source.token} is incomplete.")
        return collect_wp_job_manager_source(
            WPJobManagerSource(
                name=source.name, token=source.token, listing_url=source.listing_url,
                api_url=source.api_url, page_size=source.page_size,
                max_pages=source.max_pages, request_delay_seconds=source.request_delay_seconds,
            ), wp_job_manager_client, store, collected_at,
        )
    raise ValueError(f"Unsupported collection provider: {source.provider}")


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
        "provider_job_counts": {
            provider: sum(
                result.job_count
                for result in results
                if result.source_provider == provider
            )
            for provider in sorted({result.source_provider for result in results})
        },
        "results": [asdict(result) for result in results],
    }
    report_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report_path


def print_summary(results: list[CollectionResult], report_path: Path) -> None:
    print("\nRaw-ingestion summary")
    print("=" * 96)
    for result in results:
        print(
            f"{result.status.upper():9} | {result.source_provider:14} | "
            f"{result.source_name:18} | jobs={result.job_count:3} | "
            f"token={result.source_token}"
        )
        if result.error:
            print(f"           - {result.error}")
    print(f"\nRun report: {report_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect exact raw snapshots from every configured public provider."
        )
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument(
        "--source-token",
        action="append",
        dest="source_tokens",
        help="Collect only this source token. May be supplied more than once.",
    )
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--lever-page-limit", type=int, default=500)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    requested_tokens = set(args.source_tokens) if args.source_tokens else None

    try:
        sources = load_collection_sources(args.config, requested_tokens)
        greenhouse_client = GreenhouseClient(timeout_seconds=args.timeout)
        lever_client = LeverClient(
            timeout_seconds=args.timeout,
            page_limit=args.lever_page_limit,
        )
        successfactors_client = SuccessFactorsClient(timeout_seconds=args.timeout)
        workday_client = WorkdayClient(timeout_seconds=args.timeout)
        oracle_hcm_client = OracleHCMClient(timeout_seconds=args.timeout)
        wp_job_manager_client = WPJobManagerClient(timeout_seconds=args.timeout)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    collected_at = datetime.now(timezone.utc)
    store = RawSnapshotStore(args.raw_root)
    results = [
        collect_configured_source(
            source,
            greenhouse_client,
            lever_client,
            successfactors_client,
            workday_client,
            oracle_hcm_client,
            wp_job_manager_client,
            store,
            collected_at,
        )
        for source in sources
    ]
    report_path = write_run_report(args.raw_root, collected_at, results)
    print_summary(results, report_path)

    return 1 if any(result.status == "failed" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
