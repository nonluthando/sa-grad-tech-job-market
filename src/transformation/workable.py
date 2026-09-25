"""Transform Workable job objects into the canonical schema."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def normalize_workable_jobs(
    payload: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Transform Workable JSON to internal job schema."""
    normalized = []
    for job in payload:
        normalized.append({
            "id": job.get("id"),
            "title": job.get("title"),
            "description": job.get("description"),
            "location": job.get("location"),
            "department": job.get("department"),
            "posted_date": job.get("created_at"),
            "updated_date": job.get("updated_at"),
            "employment_type": job.get("employment_type"),
        })
    return normalized


def extract_workable_metadata(
    company_slug: str,
    response_count: int,
    job_count: int,
    first_job_timestamp: str | None,
    last_job_timestamp: str | None,
) -> dict[str, Any]:
    """Extract metadata from Workable responses."""
    return {
        "provider": "workable",
        "company_slug": company_slug,
        "response_count": response_count,
        "job_count": job_count,
        "first_job_posted": first_job_timestamp,
        "last_job_posted": last_job_timestamp,
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }
