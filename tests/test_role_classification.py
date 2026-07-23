from src.role_classification.classifier import classify_role
from src.role_classification.evidence import extract_experience_evidence


def test_explicit_graduate_title_has_high_confidence():
    result = classify_role("Graduate Software Engineer", "")

    assert result.level == "graduate"
    assert result.confidence == "high"
    assert result.score >= 15


def test_two_plus_years_remains_ambiguous():
    result = classify_role(
        "Software Engineer",
        "The role requires 2+ years experience.",
    )

    assert result.level == "ambiguous"
    assert result.confidence == "low"
    assert result.score == 2


def test_three_plus_years_is_mid_level():
    result = classify_role(
        "Software Engineer",
        "Candidates need 3+ years of experience.",
    )

    assert result.level == "mid_level"
    assert result.confidence == "medium"


def test_five_years_is_senior():
    result = classify_role(
        "Data Engineer",
        "At least 5 years' experience is required.",
    )

    assert result.level == "senior"
    assert result.confidence == "medium"


def test_senior_title_overrides_early_career_description():
    result = classify_role(
        "Senior Software Engineer",
        "We welcome recent graduates and candidates with 1 year of experience.",
    )

    assert result.level == "senior"
    assert result.confidence == "high"


def test_talent_pool_is_independent_metadata():
    result = classify_role(
        "Android Developer - Talent Pool",
        "Two years of experience preferred.",
    )

    assert result.is_talent_pool is True


def test_experience_parser_avoids_nested_duplicate_matches():
    result = extract_experience_evidence("Requires 1-2 years of experience.")

    assert result.minimum_years == 1
    assert result.maximum_years == 2
    assert len(result.evidence) == 1
