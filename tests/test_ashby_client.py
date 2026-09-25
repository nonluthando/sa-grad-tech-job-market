import json

import pytest
import requests

from src.ingestion.ashby import AshbyClient


class FakeResponse:
    def __init__(self, url, payload, status_code=200, content_type="application/json"):
        self.url = url
        self.status_code = status_code
        self.content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        pass

    def json(self):
        return json.loads(self.content)


class StubSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_ashby_client_fetches_job_board():
    payload = {
        "organizationName": "Andela",
        "jobs": [
            {"id": "1", "title": "Software Engineer"},
            {"id": "2", "title": "Data Analyst"},
        ],
    }
    session = StubSession(
        FakeResponse("https://api.ashbyhq.com/posting-api/job-board/andela", payload)
    )
    result = AshbyClient(session=session).fetch_board("andela")
    assert result.job_count == 2
    assert result.job_board_name == "andela"
    assert session.calls[0][0] == "https://api.ashbyhq.com/posting-api/job-board/andela"


def test_ashby_client_strips_job_board_name():
    payload = {"jobs": []}
    session = StubSession(
        FakeResponse("https://api.ashbyhq.com/posting-api/job-board/andela", payload)
    )
    result = AshbyClient(session=session).fetch_board("  andela  ")
    assert result.job_board_name == "andela"
    assert result.job_count == 0


def test_ashby_client_rejects_empty_job_board_name():
    with pytest.raises(ValueError, match="cannot be empty"):
        AshbyClient(session=StubSession(FakeResponse("x", {"jobs": []}))).fetch_board("   ")


def test_ashby_client_rejects_non_json_response():
    class BadJsonResponse(FakeResponse):
        def json(self):
            raise requests.JSONDecodeError("bad", "doc", 0)

    session = StubSession(BadJsonResponse("https://api.ashbyhq.com/x", b"not json"))
    with pytest.raises(ValueError, match="invalid JSON"):
        AshbyClient(session=session).fetch_board("andela")


def test_ashby_client_rejects_payload_missing_jobs_list():
    session = StubSession(
        FakeResponse("https://api.ashbyhq.com/posting-api/job-board/andela", {"organizationName": "Andela"})
    )
    with pytest.raises(ValueError, match="jobs list"):
        AshbyClient(session=session).fetch_board("andela")


def test_ashby_client_rejects_zero_timeout():
    with pytest.raises(ValueError, match="timeout_seconds"):
        AshbyClient(timeout_seconds=0)
