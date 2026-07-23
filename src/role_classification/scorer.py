"""Score evidence and convert it into an inferred role-level band."""

from __future__ import annotations

from collections import Counter

from src.role_classification.models import ClassificationEvidence


def score_evidence(evidence: tuple[ClassificationEvidence, ...]) -> int:
    return sum(item.weight for item in evidence)


def strongest_category(
    evidence: tuple[ClassificationEvidence, ...],
) -> str | None:
    """Return the category with the greatest absolute accumulated weight."""

    if not evidence:
        return None

    category_scores = Counter()
    for item in evidence:
        category_scores[item.category] += item.weight

    return max(
        category_scores,
        key=lambda category: abs(category_scores[category]),
    )


def confidence_for(
    level: str,
    evidence: tuple[ClassificationEvidence, ...],
) -> str:
    title_categories = {
        item.category
        for item in evidence
        if item.source in {"title", "source_level"}
    }
    if level != "ambiguous" and level in title_categories:
        return "high"

    experience_items = [item for item in evidence if item.source == "experience"]
    if level != "ambiguous" and experience_items:
        return "medium"

    if len(evidence) >= 2 and level != "ambiguous":
        return "medium"

    return "low"
