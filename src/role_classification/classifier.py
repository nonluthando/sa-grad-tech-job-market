"""Combine role evidence into an explainable inference."""

from __future__ import annotations

from src.role_classification.evidence import (
    detect_talent_pool,
    extract_description_text_evidence,
    extract_explicit_level_evidence,
    extract_experience_evidence,
    extract_title_evidence,
)
from src.role_classification.models import RoleClassificationResult
from src.role_classification.scorer import confidence_for, score_evidence


_AUTHORITATIVE_TITLE_LEVELS = ("senior", "internship", "graduate", "junior")


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
    level = "ambiguous"
    for candidate in _AUTHORITATIVE_TITLE_LEVELS:
        if any(item.category == candidate for item in authoritative):
            level = candidate
            break

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
