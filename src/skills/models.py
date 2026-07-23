"""Value objects used by the skills extraction layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedSkill:
    """One canonical skill detected in a job posting."""

    skill: str
    category: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class JobEnrichment:
    """Structured skills and requirements extracted from one job."""

    skills: tuple[ExtractedSkill, ...]
    degree_required: bool
    degree_fields: tuple[str, ...]
    minimum_experience_years: int | None
    maximum_experience_years: int | None
    soft_skills: tuple[str, ...]
    extraction_warnings: tuple[str, ...]
