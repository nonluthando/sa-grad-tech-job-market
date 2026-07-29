"""Reusable Plotly chart builders for the Streamlit dashboard."""

from __future__ import annotations

from typing import Any


CHART_TEMPLATE = "plotly_white"
ACCENT = "#7A263A"
SECONDARY = "#536878"
GOLD = "#A56A2A"
MUTED = "#6B7280"
GRID = "#E3DED5"
PAPER = "#FFFFFF"
PALETTE = [ACCENT, SECONDARY, GOLD, "#6C5B7B", "#477A6E", "#9B4D3A"]


def _px() -> Any:
    import plotly.express as px

    return px


def _go() -> Any:
    import plotly.graph_objects as go

    return go


def _apply_layout(figure: Any, *, height: int, margin: dict[str, int]) -> Any:
    figure.update_layout(
        template=CHART_TEMPLATE,
        height=height,
        paper_bgcolor=PAPER,
        plot_bgcolor=PAPER,
        font={"color": "#20252B", "family": "Arial, sans-serif"},
        title={"font": {"size": 17}, "x": 0.0, "xanchor": "left"},
        margin=margin,
        hoverlabel={"bgcolor": "#20252B", "font_color": "#FFFFFF"},
    )
    figure.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    figure.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return figure


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
        font={"size": 15, "color": MUTED},
    )
    figure.update_layout(
        template=CHART_TEMPLATE,
        height=340,
        paper_bgcolor=PAPER,
        plot_bgcolor=PAPER,
        xaxis={"visible": False},
        yaxis={"visible": False},
        margin={"l": 20, "r": 20, "t": 25, "b": 20},
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
    figure.update_traces(
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0,
        hovertemplate="%{y}<br>%{x:,}<extra></extra>",
    )
    _apply_layout(
        figure,
        height=height,
        margin={"l": 18, "r": 52, "t": 55, "b": 30},
    )
    figure.update_layout(
        xaxis_title=(
            "Vacancies" if value == "count" else value.replace("_", " ").title()
        ),
        yaxis_title=None,
        showlegend=False,
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
        hole=0.68,
        title=title,
        color_discrete_sequence=PALETTE,
    )
    figure.update_traces(
        textposition="inside",
        textinfo="percent",
        hovertemplate="%{label}<br>%{value:,} vacancies<extra></extra>",
        marker={"line": {"color": PAPER, "width": 2}},
    )
    _apply_layout(
        figure,
        height=420,
        margin={"l": 18, "r": 18, "t": 55, "b": 20},
    )
    figure.update_layout(legend_title=None)
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
    figure.update_traces(
        line={"width": 2.5},
        marker={"size": 7, "line": {"width": 1, "color": PAPER}},
        hovertemplate="%{x|%b %Y}<br>%{y:,} vacancies<extra></extra>",
    )
    _apply_layout(
        figure,
        height=380,
        margin={"l": 18, "r": 18, "t": 55, "b": 30},
    )
    figure.update_layout(xaxis_title=None, yaxis_title="Vacancies observed")
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
        color_continuous_scale=[
            [0.0, "#F4F0EA"],
            [0.5, "#C7A9B1"],
            [1.0, ACCENT],
        ],
    )
    _apply_layout(
        figure,
        height=500,
        margin={"l": 18, "r": 18, "t": 55, "b": 30},
    )
    figure.update_layout(
        xaxis_title="Technology",
        yaxis_title="Role level",
        coloraxis_colorbar_title="Mentions",
    )
    return figure
