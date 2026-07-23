import json

import pytest
import requests

from src.ingestion.config import SuccessFactorsSource
from src.ingestion.successfactors import (
    SuccessFactorsClient,
    parse_listing_page,
)


LISTING_PAGE_1 = b"""
<html><body>
<div>Results 1 - 2 of 3 Page 1 of 2</div>
<table>
<tr><td><a href="/job/Johannesburg-Junior-Data-Analyst/1001/">Junior Data Analyst</a></td><td>Johannesburg, ZA</td><td>20 Jul 2026</td></tr>
<tr><td><a href="/job/Cape-Town-Senior-Developer/1002/">Senior Developer</a></td><td>Cape Town, ZA</td><td>21 Jul 2026</td></tr>
</table>
</body></html>
"""

LISTING_PAGE_2 = b"""
<html><body>
<div>Results 3 - 3 of 3 Page 2 of 2</div>
<table>
<tr><td><a href="/job/Sandton-QA-Engineer/1003/">QA Engineer</a></td><td>Sandton, GP, ZA</td><td>22 Jul 2026</td></tr>
</table>
</body></html>
"""

DETAIL = b"""
<html><body><div class="job">
<div class="jobTitle"><h1>Junior Data Analyst</h1></div>
<div class="jobGeoLocation">Location: Johannesburg, ZA</div>
<div>Date: 20 Jul 2026</div>
<div class="jobdescription"><h2>Job Purpose</h2><p>Use SQL and Python to analyse data.</p></div>
</div></body></html>
"""


class FakeResponse:
    def __init__(self, url, content, status_code=200):
        self.url = url
        self.content = content
        self.status_code = status_code
        self.headers = {"Content-Type": "text/html; charset=utf-8"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.headers = {}
        self.requested = []

    def get(self, url, timeout):
        self.requested.append((url, timeout))
        return self.responses[url]


def test_parse_listing_page_extracts_unique_jobs_and_total():
    parsed = parse_listing_page(
        LISTING_PAGE_1,
        "https://example.test/go/All/123/",
    )

    assert parsed.reported_total == 3
    assert [job["source_job_id"] for job in parsed.jobs] == ["1001", "1002"]
    assert parsed.jobs[0]["location_raw"] == "Johannesburg, ZA"
    assert parsed.jobs[0]["published_text"] == "20 Jul 2026"


def test_successfactors_client_fetches_all_pages_and_details():
    base = "https://example.test/go/All/123/"
    page_2 = "https://example.test/go/All/123/2/"
    detail_urls = [
        "https://example.test/job/Johannesburg-Junior-Data-Analyst/1001/",
        "https://example.test/job/Cape-Town-Senior-Developer/1002/",
        "https://example.test/job/Sandton-QA-Engineer/1003/",
    ]
    responses = {
        base: FakeResponse(base, LISTING_PAGE_1),
        page_2: FakeResponse(page_2, LISTING_PAGE_2),
        **{url: FakeResponse(url, DETAIL) for url in detail_urls},
    }
    session = FakeSession(responses)
    source = SuccessFactorsSource(
        name="Example Bank",
        token="example-bank",
        listing_url=base,
        page_size=2,
        max_pages=3,
        request_delay_seconds=0,
    )

    response = SuccessFactorsClient(
        timeout_seconds=12,
        session=session,
        sleep=lambda _: None,
    ).fetch_source(source)

    assert response.job_count == 3
    assert response.listing_page_count == 2
    assert response.detail_page_count == 3
    payload = json.loads(response.raw_bytes)
    assert payload["reported_job_count"] == 3
    assert len(payload["listing_pages"]) == 2
    assert len(payload["job_pages"]) == 3
    assert session.requested[0] == (base, 12)


def test_successfactors_client_rejects_incomplete_pagination():
    base = "https://example.test/go/All/123/"
    page_2 = "https://example.test/go/All/123/2/"
    responses = {
        base: FakeResponse(base, LISTING_PAGE_1),
        page_2: FakeResponse(page_2, LISTING_PAGE_1),
    }
    source = SuccessFactorsSource(
        name="Example Bank",
        token="example-bank",
        listing_url=base,
        page_size=2,
        max_pages=3,
        request_delay_seconds=0,
    )

    with pytest.raises(ValueError, match="no new jobs"):
        SuccessFactorsClient(
            session=FakeSession(responses),
            sleep=lambda _: None,
        ).fetch_source(source)
