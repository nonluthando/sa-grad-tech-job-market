from datetime import datetime, timezone

from src.ingestion.collect import collect_smartrecruiters_source
from src.ingestion.config import SmartRecruitersSource
from src.ingestion.smartrecruiters import SmartRecruitersResponse
from src.ingestion.snapshot import RawSnapshotStore

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


class StubClient:
    def __init__(self, response):
        self.response = response

    def fetch_source(self, source):
        return self.response


def _response(token: str) -> SmartRecruitersResponse:
    return SmartRecruitersResponse(
        source_token=token,
        endpoint="https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings",
        status_code=200,
        content_type="application/vnd.sa-tech-job-market.smartrecruiters+json",
        raw_bytes=b'{"provider":"smartrecruiters"}\n',
        job_count=2,
        listing_page_count=1,
        detail_page_count=2,
    )


def test_collect_smartrecruiters_source_writes_snapshot(tmp_path):
    source = SmartRecruitersSource(
        name="Standard Bank",
        token="standardbankgroup",
        host="https://api.smartrecruiters.test",
        site="StandardBankGroup",
    )
    result = collect_smartrecruiters_source(
        source,
        StubClient(_response("standardbankgroup")),
        RawSnapshotStore(tmp_path),
        NOW,
    )
    assert result.status == "written"
    assert result.source_provider == "smartrecruiters"
    assert result.job_count == 2


def test_collect_smartrecruiters_source_reports_failure():
    source = SmartRecruitersSource(
        name="Standard Bank",
        token="standardbankgroup",
        host="https://api.smartrecruiters.test",
        site="StandardBankGroup",
    )

    class FailingClient:
        def fetch_source(self, source):
            raise ValueError("boom")

    result = collect_smartrecruiters_source(
        source, FailingClient(), RawSnapshotStore(_tmp_dir()), NOW
    )
    assert result.status == "failed"
    assert result.error == "boom"


def _tmp_dir():
    import tempfile
    from pathlib import Path

    return Path(tempfile.mkdtemp())
