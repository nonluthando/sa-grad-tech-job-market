import json
from pathlib import Path

from src.transformation.lever import transform_lever_job


FIXTURE = Path(__file__).parent / "fixtures" / "lever_jobs.json"


def metadata() -> dict[str, object]:
    return {
        "source": "lever",
        "source_name": "Example Tech",
        "source_token": "example",
        "collected_at": "2026-07-23T15:00:00+00:00",
        "content_sha256": "abc123",
    }


def test_transform_lever_job_builds_target_market_record() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    result = transform_lever_job(
        payload[0],
        metadata(),
        Path("lever/example/snapshot.json"),
    )

    assert result.job_key == "lever:example:lever-1001"
    assert result.source_provider == "lever"
    assert result.company == "Example Tech"
    assert result.title == "Software Engineer"
    assert result.department == "Technology"
    assert result.location_raw == "Cape Town, South Africa"
    assert result.city == "Cape Town"
    assert result.country == "South Africa"
    assert result.workplace_type == "hybrid"
    assert result.role_level == "graduate"
    assert result.role_level_evidence == ("description: recent graduate",)
    assert result.is_technology_role is True
    assert result.is_early_career is True
    assert result.is_target_market is True
    assert "What you will do" in result.description_text
    assert result.application_url.endswith("/apply")
    assert result.source_updated_at is None
    assert result.data_quality_issues == ()


def test_senior_title_cannot_be_downgraded_by_source_or_description() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    result = transform_lever_job(
        payload[1],
        metadata(),
        Path("lever/example/snapshot.json"),
    )

    assert result.role_level == "senior"
    assert result.role_level_evidence == ("title: Senior",)
    assert result.is_early_career is False
    assert result.is_target_market is True


def test_non_technology_lever_job_is_not_target_market() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    result = transform_lever_job(
        payload[2],
        metadata(),
        Path("lever/example/snapshot.json"),
    )

    assert result.workplace_type == "on_site"
    assert result.is_south_africa is True
    assert result.is_technology_role is False
    assert result.is_early_career is False
    assert result.is_target_market is False
