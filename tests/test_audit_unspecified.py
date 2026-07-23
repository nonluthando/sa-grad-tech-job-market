from scripts.audit_unspecified import (
    build_audit_rows,
    classify_unspecified_role,
    extract_experience_evidence,
)


def test_extracts_experience_range():
    evidence = extract_experience_evidence(
        "The successful candidate should have 1-2 years of experience."
    )

    assert evidence.minimum_years == 1
    assert evidence.maximum_years == 2
    assert evidence.matches == ("1-2 years of experience",)


def test_classifies_two_year_requirement_as_likely_early_career():
    result = classify_unspecified_role(
        "Software Engineer",
        "You should have 0 to 2 years of experience.",
    )

    assert result.likely_level == "likely_early_career"


def test_classifies_five_year_requirement_as_likely_senior():
    result = classify_unspecified_role(
        "Data Engineer",
        "A minimum of 5 years in data engineering is required.",
    )

    assert result.likely_level == "likely_senior"


def test_build_audit_rows_only_keeps_target_market_unspecified_jobs():
    jobs = [
        {
            "company": "Example",
            "title": "QA Engineer",
            "city": "Cape Town",
            "province": "Western Cape",
            "workplace_type": "hybrid",
            "role_level": "unspecified",
            "is_target_market": True,
            "description_text": "1-2 years of experience.",
            "application_url": "https://example.com/1",
        },
        {
            "company": "Example",
            "title": "Senior Engineer",
            "role_level": "senior",
            "is_target_market": True,
            "description_text": "",
        },
        {
            "company": "International",
            "title": "Software Engineer",
            "role_level": "unspecified",
            "is_target_market": False,
            "description_text": "",
        },
    ]

    rows = build_audit_rows(jobs)

    assert len(rows) == 1
    assert rows[0]["title"] == "QA Engineer"
    assert rows[0]["likely_level"] == "likely_early_career"
