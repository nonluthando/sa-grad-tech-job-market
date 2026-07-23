"""Transform Oracle Fusion Candidate Experience requisitions."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

from src.transformation.classification import classify_location, classify_role_level, classify_technology_role, classify_workplace
from src.transformation.cleaning import clean_display_text, html_to_text, normalize_whitespace, normalized_key, unique_strings
from src.transformation.greenhouse import parse_datetime
from src.transformation.schema import CanonicalJob

_EARLY = {"internship", "graduate", "junior"}


def _first(job: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = job.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _stable_key(token: str, source_id: str, url: str, fallback: str) -> str:
    identity = source_id or ("url-" + hashlib.sha256(url.encode()).hexdigest()[:24] if url else "content-" + hashlib.sha256(fallback.encode()).hexdigest()[:24])
    return f"oracle_hcm:{token}:{identity}"


def transform_oracle_hcm_job(job: Mapping[str, Any], metadata: Mapping[str, Any], raw_path: Path) -> CanonicalJob:
    source_name = clean_display_text(metadata.get("source_name"))
    token = clean_display_text(metadata.get("source_token"))
    collected_at = parse_datetime(metadata.get("collected_at"))
    if collected_at is None:
        raise ValueError("Snapshot metadata contains an invalid collected_at value.")
    source_id = clean_display_text(_first(job, "Id", "ID", "RequisitionId", "RequisitionNumber", "requisitionNumber"))
    title = clean_display_text(_first(job, "Title", "JobTitle", "title"))
    description = html_to_text(clean_display_text(_first(job, "ExternalDescriptionStr", "ExternalDescription", "Description", "description")))
    location_raw = clean_display_text(_first(job, "PrimaryLocation", "Location", "JobLocation", "primaryLocation"))
    department = clean_display_text(_first(job, "JobFunction", "JobFamily", "Department", "BusinessUnit")) or None
    office = clean_display_text(_first(job, "PrimaryLocation")) or None
    application_url = clean_display_text(_first(job, "ExternalApplyURL", "ApplyUrl", "JobUrl", "_detail_url"))
    public_base = clean_display_text(job.get("_public_base_url"))
    if public_base and source_id:
        application_url = f"{public_base.rstrip('/')}/{quote(source_id)}"

    location = classify_location(location_raw, description)
    workplace = classify_workplace(title, location_raw, description, clean_display_text(_first(job, "WorkplaceType", "RemoteType")))
    role_level = classify_role_level(title, description, clean_display_text(_first(job, "JobLevel", "Grade")))
    technology = classify_technology_role(title, department, description)
    early = role_level.label in _EARLY
    target = location.is_south_africa and technology.is_technology_role
    issues: list[str] = []
    for missing, value in (("missing_source_job_id", source_id), ("missing_title", title), ("missing_application_url", application_url), ("missing_location", location_raw), ("missing_description", description)):
        if not value: issues.append(missing)
    source_updated = parse_datetime(_first(job, "PostedDate", "PostingDate", "LastUpdateDate", "datePosted"))
    fallback = "|".join((source_name, normalized_key(title), normalized_key(location_raw), description[:500]))
    return CanonicalJob(
        job_key=_stable_key(token, source_id, application_url, fallback), source_provider="oracle_hcm",
        source_name=source_name, source_token=token, source_job_id=source_id,
        source_snapshot_sha256=clean_display_text(metadata.get("content_sha256")), source_snapshot_path=str(raw_path),
        first_seen_at=collected_at, last_seen_at=collected_at, source_updated_at=source_updated,
        observation_count=1, title=title, title_normalized=normalized_key(title), company=source_name,
        department=department, office=office, location_raw=location_raw, city=location.city,
        province=location.province, country=location.country, location_evidence=location.evidence,
        is_south_africa=location.is_south_africa, workplace_type=workplace.label,
        role_level=role_level.label, role_level_evidence=role_level.evidence,
        is_technology_role=technology.is_technology_role, technology_evidence=technology.evidence,
        is_early_career=early, is_target_market=target, description_text=normalize_whitespace(description),
        application_url=application_url, data_quality_issues=unique_strings(issues),
    )
