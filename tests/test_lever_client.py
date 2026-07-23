import json
from pathlib import Path

import pytest
import requests

from src.ingestion.lever import LeverClient


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "lever_jobs.json"


class FakeResponse:
    def __init__(self, raw_bytes: bytes, status_code: int = 200):
        self.content = raw_bytes
        self.status_code = status_code
        self.url = "https://api.lever.co/v0/postings/example?mode=json&limit=500"
        self.headers = {"Content-Type": "application/json; charset=utf-8"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return json.loads(self.content.decode("utf-8"))


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("No fake response remains for this request.")
        return self.responses.pop(0)


def test_fetch_site_preserves_exact_response_bytes_and_checks_completeness():
    raw_bytes = FIXTURE_PATH.read_bytes()
    session = FakeSession(
        FakeResponse(raw_bytes),
        FakeResponse(b"[]"),
    )
    client = LeverClient(session=session, timeout_seconds=12, page_limit=500)

    result = client.fetch_site("ExampleSite")

    assert result.raw_bytes == raw_bytes
    assert result.job_count == 3
    assert session.calls[0][0].endswith("/ExampleSite")
    assert session.calls[0][1]["params"] == {"mode": "json", "limit": 500}
    assert session.calls[0][1]["timeout"] == 12
    assert session.calls[1][1]["params"] == {
        "mode": "json",
        "skip": 3,
        "limit": 1,
    }


def test_fetch_site_rejects_non_list_payload():
    client = LeverClient(
        session=FakeSession(FakeResponse(b'{"jobs": []}')),
    )

    with pytest.raises(ValueError, match="list of job objects"):
        client.fetch_site("example")


def test_fetch_site_rejects_full_page_to_avoid_silent_truncation():
    raw_bytes = json.dumps([{"id": "1"}, {"id": "2"}]).encode("utf-8")
    client = LeverClient(
        session=FakeSession(FakeResponse(raw_bytes)),
        page_limit=2,
    )

    with pytest.raises(ValueError, match="pagination is required"):
        client.fetch_site("example")


def test_fetch_site_rejects_hidden_server_side_page_cap():
    first_page = json.dumps([{"id": "1"}, {"id": "2"}]).encode("utf-8")
    continuation = json.dumps([{"id": "3"}]).encode("utf-8")
    client = LeverClient(
        session=FakeSession(
            FakeResponse(first_page),
            FakeResponse(continuation),
        ),
        page_limit=500,
    )

    with pytest.raises(ValueError, match="additional postings"):
        client.fetch_site("example")
