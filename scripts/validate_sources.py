#!/usr/bin/env python3
"""Validate public ATS job sources for South African technology coverage."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "sources.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "source-test-results"
USER_AGENT = (
    "sa-grad-tech-job-market/0.1 "
    "(public portfolio research project; contact via repository)"
)


@dataclass
class NormalizedJob:
    source_job_id: str
    title: str
    location: str
    description: str
    application_url: str


@dataclass
class SourceResult:
    name: str
    provider: str
    token: str
    endpoint: str
    checked_at: str
    http_status: int | None
    response_format: str
    total_jobs: int
    south_africa_jobs: int
    technology_jobs: int
    unique_id_ratio: float
    required_field_completion_ratio: float
    passed: bool
    errors: list[str]
    sample_jobs: list[dict[str, str]]


def contains_any(text: str, terms: list[str]) -> bool:
    normalized_text = f" {text.casefold()} "
    return any(term.casefold() in normalized_text for term in terms)


def required_fields_complete(job: NormalizedJob) -> bool:
    return all(
        [
            job.source_job_id.strip(),
            job.title.strip(),
            job.location.strip(),
            job.description.strip(),
            job.application_url.strip(),
        ]
    )


def greenhouse_endpoint(token: str) -> str:
    return (
        "https://boards-api.greenhouse.io/v1/boards/"
        f"{token}/jobs?content=true"
    )


def lever_endpoint(token: str) -> str:
    return f"https://api.lever.co/v0/postings/{token}?mode=json"


def request_text(
    url: str,
    timeout_seconds: int,
    accept: str = "*/*",
) -> tuple[int, str, str]:
    request = Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        status = getattr(response, "status", 200)
        charset = response.headers.get_content_charset() or "utf-8"
        content_type = response.headers.get_content_type()
        payload = response.read().decode(charset, errors="replace")
        return status, content_type, payload


def request_json(url: str, timeout_seconds: int) -> tuple[int, Any]:
    status, _, payload = request_text(
        url,
        timeout_seconds,
        accept="application/json",
    )
    return status, json.loads(payload)


def normalize_greenhouse(payload: Any) -> list[NormalizedJob]:
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("Greenhouse response must contain a jobs list.")

    jobs: list[NormalizedJob] = []
    for item in payload["jobs"]:
        location = item.get("location") or {}
        jobs.append(
            NormalizedJob(
                source_job_id=str(item.get("id") or ""),
                title=str(item.get("title") or ""),
                location=str(location.get("name") or ""),
                description=str(item.get("content") or ""),
                application_url=str(item.get("absolute_url") or ""),
            )
        )
    return jobs


def normalize_lever(payload: Any) -> list[NormalizedJob]:
    if not isinstance(payload, list):
        raise ValueError("Lever response must be a list.")

    jobs: list[NormalizedJob] = []
    for item in payload:
        categories = item.get("categories") or {}
        all_locations = categories.get("allLocations") or []
        primary_location = categories.get("location") or ""
        location = ", ".join(all_locations) if all_locations else primary_location

        jobs.append(
            NormalizedJob(
                source_job_id=str(item.get("id") or ""),
                title=str(item.get("text") or ""),
                location=str(location or ""),
                description=str(
                    item.get("descriptionPlain")
                    or item.get("description")
                    or ""
                ),
                application_url=str(
                    item.get("applyUrl")
                    or item.get("hostedUrl")
                    or ""
                ),
            )
        )
    return jobs


def build_endpoint(provider: str, token: str, source: dict[str, Any] | None = None) -> str:
    if provider == "greenhouse":
        return greenhouse_endpoint(token)
    if provider == "lever":
        return lever_endpoint(token)
    if provider == "html_listing_page" and source:
        return str(source["url"])
    raise ValueError(f"Unsupported provider: {provider}")


def normalize_jobs(provider: str, payload: Any) -> list[NormalizedJob]:
    if provider == "greenhouse":
        return normalize_greenhouse(payload)
    if provider == "lever":
        return normalize_lever(payload)
    raise ValueError(f"Unsupported provider: {provider}")


def assess_source(
    source: dict[str, Any],
    location_terms: list[str],
    technology_terms: list[str],
    timeout_seconds: int,
) -> SourceResult:
    provider = str(source["provider"])
    token = str(source["token"])
    endpoint = build_endpoint(provider, token, source)
    checked_at = datetime.now(timezone.utc).isoformat()

    try:
        if provider == "html_listing_page":
            return assess_html_listing_page(
                source=source,
                endpoint=endpoint,
                checked_at=checked_at,
                timeout_seconds=timeout_seconds,
            )

        status, payload = request_json(endpoint, timeout_seconds)
        jobs = normalize_jobs(provider, payload)

        total_jobs = len(jobs)
        south_africa_jobs = [
            job for job in jobs if contains_any(job.location, location_terms)
        ]
        technology_jobs = [
            job
            for job in south_africa_jobs
            if contains_any(job.title, technology_terms)
        ]

        ids = [job.source_job_id for job in jobs if job.source_job_id]
        unique_id_ratio = len(set(ids)) / len(ids) if ids else 0.0
        completion_ratio = (
            sum(required_fields_complete(job) for job in jobs) / total_jobs
            if total_jobs
            else 0.0
        )

        errors: list[str] = []
        if not jobs:
            errors.append("No jobs returned.")
        if not south_africa_jobs:
            errors.append("No South African jobs detected.")
        if unique_id_ratio < 1.0:
            errors.append("Source job IDs are not fully unique.")
        if completion_ratio < 0.8:
            errors.append(
                "Fewer than 80% of jobs contain all required raw fields."
            )

        passed = (
            status == 200
            and total_jobs > 0
            and len(south_africa_jobs) > 0
            and unique_id_ratio == 1.0
            and completion_ratio >= 0.8
        )

        sample_jobs = [
            {
                "source_job_id": job.source_job_id,
                "title": job.title,
                "location": job.location,
                "application_url": job.application_url,
            }
            for job in (technology_jobs or south_africa_jobs)[:5]
        ]

        return SourceResult(
            name=str(source["name"]),
            provider=provider,
            token=token,
            endpoint=endpoint,
            checked_at=checked_at,
            http_status=status,
            response_format="json",
            total_jobs=total_jobs,
            south_africa_jobs=len(south_africa_jobs),
            technology_jobs=len(technology_jobs),
            unique_id_ratio=round(unique_id_ratio, 4),
            required_field_completion_ratio=round(completion_ratio, 4),
            passed=passed,
            errors=errors,
            sample_jobs=sample_jobs,
        )

    except HTTPError as error:
        return failure_result(source, endpoint, checked_at, error.code, str(error))
    except (URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
        return failure_result(source, endpoint, checked_at, None, str(error))



def strip_html_tags(value: str) -> str:
    without_scripts = re.sub(
        r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>",
        " ",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()


def count_matching_links(html: str, pattern: str) -> int:
    hrefs = re.findall(
        r"""href\s*=\s*["']([^"']+)["']""",
        html,
        flags=re.IGNORECASE,
    )
    matching = {
        href
        for href in hrefs
        if re.search(pattern, href, flags=re.IGNORECASE)
    }
    return len(matching)


def assess_html_listing_page(
    source: dict[str, Any],
    endpoint: str,
    checked_at: str,
    timeout_seconds: int,
) -> SourceResult:
    status, content_type, html = request_text(
        endpoint,
        timeout_seconds,
        accept="text/html,application/xhtml+xml",
    )
    plain_text = strip_html_tags(html)
    evidence_terms = [str(term) for term in source.get("evidence_terms", [])]
    missing_evidence = [
        term for term in evidence_terms
        if term.casefold() not in plain_text.casefold()
    ]
    job_link_count = count_matching_links(
        html,
        str(source.get("job_link_pattern", r"/job/")),
    )

    errors: list[str] = []
    if status != 200:
        errors.append(f"Unexpected HTTP status: {status}")
    if "html" not in content_type:
        errors.append(f"Unexpected content type: {content_type}")
    if missing_evidence:
        errors.append(
            "Missing expected page evidence: " + ", ".join(missing_evidence)
        )
    if job_link_count == 0:
        errors.append(
            "No job links detected. The page may be empty, client-rendered, "
            "or its markup may have changed."
        )

    passed = (
        status == 200
        and "html" in content_type
        and not missing_evidence
        and job_link_count > 0
    )

    # These sources are market-scoped pages rather than normalized APIs.
    # Counts represent detected listing links, not validated unique vacancies.
    return SourceResult(
        name=str(source["name"]),
        provider=str(source["provider"]),
        token=str(source["token"]),
        endpoint=endpoint,
        checked_at=checked_at,
        http_status=status,
        response_format="html",
        total_jobs=job_link_count,
        south_africa_jobs=(
            job_link_count
            if source.get("market_scope") == "south_africa"
            else 0
        ),
        technology_jobs=0,
        unique_id_ratio=0.0,
        required_field_completion_ratio=0.0,
        passed=passed,
        errors=errors,
        sample_jobs=[],
    )

def failure_result(
    source: dict[str, Any],
    endpoint: str,
    checked_at: str,
    status: int | None,
    message: str,
) -> SourceResult:
    return SourceResult(
        name=str(source["name"]),
        provider=str(source["provider"]),
        token=str(source["token"]),
        endpoint=endpoint,
        checked_at=checked_at,
        http_status=status,
        response_format="unknown",
        total_jobs=0,
        south_africa_jobs=0,
        technology_jobs=0,
        unique_id_ratio=0.0,
        required_field_completion_ratio=0.0,
        passed=False,
        errors=[message],
        sample_jobs=[],
    )


def write_results(results: list[SourceResult], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"source_validation_{timestamp}.json"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "milestone_passed": any(result.passed for result in results),
        "sources": [asdict(result) for result in results],
    }
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


def print_summary(results: list[SourceResult]) -> None:
    print()
    print("Source validation summary")
    print("=" * 80)
    for result in results:
        outcome = "PASS" if result.passed else "FAIL"
        print(
            f"{outcome:4} | {result.name:18} | "
            f"all={result.total_jobs:3} | "
            f"SA={result.south_africa_jobs:3} | "
            f"tech={result.technology_jobs:3} | "
            f"format={result.response_format}"
        )
        for error in result.errors:
            print(f"     - {error}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to source configuration JSON.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for machine-readable test results.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))

    enabled_sources = [
        source for source in config["sources"] if source.get("enabled", True)
    ]
    results = [
        assess_source(
            source=source,
            location_terms=config["south_africa_location_terms"],
            technology_terms=config["technology_title_terms"],
            timeout_seconds=args.timeout,
        )
        for source in enabled_sources
    ]

    output_path = write_results(results, args.output_dir)
    print_summary(results)
    print()
    print(f"Saved: {output_path}")

    return 0 if any(result.passed for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
