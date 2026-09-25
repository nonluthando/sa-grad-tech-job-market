from pathlib import Path

from src.transformation.breezy_hr import transform_breezy_hr_job

META = {
    "source_name": "Mukuru",
    "source_token": "mukuru",
    "collected_at": "2026-07-23T12:00:00Z",
    "content_sha256": "a" * 64,
}


def test_breezy_hr_transform_classifies_sa_technology_role():
    position = {
        "id": "1",
        "name": "Software Engineer",
        "description": "Build remittance platform services using Java.",
        "location": "Cape Town, South Africa",
        "department": "Engineering",
        "url": "https://mukuru.breezy.hr/p/abc123",
        "created_at": "2026-07-01T00:00:00Z",
        "updated_at": "2026-07-05T00:00:00Z",
    }
    result = transform_breezy_hr_job(position, META, Path("raw.json"))
    assert result.source_provider == "breezy_hr"
    assert result.is_south_africa is True
    assert result.is_technology_role is True
    assert result.is_target_market is True
    assert result.application_url == "https://mukuru.breezy.hr/p/abc123"


def test_breezy_hr_transform_handles_location_object():
    position = {
        "id": "2",
        "name": "Data Analyst",
        "description": "Analyse transaction data.",
        "location": {"city": "Johannesburg", "state": "Gauteng", "country": "South Africa"},
        "candidate_url": "https://mukuru.breezy.hr/p/def456",
    }
    result = transform_breezy_hr_job(position, META, Path("raw.json"))
    assert result.location_raw == "Johannesburg, Gauteng, South Africa"
    assert result.is_south_africa is True


def test_breezy_hr_transform_uses_category_as_department_fallback():
    position = {
        "id": "3",
        "name": "QA Engineer",
        "description": "Test our platform.",
        "location": "Cape Town, South Africa",
        "category": "Quality Assurance",
        "url": "https://mukuru.breezy.hr/p/ghi789",
    }
    result = transform_breezy_hr_job(position, META, Path("raw.json"))
    assert result.department == "Quality Assurance"


def test_breezy_hr_transform_flags_missing_fields():
    position = {"id": "", "name": ""}
    result = transform_breezy_hr_job(position, META, Path("raw.json"))
    assert "missing_source_job_id" in result.data_quality_issues
    assert "missing_title" in result.data_quality_issues
    assert "missing_application_url" in result.data_quality_issues
    assert "missing_location" in result.data_quality_issues
    assert "missing_description" in result.data_quality_issues


def test_breezy_hr_transform_classifies_early_career():
    position = {
        "id": "4",
        "name": "Graduate Data Analyst",
        "description": "Join our graduate programme in data.",
        "location": "Cape Town, South Africa",
        "url": "https://mukuru.breezy.hr/p/jkl012",
    }
    result = transform_breezy_hr_job(position, META, Path("raw.json"))
    assert result.is_early_career is True
