from datetime import datetime, timezone

from src.ingestion.ashby import AshbyResponse
from src.ingestion.collect import collect_ashby_source
from src.ingestion.config import AshbySource
from src.ingestion.snapshot import RawSnapshotStore

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


class StubClient:
    def __init__(self, response):
        self.response = response

    def fetch_board(self, job_board_name):
        return self.response


def test_collect_ashby_source_writes_snapshot(tmp_path):
    source = AshbySource(name="Andela", token="andela", employer_id="andela")
    response = AshbyResponse(
        job_board_name="andela",
        endpoint="https://api.ashbyhq.com/posting-api/job-board/andela",
        status_code=200,
        content_type="application/json",
        raw_bytes=b'{"jobs": [{"id": "1"}, {"id": "2"}]}',
        payload={"jobs": [{"id": "1"}, {"id": "2"}]},
    )
    result = collect_ashby_source(source, StubClient(response), RawSnapshotStore(tmp_path), NOW)
    assert result.status == "written"
    assert result.source_provider == "ashby"
    assert result.job_count == 2


def test_collect_ashby_source_reports_failure(tmp_path):
    source = AshbySource(name="Andela", token="andela", employer_id="andela")

    class FailingClient:
        def fetch_board(self, job_board_name):
            raise ValueError("boom")

    result = collect_ashby_source(source, FailingClient(), RawSnapshotStore(tmp_path), NOW)
    assert result.status == "failed"
    assert result.error == "boom"
