"""Collect complete public Workday Candidate Experience snapshots."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import urljoin

import requests

from src.ingestion.config import WorkdaySource


USER_AGENT = (
    "sa-tech-job-market/0.4 "
    "(public portfolio research project; contact via repository)"
)


@dataclass(frozen=True)
class WorkdayResponse:
    """One complete Workday listing-and-detail bundle."""

    source_token: str
    endpoint: str
    status_code: int
    content_type: str
    raw_bytes: bytes
    job_count: int
    listing_page_count: int
    detail_page_count: int


def _page_record(
    *,
    requested_url: str,
    final_url: str,
    status_code: int,
    content_type: str,
    raw_bytes: bytes,
    request_body: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "requested_url": requested_url,
        "final_url": final_url,
        "status_code": status_code,
        "content_type": content_type,
        "content_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "body_base64": base64.b64encode(raw_bytes).decode("ascii"),
    }
    if request_body is not None:
        record["request_body"] = dict(request_body)
    return record


def _json_object(raw_bytes: bytes, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_bytes)
    except json.JSONDecodeError as error:
        raise ValueError(f"Workday {label} response was not valid JSON.") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Workday {label} response must be an object.")
    return payload


def _external_path(posting: Mapping[str, Any]) -> str:
    return str(
        posting.get("externalPath")
        or posting.get("external_path")
        or posting.get("url")
        or ""
    ).strip()


class WorkdayClient:
    """Fetch every public CXS listing page and job-detail document."""

    def __init__(
        self,
        timeout_seconds: int = 30,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            }
        )
        self.sleep = sleep

    @staticmethod
    def _cxs_base(source: WorkdaySource) -> str:
        return (
            f"{source.host.rstrip('/')}/wday/cxs/"
            f"{source.tenant}/{source.site}"
        )

    def _post(self, url: str, body: Mapping[str, Any]) -> requests.Response:
        response = self.session.post(
            url,
            json=dict(body),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response

    def _get(self, url: str) -> requests.Response:
        response = self.session.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response

    def fetch_source(self, source: WorkdaySource) -> WorkdayResponse:
        """Fetch a complete CXS source and reject truncated pagination."""

        cxs_base = self._cxs_base(source)
        listing_url = f"{cxs_base}/jobs"
        listing_pages: list[dict[str, Any]] = []
        indexed_jobs: dict[str, dict[str, Any]] = {}
        reported_total: int | None = None

        for page_number in range(source.max_pages):
            offset = page_number * source.page_size
            request_body = {
                "appliedFacets": {},
                "limit": source.page_size,
                "offset": offset,
                "searchText": "",
            }
            response = self._post(listing_url, request_body)
            raw_bytes = response.content
            payload = _json_object(raw_bytes, "listing")

            total = payload.get("total")
            if not isinstance(total, int) or isinstance(total, bool) or total < 0:
                raise ValueError("Workday listing response has an invalid total.")
            if reported_total is None:
                reported_total = total
            elif total != reported_total:
                raise ValueError("Workday reported job count changed during pagination.")

            postings = payload.get("jobPostings")
            if not isinstance(postings, list):
                raise ValueError("Workday listing response has no jobPostings list.")

            listing_pages.append(
                _page_record(
                    requested_url=listing_url,
                    final_url=response.url,
                    status_code=response.status_code,
                    content_type=response.headers.get("Content-Type", ""),
                    raw_bytes=raw_bytes,
                    request_body=request_body,
                )
            )

            before = len(indexed_jobs)
            for posting in postings:
                if not isinstance(posting, dict):
                    raise ValueError("Workday jobPostings contains a non-object.")
                external_path = _external_path(posting)
                if not external_path:
                    raise ValueError("Workday posting is missing externalPath.")
                indexed_jobs.setdefault(external_path, dict(posting))

            if reported_total == 0 or len(indexed_jobs) >= reported_total:
                break
            if len(indexed_jobs) == before:
                raise ValueError(
                    "Workday pagination returned no new jobs before completion."
                )
        else:
            raise ValueError(f"Workday source exceeded max_pages={source.max_pages}.")

        if reported_total is None:
            raise ValueError("Workday listing did not return a reported total.")
        if len(indexed_jobs) != reported_total:
            raise ValueError(
                "Workday completeness check failed: "
                f"reported {reported_total}, discovered {len(indexed_jobs)}."
            )

        job_pages: list[dict[str, Any]] = []
        job_index: list[dict[str, Any]] = []
        for external_path, index_record in indexed_jobs.items():
            if source.request_delay_seconds:
                self.sleep(source.request_delay_seconds)
            detail_url = urljoin(f"{cxs_base}/", external_path.lstrip("/"))
            response = self._get(detail_url)
            raw_bytes = response.content
            _json_object(raw_bytes, "detail")
            page = _page_record(
                requested_url=detail_url,
                final_url=response.url,
                status_code=response.status_code,
                content_type=response.headers.get("Content-Type", ""),
                raw_bytes=raw_bytes,
            )
            page["external_path"] = external_path
            job_pages.append(page)
            job_index.append(index_record)

        envelope: Mapping[str, Any] = {
            "provider": "workday",
            "source_token": source.token,
            "host": source.host,
            "tenant": source.tenant,
            "site": source.site,
            "listing_url": listing_url,
            "public_base_url": (
                f"{source.host.rstrip('/')}/en-US/{source.site}"
            ),
            "reported_job_count": reported_total,
            "listing_pages": listing_pages,
            "job_index": job_index,
            "job_pages": job_pages,
        }
        raw_bundle = (
            json.dumps(
                envelope,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")
        return WorkdayResponse(
            source_token=source.token,
            endpoint=listing_url,
            status_code=200,
            content_type="application/vnd.sa-tech-job-market.workday+json",
            raw_bytes=raw_bundle,
            job_count=reported_total,
            listing_page_count=len(listing_pages),
            detail_page_count=len(job_pages),
        )
