from __future__ import annotations

import importlib.util

import pandas as pd
import pytest


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("plotly") is None,
    reason="Plotly is installed from requirements",
)


def test_horizontal_bar_builds_one_trace() -> None:
    from src.dashboard.charts import horizontal_bar

    figure = horizontal_bar(
        pd.DataFrame({"label": ["Python", "SQL"], "count": [8, 5]}),
        label="label",
        value="count",
        title="Technology demand",
    )

    assert len(figure.data) == 1
    assert figure.layout.title.text == "Technology demand"


def test_empty_chart_explains_missing_data() -> None:
    from src.dashboard.charts import horizontal_bar

    figure = horizontal_bar(
        pd.DataFrame(columns=["label", "count"]),
        label="label",
        value="count",
        title="Empty",
    )

    assert figure.layout.annotations[0].text == "No data for the selected filters"
