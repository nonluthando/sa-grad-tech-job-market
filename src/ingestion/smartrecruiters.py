"""Collect complete public SmartRecruiters posting-board snapshots."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import requests

from src.ingestion.config import SmartRecruitersSource


USER_AGENT = (
    "sa-tech-job-market/0.4 "
    "(public portfolio research project; contact via repository)"
)


@dataclass(frozen=True)
class SmartRecruitersResponse:
    """One complete SmartRecruiters listing-and-detail bundle."""

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
    request_params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "requested_url": requested_url,
        "final_url": final_url,
        "status_code": status_code,
        "content_type": content_type,
        "content_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "body_base64": base64.b64encode(raw_bytes).decode("ascii"),
    }
    if request_params is not None:
        record["request_params"] = dict(request_params)
    return record


def _json_object(raw_bytes: bytes, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_bytes)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"SmartRecruiters {label} response was not valid JSON."
        ) from error
    if not isinstance(payload, dict):
        raise ValueError(f"SmartRecruiters {label} response must be an object.")
    return payload


def _posting_id(posting: Mapping[str, Any]) -> str:
    return str(posting.get("id") or posting.get("uuid") or "").strip()


class SmartRecruitersClient:
    """Fetch public SmartRecruiters postings through its documented REST API."""

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
                "User-Agent": USER_AGENT,
            }
        )
        self.sleep = sleep

    def _get(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
    ) -> requests.Response:
        response = self.session.get(
            url,
            params=dict(params) if params else None,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response

    def fetch_source(self, source: SmartRecruitersSource) -> SmartRecruitersResponse:
        """Fetch every posting and its detail without silently truncating."""

        api_root = f"{source.host.rstrip('/')}/v1/companies/{source.site}"
        listing_url = f"{api_root}/postings"
        listing_pages: list[dict[str, Any]] = []
        indexed_jobs: dict[str, dict[str, Any]] = {}
        reported_total: int | None = None

        for page_number in range(source.max_pages):
            offset = page_number * source.page_size
            params = {"limit": source.page_size, "offset": offset}
            response = self._get(listing_url, params)
            raw_bytes = response.content
            payload = _json_object(raw_bytes, "listing")

            content = payload.get("content")
            if not isinstance(content, list):
                raise ValueError("SmartRecruiters listing response has no content list.")

            total = payload.get("totalFound")
            if not isinstance(total, int) or isinstance(total, bool) or total < 0:
                raise ValueError(
                    "SmartRecruiters listing response has an invalid totalFound."
                )
            if reported_total is None:
                reported_total = total
            elif total != reported_total:
                raise ValueError(
                    "SmartRecruiters reported job count changed during pagination."
                )

            listing_pages.append(
                _page_record(
                    requested_url=listing_url,
                    final_url=response.url,
                    status_code=response.status_code,
                    content_type=response.headers.get("Content-Type", ""),
                    raw_bytes=raw_bytes,
                    request_params=params,
                )
            )

            before = len(indexed_jobs)
            for posting in content:
                if not isinstance(posting, dict):
                    raise ValueError("SmartRecruiters content contains a non-object.")
                posting_id = _posting_id(posting)
                if not posting_id:
                    raise ValueError("SmartRecruiters posting is missing an id.")
                indexed_jobs.setdefault(posting_id, dict(posting))

            if reported_total == 0 or len(indexed_jobs) >= reported_total:
                break
            if not content:
                break
            if len(indexed_jobs) == before:
                raise ValueError(
                    "SmartRecruiters pagination returned no new jobs before completion."
                )
        else:
            raise ValueError(
                f"SmartRecruiters source exceeded max_pages={source.max_pages}."
            )

        if reported_total is None:
            raise ValueError("SmartRecruiters listing did not return a reported total.")
        if len(indexed_jobs) != reported_total:
            raise ValueError(
                "SmartRecruiters completeness check failed: "
                f"reported {reported_total}, discovered {len(indexed_jobs)}."
            )

        job_pages: list[dict[str, Any]] = []
        job_index: list[dict[str, Any]] = []
        for posting_id, index_record in indexed_jobs.items():
            if source.request_delay_seconds:
                self.sleep(source.request_delay_seconds)
            detail_url = f"{api_root}/postings/{posting_id}"
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
            page["source_job_id"] = posting_id
            job_pages.append(page)
            job_index.append(index_record)

        envelope: Mapping[str, Any] = {
            "provider": "smartrecruiters",
            "source_token": source.token,
            "host": source.host,
            "site": source.site,
            "listing_url": listing_url,
            "public_base_url": f"https://careers.smartrecruiters.com/{source.site}",
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
        return SmartRecruitersResponse(
            source_token=source.token,
            endpoint=listing_url,
            status_code=200,
            content_type="application/vnd.sa-tech-job-market.smartrecruiters+json",
            raw_bytes=raw_bundle,
            job_count=reported_total,
            listing_page_count=len(listing_pages),
            detail_page_count=len(job_pages),
        )
