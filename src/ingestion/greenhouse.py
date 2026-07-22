"""Client for the public Greenhouse Job Board API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


DEFAULT_TIMEOUT_SECONDS = 30
USER_AGENT = (
    "sa-grad-tech-job-market/0.1 "
    "(public portfolio research project; contact via repository)"
)


@dataclass(frozen=True)
class GreenhouseResponse:
    """One successfully retrieved Greenhouse board response."""

    board_token: str
    endpoint: str
    status_code: int
    content_type: str
    raw_bytes: bytes
    payload: dict[str, Any]

    @property
    def job_count(self) -> int:
        jobs = self.payload.get("jobs", [])
        return len(jobs) if isinstance(jobs, list) else 0


class GreenhouseClient:
    """Fetch public job-board payloads without authentication."""

    base_url = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def fetch_board(self, board_token: str) -> GreenhouseResponse:
        token = board_token.strip()
        if not token:
            raise ValueError("board_token cannot be empty.")

        endpoint = f"{self.base_url}/{token}/jobs"
        response = self.session.get(
            endpoint,
            params={"content": "true"},
            headers={
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        try:
            payload = response.json()
        except requests.JSONDecodeError as error:
            raise ValueError(
                f"Greenhouse returned invalid JSON for board {token}."
            ) from error

        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError(
                f"Greenhouse response for board {token} must contain a jobs list."
            )

        return GreenhouseResponse(
            board_token=token,
            endpoint=response.url,
            status_code=response.status_code,
            content_type=content_type,
            raw_bytes=response.content,
            payload=payload,
        )
