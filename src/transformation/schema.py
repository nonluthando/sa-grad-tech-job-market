"""Canonical records produced by the transformation layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CanonicalJob:
    """One standardised job posting with source lineage and classifications."""

    job_key: str
    source_provider: str
    source_name: str
    source_token: str
    source_job_id: str
    source_snapshot_sha256: str
    source_snapshot_path: str
    first_seen_at: datetime
    last_seen_at: datetime
    source_updated_at: datetime | None
    observation_count: int
    title: str
    title_normalized: str
    company: str
    department: str | None
    office: str | None
    location_raw: str
    city: str | None
    province: str | None
    country: str | None
    location_evidence: tuple[str, ...]
    is_south_africa: bool
    workplace_type: str
    role_level: str
    role_level_evidence: tuple[str, ...]
    is_technology_role: bool
    technology_evidence: tuple[str, ...]
    is_early_career: bool
    is_target_market: bool
    description_text: str
    application_url: str
    data_quality_issues: tuple[str, ...]

    def with_observation_window(
        self,
        *,
        first_seen_at: datetime,
        last_seen_at: datetime,
        observation_count: int,
        data_quality_issues: tuple[str, ...],
    ) -> "CanonicalJob":
        """Return a copy containing the complete observation history."""

        return replace(
            self,
            first_seen_at=first_seen_at,
            last_seen_at=last_seen_at,
            observation_count=observation_count,
            data_quality_issues=data_quality_issues,
        )

    def to_record(self) -> dict[str, Any]:
        """Return a PyArrow-friendly mapping in canonical field order."""

        record = asdict(self)
        for field_name in (
            "location_evidence",
            "role_level_evidence",
            "technology_evidence",
            "data_quality_issues",
        ):
            record[field_name] = list(record[field_name])
        return record
