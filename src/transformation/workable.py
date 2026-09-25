"""Transform Workable job objects into the canonical schema."""

from __future__ import annotations

import hashlib
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
    normalize_whitespace,
    normalized_key,
    unique_strings,
)
from src.transformation.greenhouse import parse_datetime
from src.transformation.schema import CanonicalJob


_EARLY_CAREER_ROLE_LEVELS = {"internship", "graduate", "junior"}


def _location_text(value: Any) -> str:
    if isinstance(value, Mapping):
        parts = [
            clean_display_text(value.get("city")),
            clean_display_text(value.get("region")),
            clean_display_text(value.get("country")),
        ]
        return ", ".join(part for part in parts if part)
    return clean_display_text(value)


def _first(job: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = job.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


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
    return f"workable:{source_token}:{identity}"


def transform_workable_job(
    job: Mapping[str, Any],
    metadata: Mapping[str, Any],
    raw_path: Path,
) -> CanonicalJob:
    """Create one fully classified canonical Workable observation."""

    source_name = clean_display_text(metadata.get("source_name"))
    source_token = clean_display_text(metadata.get("source_token"))
    snapshot_sha256 = clean_display_text(metadata.get("content_sha256"))
    collected_at = parse_datetime(metadata.get("collected_at"))
    if collected_at is None:
        raise ValueError("Snapshot metadata contains an invalid collected_at value.")

    source_job_id = clean_display_text(_first(job, "id", "shortcode"))
    title = clean_display_text(_first(job, "title", "full_title"))
    title_normalized = normalized_key(title)
    application_url = clean_display_text(
        _first(job, "application_url", "url", "shortlink")
    )

    department = clean_display_text(job.get("department")) or None
    location_raw = _location_text(job.get("location"))
    description_text = html_to_text(clean_display_text(job.get("description")))

    location = classify_location(location_raw, description_text)
    telecommute = job.get("telecommute")
    explicit_workplace = "remote" if telecommute is True else ""
    workplace = classify_workplace(
        title,
        location_raw,
        description_text,
        explicit_workplace_type=explicit_workplace,
    )
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

    source_updated_at = parse_datetime(
        _first(job, "updated_at", "published_on", "created_at")
    )
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
        source_provider="workable",
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
        description_text=normalize_whitespace(description_text),
        application_url=application_url,
        data_quality_issues=unique_strings(issues),
    )
