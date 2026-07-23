import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from src.transformation.dataset import (
    build_dataset,
    deduplicate_jobs,
    write_dataset_outputs,
)
from src.transformation.greenhouse import transform_greenhouse_job


FIXTURE = Path(__file__).parent / "fixtures" / "greenhouse_jobs_m2.json"


def write_snapshot(
    raw_root: Path,
    payload: dict[str, object],
    *,
    timestamp: str,
    collected_at: str,
) -> None:
    source_directory = raw_root / "greenhouse" / "example"
    source_directory.mkdir(parents=True, exist_ok=True)
    raw_bytes = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    raw_path = source_directory / f"{timestamp}.json"
    raw_path.write_bytes(raw_bytes)
    metadata_path = source_directory / f"{timestamp}.metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "source": "greenhouse",
                "source_name": "Example Tech",
                "source_token": "example",
                "collected_at": collected_at,
                "content_sha256": hashlib.sha256(raw_bytes).hexdigest(),
                "source_job_count": len(payload["jobs"]),
                "raw_file": raw_path.name,
            }
        ),
        encoding="utf-8",
    )


def test_deduplicate_jobs_keeps_latest_record_and_observation_window() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    first_metadata = {
        "source_name": "Example Tech",
        "source_token": "example",
        "collected_at": "2026-07-20T10:00:00Z",
        "content_sha256": "first",
    }
    second_metadata = {
        "source_name": "Example Tech",
        "source_token": "example",
        "collected_at": "2026-07-22T10:00:00Z",
        "content_sha256": "second",
    }
    first = transform_greenhouse_job(
        payload["jobs"][0], first_metadata, Path("first.json")
    )
    changed_job = dict(payload["jobs"][0])
    changed_job["title"] = "Junior Backend Software Engineer"
    second = transform_greenhouse_job(changed_job, second_metadata, Path("second.json"))

    result = deduplicate_jobs([second, first])

    assert len(result) == 1
    assert result[0].title == "Junior Backend Software Engineer"
    assert result[0].observation_count == 2
    assert result[0].first_seen_at.isoformat() == "2026-07-20T10:00:00+00:00"
    assert result[0].last_seen_at.isoformat() == "2026-07-22T10:00:00+00:00"
    assert result[0].source_snapshot_sha256 == "second"


def test_build_dataset_reports_deduplication_and_market_counts(tmp_path: Path) -> None:
    first_payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    second_payload = {
        "jobs": [
            {
                **first_payload["jobs"][0],
                "title": "Junior Backend Software Engineer",
                "updated_at": "2026-07-23T08:00:00Z",
            },
            first_payload["jobs"][1],
        ]
    }
    write_snapshot(
        tmp_path,
        first_payload,
        timestamp="first",
        collected_at="2026-07-22T12:00:00Z",
    )
    write_snapshot(
        tmp_path,
        second_payload,
        timestamp="second",
        collected_at="2026-07-23T12:00:00Z",
    )

    result = build_dataset(tmp_path)

    assert len(result.jobs) == 3
    report = result.quality_report
    assert report["source_window_start"] == "2026-07-22T12:00:00+00:00"
    assert report["source_window_end"] == "2026-07-23T12:00:00+00:00"
    assert report["raw_snapshot_count"] == 2
    assert report["raw_job_observation_count"] == 5
    assert report["canonical_job_count"] == 3
    assert report["duplicate_observations_removed"] == 2
    assert report["south_africa_job_count"] == 2
    assert report["technology_job_count"] == 2
    assert report["target_market_definition"] == "south_africa_technology_roles"
    assert report["target_market_job_count"] == 2
    assert report["early_career_target_market_job_count"] == 2
    assert report["role_level_counts"] == {
        "graduate": 1,
        "junior": 1,
        "senior": 1,
    }
    latest_job = next(job for job in result.jobs if job.source_job_id == "1001")
    assert latest_job.source_snapshot_path == "greenhouse/example/second.json"


@pytest.mark.skipif(
    importlib.util.find_spec("pyarrow") is None,
    reason="pyarrow is installed from requirements in the project environment",
)
def test_write_dataset_outputs_creates_real_parquet_and_quality_report(
    tmp_path: Path,
) -> None:
    import pyarrow.parquet as pq

    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    write_snapshot(
        tmp_path / "raw",
        payload,
        timestamp="snapshot",
        collected_at="2026-07-22T12:00:00Z",
    )
    result = build_dataset(tmp_path / "raw")

    parquet_path, quality_path = write_dataset_outputs(
        result,
        tmp_path / "processed",
    )

    table = pq.read_table(parquet_path)
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    assert table.num_rows == 3
    assert table.column_names[0] == "job_key"
    assert "is_early_career" in table.column_names
    assert quality["canonical_job_count"] == 3


def write_lever_snapshot(
    raw_root: Path,
    payload: list[dict[str, object]],
    *,
    timestamp: str,
    collected_at: str,
) -> None:
    source_directory = raw_root / "lever" / "lever-example"
    source_directory.mkdir(parents=True, exist_ok=True)
    raw_bytes = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    raw_path = source_directory / f"{timestamp}.json"
    raw_path.write_bytes(raw_bytes)
    metadata_path = source_directory / f"{timestamp}.metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "source": "lever",
                "source_name": "Lever Example",
                "source_token": "lever-example",
                "collected_at": collected_at,
                "content_sha256": hashlib.sha256(raw_bytes).hexdigest(),
                "source_job_count": len(payload),
                "raw_file": raw_path.name,
            }
        ),
        encoding="utf-8",
    )


def test_build_dataset_combines_greenhouse_and_lever_snapshots(tmp_path: Path) -> None:
    greenhouse_payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    lever_fixture = Path(__file__).parent / "fixtures" / "lever_jobs.json"
    lever_payload = json.loads(lever_fixture.read_text(encoding="utf-8"))

    write_snapshot(
        tmp_path,
        greenhouse_payload,
        timestamp="greenhouse",
        collected_at="2026-07-22T12:00:00Z",
    )
    write_lever_snapshot(
        tmp_path,
        lever_payload,
        timestamp="lever",
        collected_at="2026-07-23T12:00:00Z",
    )

    result = build_dataset(tmp_path)

    assert len(result.jobs) == 6
    assert {job.source_provider for job in result.jobs} == {"greenhouse", "lever"}
    report = result.quality_report
    assert report["raw_snapshot_count"] == 2
    assert report["provider_job_counts"] == {"greenhouse": 3, "lever": 3}
    assert report["south_africa_technology_job_count"] == 4
    assert report["target_market_job_count"] == 4
    assert report["target_market_job_count"] == report["south_africa_technology_job_count"]
    assert report["early_career_target_market_job_count"] == 3
    assert report["target_market_company_counts"] == {
        "Example Tech": 2,
        "Lever Example": 2,
    }
    assert report["early_career_target_market_company_counts"] == {
        "Example Tech": 2,
        "Lever Example": 1,
    }
    lever_job = next(job for job in result.jobs if job.source_job_id == "lever-1001")
    assert lever_job.source_snapshot_path == "lever/lever-example/lever.json"
    assert lever_job.is_early_career is True
    assert lever_job.role_level_evidence
