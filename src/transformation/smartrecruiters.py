"""Transform SmartRecruiters postings into the canonical job schema."""

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
    normalize_whitespace,
    normalized_key,
    unique_strings,
)
from src.transformation.greenhouse import parse_datetime
from src.transformation.schema import CanonicalJob


_EARLY_CAREER_ROLE_LEVELS = {"internship", "graduate", "junior"}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _label(value: Any) -> str:
    if isinstance(value, Mapping):
        return clean_display_text(value.get("label"))
    return clean_display_text(value)


def _location_text(location: Mapping[str, Any]) -> str:
    parts = [
        clean_display_text(location.get("city")),
        clean_display_text(location.get("region")),
        clean_display_text(location.get("country")),
    ]
    return ", ".join(part for part in parts if part)


def _description_text(job: Mapping[str, Any]) -> str:
    job_ad = _mapping(job.get("jobAd"))
    sections = _mapping(job_ad.get("sections"))
    parts: list[str] = []
    for key in (
        "companyDescription",
        "jobDescription",
        "qualifications",
        "additionalInformation",
    ):
        section = _mapping(sections.get(key))
        text = clean_display_text(section.get("text"))
        if text:
            parts.append(text)
    return normalize_whitespace(" ".join(parts))


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
    return f"smartrecruiters:{source_token}:{identity}"


def transform_smartrecruiters_job(
    job: Mapping[str, Any],
    metadata: Mapping[str, Any],
    raw_path: Path,
) -> CanonicalJob:
    """Create one fully classified canonical SmartRecruiters observation."""

    source_name = clean_display_text(metadata.get("source_name"))
    source_token = clean_display_text(metadata.get("source_token"))
    snapshot_sha256 = clean_display_text(metadata.get("content_sha256"))
    collected_at = parse_datetime(metadata.get("collected_at"))
    if collected_at is None:
        raise ValueError("Snapshot metadata contains an invalid collected_at value.")

    source_job_id = clean_display_text(job.get("id") or job.get("uuid"))
    title = clean_display_text(job.get("name"))
    title_normalized = normalized_key(title)

    application_url = clean_display_text(job.get("applyUrl"))
    if not application_url:
        application_url = clean_display_text(job.get("postingUrl"))
    if not application_url:
        public_base = clean_display_text(job.get("_public_base_url"))
        if public_base and source_job_id:
            application_url = f"{public_base.rstrip('/')}/{source_job_id}"

    department = _label(job.get("department")) or None
    office = _label(job.get("function")) or None
    if department is None:
        department = office

    location_raw = _location_text(_mapping(job.get("location")))
    description_text = _description_text(job)

    location = classify_location(location_raw, description_text)
    remote_flag = _mapping(job.get("location")).get("remote")
    explicit_workplace = "remote" if remote_flag is True else ""
    workplace = classify_workplace(
        title,
        location_raw,
        description_text,
        explicit_workplace_type=explicit_workplace,
    )
    role_level = classify_role_level(
        title,
        description_text,
        explicit_level=_label(job.get("experienceLevel")),
    )
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

    source_updated_at = parse_datetime(job.get("updatedOn") or job.get("releasedDate"))
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
        source_provider="smartrecruiters",
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
