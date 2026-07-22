from datetime import datetime, timezone

from src.ingestion.collect import collect_source
from src.ingestion.config import GreenhouseSource
from src.ingestion.greenhouse import GreenhouseResponse
from src.ingestion.snapshot import RawSnapshotStore


class StubClient:
    def fetch_board(self, board_token):
        return GreenhouseResponse(
            board_token=board_token,
            endpoint=f"https://example.test/{board_token}",
            status_code=200,
            content_type="application/json",
            raw_bytes=b'{"jobs": []}',
            payload={"jobs": []},
        )


def test_collect_source_returns_written_result(tmp_path):
    source = GreenhouseSource(name="Example", token="example")
    result = collect_source(
        source=source,
        client=StubClient(),
        store=RawSnapshotStore(tmp_path),
        collected_at=datetime(2026, 7, 22, tzinfo=timezone.utc),
    )

    assert result.status == "written"
    assert result.source_token == "example"
    assert result.job_count == 0
    assert result.error is None
