from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from src.skills.build import build, build_rows
from src.skills.lineage import job_text_sha256


def canonical_job() -> dict[str, object]:
    return {
        "job_key": "one",
        "company": "Example Careers",
        "employer_id": "example",
        "employer_name": "Example",
        "parent_company": "Example Holdings",
        "industry": "Software",
        "title": "Junior Data Engineer",
        "city": "Cape Town",
        "province": "Western Cape",
        "workplace_type": "hybrid",
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
    }


def test_build_rows_adds_employer_and_skill_dimensions() -> None:
    skill_rows, requirement_rows, summary_rows, company_rows, report = build_rows(
        [canonical_job()]
    )

    assert report["canonical_job_count"] == 1
    assert report["target_market_job_count"] == 1
    assert report["unique_skill_count"] >= 4
    assert report["capability_mention_counts"]
    assert "programming_language" in report["category_mention_counts"]
    assert "language" in report["technology_category_mention_counts"]

    python_row = next(row for row in skill_rows if row["technology"] == "Python")
    assert python_row["job_text_sha256"] == job_text_sha256(canonical_job())
    assert python_row["employer_id"] == "example"
    assert python_row["employer_name"] == "Example"
    assert python_row["industry"] == "Software"
    assert python_row["technology_category"] == "language"
    assert python_row["capability"] == "Programming"

    sql_row = next(row for row in skill_rows if row["technology"] == "SQL")
    assert sql_row["technology_category"] == "query_language"
    assert sql_row["capability"] == "Data Storage"

    assert requirement_rows[0]["job_text_sha256"] == job_text_sha256(canonical_job())
    assert requirement_rows[0]["employer_id"] == "example"
    assert requirement_rows[0]["degree_required"] is True
    assert any(row["technology"] == "Python" for row in summary_rows)
    assert any(row["employer_id"] == "example" for row in company_rows)


@pytest.mark.skipif(
    importlib.util.find_spec("pyarrow") is None,
    reason="pyarrow is installed from requirements in the project environment",
)
def test_build_writes_skills_outputs(tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    input_path = tmp_path / "jobs.parquet"
    output_dir = tmp_path / "processed"
    pq.write_table(pa.Table.from_pylist([canonical_job()]), input_path)
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

    skill_columns = pq.read_table(output_dir / "job_skills.parquet").column_names
    assert "employer_id" in skill_columns
    assert "technology_category" in skill_columns
    assert "capability" in skill_columns
