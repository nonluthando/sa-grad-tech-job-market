from pathlib import Path

from src.transformation.ashby import transform_ashby_job

META = {
    "source_name": "Andela",
    "source_token": "andela",
    "collected_at": "2026-07-23T12:00:00Z",
    "content_sha256": "a" * 64,
}


def test_ashby_transform_classifies_sa_technology_role():
    job = {
        "id": "10",
        "title": "Software Engineer",
        "department": "Engineering",
        "location": "Cape Town, South Africa",
        "descriptionPlain": "Build and maintain distributed systems using Python.",
        "applyUrl": "https://jobs.ashbyhq.com/andela/10/application",
        "jobUrl": "https://jobs.ashbyhq.com/andela/10",
        "publishedAt": "2026-07-01T00:00:00Z",
    }
    result = transform_ashby_job(job, META, Path("raw.json"))
    assert result.source_provider == "ashby"
    assert result.is_south_africa is True
    assert result.is_technology_role is True
    assert result.is_target_market is True
    assert result.application_url == "https://jobs.ashbyhq.com/andela/10/application"


def test_ashby_transform_falls_back_to_job_url():
    job = {
        "id": "11",
        "title": "Data Engineer",
        "location": "Johannesburg, South Africa",
        "descriptionPlain": "Work with our data pipelines.",
        "jobUrl": "https://jobs.ashbyhq.com/andela/11",
    }
    result = transform_ashby_job(job, META, Path("raw.json"))
    assert result.application_url == "https://jobs.ashbyhq.com/andela/11"


def test_ashby_transform_marks_explicit_remote_workplace():
    job = {
        "id": "12",
        "title": "Backend Engineer",
        "location": "South Africa (Remote)",
        "isRemote": True,
        "descriptionPlain": "Build backend services.",
        "applyUrl": "https://jobs.ashbyhq.com/andela/12/application",
    }
    result = transform_ashby_job(job, META, Path("raw.json"))
    assert result.workplace_type == "remote"


def test_ashby_transform_classifies_early_career():
    job = {
        "id": "13",
        "title": "Graduate Software Engineer",
        "location": "Cape Town, South Africa",
        "descriptionPlain": "Join our graduate programme.",
        "applyUrl": "https://jobs.ashbyhq.com/andela/13/application",
    }
    result = transform_ashby_job(job, META, Path("raw.json"))
    assert result.is_early_career is True


def test_ashby_transform_flags_missing_fields():
    job = {"id": "", "title": ""}
    result = transform_ashby_job(job, META, Path("raw.json"))
    assert "missing_source_job_id" in result.data_quality_issues
    assert "missing_title" in result.data_quality_issues
    assert "missing_application_url" in result.data_quality_issues
    assert "missing_location" in result.data_quality_issues
    assert "missing_description" in result.data_quality_issues


def test_ashby_transform_prefers_html_description_when_plain_missing():
    job = {
        "id": "14",
        "title": "Cloud Engineer",
        "location": "Durban, South Africa",
        "descriptionHtml": "<p>Operate our <b>AWS</b> infrastructure.</p>",
        "applyUrl": "https://jobs.ashbyhq.com/andela/14/application",
    }
    result = transform_ashby_job(job, META, Path("raw.json"))
    assert "AWS" in result.description_text
    assert "<b>" not in result.description_text
