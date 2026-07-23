import json

import requests

from src.ingestion.config import OracleHCMSource, WorkdaySource, WPJobManagerSource
from src.ingestion.oracle_hcm import OracleHCMClient
from src.ingestion.workday import WorkdayClient
from src.ingestion.wp_job_manager import WPJobManagerClient


class FakeResponse:
    def __init__(self, url, payload, content_type="application/json"):
        self.url = url
        self.content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.status_code = 200
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        pass


class QueueSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)


def test_workday_client_collects_listing_and_details():
    session = QueueSession([
        FakeResponse("https://wd.test/jobs", {"total": 2, "jobPostings": [
            {"title": "Junior Engineer", "externalPath": "/job/a"},
            {"title": "Data Analyst", "externalPath": "/job/b"},
        ]}),
        FakeResponse("https://wd.test/job/a", {"jobPostingInfo": {"jobReqId": "1"}}),
        FakeResponse("https://wd.test/job/b", {"jobPostingInfo": {"jobReqId": "2"}}),
    ])
    source = WorkdaySource("DigiOutsource", "digioutsource", "https://wd.test", "tenant", "site", request_delay_seconds=0)
    result = WorkdayClient(session=session, sleep=lambda _: None).fetch_source(source)
    payload = json.loads(result.raw_bytes)
    assert result.job_count == 2
    assert len(payload["job_pages"]) == 2
    assert session.calls[0][0] == "POST"


def test_oracle_hcm_client_collects_listing_and_details():
    session = QueueSession([
        FakeResponse("https://oracle.test/list", {"items": [{"Id": "10", "Title": "Developer"}], "totalResults": 1, "hasMore": False}),
        FakeResponse("https://oracle.test/detail", {"Id": "10", "Title": "Developer"}),
    ])
    source = OracleHCMSource("ACI Worldwide", "aci-worldwide", "https://oracle.test", "CX", request_delay_seconds=0)
    result = OracleHCMClient(session=session, sleep=lambda _: None).fetch_source(source)
    payload = json.loads(result.raw_bytes)
    assert result.job_count == 1
    assert payload["job_index"][0]["Id"] == "10"


def test_wp_job_manager_client_collects_listing_and_details():
    listing = {
        "success": True,
        "data": {
            "html": '<a href="https://bet.test/jobs/software-engineer">Software Engineer</a>',
            "max_num_pages": 1,
            "found_jobs": True,
        },
    }
    detail = b"<html><h1>Software Engineer</h1></html>"
    session = QueueSession([
        FakeResponse("https://bet.test/ajax", listing),
        FakeResponse("https://bet.test/jobs/software-engineer", detail, "text/html"),
    ])
    source = WPJobManagerSource("BET Software", "betsoftware", "https://bet.test/jobs", "https://bet.test/ajax", request_delay_seconds=0)
    result = WPJobManagerClient(session=session, sleep=lambda _: None).fetch_source(source)
    payload = json.loads(result.raw_bytes)
    assert result.job_count == 1
    assert payload["job_index"][0]["source_job_id"] == "software-engineer"
