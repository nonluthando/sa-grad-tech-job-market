from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/refresh-dashboard.yml")


def test_dashboard_workflow_runs_cloud_pipeline() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in content
    assert "schedule:" in content
    assert 'cron: "15 4,12,20 * * *"' in content
    assert "python -m src.ingestion.collect" in content
    assert "python -m src.transformation.build" in content
    assert "python -m scripts.audit_unspecified" in content
    assert "python -m src.skills.build" in content
    assert "python -m src.analytics.build" in content
    assert "data/processed/dashboard_jobs.parquet" in content
    assert "data/processed/dashboard_skills.parquet" in content
    assert "data/processed/dashboard-quality-report.json" in content
    assert "timeout-minutes: 90" in content


def test_dashboard_workflow_does_not_require_local_uv_project_files() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "actions/setup-python@v5" in content
    assert "python -m pip install -r requirements.txt" in content
    assert "uv run" not in content


def test_dashboard_workflow_persists_raw_snapshot_history() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "git add -f" in content
    assert "data/raw" in content


def test_dashboard_workflow_publishes_unspecified_role_audit() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "data/analysis/unspecified-role-audit.csv" in content
    assert "data/analysis/unspecified-role-audit.md" in content
    assert "scripts/audit_unspecified.py" in content
