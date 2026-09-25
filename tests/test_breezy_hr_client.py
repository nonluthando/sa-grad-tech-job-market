"""Tests for Breezy HR API client."""

import json
import pytest
import requests
from src.ingestion.breezy_hr import BreezyHRClient


class FakeResponse:
    def __init__(self, raw_bytes: bytes, status_code: int = 200):
        self.content = raw_bytes
        self.status_code = status_code
        self.url = "https://acme.breezy.hr/api/position/list?limit=50&offset=0"
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


class TestBreezyHRClient:
    def test_init_validates_timeout(self):
        with pytest.raises(ValueError, match="timeout_seconds must be greater than zero"):
            BreezyHRClient(timeout_seconds=0)

    def test_init_validates_page_limit(self):
        with pytest.raises(ValueError, match="page_limit must be greater than zero"):
            BreezyHRClient(page_limit=0)

    def test_fetch_single_page(self):
        response_data = {
            "success": True,
            "positions": [
                {
                    "id": "1",
                    "name": "Software Engineer",
                    "description": "Build things",
                    "location": "Johannesburg, South Africa",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-02T00:00:00Z",
                }
            ],
        }
        session = FakeSession(
            FakeResponse(json.dumps(response_data).encode("utf-8")),
            FakeResponse(json.dumps({"success": True, "positions": []}).encode("utf-8")),
        )
        client = BreezyHRClient(session=session, timeout_seconds=5, page_limit=50)

        result = client.fetch("acme")
        assert len(result) == 1
        assert result[0].company_slug == "acme"
        assert result[0].job_count == 1

    def test_fetch_multiple_pages(self):
        session = FakeSession(
            FakeResponse(json.dumps({"success": True, "positions": [{"id": "1", "name": "Role 1"}, {"id": "2", "name": "Role 2"}]}).encode()),
            FakeResponse(json.dumps({"success": True, "positions": [{"id": "3", "name": "Role 3"}]}).encode()),
            FakeResponse(json.dumps({"success": True, "positions": []}).encode()),
        )
        client = BreezyHRClient(session=session, timeout_seconds=5, page_limit=50)

        result = client.fetch("acme")
        assert len(result) == 2
        assert sum(r.job_count for r in result) == 3

    def test_fetch_validates_empty_slug(self):
        client = BreezyHRClient(timeout_seconds=5, page_limit=50)
        with pytest.raises(ValueError, match="company_slug cannot be empty"):
            client.fetch("")

    def test_fetch_handles_invalid_json(self):
        session = FakeSession(
            FakeResponse(b"not json")
        )
        client = BreezyHRClient(session=session, timeout_seconds=5, page_limit=50)

        with pytest.raises(ValueError, match="Breezy HR returned invalid JSON"):
            client.fetch("acme")

    def test_fetch_validates_api_error(self):
        session = FakeSession(
            FakeResponse(json.dumps({"success": False, "message": "API error"}).encode())
        )
        client = BreezyHRClient(session=session, timeout_seconds=5, page_limit=50)

        with pytest.raises(ValueError, match="Breezy HR API error"):
            client.fetch("acme")

    def test_fetch_validates_response_structure(self):
        session = FakeSession(
            FakeResponse(json.dumps({"success": True, "positions": "not a list"}).encode())
        )
        client = BreezyHRClient(session=session, timeout_seconds=5, page_limit=50)

        with pytest.raises(ValueError, match="positions array.*must be a list"):
            client.fetch("acme")
