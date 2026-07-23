from pathlib import Path

from src.transformation.successfactors import (
    parse_successfactors_detail,
    transform_successfactors_job,
)


DETAIL = b"""
<html><body>
<div class="job">
  <div class="jobTitle"><h1>Junior Data Analyst</h1></div>
  <div class="jobGeoLocation">Location: Johannesburg, ZA</div>
  <div>Date: 20 Jul 2026</div>
  <div class="jobdescription">
    <h2>Job Purpose</h2>
    <p>Use SQL and Python to analyse customer data.</p>
  </div>
</div>
</body></html>
"""


def test_parse_successfactors_detail_extracts_core_fields():
    job = parse_successfactors_detail(
        DETAIL,
        "https://example.test/job/Johannesburg-Junior-Data-Analyst/1001/",
    )

    assert job["source_job_id"] == "1001"
    assert job["title"] == "Junior Data Analyst"
    assert job["location_raw"] == "Johannesburg, ZA"
    assert job["published_text"] == "20 Jul 2026"
    assert "SQL and Python" in job["description_text"]


def test_transform_successfactors_job_uses_broadened_market_scope():
    parsed = parse_successfactors_detail(
        DETAIL,
        "https://example.test/job/Johannesburg-Junior-Data-Analyst/1001/",
    )
    metadata = {
        "source_name": "Example Bank",
        "source_token": "example-bank",
        "collected_at": "2026-07-23T12:00:00Z",
        "content_sha256": "abc",
    }

    job = transform_successfactors_job(parsed, metadata, Path("snapshot.json"))

    assert job.source_provider == "successfactors"
    assert job.company == "Example Bank"
    assert job.is_south_africa is True
    assert job.is_technology_role is True
    assert job.is_target_market is True
    assert job.is_early_career is True
    assert job.source_updated_at.isoformat() == "2026-07-20T00:00:00+00:00"
