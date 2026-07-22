import hashlib
import json
from pathlib import Path

import pytest

from src.transformation.snapshots import (
    SnapshotReadError,
    load_greenhouse_snapshots,
    read_greenhouse_snapshot,
)


def write_snapshot(
    raw_root: Path,
    fixture_path: Path,
    *,
    source_name: str = "Example Tech",
    source_token: str = "example",
    collected_at: str = "2026-07-22T12:00:00+00:00",
) -> Path:
    source_directory = raw_root / "greenhouse" / source_token
    source_directory.mkdir(parents=True)
    raw_bytes = fixture_path.read_bytes()
    raw_path = source_directory / "snapshot.json"
    raw_path.write_bytes(raw_bytes)
    payload = json.loads(raw_bytes)
    metadata_path = source_directory / "snapshot.metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "source": "greenhouse",
                "source_name": source_name,
                "source_token": source_token,
                "collected_at": collected_at,
                "content_sha256": hashlib.sha256(raw_bytes).hexdigest(),
                "source_job_count": len(payload["jobs"]),
                "raw_file": raw_path.name,
            }
        ),
        encoding="utf-8",
    )
    return metadata_path


def test_read_greenhouse_snapshot_verifies_hash_and_count(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "greenhouse_jobs_m2.json"
    metadata_path = write_snapshot(tmp_path, fixture)

    snapshot = read_greenhouse_snapshot(metadata_path)

    assert snapshot.metadata["source_name"] == "Example Tech"
    assert len(snapshot.jobs) == 3
    assert snapshot.raw_path.name == "snapshot.json"


def test_read_greenhouse_snapshot_rejects_modified_raw_file(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "greenhouse_jobs_m2.json"
    metadata_path = write_snapshot(tmp_path, fixture)
    raw_path = metadata_path.parent / "snapshot.json"
    raw_path.write_text('{"jobs": []}', encoding="utf-8")

    with pytest.raises(SnapshotReadError, match="SHA-256 mismatch"):
        read_greenhouse_snapshot(metadata_path)


def test_load_greenhouse_snapshots_requires_saved_data(tmp_path: Path) -> None:
    with pytest.raises(SnapshotReadError, match="No Greenhouse metadata"):
        load_greenhouse_snapshots(tmp_path)
