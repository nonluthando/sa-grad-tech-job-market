from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.analytics.build import (
    AnalyticsBuildError,
    build_analytics_rows,
    write_outputs,
)
from src.skills.lineage import job_text_sha256


def canonical_job(
    job_key: str,
    *,
    employer_id: str = "example-tech",
    employer_name: str = "Example Tech",
    parent_company: str | None = "Example Holdings",
    target: bool = True,
    early: bool = True,
    inferred_level: str = "junior",
    workplace_type: str = "hybrid",
    province: str | None = "Western Cape",
) -> dict[str, object]:
    return {
        "job_key": job_key,
        "source_provider": "greenhouse",
        "source_name": "Example Tech",
        "source_job_id": f"source-{job_key}",
        "first_seen_at": datetime(2026, 7, 20, tzinfo=timezone.utc),
        "last_seen_at": datetime(2026, 7, 22, tzinfo=timezone.utc),
        "source_updated_at": None,
        "observation_count": 2,
        "title": "Junior Data Engineer",
        "title_normalized": "junior data engineer",
        "company": "Example Tech Careers",
        "employer_id": employer_id,
        "employer_name": employer_name,
        "parent_company": parent_company,
        "industry": "Software",
        "employer_priority": "tier_1",
        "graduate_programme": "yes",
        "city": "Cape Town",
        "province": province,
        "country": "South Africa",
        "workplace_type": workplace_type,
        "role_level": "junior",
        "inferred_role_level": inferred_level,
        "role_level_confidence": "high",
        "is_early_career": early,
        "is_target_market": target,
        "is_talent_pool": False,
        "application_url": f"https://example.test/{job_key}",
        "data_quality_issues": [],
        "description_text": (
            "Use Python and SQL to build reliable data pipelines."
        ),
    }


def requirement(job_key: str) -> dict[str, object]:
    return {
        "job_key": job_key,
        "job_text_sha256": job_text_sha256(canonical_job(job_key)),
        "degree_required": True,
        "degree_fields": ["Computer Science"],
        "minimum_experience_years": 1,
        "maximum_experience_years": 2,
        "soft_skills": ["Communication"],
        "extraction_warnings": [],
    }


def skill(job_key: str, name: str, category: str) -> dict[str, object]:
    return {
        "job_key": job_key,
        "job_text_sha256": job_text_sha256(canonical_job(job_key)),
        "skill": name,
        "category": category,
        "evidence": [name],
    }


def test_build_analytics_rows_creates_dashboard_data_marts() -> None:
    jobs = [
        canonical_job("one"),
        canonical_job(
            "two",
            employer_id="other",
            employer_name="Other Employer",
            parent_company=None,
            target=False,
            early=False,
            inferred_level="ambiguous",
            workplace_type="unknown",
            province=None,
        ),
    ]
    skills = [
        skill("one", "Python", "programming_language"),
        skill("one", "SQL", "programming_language"),
    ]
    requirements = [requirement("one"), requirement("two")]

    result = build_analytics_rows(jobs, skills, requirements)

    assert len(result.jobs) == 2
    assert len(result.skills) == 2
    first = result.jobs[0]
    assert first["job_key"] == "one"
    assert first["employer_group"] == "Example Holdings"
    assert first["location_label"] == "Cape Town, Western Cape"
    assert first["effective_role_level"] == "junior"
    assert first["is_early_career_target"] is True
    assert first["skills"] == ["Python", "SQL"]
    assert first["skill_count"] == 2
    assert first["capabilities"] == ["Data Storage", "Programming"]
    assert first["degree_required"] is True

    second = result.jobs[1]
    assert second["employer_group"] == "Other Employer"
    assert second["effective_role_level"] == "junior"
    assert second["is_early_career_target"] is False
    assert second["skill_count"] == 0

    sql_row = next(row for row in result.skills if row["technology"] == "SQL")
    assert sql_row["technology_category"] == "query_language"
    assert sql_row["capability"] == "Data Storage"
    assert sql_row["employer_id"] == "example-tech"

    report = result.quality_report
    assert report["schema_version"] == 1
    assert report["dashboard_job_count"] == 2
    assert report["dashboard_skill_row_count"] == 2
    assert report["target_market_job_count"] == 1
    assert report["early_career_target_job_count"] == 1
    assert report["unique_technology_count"] == 2
    assert report["target_skill_coverage_rate"] == 1.0
    assert "small_early_career_sample" in report["warnings"]


def test_build_rejects_duplicate_canonical_job_keys() -> None:
    jobs = [canonical_job("duplicate"), canonical_job("duplicate")]

    with pytest.raises(AnalyticsBuildError, match="duplicate job_key"):
        build_analytics_rows(
            jobs,
            [],
            [requirement("duplicate")],
        )


def test_build_rejects_orphan_skill_rows() -> None:
    with pytest.raises(AnalyticsBuildError, match="orphan row"):
        build_analytics_rows(
            [canonical_job("one")],
            [skill("missing", "Python", "programming_language")],
            [requirement("one")],
        )


def test_build_rejects_duplicate_job_skill_pairs() -> None:
    duplicate_skill = skill("one", "Python", "programming_language")

    with pytest.raises(AnalyticsBuildError, match="duplicate job-skill pair"):
        build_analytics_rows(
            [canonical_job("one")],
            [duplicate_skill, dict(duplicate_skill)],
            [requirement("one")],
        )


def test_build_rejects_missing_requirement_rows() -> None:
    with pytest.raises(AnalyticsBuildError, match="missing canonical jobs"):
        build_analytics_rows(
            [canonical_job("one"), canonical_job("two")],
            [],
            [requirement("one")],
        )


def test_build_rejects_stale_skill_extraction() -> None:
    stale = skill("one", "Python", "programming_language")
    stale["job_text_sha256"] = "stale"

    with pytest.raises(AnalyticsBuildError, match="stale extraction data"):
        build_analytics_rows(
            [canonical_job("one")],
            [stale],
            [requirement("one")],
        )


def test_build_rejects_stale_requirement_extraction() -> None:
    stale = requirement("one")
    stale["job_text_sha256"] = "stale"

    with pytest.raises(AnalyticsBuildError, match="stale extraction data"):
        build_analytics_rows(
            [canonical_job("one")],
            [],
            [stale],
        )


def test_build_rejects_missing_employer_metadata() -> None:
    job = canonical_job("one", employer_id="")

    with pytest.raises(AnalyticsBuildError, match="employer metadata"):
        build_analytics_rows([job], [], [requirement("one")])


@pytest.mark.skipif(
    importlib.util.find_spec("pyarrow") is None,
    reason="pyarrow is installed from requirements in the project environment",
)
def test_write_outputs_creates_schema_controlled_parquet(tmp_path: Path) -> None:
    import pyarrow.parquet as pq

    result = build_analytics_rows(
        [canonical_job("one")],
        [skill("one", "Python", "programming_language")],
        [requirement("one")],
    )

    jobs_path, skills_path, quality_path = write_outputs(result, tmp_path)

    jobs_table = pq.read_table(jobs_path)
    skills_table = pq.read_table(skills_path)
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    assert jobs_table.num_rows == 1
    assert skills_table.num_rows == 1
    assert "employer_group" in jobs_table.column_names
    assert "capability" in skills_table.column_names
    assert quality["dashboard_job_count"] == 1
