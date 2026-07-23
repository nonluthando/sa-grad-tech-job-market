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


def test_snapshot_store_writes_lever_raw_bytes_and_metadata(tmp_path):
    from src.ingestion.lever import LeverResponse

    fixture_path = Path(__file__).parent / "fixtures" / "lever_jobs.json"
    raw_bytes = fixture_path.read_bytes()
    response = LeverResponse(
        site_token="example",
        endpoint="https://api.lever.co/v0/postings/example?mode=json&limit=500",
        status_code=200,
        content_type="application/json",
        raw_bytes=raw_bytes,
        payload=json.loads(raw_bytes.decode("utf-8")),
    )
    store = RawSnapshotStore(tmp_path)

    result = store.write_lever_snapshot(
        source_name="Lever Example",
        response=response,
        collected_at=datetime(2026, 7, 23, 19, 0, tzinfo=timezone.utc),
    )

    assert result.was_written
    assert result.raw_path.parent == tmp_path / "lever" / "example"
    assert result.raw_path.read_bytes() == raw_bytes
    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["source"] == "lever"
    assert metadata["source_name"] == "Lever Example"
    assert metadata["source_job_count"] == 3


def test_store_writes_successfactors_snapshot_metadata(tmp_path):
    from src.ingestion.successfactors import SuccessFactorsResponse

    response = SuccessFactorsResponse(
        source_token="example-bank",
        endpoint="https://jobs.example.test/go/All/123/",
        status_code=200,
        content_type="application/vnd.test+json",
        raw_bytes=b'{"provider":"successfactors"}',
        job_count=2,
        listing_page_count=1,
        detail_page_count=2,
    )

    result = RawSnapshotStore(tmp_path).write_successfactors_snapshot(
        source_name="Example Bank",
        response=response,
        collected_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["source"] == "successfactors"
    assert metadata["listing_page_count"] == 1
    assert metadata["detail_page_count"] == 2
