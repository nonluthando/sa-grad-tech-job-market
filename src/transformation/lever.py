"""Transform Lever postings into the canonical job schema."""

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
_COUNTRY_NAMES = {
    "ZA": "South Africa",
    "GB": "United Kingdom",
    "US": "United States",
    "CA": "Canada",
    "AU": "Australia",
    "DE": "Germany",
    "FR": "France",
    "IE": "Ireland",
    "IN": "India",
    "KE": "Kenya",
    "MY": "Malaysia",
    "NG": "Nigeria",
    "NL": "Netherlands",
    "PT": "Portugal",
    "SG": "Singapore",
    "ES": "Spain",
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return unique_strings(clean_display_text(item) for item in value)


def _description_text(job: Mapping[str, Any]) -> str:
    parts: list[str] = []

    description_plain = clean_display_text(job.get("descriptionPlain"))
    if description_plain:
        parts.append(description_plain)
    else:
        parts.append(html_to_text(clean_display_text(job.get("description"))))

    raw_lists = job.get("lists")
    if isinstance(raw_lists, list):
        for raw_list in raw_lists:
            if not isinstance(raw_list, Mapping):
                continue
            heading = clean_display_text(raw_list.get("text"))
            content = html_to_text(clean_display_text(raw_list.get("content")))
            if heading:
                parts.append(heading)
            if content:
                parts.append(content)

    additional_plain = clean_display_text(job.get("additionalPlain"))
    if additional_plain:
        parts.append(additional_plain)
    else:
        parts.append(html_to_text(clean_display_text(job.get("additional"))))

    return normalize_whitespace(" ".join(part for part in parts if part))


def _location_text(categories: Mapping[str, Any], country_code: str) -> str:
    primary = clean_display_text(categories.get("location"))
    all_locations = _string_list(categories.get("allLocations"))
    values = list(all_locations)
    if primary and primary.casefold() not in {value.casefold() for value in values}:
        values.insert(0, primary)

    country_name = _COUNTRY_NAMES.get(country_code.upper())
    if country_name and country_name.casefold() not in {
        value.casefold() for value in values
    }:
        values.append(country_name)

    return ", ".join(values)


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
    return f"lever:{source_token}:{identity}"


def transform_lever_job(
    job: Mapping[str, Any],
    metadata: Mapping[str, Any],
    raw_path: Path,
) -> CanonicalJob:
    """Create one fully classified canonical Lever observation."""

    source_name = clean_display_text(metadata.get("source_name"))
    source_token = clean_display_text(metadata.get("source_token"))
    snapshot_sha256 = clean_display_text(metadata.get("content_sha256"))
    collected_at = parse_datetime(metadata.get("collected_at"))
    if collected_at is None:
        raise ValueError("Snapshot metadata contains an invalid collected_at value.")

    source_job_id = clean_display_text(job.get("id"))
    title = clean_display_text(job.get("text"))
    title_normalized = normalized_key(title)
    application_url = clean_display_text(job.get("applyUrl"))
    if not application_url:
        application_url = clean_display_text(job.get("hostedUrl"))

    categories = _mapping(job.get("categories"))
    department = clean_display_text(categories.get("department")) or None
    team = clean_display_text(categories.get("team")) or None
    if department is None:
        department = team
    office = team if team and team != department else None

    country_code = clean_display_text(job.get("country"))
    location_raw = _location_text(categories, country_code)
    description_text = _description_text(job)

    location = classify_location(location_raw, description_text)
    workplace = classify_workplace(
        title,
        location_raw,
        description_text,
        explicit_workplace_type=clean_display_text(job.get("workplaceType")),
    )
    role_level = classify_role_level(
        title,
        description_text,
        explicit_level=clean_display_text(categories.get("level")),
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
        source_provider="lever",
        source_name=source_name,
        source_token=source_token,
        source_job_id=source_job_id,
        source_snapshot_sha256=snapshot_sha256,
        source_snapshot_path=str(raw_path),
        first_seen_at=collected_at,
        last_seen_at=collected_at,
        source_updated_at=None,
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
