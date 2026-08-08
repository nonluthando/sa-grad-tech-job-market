from __future__ import annotations

from pathlib import Path


APP = Path("src/dashboard/app.py")


def test_opportunities_table_shows_first_seen_date() -> None:
    app = APP.read_text(encoding="utf-8")
    opportunities = app.split("def _opportunities", 1)[1].split(
        "def _quality", 1
    )[0]

    assert '"first_seen_at"' in opportunities
    assert '"first_seen_at": "First seen"' in opportunities
    assert '"First seen": st.column_config.DatetimeColumn(' in opportunities
    assert '"last_seen_at": "Last seen"' in opportunities


def test_unspecified_role_filter_renders_audit_output() -> None:
    app = APP.read_text(encoding="utf-8")

    assert "unspecified-role-audit.csv" in app
    assert "def _render_unspecified_audit" in app
    assert '"Audit suggestion"' in app
    assert "Audit suggestions do not overwrite canonical labels." in app
    assert "show_unspecified_audit=any(" in app
    assert 'str(level).casefold() == "unspecified"' in app
