"""Value objects used by the skills extraction layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedSkill:
    """One canonical technology or domain detected in a job posting."""

    # Legacy fields remain available during the output migration.
    skill: str
    category: str
    evidence: tuple[str, ...]

    technology: str = ""
    technology_category: str = ""
    capability: str = ""

    def __post_init__(self) -> None:
        from src.skills.dimensions import classify_skill_dimensions

        technology_category, capability = classify_skill_dimensions(
            self.skill,
            self.category,
        )
        object.__setattr__(self, "technology", self.technology or self.skill)
        object.__setattr__(
            self,
            "technology_category",
            self.technology_category or technology_category,
        )
        object.__setattr__(
            self,
            "capability",
            self.capability or capability,
        )


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
