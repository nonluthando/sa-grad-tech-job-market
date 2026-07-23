"""Read and verify immutable raw job-source snapshots."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from src.transformation.greenhouse import parse_datetime
from src.transformation.successfactors import parse_successfactors_detail

SUPPORTED_SNAPSHOT_PROVIDERS = (
    "greenhouse", "lever", "successfactors", "workday", "oracle_hcm",
    "wp_job_manager",
)


class SnapshotReadError(ValueError):
    """Raised when a saved raw snapshot violates the ingestion contract."""


@dataclass(frozen=True)
class SourceSnapshot:
    metadata_path: Path
    raw_path: Path
    metadata: Mapping[str, Any]
    jobs: tuple[Mapping[str, Any], ...]

    @property
    def provider(self) -> str:
        return str(self.metadata.get("source") or "")


GreenhouseSnapshot = SourceSnapshot
LeverSnapshot = SourceSnapshot
SuccessFactorsSnapshot = SourceSnapshot
WorkdaySnapshot = SourceSnapshot
OracleHCMSnapshot = SourceSnapshot
WPJobManagerSnapshot = SourceSnapshot


def discover_metadata_paths(raw_root: Path, provider: str) -> list[Path]:
    if provider not in SUPPORTED_SNAPSHOT_PROVIDERS:
        raise SnapshotReadError(f"Unsupported snapshot provider: {provider}")
    return sorted((raw_root / provider).glob("*/*.metadata.json"))


def discover_all_metadata_paths(raw_root: Path) -> list[Path]:
    return sorted(
        path
        for provider in SUPPORTED_SNAPSHOT_PROVIDERS
        for path in discover_metadata_paths(raw_root, provider)
    )


def _read_metadata(metadata_path: Path, expected_provider: str) -> dict[str, Any]:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SnapshotReadError(f"Cannot read metadata {metadata_path}: {error}") from error
    if not isinstance(metadata, dict):
        raise SnapshotReadError(f"Metadata must be an object: {metadata_path}")
    required = (
        "source", "source_name", "source_token", "collected_at",
        "content_sha256", "source_job_count", "raw_file",
    )
    missing = [field for field in required if field not in metadata]
    if missing:
        raise SnapshotReadError(
            f"Metadata {metadata_path} is missing: {', '.join(missing)}"
        )
    if metadata.get("source") != expected_provider:
        raise SnapshotReadError(
            f"Expected {expected_provider} metadata but found "
            f"{metadata.get('source')!r}: {metadata_path}"
        )
    for field in ("source_name", "source_token"):
        if not isinstance(metadata.get(field), str) or not metadata[field].strip():
            raise SnapshotReadError(f"Invalid {field} in metadata: {metadata_path}")
    if parse_datetime(metadata.get("collected_at")) is None:
        raise SnapshotReadError(f"Invalid collected_at in metadata: {metadata_path}")
    digest = metadata.get("content_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise SnapshotReadError(f"Invalid content_sha256 in metadata: {metadata_path}")
    raw_file = metadata.get("raw_file")
    if not isinstance(raw_file, str) or Path(raw_file).name != raw_file or Path(raw_file).is_absolute():
        raise SnapshotReadError(f"Invalid raw_file in metadata: {metadata_path}")
    return metadata


def _read_verified_payload(metadata_path: Path, metadata: Mapping[str, Any]) -> tuple[Path, Any]:
    raw_path = metadata_path.parent / str(metadata["raw_file"])
    try:
        raw_bytes = raw_path.read_bytes()
    except OSError as error:
        raise SnapshotReadError(f"Cannot read raw snapshot {raw_path}: {error}") from error
    if hashlib.sha256(raw_bytes).hexdigest() != metadata["content_sha256"]:
        raise SnapshotReadError(f"SHA-256 mismatch for raw snapshot: {raw_path}")
    try:
        return raw_path, json.loads(raw_bytes)
    except json.JSONDecodeError as error:
        raise SnapshotReadError(f"Raw snapshot is not valid JSON: {raw_path}") from error


def _validate_jobs(payload_jobs: Any, raw_path: Path, expected_count: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(payload_jobs, list):
        raise SnapshotReadError(f"Raw snapshot must contain a jobs list: {raw_path}")
    jobs: list[Mapping[str, Any]] = []
    for index, job in enumerate(payload_jobs):
        if not isinstance(job, dict):
            raise SnapshotReadError(f"Job at index {index} is not an object: {raw_path}")
        jobs.append(job)
    if not isinstance(expected_count, int) or isinstance(expected_count, bool) or expected_count != len(jobs):
        raise SnapshotReadError(f"source_job_count does not match jobs: {raw_path}")
    return tuple(jobs)


def read_greenhouse_snapshot(metadata_path: Path) -> GreenhouseSnapshot:
    metadata = _read_metadata(metadata_path, "greenhouse")
    raw_path, payload = _read_verified_payload(metadata_path, metadata)
    if not isinstance(payload, dict):
        raise SnapshotReadError(f"Greenhouse snapshot must be an object: {raw_path}")
    jobs = _validate_jobs(payload.get("jobs"), raw_path, metadata.get("source_job_count"))
    return SourceSnapshot(metadata_path, raw_path, metadata, jobs)


def read_lever_snapshot(metadata_path: Path) -> LeverSnapshot:
    metadata = _read_metadata(metadata_path, "lever")
    raw_path, payload = _read_verified_payload(metadata_path, metadata)
    jobs = _validate_jobs(payload, raw_path, metadata.get("source_job_count"))
    return SourceSnapshot(metadata_path, raw_path, metadata, jobs)


def _decode_page(page: Any, raw_path: Path, provider: str) -> bytes:
    if not isinstance(page, dict):
        raise SnapshotReadError(f"{provider} page must be an object: {raw_path}")
    body_base64 = page.get("body_base64")
    expected_digest = page.get("content_sha256")
    if not isinstance(body_base64, str) or not isinstance(expected_digest, str):
        raise SnapshotReadError(f"{provider} page is missing body or digest: {raw_path}")
    try:
        body = base64.b64decode(body_base64, validate=True)
    except (ValueError, TypeError) as error:
        raise SnapshotReadError(f"Invalid {provider} base64 page body: {raw_path}") from error
    if hashlib.sha256(body).hexdigest() != expected_digest:
        raise SnapshotReadError(f"{provider} embedded page SHA-256 mismatch: {raw_path}")
    return body


def _read_bundle(
    metadata_path: Path,
    provider: str,
    detail_parser: Callable[[bytes, Mapping[str, Any], Mapping[str, Any], str], Mapping[str, Any]],
) -> SourceSnapshot:
    metadata = _read_metadata(metadata_path, provider)
    raw_path, payload = _read_verified_payload(metadata_path, metadata)
    if not isinstance(payload, dict) or payload.get("provider") != provider:
        raise SnapshotReadError(f"{provider} snapshot must be a provider envelope: {raw_path}")
    listing_pages = payload.get("listing_pages")
    job_pages = payload.get("job_pages")
    job_index = payload.get("job_index")
    if not isinstance(listing_pages, list) or not listing_pages:
        raise SnapshotReadError(f"{provider} snapshot has no listing pages: {raw_path}")
    if not isinstance(job_pages, list) or not isinstance(job_index, list):
        raise SnapshotReadError(f"{provider} snapshot has invalid pages/index: {raw_path}")
    for page in listing_pages:
        _decode_page(page, raw_path, provider)
    jobs: list[Mapping[str, Any]] = []
    for position, page in enumerate(job_pages):
        body = _decode_page(page, raw_path, provider)
        index = job_index[position] if position < len(job_index) and isinstance(job_index[position], dict) else {}
        if not isinstance(page, dict):
            raise SnapshotReadError(f"{provider} job page must be an object: {raw_path}")
        final_url = str(page.get("final_url") or page.get("requested_url") or "")
        jobs.append(detail_parser(body, index, payload, final_url))
    expected = metadata.get("source_job_count")
    if payload.get("reported_job_count") != expected or len(jobs) != expected:
        raise SnapshotReadError(f"{provider} source_job_count does not match bundle pages: {raw_path}")
    return SourceSnapshot(metadata_path, raw_path, metadata, tuple(jobs))


def _successfactors_detail(body: bytes, index: Mapping[str, Any], payload: Mapping[str, Any], url: str) -> Mapping[str, Any]:
    return parse_successfactors_detail(body, url, index)


def _json_detail(body: bytes, index: Mapping[str, Any], payload: Mapping[str, Any], url: str) -> Mapping[str, Any]:
    try:
        raw = json.loads(body)
    except json.JSONDecodeError as error:
        raise SnapshotReadError(f"Embedded JSON detail is invalid: {url}") from error
    if not isinstance(raw, dict):
        raise SnapshotReadError(f"Embedded JSON detail must be an object: {url}")
    items = raw.get("items")
    if isinstance(items, list) and len(items) == 1 and isinstance(items[0], dict):
        raw = dict(items[0])
    combined = dict(index)
    combined.update(raw)
    combined["_detail_url"] = url
    combined["_public_base_url"] = str(payload.get("public_base_url") or "")
    external_path = str(index.get("externalPath") or index.get("external_path") or "")
    if external_path:
        combined["_external_path"] = external_path
    return combined


def _html_detail(body: bytes, index: Mapping[str, Any], payload: Mapping[str, Any], url: str) -> Mapping[str, Any]:
    return {
        **dict(index),
        "_detail_html": body.decode("utf-8", errors="replace"),
        "_detail_url": url,
    }


def read_successfactors_snapshot(path: Path) -> SuccessFactorsSnapshot:
    return _read_bundle(path, "successfactors", _successfactors_detail)


def read_workday_snapshot(path: Path) -> WorkdaySnapshot:
    return _read_bundle(path, "workday", _json_detail)


def read_oracle_hcm_snapshot(path: Path) -> OracleHCMSnapshot:
    return _read_bundle(path, "oracle_hcm", _json_detail)


def read_wp_job_manager_snapshot(path: Path) -> WPJobManagerSnapshot:
    return _read_bundle(path, "wp_job_manager", _html_detail)


def _sort_snapshots(snapshots: list[SourceSnapshot]) -> list[SourceSnapshot]:
    return sorted(snapshots, key=lambda s: (parse_datetime(s.metadata.get("collected_at")), s.provider, str(s.metadata_path)))


def load_snapshots(raw_root: Path) -> list[SourceSnapshot]:
    metadata_paths = discover_all_metadata_paths(raw_root)
    if not metadata_paths:
        raise SnapshotReadError(f"No supported metadata snapshots found beneath: {raw_root}")
    readers = {
        "greenhouse": read_greenhouse_snapshot,
        "lever": read_lever_snapshot,
        "successfactors": read_successfactors_snapshot,
        "workday": read_workday_snapshot,
        "oracle_hcm": read_oracle_hcm_snapshot,
        "wp_job_manager": read_wp_job_manager_snapshot,
    }
    snapshots = []
    for path in metadata_paths:
        provider = path.parent.parent.name
        reader = readers.get(provider)
        if reader is None:
            raise SnapshotReadError(f"Unsupported snapshot provider directory: {path}")
        snapshots.append(reader(path))
    return _sort_snapshots(snapshots)


def _load_required(raw_root: Path, provider: str, reader: Callable[[Path], SourceSnapshot]) -> list[SourceSnapshot]:
    paths = discover_metadata_paths(raw_root, provider)
    if not paths:
        raise SnapshotReadError(f"No {provider.title()} metadata snapshots found beneath: {raw_root}")
    return _sort_snapshots([reader(path) for path in paths])


def load_greenhouse_snapshots(raw_root: Path) -> list[GreenhouseSnapshot]:
    return _load_required(raw_root, "greenhouse", read_greenhouse_snapshot)


def load_lever_snapshots(raw_root: Path) -> list[LeverSnapshot]:
    return _load_required(raw_root, "lever", read_lever_snapshot)


def load_successfactors_snapshots(raw_root: Path) -> list[SuccessFactorsSnapshot]:
    return _load_required(raw_root, "successfactors", read_successfactors_snapshot)
