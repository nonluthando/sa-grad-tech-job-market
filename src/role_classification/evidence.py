"""Extract explainable title, source-level and experience evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from src.role_classification.models import ClassificationEvidence
from src.role_classification.patterns import (
    DESCRIPTION_TEXT_RULES,
    EXPLICIT_LEVEL_RULES,
    TALENT_POOL_PATTERNS,
    TITLE_RULES,
)


_RANGE_YEARS = re.compile(
    r"\b(\d+)\s*(?:-|–|—|to)\s*(\d+)\s*(?:years?|yrs?)"
    r"(?:\s*(?:of\s+)?(?:relevant\s+|professional\s+|work\s+)?experience)?\b",
    re.IGNORECASE,
)
_SINGLE_YEARS = re.compile(
    r"\b(?:(?:at\s+least|minimum(?:\s+of)?|min\.?)\s+)?"
    r"(\d+)\s*(?:\+|plus)?\s*(?:years?|yrs?)"
    r"(?:['’]?\s*(?:of\s+)?(?:relevant\s+|professional\s+|work\s+)?experience)?\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExperienceEvidence:
    minimum_years: int | None
    maximum_years: int | None
    evidence: tuple[ClassificationEvidence, ...]


def _unique_evidence(
    evidence: Iterable[ClassificationEvidence],
) -> tuple[ClassificationEvidence, ...]:
    seen: set[tuple[str, str, int, str]] = set()
    result: list[ClassificationEvidence] = []
    for item in evidence:
        key = (item.source, item.value.casefold(), item.weight, item.category)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return tuple(result)


def _rule_evidence(
    text: str,
    source: str,
    rules: tuple[tuple[str, int, str, tuple[str, ...]], ...],
) -> tuple[ClassificationEvidence, ...]:
    items: list[ClassificationEvidence] = []
    for _, weight, category, patterns in rules:
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                items.append(
                    ClassificationEvidence(
                        source=source,
                        value=match.group(0),
                        weight=weight,
                        category=category,
                    )
                )
    return _unique_evidence(items)


def extract_title_evidence(title: str) -> tuple[ClassificationEvidence, ...]:
    return _rule_evidence(title, "title", TITLE_RULES)


def extract_explicit_level_evidence(
    explicit_level: str | None,
) -> tuple[ClassificationEvidence, ...]:
    if not explicit_level:
        return ()
    return _rule_evidence(explicit_level, "source_level", EXPLICIT_LEVEL_RULES)


def extract_description_text_evidence(
    description: str,
) -> tuple[ClassificationEvidence, ...]:
    return _rule_evidence(description, "description", DESCRIPTION_TEXT_RULES)


def _experience_weight(minimum_years: int) -> tuple[int, str]:
    if minimum_years <= 1:
        return 5, "junior"
    if minimum_years == 2:
        return 2, "ambiguous"
    if minimum_years == 3:
        return -2, "mid_level"
    if minimum_years == 4:
        return -5, "mid_level"
    return -10, "senior"


def extract_experience_evidence(description: str) -> ExperienceEvidence:
    minimums: list[int] = []
    maximums: list[int] = []
    items: list[ClassificationEvidence] = []
    occupied_spans: list[tuple[int, int]] = []

    def overlaps(start: int, end: int) -> bool:
        return any(
            start < existing_end and end > existing_start
            for existing_start, existing_end in occupied_spans
        )

    for match in _RANGE_YEARS.finditer(description):
        lower = min(int(match.group(1)), int(match.group(2)))
        upper = max(int(match.group(1)), int(match.group(2)))
        weight, category = _experience_weight(lower)
        minimums.append(lower)
        maximums.append(upper)
        occupied_spans.append(match.span())
        items.append(
            ClassificationEvidence(
                source="experience",
                value=match.group(0),
                weight=weight,
                category=category,
            )
        )

    for match in _SINGLE_YEARS.finditer(description):
        if overlaps(*match.span()):
            continue
        years = int(match.group(1))
        weight, category = _experience_weight(years)
        minimums.append(years)
        occupied_spans.append(match.span())
        items.append(
            ClassificationEvidence(
                source="experience",
                value=match.group(0),
                weight=weight,
                category=category,
            )
        )

    return ExperienceEvidence(
        minimum_years=min(minimums) if minimums else None,
        maximum_years=max(maximums) if maximums else None,
        evidence=_unique_evidence(items),
    )


def detect_talent_pool(title: str, description: str) -> bool:
    combined = f"{title} {description}"
    return any(
        re.search(pattern, combined, flags=re.IGNORECASE)
        for pattern in TALENT_POOL_PATTERNS
    )
