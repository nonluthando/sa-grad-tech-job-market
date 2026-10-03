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


def test_overloaded_senior_word_loses_to_explicit_junior_in_same_title():
    result = classify_role("Junior Product Manager (Marketplace)", "")

    assert result.level == "junior"
    assert result.confidence == "high"


def test_overloaded_senior_word_loses_to_explicit_junior_regardless_of_order():
    result = classify_role("Project Manager (Junior)", "")

    assert result.level == "junior"


def test_unambiguous_senior_word_still_wins_over_explicit_junior():
    result = classify_role("Junior Director of Engineering", "")

    assert result.level == "senior"


def test_graduate_programme_manager_is_still_senior():
    result = classify_role("Graduate Programme Manager", "")

    assert result.level == "senior"


def test_manager_with_no_early_career_word_is_still_senior():
    result = classify_role("Engineering Manager", "")

    assert result.level == "senior"


def test_associate_platform_infrastructure_engineer_is_junior():
    result = classify_role("Associate Platform Infrastructure Engineer", "")

    assert result.level == "junior"
    assert result.confidence == "high"


def test_bare_associate_alone_is_no_longer_authoritative_junior_evidence():
    result = classify_role("Associate", "")

    assert result.level == "ambiguous"


def test_associate_architect_title_is_senior_not_junior():
    result = classify_role(
        "Associate Data Architect",
        "At least 8 years of relevant experience is required.",
    )

    assert result.level == "senior"


def test_explicit_high_experience_overrides_decontextualized_no_experience_phrase():
    result = classify_role(
        "Software Quality Engineer II",
        "Minimum Experience Level Total number of years of experience: "
        "7 - 10 years. Management experience as part of the above years: "
        "No experience required.",
    )

    assert result.level == "senior"
    assert result.confidence == "medium"


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


def test_age_eligibility_is_not_read_as_years_of_experience():
    result = extract_experience_evidence(
        "Be between the ages of 18 and 25 years; have a valid matric certificate."
    )

    assert result.minimum_years is None
    assert result.evidence == ()


def test_graduate_title_with_age_eligibility_stays_graduate_not_senior():
    """A real-world shape: a Learnership/graduate posting with an age

    eligibility clause must not have that age read as 25 years of
    experience and pushed toward senior.
    """
    result = classify_role(
        "Learnership - Short Term Insurance",
        "Be between the ages of 18 and 30 years; Grade 12 with Mathematics.",
    )

    assert result.level != "senior"
