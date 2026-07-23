import pytest

from src.transformation.classification import (
    classify_location,
    classify_role_level,
    classify_technology_role,
    classify_workplace,
)


def test_classify_south_african_city_and_province() -> None:
    result = classify_location("Sandton, Johannesburg, South Africa")

    assert result.city == "Johannesburg"
    assert result.province == "Gauteng"
    assert result.country == "South Africa"
    assert result.is_south_africa is True
    assert "Sandton" in result.evidence


def test_classify_remote_south_africa_from_description_without_guessing_city() -> None:
    result = classify_location(
        "Remote",
        "Applicants must be based in South Africa for this position.",
    )

    assert result.city is None
    assert result.province is None
    assert result.country == "South Africa"
    assert result.is_south_africa is True


def test_classify_known_international_country() -> None:
    result = classify_location("London, United Kingdom")

    assert result.city == "London"
    assert result.country == "United Kingdom"
    assert result.is_south_africa is False


def test_workplace_prefers_hybrid_when_remote_is_also_mentioned() -> None:
    result = classify_workplace(
        "Junior Developer",
        "Cape Town",
        "Hybrid role with occasional remote work.",
    )

    assert result.label == "hybrid"
    assert result.evidence == ("text: Hybrid",)


def test_role_level_uses_title_before_description() -> None:
    result = classify_role_level(
        "Senior Software Engineer",
        "You will mentor interns and graduates.",
    )

    assert result.label == "senior"
    assert result.evidence == ("title: Senior",)


def test_role_level_can_use_explicit_description_evidence() -> None:
    result = classify_role_level(
        "Software Engineer",
        "This is an entry-level role for candidates with 0-2 years of experience.",
    )

    assert result.label == "junior"
    assert "description: entry-level role" in result.evidence


def test_technology_classifier_avoids_data_privacy_false_positive() -> None:
    result = classify_technology_role(
        "Data Protection Officer",
        "Legal",
        "Own privacy compliance and policy.",
    )

    assert result.is_technology_role is False
    assert result.evidence == ()


def test_generic_graduate_role_uses_description_technology_evidence() -> None:
    result = classify_technology_role(
        "Graduate Programme",
        None,
        "Rotations include software engineering and cloud infrastructure.",
    )

    assert result.is_technology_role is True
    assert "software_engineering" in result.evidence


def test_non_technical_title_is_not_reclassified_from_engineering_department() -> None:
    result = classify_technology_role(
        "Talent Acquisition Partner",
        "Engineering",
        "Recruit software engineers and data analysts.",
    )

    assert result.is_technology_role is False
    assert result.evidence == ()


@pytest.mark.parametrize(
    "title",
    [
        "Mr D - Android Engineer",
        "GenAI Engineer - Product Marketing & Adoption",
        "Internal Systems Engineer (Applied AI)",
        "Technical Services Engineer III",
        "Integration Engineer",
        "Product Data Lead",
        "Senior Database Administrator",
        "IT Auditor",
    ],
)
def test_real_market_technology_titles_are_recognised(title: str) -> None:
    result = classify_technology_role(title, None, "")

    assert result.is_technology_role is True


def test_recent_graduate_description_is_classified_as_graduate() -> None:
    result = classify_role_level(
        "Software Engineer",
        "This opportunity is designed for a recent graduate.",
    )

    assert result.label == "graduate"
    assert result.evidence == ("description: recent graduate",)


def test_no_experience_required_is_junior_evidence() -> None:
    result = classify_role_level(
        "QA Engineer",
        "No prior professional experience is required.",
    )

    assert result.label == "junior"
    assert result.evidence == (
        "description: No prior professional experience is required",
    )


def test_senior_title_overrides_early_career_description_and_source_level() -> None:
    result = classify_role_level(
        "Senior Software Engineer",
        "This entry-level opportunity welcomes recent graduates.",
        explicit_level="Entry Level",
    )

    assert result.label == "senior"
    assert result.evidence == ("title: Senior",)


def test_explicit_source_level_is_used_before_description() -> None:
    result = classify_role_level(
        "Software Engineer",
        "General engineering role.",
        explicit_level="Associate",
    )

    assert result.label == "junior"
    assert result.evidence == ("source_level: Associate",)


def test_explicit_workplace_type_is_authoritative() -> None:
    result = classify_workplace(
        "Software Engineer",
        "Cape Town",
        "The wider company also supports remote work.",
        explicit_workplace_type="hybrid",
    )

    assert result.label == "hybrid"
    assert result.evidence == ("source: hybrid",)
