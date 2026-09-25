from pathlib import Path

from src.transformation.smartrecruiters import transform_smartrecruiters_job

META = {
    "source_name": "Standard Bank",
    "source_token": "standardbankgroup",
    "collected_at": "2026-07-23T12:00:00Z",
    "content_sha256": "a" * 64,
}


def test_smartrecruiters_transform_classifies_sa_technology_role():
    job = {
        "id": "10",
        "name": "Software Engineer",
        "location": {"city": "Johannesburg", "region": "Gauteng", "country": "South Africa"},
        "department": {"label": "Technology"},
        "jobAd": {
            "sections": {
                "jobDescription": {"text": "Build and maintain banking applications using Java."},
                "qualifications": {"text": "Experience with Spring Boot and SQL."},
            }
        },
        "applyUrl": "https://careers.smartrecruiters.com/StandardBankGroup/10",
        "_detail_url": "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings/10",
    }
    result = transform_smartrecruiters_job(job, META, Path("raw.json"))
    assert result.source_provider == "smartrecruiters"
    assert result.is_south_africa is True
    assert result.is_technology_role is True
    assert result.is_target_market is True
    assert result.application_url == "https://careers.smartrecruiters.com/StandardBankGroup/10"


def test_smartrecruiters_transform_classifies_early_career():
    job = {
        "id": "11",
        "name": "Graduate Data Analyst",
        "location": {"city": "Cape Town", "country": "South Africa"},
        "experienceLevel": {"label": "Entry level"},
        "jobAd": {
            "sections": {
                "jobDescription": {"text": "Join our graduate programme analysing data."},
            }
        },
        "postingUrl": "https://careers.smartrecruiters.com/StandardBankGroup/11",
        "_detail_url": "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings/11",
    }
    result = transform_smartrecruiters_job(job, META, Path("raw.json"))
    assert result.is_early_career is True


def test_smartrecruiters_transform_falls_back_to_public_base_url():
    job = {
        "id": "12",
        "name": "Cloud Engineer",
        "location": {"city": "Johannesburg", "country": "South Africa"},
        "jobAd": {
            "sections": {"jobDescription": {"text": "Operate AWS cloud infrastructure."}},
        },
        "_public_base_url": "https://careers.smartrecruiters.com/StandardBankGroup",
        "_detail_url": "https://api.smartrecruiters.test/v1/companies/StandardBankGroup/postings/12",
    }
    result = transform_smartrecruiters_job(job, META, Path("raw.json"))
    assert result.application_url == "https://careers.smartrecruiters.com/StandardBankGroup/12"


def test_smartrecruiters_transform_flags_missing_fields():
    job = {"id": "", "name": "", "jobAd": {}}
    result = transform_smartrecruiters_job(job, META, Path("raw.json"))
    assert "missing_source_job_id" in result.data_quality_issues
    assert "missing_title" in result.data_quality_issues
    assert "missing_application_url" in result.data_quality_issues
    assert "missing_location" in result.data_quality_issues
    assert "missing_description" in result.data_quality_issues


def test_smartrecruiters_transform_marks_explicit_remote_workplace():
    job = {
        "id": "13",
        "name": "Backend Engineer",
        "location": {"city": "Johannesburg", "country": "South Africa", "remote": True},
        "jobAd": {"sections": {"jobDescription": {"text": "Build backend services."}}},
        "applyUrl": "https://careers.smartrecruiters.com/StandardBankGroup/13",
    }
    result = transform_smartrecruiters_job(job, META, Path("raw.json"))
    assert result.workplace_type == "remote"
