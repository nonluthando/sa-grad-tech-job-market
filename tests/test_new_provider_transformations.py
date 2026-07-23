from pathlib import Path

from src.transformation.oracle_hcm import transform_oracle_hcm_job
from src.transformation.workday import transform_workday_job
from src.transformation.wp_job_manager import transform_wp_job_manager_job

META = {
    "source_name": "Example",
    "source_token": "example",
    "collected_at": "2026-07-23T12:00:00Z",
    "content_sha256": "a" * 64,
}


def test_workday_transform_classifies_sa_technology_role():
    job = {
        "jobPostingInfo": {
            "jobReqId": "JR1", "title": "Junior Network Engineer",
            "location": "Cape Town, South Africa",
            "jobDescription": "Support cloud infrastructure.",
            "startDate": "2026-07-20",
        },
        "_detail_url": "https://example.test/job/JR1",
    }
    result = transform_workday_job(job, META, Path("raw.json"))
    assert result.source_provider == "workday"
    assert result.is_target_market is True
    assert result.is_early_career is True


def test_oracle_transform_classifies_sa_technology_role():
    job = {
        "Id": "10", "Title": "Software Engineer",
        "PrimaryLocation": "Johannesburg, South Africa",
        "ExternalDescriptionStr": "Develop Java applications.",
        "_detail_url": "https://example.test/job/10",
    }
    result = transform_oracle_hcm_job(job, META, Path("raw.json"))
    assert result.source_provider == "oracle_hcm"
    assert result.is_target_market is True


def test_wp_transform_prefers_jobposting_json_ld():
    html = '''<html><script type="application/ld+json">{
      "@type":"JobPosting", "title":"Graduate Software Developer",
      "description":"Build Python services", "datePosted":"2026-07-20",
      "jobLocation":{"address":{"addressLocality":"Durban","addressCountry":"South Africa"}}
    }</script></html>'''
    job = {"source_job_id": "graduate-developer", "_detail_html": html, "_detail_url": "https://example.test/jobs/graduate-developer"}
    result = transform_wp_job_manager_job(job, META, Path("raw.json"))
    assert result.source_provider == "wp_job_manager"
    assert result.is_target_market is True
    assert result.is_early_career is True
