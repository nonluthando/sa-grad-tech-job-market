from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/refresh-dashboard.yml")


def test_dashboard_workflow_runs_cloud_pipeline() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in content
    assert "schedule:" in content
    assert 'cron: "15 4 * * *"' in content
    assert "python -m src.ingestion.collect" in content
    assert "python -m src.transformation.build" in content
    assert "python -m src.skills.build" in content
    assert "python -m src.analytics.build" in content
    assert "data/processed/dashboard_jobs.parquet" in content
    assert "data/processed/dashboard_skills.parquet" in content
    assert "data/processed/dashboard-quality-report.json" in content


def test_dashboard_workflow_does_not_require_local_uv_project_files() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "actions/setup-python@v5" in content
    assert "python -m pip install -r requirements.txt" in content
    assert "uv run" not in content
