"""Transform public Workday CXS job details into canonical jobs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin

from src.transformation.classification import (
    classify_location, classify_role_level, classify_technology_role,
    classify_workplace,
)
from src.transformation.cleaning import (
    clean_display_text, html_to_text, normalize_whitespace, normalized_key,
    unique_strings,
)
from src.transformation.greenhouse import parse_datetime
from src.transformation.schema import CanonicalJob

_EARLY = {"internship", "graduate", "junior"}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(job: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = job.get(key)
        if value not in (None, "", [], {}):
            return value
    info = _mapping(job.get("jobPostingInfo"))
    for key in keys:
        value = info.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _location(job: Mapping[str, Any]) -> str:
    values: list[str] = []
    primary = clean_display_text(_first(job, "location", "primaryLocation"))
    if primary:
        values.append(primary)
    additions = _first(job, "additionalLocations", "locationsText")
    if isinstance(additions, list):
        values.extend(clean_display_text(item) for item in additions)
    elif additions:
        values.append(clean_display_text(additions))
    return ", ".join(unique_strings(value for value in values if value))


def _stable_key(token: str, source_id: str, url: str, fallback: str) -> str:
    identity = source_id or ("url-" + hashlib.sha256(url.encode()).hexdigest()[:24] if url else "content-" + hashlib.sha256(fallback.encode()).hexdigest()[:24])
    return f"workday:{token}:{identity}"


def transform_workday_job(job: Mapping[str, Any], metadata: Mapping[str, Any], raw_path: Path) -> CanonicalJob:
    source_name = clean_display_text(metadata.get("source_name"))
    token = clean_display_text(metadata.get("source_token"))
    collected_at = parse_datetime(metadata.get("collected_at"))
    if collected_at is None:
        raise ValueError("Snapshot metadata contains an invalid collected_at value.")

    source_id = clean_display_text(_first(job, "jobReqId", "requisitionId", "id"))
    title = clean_display_text(_first(job, "title", "jobTitle"))
    description = html_to_text(clean_display_text(_first(job, "jobDescription", "description")))
    location_raw = _location(job)
    department = clean_display_text(_first(job, "jobFamily", "jobCategory", "businessUnit")) or None
    office = clean_display_text(_first(job, "location")) or None
    external_path = clean_display_text(job.get("_external_path") or _first(job, "externalPath"))
    detail_url = clean_display_text(job.get("_detail_url"))
    public_base = clean_display_text(job.get("_public_base_url"))
    application_url = urljoin(public_base.rstrip("/") + "/", external_path.lstrip("/")) if external_path and public_base else detail_url

    location = classify_location(location_raw, description)
    workplace = classify_workplace(title, location_raw, description, clean_display_text(_first(job, "timeType", "workplaceType")))
    role_level = classify_role_level(title, description)
    technology = classify_technology_role(title, department, description)
    early = role_level.label in _EARLY
    target = location.is_south_africa and technology.is_technology_role

    issues: list[str] = []
    for missing, value in (("missing_source_job_id", source_id), ("missing_title", title), ("missing_application_url", application_url), ("missing_location", location_raw), ("missing_description", description)):
        if not value:
            issues.append(missing)
    source_updated = parse_datetime(_first(job, "startDate", "postedOn", "datePosted"))
    fallback = "|".join((source_name, normalized_key(title), normalized_key(location_raw), description[:500]))
    return CanonicalJob(
        job_key=_stable_key(token, source_id, application_url, fallback),
        source_provider="workday", source_name=source_name, source_token=token,
        source_job_id=source_id, source_snapshot_sha256=clean_display_text(metadata.get("content_sha256")),
        source_snapshot_path=str(raw_path), first_seen_at=collected_at, last_seen_at=collected_at,
        source_updated_at=source_updated, observation_count=1, title=title,
        title_normalized=normalized_key(title), company=source_name,
        department=department, office=office, location_raw=location_raw,
        city=location.city, province=location.province, country=location.country,
        location_evidence=location.evidence, is_south_africa=location.is_south_africa,
        workplace_type=workplace.label, role_level=role_level.label,
        role_level_evidence=role_level.evidence,
        is_technology_role=technology.is_technology_role,
        technology_evidence=technology.evidence, is_early_career=early,
        is_target_market=target, description_text=normalize_whitespace(description),
        application_url=application_url, data_quality_issues=unique_strings(issues),
    )
