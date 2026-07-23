"""Transform Greenhouse job objects into the canonical schema."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.transformation.classification import (
    classify_location,
    classify_role_level,
    classify_technology_role,
    classify_workplace,
)
from src.transformation.cleaning import (
    clean_display_text,
    html_to_text,
    join_named_values,
    normalized_key,
    unique_strings,
)
from src.transformation.schema import CanonicalJob


_EARLY_CAREER_ROLE_LEVELS = {"internship", "graduate", "junior"}


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO-8601 value and normalise it to UTC."""

    if value is None:
        return None
    text = clean_display_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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
    return f"greenhouse:{source_token}:{identity}"


def transform_greenhouse_job(
    job: Mapping[str, Any],
    metadata: Mapping[str, Any],
    raw_path: Path,
) -> CanonicalJob:
    """Create one fully classified canonical observation."""

    source_name = clean_display_text(metadata.get("source_name"))
    source_token = clean_display_text(metadata.get("source_token"))
    snapshot_sha256 = clean_display_text(metadata.get("content_sha256"))
    collected_at = parse_datetime(metadata.get("collected_at"))
    if collected_at is None:
        raise ValueError("Snapshot metadata contains an invalid collected_at value.")

    source_job_id_value = job.get("id")
    if source_job_id_value is None:
        source_job_id_value = job.get("internal_job_id")
    source_job_id = clean_display_text(source_job_id_value)

    title = clean_display_text(job.get("title"))
    title_normalized = normalized_key(title)
    application_url = clean_display_text(job.get("absolute_url"))
    description_text = html_to_text(clean_display_text(job.get("content")))
    department = join_named_values(job.get("departments"))
    office = join_named_values(job.get("offices"))

    location_object = job.get("location")
    location_raw = ""
    if isinstance(location_object, Mapping):
        location_raw = clean_display_text(location_object.get("name"))
    if not location_raw and office:
        location_raw = office

    location = classify_location(location_raw, description_text)
    workplace = classify_workplace(title, location_raw, description_text)
    role_level = classify_role_level(title, description_text)
    technology = classify_technology_role(title, department, description_text)

    is_early_career = role_level.label in _EARLY_CAREER_ROLE_LEVELS
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

    source_updated_at = parse_datetime(job.get("updated_at"))
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
        source_provider="greenhouse",
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
        department=department,
        office=office,
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
