"""Collect public WP Job Manager listings and exact job-detail pages."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.ingestion.config import WPJobManagerSource


USER_AGENT = (
    "sa-tech-job-market/0.4 "
    "(public portfolio research project; contact via repository)"
)


@dataclass(frozen=True)
class WPJobManagerResponse:
    """One complete WP Job Manager listing-and-detail bundle."""

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


def _clean_url(base_url: str, href: str) -> str:
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    return parsed._replace(query="", fragment="").geturl()


def _job_links(html: str, listing_url: str) -> tuple[dict[str, str], ...]:
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "")
        url = _clean_url(listing_url, href)
        path = urlparse(url).path.rstrip("/")
        if "/jobs/" not in path.lower() or path.lower().endswith("/jobs"):
            continue
        if url in seen:
            continue
        title = " ".join(anchor.get_text(" ", strip=True).split())
        if not title:
            parent = anchor.find_parent(["li", "article", "div"])
            if parent is not None:
                heading = parent.find(["h2", "h3", "h4"])
                if heading is not None:
                    title = " ".join(heading.get_text(" ", strip=True).split())
        slug = path.split("/")[-1]
        jobs.append(
            {
                "source_job_id": slug,
                "title": title,
                "application_url": url,
            }
        )
        seen.add(url)
    return tuple(jobs)


class WPJobManagerClient:
    """Fetch WP Job Manager's public AJAX listing and each detail page."""

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
                "Accept": "application/json,text/html",
                "User-Agent": USER_AGENT,
            }
        )
        self.sleep = sleep

    def _post(self, url: str, body: Mapping[str, Any]) -> requests.Response:
        response = self.session.post(
            url,
            data=dict(body),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response

    def _get(self, url: str) -> requests.Response:
        response = self.session.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response

    def fetch_source(self, source: WPJobManagerSource) -> WPJobManagerResponse:
        """Fetch all AJAX pages, reject incomplete pages, then fetch details."""

        listing_pages: list[dict[str, Any]] = []
        indexed_jobs: dict[str, dict[str, str]] = {}
        max_num_pages: int | None = None

        for page_number in range(1, source.max_pages + 1):
            request_body = {
                "action": "get_listings",
                "search_keywords": "",
                "search_location": "",
                "filter_job_type[]": "",
                "per_page": source.page_size,
                "page": page_number,
                "orderby": "featured",
                "order": "DESC",
                "show_pagination": "false",
            }
            response = self._post(source.api_url, request_body)
            raw_bytes = response.content
            try:
                payload = json.loads(raw_bytes)
            except json.JSONDecodeError as error:
                raise ValueError(
                    "WP Job Manager listing response was not valid JSON."
                ) from error
            if not isinstance(payload, dict) or payload.get("success") is not True:
                raise ValueError("WP Job Manager listing request was unsuccessful.")
            data = payload.get("data")
            if not isinstance(data, dict):
                raise ValueError("WP Job Manager listing response has no data object.")
            html = data.get("html")
            if not isinstance(html, str):
                raise ValueError("WP Job Manager listing response has no HTML.")

            page_count_value = data.get("max_num_pages")
            try:
                current_page_count = int(page_count_value or 0)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    "WP Job Manager listing has an invalid max_num_pages."
                ) from error
            if max_num_pages is None:
                max_num_pages = max(current_page_count, 1)
            elif current_page_count and current_page_count != max_num_pages:
                raise ValueError(
                    "WP Job Manager page count changed during pagination."
                )

            listing_pages.append(
                _page_record(
                    requested_url=source.api_url,
                    final_url=response.url,
                    status_code=response.status_code,
                    content_type=response.headers.get("Content-Type", ""),
                    raw_bytes=raw_bytes,
                    request_body=request_body,
                )
            )
            before = len(indexed_jobs)
            for job in _job_links(html, source.listing_url):
                indexed_jobs.setdefault(job["application_url"], job)

            if page_number >= (max_num_pages or 1):
                break
            if len(indexed_jobs) == before:
                raise ValueError(
                    "WP Job Manager pagination returned no new jobs before completion."
                )
        else:
            raise ValueError(
                f"WP Job Manager source exceeded max_pages={source.max_pages}."
            )

        if max_num_pages is None:
            raise ValueError("WP Job Manager listing returned no page count.")
        if max_num_pages > source.max_pages:
            raise ValueError(
                "WP Job Manager completeness check failed: "
                f"reported {max_num_pages} pages, max_pages={source.max_pages}."
            )
        if not indexed_jobs:
            found_jobs = any(
                json.loads(base64.b64decode(page["body_base64"]))
                .get("data", {})
                .get("found_jobs")
                for page in listing_pages
            )
            if found_jobs:
                raise ValueError(
                    "WP Job Manager reported jobs but no detail links were found."
                )

        job_pages: list[dict[str, Any]] = []
        job_index: list[dict[str, str]] = []
        for job_url, index_record in indexed_jobs.items():
            if source.request_delay_seconds:
                self.sleep(source.request_delay_seconds)
            response = self._get(job_url)
            raw_bytes = response.content
            page = _page_record(
                requested_url=job_url,
                final_url=response.url,
                status_code=response.status_code,
                content_type=response.headers.get("Content-Type", ""),
                raw_bytes=raw_bytes,
            )
            page["source_job_id"] = index_record["source_job_id"]
            job_pages.append(page)
            job_index.append(index_record)

        envelope: Mapping[str, Any] = {
            "provider": "wp_job_manager",
            "source_token": source.token,
            "listing_url": source.listing_url,
            "api_url": source.api_url,
            "reported_page_count": max_num_pages,
            "reported_job_count": len(indexed_jobs),
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
        return WPJobManagerResponse(
            source_token=source.token,
            endpoint=source.api_url,
            status_code=200,
            content_type="application/vnd.sa-tech-job-market.wp-job-manager+json",
            raw_bytes=raw_bundle,
            job_count=len(indexed_jobs),
            listing_page_count=len(listing_pages),
            detail_page_count=len(job_pages),
        )
