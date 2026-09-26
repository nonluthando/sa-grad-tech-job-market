from pathlib import Path

from src.transformation.workable import transform_workable_job

META = {
    "source_name": "Stitch",
    "source_token": "stitchmoney",
    "collected_at": "2026-07-23T12:00:00Z",
    "content_sha256": "a" * 64,
}


def test_workable_transform_classifies_sa_technology_role():
    job = {
        "id": "1",
        "title": "Backend Engineer",
        "description": "Build payment APIs using Python and PostgreSQL.",
        "location": "Cape Town, South Africa",
        "department": "Engineering",
        "url": "https://apply.workable.com/stitchmoney/j/ABC123/",
        "created_at": "2026-07-01T00:00:00Z",
        "updated_at": "2026-07-05T00:00:00Z",
    }
    result = transform_workable_job(job, META, Path("raw.json"))
    assert result.source_provider == "workable"
    assert result.is_south_africa is True
    assert result.is_technology_role is True
    assert result.is_target_market is True
    assert result.application_url == "https://apply.workable.com/stitchmoney/j/ABC123/"


def test_workable_transform_handles_location_object():
    job = {
        "id": "2",
        "title": "Data Engineer",
        "description": "Own our data pipelines.",
        "location": {"city": "Johannesburg", "region": "Gauteng", "country": "South Africa"},
        "shortlink": "https://apply.workable.com/stitchmoney/j/DEF456/",
    }
    result = transform_workable_job(job, META, Path("raw.json"))
    assert result.location_raw == "Johannesburg, Gauteng, South Africa"
    assert result.is_south_africa is True


def test_workable_transform_marks_explicit_remote_workplace():
    job = {
        "id": "3",
        "title": "Cloud Engineer",
        "description": "Operate cloud infrastructure.",
        "location": "South Africa",
        "telecommute": True,
        "url": "https://apply.workable.com/stitchmoney/j/GHI789/",
    }
    result = transform_workable_job(job, META, Path("raw.json"))
    assert result.workplace_type == "remote"


def test_workable_transform_flags_missing_fields():
    job = {"id": "", "title": ""}
    result = transform_workable_job(job, META, Path("raw.json"))
    assert "missing_source_job_id" in result.data_quality_issues
    assert "missing_title" in result.data_quality_issues
    assert "missing_application_url" in result.data_quality_issues
    assert "missing_location" in result.data_quality_issues
    assert "missing_description" in result.data_quality_issues


def test_workable_transform_classifies_early_career():
    job = {
        "id": "4",
        "title": "Graduate Software Engineer",
        "description": "Join our graduate programme building fintech products.",
        "location": "Cape Town, South Africa",
        "url": "https://apply.workable.com/stitchmoney/j/JKL012/",
    }
    result = transform_workable_job(job, META, Path("raw.json"))
    assert result.is_early_career is True
