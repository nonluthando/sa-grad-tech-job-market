"""Collect complete public Oracle Fusion Candidate Experience snapshots."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import requests

from src.ingestion.config import OracleHCMSource


USER_AGENT = (
    "sa-tech-job-market/0.4 "
    "(public portfolio research project; contact via repository)"
)


@dataclass(frozen=True)
class OracleHCMResponse:
    """One complete Oracle Candidate Experience listing-and-detail bundle."""

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
        raise ValueError(f"Oracle HCM {label} response was not valid JSON.") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Oracle HCM {label} response must be an object.")
    return payload


def _first_identifier(item: Mapping[str, Any]) -> str:
    for key in (
        "Id",
        "id",
        "SearchId",
        "searchId",
        "RequisitionNumber",
        "requisitionNumber",
        "JobIdentification",
    ):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


class OracleHCMClient:
    """Fetch Oracle Candidate Experience requisitions through its public REST layer."""

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

    def fetch_source(self, source: OracleHCMSource) -> OracleHCMResponse:
        """Fetch all requisitions and their details without silently truncating."""

        api_root = f"{source.host.rstrip('/')}/hcmRestApi/resources/latest"
        listing_url = f"{api_root}/recruitingCEJobRequisitions"
        listing_pages: list[dict[str, Any]] = []
        indexed_jobs: dict[str, dict[str, Any]] = {}
        reported_total: int | None = None

        for page_number in range(source.max_pages):
            offset = page_number * source.page_size
            params = {
                "finder": f"findReqs;siteNumber={source.site}",
                "limit": source.page_size,
                "offset": offset,
                "onlyData": "true",
            }
            response = self._get(listing_url, params)
            raw_bytes = response.content
            payload = _json_object(raw_bytes, "listing")
            items = payload.get("items")
            if not isinstance(items, list):
                raise ValueError("Oracle HCM listing response has no items list.")

            total_value = payload.get("totalResults")
            if total_value is None:
                total_value = payload.get("total")
            if total_value is not None and (
                not isinstance(total_value, int)
                or isinstance(total_value, bool)
                or total_value < 0
            ):
                raise ValueError("Oracle HCM listing response has an invalid total.")
            if isinstance(total_value, int):
                if reported_total is None:
                    reported_total = total_value
                elif total_value != reported_total:
                    raise ValueError(
                        "Oracle HCM reported job count changed during pagination."
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
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("Oracle HCM items contains a non-object.")
                identifier = _first_identifier(item)
                if not identifier:
                    raise ValueError("Oracle HCM requisition is missing an identifier.")
                indexed_jobs.setdefault(identifier, dict(item))

            has_more = payload.get("hasMore")
            if has_more is False:
                break
            if reported_total is not None and len(indexed_jobs) >= reported_total:
                break
            if not items:
                break
            if len(indexed_jobs) == before:
                raise ValueError(
                    "Oracle HCM pagination returned no new jobs before completion."
                )
        else:
            raise ValueError(
                f"Oracle HCM source exceeded max_pages={source.max_pages}."
            )

        if reported_total is None:
            reported_total = len(indexed_jobs)
        if len(indexed_jobs) != reported_total:
            raise ValueError(
                "Oracle HCM completeness check failed: "
                f"reported {reported_total}, discovered {len(indexed_jobs)}."
            )

        job_pages: list[dict[str, Any]] = []
        job_index: list[dict[str, Any]] = []
        for identifier, index_record in indexed_jobs.items():
            if source.request_delay_seconds:
                self.sleep(source.request_delay_seconds)
            detail_url = (
                f"{api_root}/recruitingCEJobRequisitionDetails/{identifier}"
            )
            response = self._get(detail_url, {"onlyData": "true"})
            raw_bytes = response.content
            _json_object(raw_bytes, "detail")
            page = _page_record(
                requested_url=detail_url,
                final_url=response.url,
                status_code=response.status_code,
                content_type=response.headers.get("Content-Type", ""),
                raw_bytes=raw_bytes,
                request_params={"onlyData": "true"},
            )
            page["source_job_id"] = identifier
            job_pages.append(page)
            job_index.append(index_record)

        envelope: Mapping[str, Any] = {
            "provider": "oracle_hcm",
            "source_token": source.token,
            "host": source.host,
            "site": source.site,
            "listing_url": listing_url,
            "public_base_url": (
                f"{source.host.rstrip('/')}/hcmUI/CandidateExperience/en/sites/"
                f"{source.site}/job"
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
        return OracleHCMResponse(
            source_token=source.token,
            endpoint=listing_url,
            status_code=200,
            content_type="application/vnd.sa-tech-job-market.oracle-hcm+json",
            raw_bytes=raw_bundle,
            job_count=reported_total,
            listing_page_count=len(listing_pages),
            detail_page_count=len(job_pages),
        )
