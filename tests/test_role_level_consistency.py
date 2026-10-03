"""Cross-check that the two independently-maintained role-level classifiers
(src/role_classification/ and src/transformation/classification.py) agree.

They're deliberately separate systems - one produces a scored inference, the
other the conservative canonical label - but the underlying notion of "what
title words mean what level" should still match. This test exists because
they silently drifted once already (the "Associate" split documented in
docs/regex-classification-audit.md) and caught a second, more serious
divergence over senior-vs-early-career title word precedence.
"""

import pytest

from src.role_classification.classifier import classify_role
from src.transformation.classification import classify_role_level


@pytest.mark.parametrize(
    "title",
    [
        "Senior Software Engineer",
        "Graduate Software Engineer",
        "Junior Data Analyst",
        "Junior Product Manager (Marketplace)",
        "Project Manager (Junior)",
        "Junior Director of Engineering",
        "Graduate Programme Manager",
        "Engineering Manager",
        "Head of Engineering",
        "Associate Platform Infrastructure Engineer",
        "Software Engineer Intern",
    ],
)
def test_role_level_systems_agree_on_title_only_cases(title: str) -> None:
    scored = classify_role(title, "")
    canonical = classify_role_level(title, "")

    if canonical.label == "unspecified":
        return

    assert scored.level == canonical.label, (
        f"{title!r}: role_classification said {scored.level!r}, "
        f"transformation.classification said {canonical.label!r}"
    )


def test_associate_architect_agrees_once_experience_is_considered() -> None:
    title = "Associate Data Architect"
    description = "At least 8 years of relevant experience is required."

    assert classify_role(title, description).level == "senior"
    assert classify_role_level(title, description).label == "senior"
