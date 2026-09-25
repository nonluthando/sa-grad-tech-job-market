"""Client for the public Workable Jobs API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from src.ingestion.greenhouse import DEFAULT_TIMEOUT_SECONDS, USER_AGENT


DEFAULT_PAGE_LIMIT = 100


@dataclass(frozen=True)
class WorkableResponse:
    """One successfully retrieved Workable jobs response."""

    company_slug: str
    endpoint: str
    status_code: int
    content_type: str
    raw_bytes: bytes
    payload: list[dict[str, Any]]

    @property
    def job_count(self) -> int:
        return len(self.payload)


class WorkableClient:
    """Fetch public Workable jobs without authentication.

    Workable's public JSON endpoint supports pagination via the 'page' parameter.
    The client fetches all pages for a company to ensure complete snapshot.
    """

    base_url = "https://apply.workable.com"

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        page_limit: int = DEFAULT_PAGE_LIMIT,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")
        if page_limit <= 0:
            raise ValueError("page_limit must be greater than zero.")
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self.page_limit = page_limit

    def fetch(self, company_slug: str) -> list[WorkableResponse]:
        """Fetch all pages of jobs for a company slug."""
        slug = company_slug.strip()
        if not slug:
            raise ValueError("company_slug cannot be empty.")

        all_jobs: list[dict[str, Any]] = []
        all_responses: list[WorkableResponse] = []
        page = 1

        while True:
            endpoint = f"{self.base_url}/{slug}/jobs.json"
            response = self.session.get(
                endpoint,
                params={"page": page},
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
            except (requests.JSONDecodeError, json.JSONDecodeError, ValueError) as error:
                raise ValueError(
                    f"Workable returned invalid JSON for company {slug} page {page}."
                ) from error

            if not isinstance(payload, dict):
                raise ValueError(
                    f"Workable response for company {slug} must be a dict."
                )

            jobs = payload.get("jobs", [])
            if not isinstance(jobs, list):
                raise ValueError(
                    f"Workable jobs array for company {slug} page {page} must be a list."
                )

            if not jobs:
                break

            workable_response = WorkableResponse(
                company_slug=slug,
                endpoint=response.url,
                status_code=response.status_code,
                content_type=content_type,
                raw_bytes=response.content,
                payload=jobs,
            )
            all_responses.append(workable_response)
            all_jobs.extend(jobs)
            page += 1

        if not all_responses:
            raise ValueError(
                f"Workable company {slug} returned no pages."
            )

        return all_responses
