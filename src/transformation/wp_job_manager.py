"""Parse WP Job Manager pages and create canonical jobs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.transformation.classification import classify_location, classify_role_level, classify_technology_role, classify_workplace
from src.transformation.cleaning import clean_display_text, normalize_whitespace, normalized_key, unique_strings
from src.transformation.greenhouse import parse_datetime
from src.transformation.schema import CanonicalJob

_EARLY = {"internship", "graduate", "junior"}


def _json_ld(soup: BeautifulSoup) -> Mapping[str, Any]:
    for script in soup.select("script[type='application/ld+json']"):
        try:
            payload = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for item in candidates:
            if isinstance(item, Mapping) and str(item.get("@type", "")).casefold() == "jobposting":
                return item
    return {}


def _location_from_ld(value: Any) -> str:
    locations = value if isinstance(value, list) else [value]
    parts: list[str] = []
    for entry in locations:
        if not isinstance(entry, Mapping): continue
        address = entry.get("address")
        if isinstance(address, Mapping):
            parts.extend(clean_display_text(address.get(k)) for k in ("addressLocality", "addressRegion", "addressCountry"))
    return ", ".join(unique_strings(part for part in parts if part))


def _stable_key(token: str, source_id: str, url: str, fallback: str) -> str:
    identity = source_id or ("url-" + hashlib.sha256(url.encode()).hexdigest()[:24] if url else "content-" + hashlib.sha256(fallback.encode()).hexdigest()[:24])
    return f"wp_job_manager:{token}:{identity}"


def transform_wp_job_manager_job(job: Mapping[str, Any], metadata: Mapping[str, Any], raw_path: Path) -> CanonicalJob:
    source_name = clean_display_text(metadata.get("source_name")); token = clean_display_text(metadata.get("source_token"))
    collected_at = parse_datetime(metadata.get("collected_at"))
    if collected_at is None: raise ValueError("Snapshot metadata contains an invalid collected_at value.")
    url = clean_display_text(job.get("_detail_url") or job.get("application_url"))
    soup = BeautifulSoup(str(job.get("_detail_html") or ""), "html.parser")
    ld = _json_ld(soup)
    title = clean_display_text(ld.get("title") or job.get("title"))
    if not title:
        heading = soup.select_one("h1, .job_listing-title, .entry-title")
        title = clean_display_text(heading.get_text(" ", strip=True) if heading else "")
    description_html = clean_display_text(ld.get("description"))
    if description_html:
        description = normalize_whitespace(BeautifulSoup(description_html, "html.parser").get_text(" ", strip=True))
    else:
        container = soup.select_one(".job_description, .job-listing-description, article, main") or soup
        for noise in container.select("script,style,nav,form"):
            noise.decompose()
        description = normalize_whitespace(container.get_text(" ", strip=True))
    location_raw = _location_from_ld(ld.get("jobLocation"))
    if not location_raw:
        node = soup.select_one(".location, .job-location, [class*='location']")
        location_raw = clean_display_text(node.get_text(" ", strip=True) if node else "")
    source_id = clean_display_text(job.get("source_job_id")) or urlparse(url).path.rstrip("/").split("/")[-1]
    department = clean_display_text(ld.get("industry") or ld.get("occupationalCategory")) or None
    location = classify_location(location_raw, description)
    workplace = classify_workplace(title, location_raw, description, clean_display_text(ld.get("jobLocationType")))
    role_level = classify_role_level(title, description, clean_display_text(ld.get("experienceRequirements")))
    technology = classify_technology_role(title, department, description)
    early = role_level.label in _EARLY; target = location.is_south_africa and technology.is_technology_role
    issues=[]
    for missing, value in (("missing_source_job_id",source_id),("missing_title",title),("missing_application_url",url),("missing_location",location_raw),("missing_description",description)):
        if not value: issues.append(missing)
    fallback="|".join((source_name, normalized_key(title), normalized_key(location_raw), description[:500]))
    return CanonicalJob(
        job_key=_stable_key(token,source_id,url,fallback), source_provider="wp_job_manager", source_name=source_name,
        source_token=token, source_job_id=source_id, source_snapshot_sha256=clean_display_text(metadata.get("content_sha256")),
        source_snapshot_path=str(raw_path), first_seen_at=collected_at, last_seen_at=collected_at,
        source_updated_at=parse_datetime(ld.get("datePosted")), observation_count=1, title=title,
        title_normalized=normalized_key(title), company=source_name, department=department, office=None,
        location_raw=location_raw, city=location.city, province=location.province, country=location.country,
        location_evidence=location.evidence, is_south_africa=location.is_south_africa,
        workplace_type=workplace.label, role_level=role_level.label, role_level_evidence=role_level.evidence,
        is_technology_role=technology.is_technology_role, technology_evidence=technology.evidence,
        is_early_career=early, is_target_market=target, description_text=description,
        application_url=url, data_quality_issues=unique_strings(issues),
    )
