"""Collect complete SAP SuccessFactors career-site snapshots."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.ingestion.config import SuccessFactorsSource


USER_AGENT = (
    "sa-tech-job-market/0.3 "
    "(public portfolio research project; contact via repository)"
)
_RESULTS_PATTERN = re.compile(
    r"Results\s+\d+\s*[–—-]\s*\d+\s+of\s+(\d+)",
    re.IGNORECASE,
)
_JOB_ID_PATTERN = re.compile(r"/job/[^?#]+/(\d+)/?(?:[?#]|$)", re.IGNORECASE)


@dataclass(frozen=True)
class SuccessFactorsResponse:
    """One complete listing-and-detail bundle from a SuccessFactors career site."""

    source_token: str
    endpoint: str
    status_code: int
    content_type: str
    raw_bytes: bytes
    job_count: int
    listing_page_count: int
    detail_page_count: int


@dataclass(frozen=True)
class ParsedListingPage:
    reported_total: int
    jobs: tuple[dict[str, str], ...]


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _job_id_from_url(url: str) -> str:
    match = _JOB_ID_PATTERN.search(url)
    return match.group(1) if match else ""


def _normalise_job_url(base_url: str, href: str) -> str:
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    return parsed._replace(query="", fragment="").geturl()


def _listing_page_url(base_url: str, offset: int) -> str:
    if offset == 0:
        return base_url
    parsed = urlparse(base_url)
    base_path = parsed.path.rstrip("/")
    path = f"{base_path}/{offset}/"
    return parsed._replace(path=path).geturl()


def parse_listing_page(raw_bytes: bytes, page_url: str) -> ParsedListingPage:
    """Extract stable job links and listing evidence from one server-rendered page."""

    soup = BeautifulSoup(raw_bytes, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    total_match = _RESULTS_PATTERN.search(page_text)
    if total_match is None:
        raise ValueError(
            "SuccessFactors listing page did not expose a Results x-y of z count."
        )
    reported_total = int(total_match.group(1))

    jobs: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "")
        if "/job/" not in href.lower():
            continue
        job_url = _normalise_job_url(page_url, href)
        job_id = _job_id_from_url(job_url)
        if not job_id or job_url in seen_urls:
            continue
        title = _clean_text(anchor.get_text(" ", strip=True))
        if not title:
            continue

        location = ""
        published_text = ""
        row = anchor.find_parent("tr")
        if row is not None:
            cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
            nonempty_cells = [cell for cell in cells if cell]
            title_index = next(
                (index for index, cell in enumerate(nonempty_cells) if title in cell),
                0,
            )
            trailing = nonempty_cells[title_index + 1 :]
            if trailing:
                location = trailing[0]
            if len(trailing) > 1:
                published_text = trailing[-1]

        jobs.append(
            {
                "source_job_id": job_id,
                "title": title,
                "location_raw": location,
                "published_text": published_text,
                "application_url": job_url,
            }
        )
        seen_urls.add(job_url)

    return ParsedListingPage(reported_total=reported_total, jobs=tuple(jobs))


def _page_record(
    *,
    requested_url: str,
    final_url: str,
    status_code: int,
    content_type: str,
    raw_bytes: bytes,
) -> dict[str, Any]:
    return {
        "requested_url": requested_url,
        "final_url": final_url,
        "status_code": status_code,
        "content_type": content_type,
        "content_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "body_base64": base64.b64encode(raw_bytes).decode("ascii"),
    }


class SuccessFactorsClient:
    """Fetch every listing page and job-detail page without browser automation."""

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
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": USER_AGENT,
            }
        )
        self.sleep = sleep

    def _get(self, url: str) -> requests.Response:
        response = self.session.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response

    def fetch_source(self, source: SuccessFactorsSource) -> SuccessFactorsResponse:
        """Fetch a complete source and fail rather than silently keep partial pages."""

        listing_pages: list[dict[str, Any]] = []
        indexed_jobs: dict[str, dict[str, str]] = {}
        reported_total: int | None = None

        for page_number in range(source.max_pages):
            offset = page_number * source.page_size
            page_url = _listing_page_url(source.listing_url, offset)
            response = self._get(page_url)
            raw_bytes = response.content
            parsed = parse_listing_page(raw_bytes, response.url)
            if reported_total is None:
                reported_total = parsed.reported_total
            elif parsed.reported_total != reported_total:
                raise ValueError(
                    "SuccessFactors reported job count changed during pagination."
                )

            listing_pages.append(
                _page_record(
                    requested_url=page_url,
                    final_url=response.url,
                    status_code=response.status_code,
                    content_type=response.headers.get("Content-Type", ""),
                    raw_bytes=raw_bytes,
                )
            )
            before = len(indexed_jobs)
            for job in parsed.jobs:
                indexed_jobs.setdefault(job["application_url"], job)

            if reported_total == 0 or len(indexed_jobs) >= reported_total:
                break
            if len(indexed_jobs) == before:
                raise ValueError(
                    "SuccessFactors pagination returned no new jobs before completion."
                )
        else:
            raise ValueError(
                f"SuccessFactors source exceeded max_pages={source.max_pages}."
            )

        if reported_total is None:
            raise ValueError("SuccessFactors listing did not return a reported total.")
        if len(indexed_jobs) != reported_total:
            raise ValueError(
                "SuccessFactors completeness check failed: "
                f"reported {reported_total}, discovered {len(indexed_jobs)}."
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
            "provider": "successfactors",
            "source_token": source.token,
            "listing_url": source.listing_url,
            "reported_job_count": reported_total,
            "listing_pages": listing_pages,
            "job_index": job_index,
            "job_pages": job_pages,
        }
        raw_bundle = (
            json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        return SuccessFactorsResponse(
            source_token=source.token,
            endpoint=source.listing_url,
            status_code=200,
            content_type="application/vnd.sa-tech-job-market.successfactors+json",
            raw_bytes=raw_bundle,
            job_count=reported_total,
            listing_page_count=len(listing_pages),
            detail_page_count=len(job_pages),
        )
