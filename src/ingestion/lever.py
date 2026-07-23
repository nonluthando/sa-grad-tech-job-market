"""Client for the public Lever Postings API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from src.ingestion.greenhouse import DEFAULT_TIMEOUT_SECONDS, USER_AGENT


DEFAULT_PAGE_LIMIT = 500


@dataclass(frozen=True)
class LeverResponse:
    """One successfully retrieved Lever postings response."""

    site_token: str
    endpoint: str
    status_code: int
    content_type: str
    raw_bytes: bytes
    payload: list[dict[str, Any]]

    @property
    def job_count(self) -> int:
        return len(self.payload)


class LeverClient:
    """Fetch public Lever postings without authentication.

    The MVP deliberately requests one large page so the exact HTTP response can
    be retained as the immutable raw snapshot. A full page is rejected rather
    than silently assuming the source has no additional postings.
    """

    base_url = "https://api.lever.co/v0/postings"

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

    def fetch_site(self, site_token: str) -> LeverResponse:
        token = site_token.strip()
        if not token:
            raise ValueError("site_token cannot be empty.")

        endpoint = f"{self.base_url}/{token}"
        response = self.session.get(
            endpoint,
            params={"mode": "json", "limit": self.page_limit},
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
                f"Lever returned invalid JSON for site {token}."
            ) from error

        if not isinstance(payload, list) or any(
            not isinstance(job, dict) for job in payload
        ):
            raise ValueError(
                f"Lever response for site {token} must be a list of job objects."
            )

        if len(payload) >= self.page_limit:
            raise ValueError(
                f"Lever site {token} returned the configured page limit "
                f"({self.page_limit}); pagination is required before this "
                "snapshot can be considered complete."
            )

        # Some APIs enforce a server-side cap smaller than the requested limit.
        # Probe immediately after the returned page so a capped response cannot
        # be accepted silently as a complete snapshot.
        if payload:
            continuation = self.session.get(
                endpoint,
                params={
                    "mode": "json",
                    "skip": len(payload),
                    "limit": 1,
                },
                headers={
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                },
                timeout=self.timeout_seconds,
            )
            continuation.raise_for_status()
            try:
                continuation_payload = continuation.json()
            except requests.JSONDecodeError as error:
                raise ValueError(
                    f"Lever returned invalid pagination JSON for site {token}."
                ) from error
            if not isinstance(continuation_payload, list):
                raise ValueError(
                    f"Lever pagination response for site {token} must be a list."
                )
            if continuation_payload:
                raise ValueError(
                    f"Lever site {token} has additional postings beyond the "
                    "saved response; paginated raw storage is required."
                )

        return LeverResponse(
            site_token=token,
            endpoint=response.url,
            status_code=response.status_code,
            content_type=content_type,
            raw_bytes=response.content,
            payload=payload,
        )
