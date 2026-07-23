"""Parse SuccessFactors job-detail HTML and create canonical jobs."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from bs4 import BeautifulSoup

from src.transformation.classification import (
    classify_location,
    classify_role_level,
    classify_technology_role,
    classify_workplace,
)
from src.transformation.cleaning import (
    clean_display_text,
    normalize_whitespace,
    normalized_key,
    unique_strings,
)
from src.transformation.greenhouse import parse_datetime
from src.transformation.schema import CanonicalJob


_EARLY_CAREER_LEVELS = {"internship", "graduate", "junior"}
_JOB_ID_PATTERN = re.compile(r"/job/[^?#]+/(\d+)/?(?:[?#]|$)", re.IGNORECASE)
_DATE_PATTERN = re.compile(
    r"\bDate:\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b",
    re.IGNORECASE,
)
_LOCATION_PATTERN = re.compile(
    r"\bLocation:\s*(.+?)(?=\s+Date:|\s+Title:|$)",
    re.IGNORECASE,
)


def _first_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        element = soup.select_one(selector)
        if element is not None:
            value = clean_display_text(element.get_text(" ", strip=True))
            if value:
                return value
    return ""


def _remove_page_noise(container: Any) -> str:
    for selector in (
        "script",
        "style",
        "nav",
        "form",
        ".apply",
        ".jobApplyBtn",
        ".socialshare",
        ".similar-jobs",
    ):
        for element in container.select(selector):
            element.decompose()
    return normalize_whitespace(container.get_text(" ", strip=True))


def parse_successfactors_detail(
    raw_bytes: bytes,
    job_url: str,
    index_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract stable fields with listing evidence as a conservative fallback."""

    index = index_record or {}
    soup = BeautifulSoup(raw_bytes, "html.parser")
    title = _first_text(
        soup,
        ("h1", ".jobTitle h1", ".jobTitle", "[itemprop='title']"),
    ) or clean_display_text(index.get("title"))

    visible_text = normalize_whitespace(soup.get_text(" ", strip=True))
    location = _first_text(
        soup,
        (".jobGeoLocation", "[itemprop='jobLocation']", ".job-location"),
    )
    location = re.sub(r"^Location:\s*", "", location, flags=re.IGNORECASE)
    if not location:
        match = _LOCATION_PATTERN.search(visible_text)
        if match:
            location = clean_display_text(match.group(1))
    if not location:
        location = clean_display_text(index.get("location_raw"))

    published_text = clean_display_text(index.get("published_text"))
    date_match = _DATE_PATTERN.search(visible_text)
    if date_match:
        published_text = date_match.group(1)

    description_container = None
    for selector in (
        ".jobdescription",
        ".jobDescription",
        "[itemprop='description']",
        ".job-detail-content",
        ".job",
    ):
        description_container = soup.select_one(selector)
        if description_container is not None:
            break
    description_text = (
        _remove_page_noise(description_container)
        if description_container is not None
        else ""
    )

    source_job_id = clean_display_text(index.get("source_job_id"))
    if not source_job_id:
        match = _JOB_ID_PATTERN.search(job_url)
        source_job_id = match.group(1) if match else ""

    return {
        "source_job_id": source_job_id,
        "title": title,
        "location_raw": location,
        "published_text": published_text,
        "description_text": description_text,
        "application_url": job_url,
    }


def _parse_source_date(value: str) -> datetime | None:
    text = clean_display_text(value)
    if not text:
        return None
    for date_format in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, date_format).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return parse_datetime(text)


def _stable_job_key(
    source_token: str,
    source_job_id: str,
    application_url: str,
    fallback_content: str,
) -> str:
    if source_job_id:
        identity = source_job_id
    elif application_url:
        identity = "url-" + hashlib.sha256(application_url.encode("utf-8")).hexdigest()[:24]
    else:
        identity = "content-" + hashlib.sha256(fallback_content.encode("utf-8")).hexdigest()[:24]
    return f"successfactors:{source_token}:{identity}"


def transform_successfactors_job(
    job: Mapping[str, Any],
    metadata: Mapping[str, Any],
    raw_path: Path,
) -> CanonicalJob:
    """Create one canonical observation from a parsed SuccessFactors detail page."""

    source_name = clean_display_text(metadata.get("source_name"))
    source_token = clean_display_text(metadata.get("source_token"))
    snapshot_sha256 = clean_display_text(metadata.get("content_sha256"))
    collected_at = parse_datetime(metadata.get("collected_at"))
    if collected_at is None:
        raise ValueError("Snapshot metadata contains an invalid collected_at value.")

    source_job_id = clean_display_text(job.get("source_job_id"))
    title = clean_display_text(job.get("title"))
    title_normalized = normalized_key(title)
    location_raw = clean_display_text(job.get("location_raw"))
    description_text = clean_display_text(job.get("description_text"))
    application_url = clean_display_text(job.get("application_url"))

    location = classify_location(location_raw, description_text)
    workplace = classify_workplace(title, location_raw, description_text)
    role_level = classify_role_level(title, description_text)
    technology = classify_technology_role(title, None, description_text)
    is_early_career = role_level.label in _EARLY_CAREER_LEVELS
    is_target_market = location.is_south_africa and technology.is_technology_role

    issues: list[str] = []
    if not source_job_id:
        issues.append("missing_source_job_id")
    if not title:
        issues.append("missing_title")
    if not application_url:
        issues.append("missing_application_url")
    if not location_raw:
        issues.append("missing_location")
    if not description_text:
        issues.append("missing_description")

    source_updated_at = _parse_source_date(clean_display_text(job.get("published_text")))
    if source_updated_at is None:
        issues.append("missing_or_invalid_source_updated_at")

    fallback_content = "|".join(
        (source_name, title_normalized, normalized_key(location_raw), description_text[:500])
    )
    return CanonicalJob(
        job_key=_stable_job_key(
            source_token,
            source_job_id,
            application_url,
            fallback_content,
        ),
        source_provider="successfactors",
        source_name=source_name,
        source_token=source_token,
        source_job_id=source_job_id,
        source_snapshot_sha256=snapshot_sha256,
        source_snapshot_path=str(raw_path),
        first_seen_at=collected_at,
        last_seen_at=collected_at,
        source_updated_at=source_updated_at,
        observation_count=1,
        title=title,
        title_normalized=title_normalized,
        company=source_name,
        department=None,
        office=None,
        location_raw=location_raw,
        city=location.city,
        province=location.province,
        country=location.country,
        location_evidence=location.evidence,
        is_south_africa=location.is_south_africa,
        workplace_type=workplace.label,
        role_level=role_level.label,
        role_level_evidence=role_level.evidence,
        is_technology_role=technology.is_technology_role,
        technology_evidence=technology.evidence,
        is_early_career=is_early_career,
        is_target_market=is_target_market,
        description_text=description_text,
        application_url=application_url,
        data_quality_issues=unique_strings(issues),
    )
