import json
from pathlib import Path

import pytest
import requests

from src.ingestion.greenhouse import GreenhouseClient


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "greenhouse_jobs.json"


class FakeResponse:
    def __init__(self, raw_bytes: bytes, status_code: int = 200):
        self.content = raw_bytes
        self.status_code = status_code
        self.url = (
            "https://boards-api.greenhouse.io/v1/boards/"
            "example/jobs?content=true"
        )
        self.headers = {"Content-Type": "application/json; charset=utf-8"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return json.loads(self.content.decode("utf-8"))


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_fetch_board_preserves_exact_response_bytes():
    raw_bytes = FIXTURE_PATH.read_bytes()
    session = FakeSession(FakeResponse(raw_bytes))
    client = GreenhouseClient(session=session, timeout_seconds=12)

    result = client.fetch_board("example")

    assert result.raw_bytes == raw_bytes
    assert result.job_count == 1
    assert session.calls[0][0].endswith("/example/jobs")
    assert session.calls[0][1]["params"] == {"content": "true"}
    assert session.calls[0][1]["timeout"] == 12


def test_fetch_board_rejects_payload_without_jobs_list():
    response = FakeResponse(b'{"meta": {"total": 0}}')
    client = GreenhouseClient(session=FakeSession(response))

    with pytest.raises(ValueError, match="jobs list"):
        client.fetch_board("example")
