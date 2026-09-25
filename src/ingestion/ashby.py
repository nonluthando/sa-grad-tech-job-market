"""Client for the public Ashby Job Board API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from src.ingestion.greenhouse import DEFAULT_TIMEOUT_SECONDS, USER_AGENT


@dataclass(frozen=True)
class AshbyResponse:
    """One successfully retrieved Ashby job-board response."""

    job_board_name: str
    endpoint: str
    status_code: int
    content_type: str
    raw_bytes: bytes
    payload: dict[str, Any]

    @property
    def job_count(self) -> int:
        jobs = self.payload.get("jobs", [])
        return len(jobs) if isinstance(jobs, list) else 0


class AshbyClient:
    """Fetch a public Ashby job board without authentication.

    Ashby's job-board API returns every currently listed posting, including
    its full description, in one response. There is no pagination and no
    separate per-job detail fetch, matching the Greenhouse/Lever pattern.
    """

    base_url = "https://api.ashbyhq.com/posting-api/job-board"

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def fetch_board(self, job_board_name: str) -> AshbyResponse:
        name = job_board_name.strip()
        if not name:
            raise ValueError("job_board_name cannot be empty.")

        endpoint = f"{self.base_url}/{name}"
        response = self.session.get(
            endpoint,
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
                f"Ashby returned invalid JSON for job board {name}."
            ) from error

        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError(
                f"Ashby response for job board {name} must contain a jobs list."
            )

        return AshbyResponse(
            job_board_name=name,
            endpoint=response.url,
            status_code=response.status_code,
            content_type=content_type,
            raw_bytes=response.content,
            payload=payload,
        )
