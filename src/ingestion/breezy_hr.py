"""Client for the public Breezy HR API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from src.ingestion.greenhouse import DEFAULT_TIMEOUT_SECONDS, USER_AGENT


DEFAULT_PAGE_LIMIT = 50


@dataclass(frozen=True)
class BreezyHRResponse:
    """One successfully retrieved Breezy HR positions response."""

    company_slug: str
    endpoint: str
    status_code: int
    content_type: str
    raw_bytes: bytes
    payload: list[dict[str, Any]]

    @property
    def job_count(self) -> int:
        return len(self.payload)


class BreezyHRClient:
    """Fetch public Breezy HR positions without authentication.

    Breezy HR's public API supports offset-based pagination via the 'offset' parameter.
    The client fetches all pages for a company to ensure complete snapshot.
    """

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

    def fetch(self, company_slug: str) -> list[BreezyHRResponse]:
        """Fetch all pages of positions for a company slug."""
        slug = company_slug.strip()
        if not slug:
            raise ValueError("company_slug cannot be empty.")

        all_positions: list[dict[str, Any]] = []
        all_responses: list[BreezyHRResponse] = []
        offset = 0

        while True:
            base_url = f"https://{slug}.breezy.hr"
            endpoint = f"{base_url}/api/position/list"
            response = self.session.get(
                endpoint,
                params={"limit": self.page_limit, "offset": offset},
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
                    f"Breezy HR returned invalid JSON for company {slug} offset {offset}."
                ) from error

            if not isinstance(payload, dict):
                raise ValueError(
                    f"Breezy HR response for company {slug} must be a dict."
                )

            if not payload.get("success", False):
                raise ValueError(
                    f"Breezy HR API error for company {slug}: {payload.get('message', 'unknown error')}."
                )

            positions = payload.get("positions", [])
            if not isinstance(positions, list):
                raise ValueError(
                    f"Breezy HR positions array for company {slug} offset {offset} must be a list."
                )

            if not positions:
                break

            breezy_response = BreezyHRResponse(
                company_slug=slug,
                endpoint=response.url,
                status_code=response.status_code,
                content_type=content_type,
                raw_bytes=response.content,
                payload=positions,
            )
            all_responses.append(breezy_response)
            all_positions.extend(positions)
            offset += len(positions)

        if not all_responses:
            raise ValueError(
                f"Breezy HR company {slug} returned no pages."
            )

        return all_responses
