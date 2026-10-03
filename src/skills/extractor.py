"""Extract skills, qualifications and experience from canonical jobs."""

from __future__ import annotations

import re
from typing import Iterable

from src.skills.models import ExtractedSkill, JobEnrichment
from src.skills.taxonomy import (
    DEGREE_FIELD_RULES,
    DEGREE_OPTIONAL_PATTERNS,
    DEGREE_REQUIRED_PATTERNS,
    SKILL_RULES,
    SOFT_SKILL_RULES,
)

# The (?!...) guard excludes age phrasing ("between 18 and 25 years old")
# from being read as a years-of-experience requirement - without it, a
# bare "<N> years" matches regardless of what follows, since the "of
# experience" suffix below is optional. It only catches "old"/"of age"
# trailing the number; "between the ages of 18 and 25 years" puts the age
# cue *before* the number instead, at a variable distance a fixed-width
# regex lookbehind can't reach - _is_age_context below checks that case.
_NOT_AN_AGE = r"(?!\s*(?:old\b|of\s+age\b))"
_AGE_CONTEXT_PATTERN = re.compile(r"\bage[sd]?\b", re.IGNORECASE)


def _is_age_context(text: str, match_start: int, window: int = 40) -> bool:
    preceding = text[max(0, match_start - window):match_start]
    return bool(_AGE_CONTEXT_PATTERN.search(preceding))

_RANGE_YEARS_PATTERN = re.compile(
    r"\b(\d+)\s*(?:-|–|—|to)\s*(\d+)\s*(?:years?|yrs?)" + _NOT_AN_AGE +
    r"(?:\s*(?:of\s+)?(?:relevant\s+|professional\s+|work\s+)?experience)?\b",
    re.IGNORECASE,
)
_SINGLE_YEARS_PATTERN = re.compile(
    r"\b(?:(?:at\s+least|minimum(?:\s+of)?|min\.?)\s+)?"
    r"(\d+)\s*(?:\+|plus)?\s*(?:years?|yrs?)" + _NOT_AN_AGE +
    r"(?:['’]?\s*(?:of\s+)?(?:relevant\s+|professional\s+|work\s+)?experience)?\b",
    re.IGNORECASE,
)


def _unique_strings(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)


def _matches(text: str, patterns: Iterable[str]) -> tuple[str, ...]:
    return _unique_strings(
        match.group(0)
        for pattern in patterns
        for match in re.finditer(pattern, text, flags=re.IGNORECASE)
    )


def extract_skills(text: str) -> tuple[ExtractedSkill, ...]:
    return tuple(
        ExtractedSkill(skill=skill, category=category, evidence=evidence)
        for skill, category, patterns in SKILL_RULES
        if (evidence := _matches(text, patterns))
    )


def extract_soft_skills(text: str) -> tuple[str, ...]:
    return tuple(
        skill for skill, patterns in SOFT_SKILL_RULES if _matches(text, patterns)
    )


def extract_degree_requirements(text: str) -> tuple[bool, tuple[str, ...]]:
    required_evidence = _matches(text, DEGREE_REQUIRED_PATTERNS)
    optional_evidence = _matches(text, DEGREE_OPTIONAL_PATTERNS)
    fields = tuple(
        field for field, patterns in DEGREE_FIELD_RULES if _matches(text, patterns)
    )
    return bool(required_evidence) and not (
        optional_evidence and not required_evidence
    ), fields


def extract_experience_years(text: str) -> tuple[int | None, int | None]:
    minimums: list[int] = []
    maximums: list[int] = []
    occupied: list[tuple[int, int]] = []

    def overlaps(start: int, end: int) -> bool:
        return any(start < e and end > s for s, e in occupied)

    for match in _RANGE_YEARS_PATTERN.finditer(text):
        if _is_age_context(text, match.start()):
            continue
        lower = min(int(match.group(1)), int(match.group(2)))
        upper = max(int(match.group(1)), int(match.group(2)))
        minimums.append(lower)
        maximums.append(upper)
        occupied.append(match.span())

    for match in _SINGLE_YEARS_PATTERN.finditer(text):
        if overlaps(*match.span()) or _is_age_context(text, match.start()):
            continue
        minimums.append(int(match.group(1)))
        occupied.append(match.span())

    return (
        min(minimums) if minimums else None,
        max(maximums) if maximums else None,
    )


def extract_job_enrichment(title: str, description_text: str) -> JobEnrichment:
    text = f"{title}\n{description_text}".strip()
    warnings: list[str] = []
    if not description_text.strip():
        warnings.append("missing_description")

    skills = extract_skills(text)
    if not skills:
        warnings.append("no_skills_detected")

    degree_required, degree_fields = extract_degree_requirements(description_text)
    minimum_years, maximum_years = extract_experience_years(description_text)

    return JobEnrichment(
        skills=skills,
        degree_required=degree_required,
        degree_fields=degree_fields,
        minimum_experience_years=minimum_years,
        maximum_experience_years=maximum_years,
        soft_skills=extract_soft_skills(description_text),
        extraction_warnings=_unique_strings(warnings),
    )
