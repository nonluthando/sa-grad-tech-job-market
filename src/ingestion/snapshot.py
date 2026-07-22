"""Persist immutable raw source snapshots and collection metadata."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.ingestion.greenhouse import GreenhouseResponse


@dataclass(frozen=True)
class SnapshotWriteResult:
    """Outcome of attempting to persist one source response."""

    status: str
    raw_path: Path
    metadata_path: Path
    content_sha256: str

    @property
    def was_written(self) -> bool:
        return self.status == "written"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def filename_timestamp(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc)
    return normalized.strftime("%Y%m%dT%H%M%S%fZ")


class RawSnapshotStore:
    """Write exact response bytes once and skip duplicate content."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def write_greenhouse_snapshot(
        self,
        source_name: str,
        response: GreenhouseResponse,
        collected_at: datetime | None = None,
    ) -> SnapshotWriteResult:
        collection_time = collected_at or utc_now()
        digest = hashlib.sha256(response.raw_bytes).hexdigest()
        source_directory = self.root / "greenhouse" / response.board_token
        source_directory.mkdir(parents=True, exist_ok=True)

        existing_metadata = self._find_existing_digest(source_directory, digest)
        if existing_metadata is not None:
            existing_payload = json.loads(existing_metadata.read_text(encoding="utf-8"))
            raw_path = source_directory / existing_payload["raw_file"]
            return SnapshotWriteResult(
                status="duplicate",
                raw_path=raw_path,
                metadata_path=existing_metadata,
                content_sha256=digest,
            )

        timestamp = filename_timestamp(collection_time)
        raw_path = source_directory / f"{timestamp}.json"
        metadata_path = source_directory / f"{timestamp}.metadata.json"

        self._atomic_write_bytes(raw_path, response.raw_bytes)
        metadata = {
            "source": "greenhouse",
            "source_name": source_name,
            "source_token": response.board_token,
            "endpoint": response.endpoint,
            "collected_at": collection_time.astimezone(timezone.utc).isoformat(),
            "http_status": response.status_code,
            "content_type": response.content_type,
            "content_sha256": digest,
            "byte_count": len(response.raw_bytes),
            "source_job_count": response.job_count,
            "raw_file": raw_path.name,
        }
        self._atomic_write_text(
            metadata_path,
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        )

        return SnapshotWriteResult(
            status="written",
            raw_path=raw_path,
            metadata_path=metadata_path,
            content_sha256=digest,
        )

    @staticmethod
    def _find_existing_digest(source_directory: Path, digest: str) -> Path | None:
        for metadata_path in sorted(source_directory.glob("*.metadata.json")):
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if metadata.get("content_sha256") == digest:
                return metadata_path
        return None

    @staticmethod
    def _atomic_write_bytes(path: Path, content: bytes) -> None:
        with NamedTemporaryFile(dir=path.parent, delete=False) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
        temporary_path.replace(path)

    @staticmethod
    def _atomic_write_text(path: Path, content: str) -> None:
        RawSnapshotStore._atomic_write_bytes(path, content.encode("utf-8"))
