from __future__ import annotations

from pathlib import Path


APP = Path("src/dashboard/app.py")
CHARTS = Path("src/dashboard/charts.py")


def test_dashboard_uses_clean_neutral_product_style() -> None:
    app = APP.read_text(encoding="utf-8")
    charts = CHARTS.read_text(encoding="utf-8")

    assert "South African tech jobs" in app
    assert "Current vacancies collected directly from employer career sites." in app
    assert "#2563eb" in app.lower()
    assert "#2563EB" in charts
    assert "Georgia" not in app
    assert "Times New Roman" not in app
    assert "linear-gradient" not in app
    assert "Employer-direct labour market data" not in app


def test_dashboard_quality_view_includes_source_coverage() -> None:
    app = APP.read_text(encoding="utf-8")

    assert '"source_name"' in app
    assert '"source_provider"' in app
    assert "Rows by source" in app
    assert "Rows by collection platform" in app
