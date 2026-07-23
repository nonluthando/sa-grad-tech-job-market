from pathlib import Path

import pytest

from src.skills.build import build

pytest.importorskip("pyarrow")
import pyarrow as pa
import pyarrow.parquet as pq


def test_build_writes_skills_outputs(tmp_path: Path):
    input_path = tmp_path / "jobs.parquet"
    output_dir = tmp_path / "processed"
    jobs = [{
        "job_key": "one",
        "company": "Example",
        "title": "Junior Data Engineer",
        "city": "Cape Town",
        "province": "Western Cape",
        "role_level": "junior",
        "inferred_role_level": "junior",
        "is_target_market": True,
        "is_early_career": True,
        "description_text": (
            "Use Python, SQL, AWS and PostgreSQL. "
            "Bachelor's degree in Computer Science required. "
            "1-2 years of experience."
        ),
        "application_url": "https://example.test/one",
    }]
    pq.write_table(pa.Table.from_pylist(jobs), input_path)
    report = build(input_path, output_dir)

    assert report["canonical_job_count"] == 1
    assert report["target_market_job_count"] == 1
    assert report["unique_skill_count"] >= 4
    for filename in (
        "job_skills.parquet",
        "job_requirements.parquet",
        "skills_summary.parquet",
        "company_skills.parquet",
        "skills-quality-report.json",
    ):
        assert (output_dir / filename).exists()
