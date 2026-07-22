import json
from pathlib import Path

from src.transformation.greenhouse import transform_greenhouse_job


FIXTURE = Path(__file__).parent / "fixtures" / "greenhouse_jobs_m2.json"


def metadata() -> dict[str, object]:
    return {
        "source": "greenhouse",
        "source_name": "Example Tech",
        "source_token": "example",
        "collected_at": "2026-07-22T15:00:00+00:00",
        "content_sha256": "abc123",
    }


def test_transform_greenhouse_job_builds_target_market_record() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    result = transform_greenhouse_job(
        payload["jobs"][0],
        metadata(),
        Path("data/raw/greenhouse/example/snapshot.json"),
    )

    assert result.job_key == "greenhouse:example:1001"
    assert result.company == "Example Tech"
    assert result.title == "Junior Software Engineer"
    assert result.title_normalized == "junior software engineer"
    assert result.description_text == "Join our hybrid engineering team."
    assert result.city == "Cape Town"
    assert result.province == "Western Cape"
    assert result.country == "South Africa"
    assert result.workplace_type == "hybrid"
    assert result.role_level == "junior"
    assert result.is_technology_role is True
    assert result.is_target_market is True
    assert result.data_quality_issues == ()


def test_transform_greenhouse_job_classifies_remote_graduate() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    result = transform_greenhouse_job(
        payload["jobs"][1],
        metadata(),
        Path("data/raw/greenhouse/example/snapshot.json"),
    )

    assert result.city is None
    assert result.country == "South Africa"
    assert result.workplace_type == "remote"
    assert result.role_level == "graduate"
    assert result.is_technology_role is True
    assert result.is_target_market is True


def test_transform_greenhouse_job_records_missing_fields_instead_of_dropping_job() -> None:
    result = transform_greenhouse_job(
        {
            "title": "Junior Developer",
            "updated_at": "not-a-date",
            "location": {"name": "Cape Town"},
            "content": "",
        },
        metadata(),
        Path("data/raw/greenhouse/example/snapshot.json"),
    )

    assert result.job_key.startswith("greenhouse:example:content-")
    assert result.source_job_id == ""
    assert result.application_url == ""
    assert result.is_target_market is True
    assert result.data_quality_issues == (
        "missing_source_job_id",
        "missing_application_url",
        "missing_description",
        "missing_or_invalid_source_updated_at",
    )
