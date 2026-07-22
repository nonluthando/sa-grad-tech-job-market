import json
from datetime import datetime, timezone
from pathlib import Path

from src.ingestion.greenhouse import GreenhouseResponse
from src.ingestion.snapshot import RawSnapshotStore


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "greenhouse_jobs.json"


def build_response() -> GreenhouseResponse:
    raw_bytes = FIXTURE_PATH.read_bytes()
    return GreenhouseResponse(
        board_token="example",
        endpoint=(
            "https://boards-api.greenhouse.io/v1/boards/"
            "example/jobs?content=true"
        ),
        status_code=200,
        content_type="application/json",
        raw_bytes=raw_bytes,
        payload=json.loads(raw_bytes.decode("utf-8")),
    )


def test_snapshot_store_writes_raw_bytes_and_metadata(tmp_path):
    store = RawSnapshotStore(tmp_path)
    collected_at = datetime(2026, 7, 22, 19, 0, tzinfo=timezone.utc)

    result = store.write_greenhouse_snapshot(
        source_name="Example Company",
        response=build_response(),
        collected_at=collected_at,
    )

    assert result.was_written
    assert result.raw_path.read_bytes() == FIXTURE_PATH.read_bytes()
    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["source_name"] == "Example Company"
    assert metadata["source_job_count"] == 1
    assert metadata["raw_file"] == result.raw_path.name


def test_snapshot_store_skips_identical_payload(tmp_path):
    store = RawSnapshotStore(tmp_path)
    response = build_response()

    first = store.write_greenhouse_snapshot("Example Company", response)
    second = store.write_greenhouse_snapshot("Example Company", response)

    assert first.status == "written"
    assert second.status == "duplicate"
    assert second.raw_path == first.raw_path
    assert len(list((tmp_path / "greenhouse" / "example").glob("*.json"))) == 2
