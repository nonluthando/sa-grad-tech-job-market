"""Tests for Workable API client."""

import json
import pytest
import requests
from src.ingestion.workable import WorkableClient


class FakeResponse:
    def __init__(self, raw_bytes: bytes, status_code: int = 200):
        self.content = raw_bytes
        self.status_code = status_code
        self.url = "https://apply.workable.com/acme/jobs.json?page=1"
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


class TestWorkableClient:
    def test_init_validates_timeout(self):
        with pytest.raises(ValueError, match="timeout_seconds must be greater than zero"):
            WorkableClient(timeout_seconds=0)

    def test_init_validates_page_limit(self):
        with pytest.raises(ValueError, match="page_limit must be greater than zero"):
            WorkableClient(page_limit=0)

    def test_fetch_single_page(self):
        response_data = {
            "jobs": [
                {
                    "id": "1",
                    "title": "Software Engineer",
                    "description": "Build things",
                    "location": "Cape Town, South Africa",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-02T00:00:00Z",
                }
            ]
        }
        session = FakeSession(
            FakeResponse(json.dumps(response_data).encode("utf-8")),
            FakeResponse(json.dumps({"jobs": []}).encode("utf-8")),
        )
        client = WorkableClient(session=session, timeout_seconds=5, page_limit=10)

        result = client.fetch("acme")
        assert len(result) == 1
        assert result[0].company_slug == "acme"
        assert result[0].job_count == 1

    def test_fetch_multiple_pages(self):
        session = FakeSession(
            FakeResponse(json.dumps({"jobs": [{"id": "1", "title": "Role 1"}]}).encode()),
            FakeResponse(json.dumps({"jobs": [{"id": "2", "title": "Role 2"}]}).encode()),
            FakeResponse(json.dumps({"jobs": []}).encode()),
        )
        client = WorkableClient(session=session, timeout_seconds=5, page_limit=10)

        result = client.fetch("acme")
        assert len(result) == 2
        assert sum(r.job_count for r in result) == 2

    def test_fetch_validates_empty_slug(self):
        client = WorkableClient(timeout_seconds=5, page_limit=10)
        with pytest.raises(ValueError, match="company_slug cannot be empty"):
            client.fetch("")

    def test_fetch_handles_invalid_json(self):
        session = FakeSession(
            FakeResponse(b"not json")
        )
        client = WorkableClient(session=session, timeout_seconds=5, page_limit=10)

        with pytest.raises(ValueError, match="Workable returned invalid JSON"):
            client.fetch("acme")

    def test_fetch_validates_response_structure(self):
        session = FakeSession(
            FakeResponse(json.dumps({"jobs": "not a list"}).encode())
        )
        client = WorkableClient(session=session, timeout_seconds=5, page_limit=10)

        with pytest.raises(ValueError, match="jobs array.*must be a list"):
            client.fetch("acme")
