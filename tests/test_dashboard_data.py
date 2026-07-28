from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from src.dashboard.data import (
    DashboardDataError,
    DashboardFilters,
    DashboardPaths,
    DashboardRepository,
    build_where_clause,
    load_quality_report,
    normalise_multiselect,
)


def test_build_where_clause_applies_global_filters_safely() -> None:
    filters = DashboardFilters(
        employers=("Example Tech", "Other Employer"),
        industries=("Software",),
        provinces=("Western Cape",),
        workplace_types=("hybrid",),
        role_levels=("junior",),
        target_market_only=True,
        early_career_only=True,
        exclude_talent_pools=True,
        search="Python",
    )

    sql, parameters = build_where_clause(filters, dataset="jobs", alias="j")

    assert "j.employer_name IN (?, ?)" in sql
    assert "j.industry IN (?)" in sql
    assert "j.is_target_market = TRUE" in sql
    assert "j.is_early_career_target = TRUE" in sql
    assert "j.is_talent_pool = FALSE" in sql
    assert "LOWER(COALESCE(j.title, '')) LIKE ?" in sql
    assert "technology" not in sql
    assert parameters == [
        "Example Tech",
        "Other Employer",
        "Software",
        "Western Cape",
        "hybrid",
        "junior",
        "%python%",
        "%python%",
    ]


def test_skill_search_includes_technology() -> None:
    sql, parameters = build_where_clause(
        DashboardFilters(
            target_market_only=False,
            exclude_talent_pools=False,
            search="SQL",
        ),
        dataset="skills",
    )

    assert "d.technology" in sql
    assert parameters == ["%sql%", "%sql%", "%sql%"]


def test_empty_filters_produce_no_where_clause() -> None:
    sql, parameters = build_where_clause(
        DashboardFilters(
            target_market_only=False,
            exclude_talent_pools=False,
        ),
        dataset="jobs",
    )

    assert sql == ""
    assert parameters == []


def test_dashboard_paths_report_every_missing_input(tmp_path: Path) -> None:
    paths = DashboardPaths.from_directory(tmp_path)

    with pytest.raises(DashboardDataError, match="dashboard_jobs.parquet"):
        paths.validate()

    assert {path.name for path in paths.missing()} == {
        "dashboard_jobs.parquet",
        "dashboard_skills.parquet",
        "dashboard-quality-report.json",
    }


def test_quality_report_requires_dashboard_contract(tmp_path: Path) -> None:
    report_path = tmp_path / "dashboard-quality-report.json"
    report_path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    with pytest.raises(DashboardDataError, match="dashboard_job_count"):
        load_quality_report(report_path)


def test_normalise_multiselect_is_ordered_and_deduplicated() -> None:
    assert normalise_multiselect(["Python", " Python ", "", "SQL"]) == (
        "Python",
        "SQL",
    )


@pytest.mark.skipif(
    importlib.util.find_spec("duckdb") is None
    or importlib.util.find_spec("pyarrow") is None,
    reason="dashboard integration dependencies are installed from requirements",
)
def test_repository_filters_parquet_marts(tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    jobs = pa.Table.from_pylist(
        [
            {
                "job_key": "one",
                "title": "Junior Data Engineer",
                "employer_id": "example",
                "employer_name": "Example Tech",
                "employer_group": "Example Tech",
                "industry": "Software",
                "province": "Western Cape",
                "city": "Cape Town",
                "location_label": "Cape Town, Western Cape",
                "workplace_type": "hybrid",
                "effective_role_level": "junior",
                "is_target_market": True,
                "is_early_career_target": True,
                "is_talent_pool": False,
                "last_seen_at": None,
            },
            {
                "job_key": "two",
                "title": "Senior Engineer",
                "employer_id": "other",
                "employer_name": "Other",
                "employer_group": "Other",
                "industry": "Banking",
                "province": "Gauteng",
                "city": "Johannesburg",
                "location_label": "Johannesburg, Gauteng",
                "workplace_type": "office",
                "effective_role_level": "senior",
                "is_target_market": True,
                "is_early_career_target": False,
                "is_talent_pool": False,
                "last_seen_at": None,
            },
        ]
    )
    skills = pa.Table.from_pylist(
        [
            {
                "job_key": "one",
                "title": "Junior Data Engineer",
                "employer_name": "Example Tech",
                "industry": "Software",
                "province": "Western Cape",
                "workplace_type": "hybrid",
                "effective_role_level": "junior",
                "is_target_market": True,
                "is_early_career_target": True,
                "is_talent_pool": False,
                "technology": "Python",
                "capability": "Programming",
                "technology_category": "programming_language",
            }
        ]
    )
    pq.write_table(jobs, tmp_path / "dashboard_jobs.parquet")
    pq.write_table(skills, tmp_path / "dashboard_skills.parquet")
    (tmp_path / "dashboard-quality-report.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dashboard_job_count": 2,
                "dashboard_skill_row_count": 1,
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )

    repository = DashboardRepository(DashboardPaths.from_directory(tmp_path))
    frame = repository.jobs(
        DashboardFilters(
            role_levels=("junior",),
            early_career_only=True,
        )
    )

    assert frame["job_key"].tolist() == ["one"]
    assert repository.filter_options()["provinces"] == ["Gauteng", "Western Cape"]
