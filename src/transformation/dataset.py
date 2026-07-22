"""Build, deduplicate and persist the canonical jobs dataset."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable

from src.transformation.cleaning import unique_strings
from src.transformation.greenhouse import parse_datetime, transform_greenhouse_job
from src.transformation.schema import CanonicalJob
from src.transformation.snapshots import GreenhouseSnapshot, load_greenhouse_snapshots


@dataclass(frozen=True)
class DatasetBuildResult:
    jobs: tuple[CanonicalJob, ...]
    quality_report: dict[str, Any]


def deduplicate_jobs(observations: Iterable[CanonicalJob]) -> list[CanonicalJob]:
    """Keep the latest observation while retaining first/last-seen history."""

    grouped: dict[str, list[CanonicalJob]] = defaultdict(list)
    for observation in observations:
        grouped[observation.job_key].append(observation)

    canonical_jobs: list[CanonicalJob] = []
    for job_key in sorted(grouped):
        group = sorted(
            grouped[job_key],
            key=lambda job: (
                job.last_seen_at,
                job.source_updated_at or datetime.min.replace(tzinfo=timezone.utc),
                job.source_snapshot_path,
            ),
        )
        latest = group[-1]
        first_seen_at = min(job.first_seen_at for job in group)
        last_seen_at = max(job.last_seen_at for job in group)
        all_issues = unique_strings(
            issue for job in group for issue in job.data_quality_issues
        )
        canonical_jobs.append(
            latest.with_observation_window(
                first_seen_at=first_seen_at,
                last_seen_at=last_seen_at,
                observation_count=len(group),
                data_quality_issues=all_issues,
            )
        )

    return canonical_jobs


def _count_values(jobs: Iterable[CanonicalJob], field_name: str) -> dict[str, int]:
    counts = Counter(str(getattr(job, field_name) or "unspecified") for job in jobs)
    return dict(sorted(counts.items()))


def _build_quality_report(
    snapshots: list[GreenhouseSnapshot],
    observations: list[CanonicalJob],
    jobs: list[CanonicalJob],
) -> dict[str, Any]:
    issue_counts = Counter(
        issue for job in jobs for issue in job.data_quality_issues
    )
    source_snapshot_counts = Counter(
        str(snapshot.metadata.get("source_name")) for snapshot in snapshots
    )
    company_counts = Counter(job.company for job in jobs)

    snapshot_times = [
        timestamp
        for snapshot in snapshots
        if (timestamp := parse_datetime(snapshot.metadata.get("collected_at"))) is not None
    ]
    source_window_start = min(snapshot_times).isoformat() if snapshot_times else None
    source_window_end = max(snapshot_times).isoformat() if snapshot_times else None

    return {
        "source_window_start": source_window_start,
        "source_window_end": source_window_end,
        "raw_snapshot_count": len(snapshots),
        "raw_job_observation_count": len(observations),
        "canonical_job_count": len(jobs),
        "duplicate_observations_removed": len(observations) - len(jobs),
        "south_africa_job_count": sum(job.is_south_africa for job in jobs),
        "technology_job_count": sum(job.is_technology_role for job in jobs),
        "target_market_job_count": sum(job.is_target_market for job in jobs),
        "role_level_counts": _count_values(jobs, "role_level"),
        "workplace_type_counts": _count_values(jobs, "workplace_type"),
        "company_counts": dict(sorted(company_counts.items())),
        "source_snapshot_counts": dict(sorted(source_snapshot_counts.items())),
        "data_quality_issue_counts": dict(sorted(issue_counts.items())),
    }


def _relative_snapshot_path(raw_path: Path, raw_root: Path) -> Path:
    """Store portable lineage paths rather than machine-specific absolute paths."""

    try:
        return raw_path.resolve().relative_to(raw_root.resolve())
    except ValueError:
        return raw_path


def build_dataset(raw_root: Path) -> DatasetBuildResult:
    """Read saved snapshots and produce deterministic canonical job rows."""

    snapshots = load_greenhouse_snapshots(raw_root)
    observations = [
        transform_greenhouse_job(
            job,
            snapshot.metadata,
            _relative_snapshot_path(snapshot.raw_path, raw_root),
        )
        for snapshot in snapshots
        for job in snapshot.jobs
    ]
    jobs = deduplicate_jobs(observations)
    quality_report = _build_quality_report(snapshots, observations, jobs)
    return DatasetBuildResult(jobs=tuple(jobs), quality_report=quality_report)


def _parquet_schema() -> Any:
    try:
        import pyarrow as pa
    except ImportError as error:
        raise RuntimeError(
            "Parquet output requires pyarrow. Run: pip install -r requirements.txt"
        ) from error

    return pa.schema(
        [
            ("job_key", pa.string()),
            ("source_provider", pa.string()),
            ("source_name", pa.string()),
            ("source_token", pa.string()),
            ("source_job_id", pa.string()),
            ("source_snapshot_sha256", pa.string()),
            ("source_snapshot_path", pa.string()),
            ("first_seen_at", pa.timestamp("us", tz="UTC")),
            ("last_seen_at", pa.timestamp("us", tz="UTC")),
            ("source_updated_at", pa.timestamp("us", tz="UTC")),
            ("observation_count", pa.int64()),
            ("title", pa.string()),
            ("title_normalized", pa.string()),
            ("company", pa.string()),
            ("department", pa.string()),
            ("office", pa.string()),
            ("location_raw", pa.string()),
            ("city", pa.string()),
            ("province", pa.string()),
            ("country", pa.string()),
            ("location_evidence", pa.list_(pa.string())),
            ("is_south_africa", pa.bool_()),
            ("workplace_type", pa.string()),
            ("role_level", pa.string()),
            ("role_level_evidence", pa.list_(pa.string())),
            ("is_technology_role", pa.bool_()),
            ("technology_evidence", pa.list_(pa.string())),
            ("is_target_market", pa.bool_()),
            ("description_text", pa.string()),
            ("application_url", pa.string()),
            ("data_quality_issues", pa.list_(pa.string())),
        ]
    )


def write_parquet(path: Path, jobs: Iterable[CanonicalJob]) -> None:
    """Write a schema-controlled Parquet file atomically."""

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as error:
        raise RuntimeError(
            "Parquet output requires pyarrow. Run: pip install -r requirements.txt"
        ) from error

    path.parent.mkdir(parents=True, exist_ok=True)
    records = [job.to_record() for job in jobs]
    table = pa.Table.from_pylist(records, schema=_parquet_schema())

    with NamedTemporaryFile(
        dir=path.parent,
        suffix=".parquet",
        delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)

    try:
        pq.write_table(table, temporary_path, compression="zstd")
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary_file:
        temporary_path = Path(temporary_file.name)
        temporary_file.write(content.encode("utf-8"))
    temporary_path.replace(path)


def write_dataset_outputs(
    result: DatasetBuildResult,
    output_root: Path,
) -> tuple[Path, Path]:
    """Write the canonical Parquet dataset and its quality report."""

    parquet_path = output_root / "jobs.parquet"
    quality_path = output_root / "quality-report.json"
    write_parquet(parquet_path, result.jobs)
    _atomic_write_json(quality_path, result.quality_report)
    return parquet_path, quality_path
