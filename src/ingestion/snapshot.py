"""Persist immutable raw source snapshots and collection metadata."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.ingestion.greenhouse import GreenhouseResponse
from src.ingestion.lever import LeverResponse
from src.ingestion.successfactors import SuccessFactorsResponse
from src.ingestion.workday import WorkdayResponse
from src.ingestion.oracle_hcm import OracleHCMResponse
from src.ingestion.wp_job_manager import WPJobManagerResponse


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
        return self._write_snapshot(
            provider="greenhouse",
            source_name=source_name,
            source_token=response.board_token,
            endpoint=response.endpoint,
            status_code=response.status_code,
            content_type=response.content_type,
            raw_bytes=response.raw_bytes,
            job_count=response.job_count,
            collected_at=collected_at,
        )

    def write_lever_snapshot(
        self,
        source_name: str,
        response: LeverResponse,
        collected_at: datetime | None = None,
    ) -> SnapshotWriteResult:
        return self._write_snapshot(
            provider="lever",
            source_name=source_name,
            source_token=response.site_token,
            endpoint=response.endpoint,
            status_code=response.status_code,
            content_type=response.content_type,
            raw_bytes=response.raw_bytes,
            job_count=response.job_count,
            collected_at=collected_at,
        )

    def write_successfactors_snapshot(
        self,
        source_name: str,
        response: SuccessFactorsResponse,
        collected_at: datetime | None = None,
    ) -> SnapshotWriteResult:
        return self._write_snapshot(
            provider="successfactors",
            source_name=source_name,
            source_token=response.source_token,
            endpoint=response.endpoint,
            status_code=response.status_code,
            content_type=response.content_type,
            raw_bytes=response.raw_bytes,
            job_count=response.job_count,
            collected_at=collected_at,
            extra_metadata={
                "listing_page_count": response.listing_page_count,
                "detail_page_count": response.detail_page_count,
            },
        )

    def write_workday_snapshot(
        self,
        source_name: str,
        response: WorkdayResponse,
        collected_at: datetime | None = None,
    ) -> SnapshotWriteResult:
        return self._write_snapshot(
            provider="workday",
            source_name=source_name,
            source_token=response.source_token,
            endpoint=response.endpoint,
            status_code=response.status_code,
            content_type=response.content_type,
            raw_bytes=response.raw_bytes,
            job_count=response.job_count,
            collected_at=collected_at,
            extra_metadata={
                "listing_page_count": response.listing_page_count,
                "detail_page_count": response.detail_page_count,
            },
        )

    def write_oracle_hcm_snapshot(
        self,
        source_name: str,
        response: OracleHCMResponse,
        collected_at: datetime | None = None,
    ) -> SnapshotWriteResult:
        return self._write_snapshot(
            provider="oracle_hcm",
            source_name=source_name,
            source_token=response.source_token,
            endpoint=response.endpoint,
            status_code=response.status_code,
            content_type=response.content_type,
            raw_bytes=response.raw_bytes,
            job_count=response.job_count,
            collected_at=collected_at,
            extra_metadata={
                "listing_page_count": response.listing_page_count,
                "detail_page_count": response.detail_page_count,
            },
        )

    def write_wp_job_manager_snapshot(
        self,
        source_name: str,
        response: WPJobManagerResponse,
        collected_at: datetime | None = None,
    ) -> SnapshotWriteResult:
        return self._write_snapshot(
            provider="wp_job_manager",
            source_name=source_name,
            source_token=response.source_token,
            endpoint=response.endpoint,
            status_code=response.status_code,
            content_type=response.content_type,
            raw_bytes=response.raw_bytes,
            job_count=response.job_count,
            collected_at=collected_at,
            extra_metadata={
                "listing_page_count": response.listing_page_count,
                "detail_page_count": response.detail_page_count,
            },
        )

    def _write_snapshot(
        self,
        *,
        provider: str,
        source_name: str,
        source_token: str,
        endpoint: str,
        status_code: int,
        content_type: str,
        raw_bytes: bytes,
        job_count: int,
        collected_at: datetime | None,
        extra_metadata: dict[str, object] | None = None,
    ) -> SnapshotWriteResult:
        collection_time = collected_at or utc_now()
        digest = hashlib.sha256(raw_bytes).hexdigest()
        source_directory = self.root / provider / source_token
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

        self._atomic_write_bytes(raw_path, raw_bytes)
        metadata = {
            "source": provider,
            "source_name": source_name,
            "source_token": source_token,
            "endpoint": endpoint,
            "collected_at": collection_time.astimezone(timezone.utc).isoformat(),
            "http_status": status_code,
            "content_type": content_type,
            "content_sha256": digest,
            "byte_count": len(raw_bytes),
            "source_job_count": job_count,
            "raw_file": raw_path.name,
        }
        if extra_metadata:
            metadata.update(extra_metadata)
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
