"""Read and verify immutable raw Greenhouse snapshots."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.transformation.greenhouse import parse_datetime


class SnapshotReadError(ValueError):
    """Raised when a saved raw snapshot violates the ingestion contract."""


@dataclass(frozen=True)
class GreenhouseSnapshot:
    metadata_path: Path
    raw_path: Path
    metadata: Mapping[str, Any]
    jobs: tuple[Mapping[str, Any], ...]


def discover_metadata_paths(raw_root: Path) -> list[Path]:
    """Return all Greenhouse metadata sidecars in deterministic order."""

    return sorted((raw_root / "greenhouse").glob("*/*.metadata.json"))


def read_greenhouse_snapshot(metadata_path: Path) -> GreenhouseSnapshot:
    """Validate metadata, integrity and the minimum raw JSON structure."""

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SnapshotReadError(f"Cannot read metadata {metadata_path}: {error}") from error

    if not isinstance(metadata, dict):
        raise SnapshotReadError(f"Metadata must be an object: {metadata_path}")

    required_fields = (
        "source",
        "source_name",
        "source_token",
        "collected_at",
        "content_sha256",
        "source_job_count",
        "raw_file",
    )
    missing_fields = [field for field in required_fields if field not in metadata]
    if missing_fields:
        missing = ", ".join(missing_fields)
        raise SnapshotReadError(f"Metadata {metadata_path} is missing: {missing}")

    if metadata.get("source") != "greenhouse":
        raise SnapshotReadError(f"Unsupported source in metadata: {metadata_path}")

    for field_name in ("source_name", "source_token"):
        field_value = metadata.get(field_name)
        if not isinstance(field_value, str) or not field_value.strip():
            raise SnapshotReadError(
                f"Invalid {field_name} in metadata: {metadata_path}"
            )

    if parse_datetime(metadata.get("collected_at")) is None:
        raise SnapshotReadError(f"Invalid collected_at in metadata: {metadata_path}")

    expected_digest = metadata.get("content_sha256")
    if not isinstance(expected_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_digest
    ):
        raise SnapshotReadError(
            f"Invalid content_sha256 in metadata: {metadata_path}"
        )

    raw_file = metadata.get("raw_file")
    if not isinstance(raw_file, str) or not raw_file.strip():
        raise SnapshotReadError(f"Invalid raw_file in metadata: {metadata_path}")
    if Path(raw_file).name != raw_file or Path(raw_file).is_absolute():
        raise SnapshotReadError(
            f"raw_file must be a filename within its snapshot directory: {metadata_path}"
        )
    raw_path = metadata_path.parent / raw_file

    try:
        raw_bytes = raw_path.read_bytes()
    except OSError as error:
        raise SnapshotReadError(f"Cannot read raw snapshot {raw_path}: {error}") from error

    actual_digest = hashlib.sha256(raw_bytes).hexdigest()
    if actual_digest != expected_digest:
        raise SnapshotReadError(f"SHA-256 mismatch for raw snapshot: {raw_path}")

    try:
        payload = json.loads(raw_bytes)
    except json.JSONDecodeError as error:
        raise SnapshotReadError(f"Raw snapshot is not valid JSON: {raw_path}") from error

    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise SnapshotReadError(f"Raw snapshot must contain a jobs list: {raw_path}")

    jobs: list[Mapping[str, Any]] = []
    for index, job in enumerate(payload["jobs"]):
        if not isinstance(job, dict):
            raise SnapshotReadError(
                f"Job at index {index} is not an object in snapshot: {raw_path}"
            )
        jobs.append(job)

    expected_count = metadata.get("source_job_count")
    if (
        not isinstance(expected_count, int)
        or isinstance(expected_count, bool)
        or expected_count != len(jobs)
    ):
        raise SnapshotReadError(
            f"source_job_count does not match the jobs list in: {raw_path}"
        )

    return GreenhouseSnapshot(
        metadata_path=metadata_path,
        raw_path=raw_path,
        metadata=metadata,
        jobs=tuple(jobs),
    )


def load_greenhouse_snapshots(raw_root: Path) -> list[GreenhouseSnapshot]:
    """Load every valid Greenhouse snapshot under the raw root."""

    metadata_paths = discover_metadata_paths(raw_root)
    if not metadata_paths:
        raise SnapshotReadError(
            f"No Greenhouse metadata snapshots found beneath: {raw_root}"
        )

    snapshots = [read_greenhouse_snapshot(path) for path in metadata_paths]
    return sorted(
        snapshots,
        key=lambda snapshot: (
            parse_datetime(snapshot.metadata.get("collected_at")),
            str(snapshot.metadata_path),
        ),
    )
