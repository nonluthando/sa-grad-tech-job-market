"""Reusable Plotly chart builders for the Streamlit dashboard."""

from __future__ import annotations

from typing import Any


DARK_TEMPLATE = "plotly_dark"
ACCENT = "#2DD4BF"
SECONDARY = "#60A5FA"
GOLD = "#FBBF24"
MUTED = "#94A3B8"


def _px() -> Any:
    import plotly.express as px

    return px


def _go() -> Any:
    import plotly.graph_objects as go

    return go


def empty_figure(message: str) -> Any:
    go = _go()
    figure = go.Figure()
    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 16, "color": MUTED},
    )
    figure.update_layout(
        template=DARK_TEMPLATE,
        height=360,
        xaxis={"visible": False},
        yaxis={"visible": False},
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
    )
    return figure


def horizontal_bar(
    frame: Any,
    *,
    label: str,
    value: str,
    title: str,
    height: int = 430,
) -> Any:
    if frame is None or frame.empty:
        return empty_figure("No data for the selected filters")
    data = frame.sort_values(value, ascending=True)
    px = _px()
    figure = px.bar(
        data,
        x=value,
        y=label,
        orientation="h",
        text=value,
        title=title,
        color_discrete_sequence=[ACCENT],
    )
    figure.update_traces(textposition="outside", cliponaxis=False)
    figure.update_layout(
        template=DARK_TEMPLATE,
        height=height,
        xaxis_title="Vacancies" if value == "count" else value.replace("_", " ").title(),
        yaxis_title=None,
        showlegend=False,
        margin={"l": 20, "r": 45, "t": 55, "b": 30},
    )
    return figure


def donut(
    frame: Any,
    *,
    label: str,
    value: str,
    title: str,
) -> Any:
    if frame is None or frame.empty:
        return empty_figure("No data for the selected filters")
    px = _px()
    figure = px.pie(
        frame,
        names=label,
        values=value,
        hole=0.62,
        title=title,
        color_discrete_sequence=[ACCENT, SECONDARY, GOLD, "#A78BFA", "#FB7185"],
    )
    figure.update_traces(textposition="inside", textinfo="percent+label")
    figure.update_layout(
        template=DARK_TEMPLATE,
        height=430,
        legend_title=None,
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
    )
    return figure


def timeline(frame: Any, *, title: str) -> Any:
    if frame is None or frame.empty:
        return empty_figure("No activity dates for the selected filters")
    px = _px()
    figure = px.line(
        frame,
        x="month",
        y="vacancies",
        markers=True,
        title=title,
        color_discrete_sequence=[ACCENT],
    )
    figure.update_traces(line={"width": 3}, marker={"size": 8})
    figure.update_layout(
        template=DARK_TEMPLATE,
        height=390,
        xaxis_title=None,
        yaxis_title="Vacancies observed",
        margin={"l": 20, "r": 20, "t": 55, "b": 30},
    )
    return figure


def heatmap(frame: Any, *, title: str) -> Any:
    if frame is None or frame.empty:
        return empty_figure("Not enough skill data for a heatmap")
    px = _px()
    figure = px.imshow(
        frame,
        text_auto=True,
        aspect="auto",
        title=title,
        color_continuous_scale="Teal",
    )
    figure.update_layout(
        template=DARK_TEMPLATE,
        height=500,
        xaxis_title="Technology",
        yaxis_title="Role level",
        coloraxis_colorbar_title="Mentions",
        margin={"l": 20, "r": 20, "t": 55, "b": 30},
    )
    return figure
