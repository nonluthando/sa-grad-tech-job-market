from datetime import datetime, timezone

from src.ingestion.collect import (
    collect_oracle_hcm_source,
    collect_workday_source,
    collect_wp_job_manager_source,
)
from src.ingestion.config import OracleHCMSource, WorkdaySource, WPJobManagerSource
from src.ingestion.oracle_hcm import OracleHCMResponse
from src.ingestion.snapshot import RawSnapshotStore
from src.ingestion.workday import WorkdayResponse
from src.ingestion.wp_job_manager import WPJobManagerResponse

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


class StubClient:
    def __init__(self, response):
        self.response = response

    def fetch_source(self, source):
        return self.response


def _response(response_type, token, provider):
    return response_type(
        source_token=token,
        endpoint="https://example.test/jobs",
        status_code=200,
        content_type=f"application/vnd.test.{provider}+json",
        raw_bytes=(f'{{"provider":"{provider}"}}\n').encode(),
        job_count=2,
        listing_page_count=1,
        detail_page_count=2,
    )


def test_collect_workday_source_writes_snapshot(tmp_path):
    source = WorkdaySource("Digi", "digi", "https://wd.test", "tenant", "site")
    result = collect_workday_source(source, StubClient(_response(WorkdayResponse, "digi", "workday")), RawSnapshotStore(tmp_path), NOW)
    assert result.status == "written"
    assert result.source_provider == "workday"


def test_collect_oracle_source_writes_snapshot(tmp_path):
    source = OracleHCMSource("ACI", "aci", "https://oracle.test", "CX")
    result = collect_oracle_hcm_source(source, StubClient(_response(OracleHCMResponse, "aci", "oracle_hcm")), RawSnapshotStore(tmp_path), NOW)
    assert result.status == "written"
    assert result.source_provider == "oracle_hcm"


def test_collect_wp_source_writes_snapshot(tmp_path):
    source = WPJobManagerSource("BET", "bet", "https://bet.test/jobs", "https://bet.test/ajax")
    result = collect_wp_job_manager_source(source, StubClient(_response(WPJobManagerResponse, "bet", "wp_job_manager")), RawSnapshotStore(tmp_path), NOW)
    assert result.status == "written"
    assert result.source_provider == "wp_job_manager"
