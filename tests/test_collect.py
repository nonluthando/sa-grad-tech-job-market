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


def test_collect_lever_source_returns_written_result(tmp_path):
    from src.ingestion.collect import collect_lever_source
    from src.ingestion.config import LeverSource
    from src.ingestion.lever import LeverResponse

    class StubLeverClient:
        def fetch_site(self, site_token):
            return LeverResponse(
                site_token=site_token,
                endpoint=f"https://example.test/{site_token}",
                status_code=200,
                content_type="application/json",
                raw_bytes=b"[]",
                payload=[],
            )

    source = LeverSource(name="Lever Example", token="lever-example")
    result = collect_lever_source(
        source=source,
        client=StubLeverClient(),
        store=RawSnapshotStore(tmp_path),
        collected_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )

    assert result.status == "written"
    assert result.source_provider == "lever"
    assert result.source_token == "lever-example"
    assert result.job_count == 0
    assert result.error is None


def test_collect_successfactors_source_returns_written_result(tmp_path):
    from src.ingestion.collect import collect_successfactors_source
    from src.ingestion.config import SuccessFactorsSource
    from src.ingestion.successfactors import SuccessFactorsResponse

    class StubSuccessFactorsClient:
        def fetch_source(self, source):
            return SuccessFactorsResponse(
                source_token=source.token,
                endpoint=source.listing_url,
                status_code=200,
                content_type="application/vnd.test+json",
                raw_bytes=b'{"provider":"successfactors"}',
                job_count=2,
                listing_page_count=1,
                detail_page_count=2,
            )

    source = SuccessFactorsSource(
        name="Example Bank",
        token="example-bank",
        listing_url="https://jobs.example.test/go/All/123/",
        request_delay_seconds=0,
    )
    result = collect_successfactors_source(
        source=source,
        client=StubSuccessFactorsClient(),
        store=RawSnapshotStore(tmp_path),
        collected_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )

    assert result.status == "written"
    assert result.source_provider == "successfactors"
    assert result.job_count == 2
    assert result.error is None
