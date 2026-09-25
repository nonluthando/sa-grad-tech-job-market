"""Transform Breezy HR position objects into the canonical schema."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def normalize_breezy_hr_jobs(
    payload: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Transform Breezy HR JSON to internal job schema."""
    normalized = []
    for position in payload:
        normalized.append({
            "id": position.get("id"),
            "title": position.get("name"),
            "description": position.get("description"),
            "location": position.get("location"),
            "department": position.get("department"),
            "category": position.get("category"),
            "posted_date": position.get("created_at"),
            "updated_date": position.get("updated_at"),
        })
    return normalized


def extract_breezy_hr_metadata(
    company_slug: str,
    response_count: int,
    job_count: int,
    first_job_timestamp: str | None,
    last_job_timestamp: str | None,
) -> dict[str, Any]:
    """Extract metadata from Breezy HR responses."""
    return {
        "provider": "breezy_hr",
        "company_slug": company_slug,
        "response_count": response_count,
        "job_count": job_count,
        "first_job_posted": first_job_timestamp,
        "last_job_posted": last_job_timestamp,
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }
