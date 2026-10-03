"""Combine role evidence into an explainable inference."""

from __future__ import annotations

import re

from src.role_classification.evidence import (
    detect_talent_pool,
    extract_description_text_evidence,
    extract_explicit_level_evidence,
    extract_experience_evidence,
    extract_title_evidence,
)
from src.role_classification.models import ClassificationEvidence, RoleClassificationResult
from src.role_classification.scorer import confidence_for, score_evidence


_AUTHORITATIVE_EARLY_CAREER_LEVELS = ("internship", "graduate", "junior")

# Mirrors transformation/classification.py's unambiguous/overloaded senior
# split: "senior", "director", "vp" etc. are unambiguous, but "manager",
# "lead", "architect" and "head of" are overloaded - they also show up in
# genuinely early-career titles ("Junior Product Manager"), so an explicit
# early-career word in the same title wins over these specifically.
_UNAMBIGUOUS_SENIOR_VALUES = frozenset(
    {"senior", "staff", "principal", "director", "vice president", "vp", "chief"}
)

# "Graduate Programme Manager" is a senior role managing an early-career
# programme - the early-career word describes the programme, not this
# role's own seniority, so an overloaded senior word here still wins.
_PROGRAMME_LED_BY_SENIOR = re.compile(
    r"\b(?:graduate|intern(?:ship)?|trainee)\s+(?:programme|program)\b",
    re.IGNORECASE,
)


def classify_role(
    title: str,
    description: str,
    explicit_level: str | None = None,
) -> RoleClassificationResult:
    title_evidence = extract_title_evidence(title)
    source_evidence = extract_explicit_level_evidence(explicit_level)
    description_evidence = extract_description_text_evidence(description)
    experience = extract_experience_evidence(description)

    evidence = (
        title_evidence
        + source_evidence
        + description_evidence
        + experience.evidence
    )
    score = score_evidence(evidence)

    # Explicit title/source evidence takes priority over numeric thresholds.
    authoritative = title_evidence + source_evidence
    senior_items: list[ClassificationEvidence] = [
        item for item in authoritative if item.category == "senior"
    ]
    unambiguous_senior = any(
        item.value.casefold() in _UNAMBIGUOUS_SENIOR_VALUES for item in senior_items
    )
    overloaded_senior = [
        item
        for item in senior_items
        if item.value.casefold() not in _UNAMBIGUOUS_SENIOR_VALUES
    ]
    programme_led_by_senior = bool(overloaded_senior) and bool(
        _PROGRAMME_LED_BY_SENIOR.search(title)
    )

    level = "ambiguous"
    if unambiguous_senior or programme_led_by_senior:
        level = "senior"
    else:
        for candidate in _AUTHORITATIVE_EARLY_CAREER_LEVELS:
            if any(item.category == candidate for item in authoritative):
                level = candidate
                break
        else:
            if overloaded_senior:
                level = "senior"

    if level == "ambiguous":
        if any(item.category == "graduate" for item in description_evidence):
            level = "graduate"
        elif any(item.category == "junior" for item in description_evidence):
            level = "junior"
        elif experience.minimum_years is not None:
            minimum = experience.minimum_years
            if minimum <= 1:
                level = "junior"
            elif minimum == 2:
                level = "ambiguous"
            elif minimum <= 4:
                level = "mid_level"
            else:
                level = "senior"
        elif score >= 8:
            level = "junior"
        elif score <= -8:
            level = "senior"

    confidence = confidence_for(level, evidence)

    return RoleClassificationResult(
        level=level,
        confidence=confidence,
        score=score,
        evidence=evidence,
        is_talent_pool=detect_talent_pool(title, description),
    )
