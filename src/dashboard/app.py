"""Streamlit application for South African graduate technology market data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.dashboard.charts import donut, heatmap, horizontal_bar, timeline
from src.dashboard.data import (
    DashboardDataError,
    DashboardFilters,
    DashboardPaths,
    DashboardRepository,
    normalise_multiselect,
)


APP_TITLE = "SA Graduate Tech Market"


@st.cache_data(show_spinner=False)
def load_options(data_dir: str) -> dict[str, list[str]]:
    repository = DashboardRepository(DashboardPaths.from_directory(Path(data_dir)))
    return repository.filter_options()


@st.cache_data(show_spinner="Querying the job market data…")
def load_filtered_data(
    data_dir: str,
    filters: DashboardFilters,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    repository = DashboardRepository(DashboardPaths.from_directory(Path(data_dir)))
    repository.validate()
    return (
        repository.jobs(filters),
        repository.skills(filters),
        repository.quality_report(),
    )


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 15% 0%, rgba(45,212,191,.12), transparent 28rem),
                #07111f;
        }
        [data-testid="stSidebar"] {
            background: #0b1727;
            border-right: 1px solid rgba(148,163,184,.16);
        }
        [data-testid="stMetric"] {
            background: linear-gradient(145deg, rgba(15,34,53,.95), rgba(9,25,42,.95));
            border: 1px solid rgba(45,212,191,.16);
            border-radius: 16px;
            padding: 1rem 1.1rem;
            box-shadow: 0 12px 35px rgba(0,0,0,.18);
        }
        [data-testid="stMetricValue"] { color: #f8fafc; }
        [data-testid="stMetricLabel"] { color: #94a3b8; }
        .hero {
            border: 1px solid rgba(45,212,191,.20);
            border-radius: 22px;
            padding: 1.4rem 1.6rem;
            background: linear-gradient(125deg, rgba(13,35,54,.98), rgba(7,25,42,.92));
            margin-bottom: 1rem;
        }
        .hero h1 { margin: 0; font-size: 2.05rem; color: #f8fafc; }
        .hero p { margin: .45rem 0 0; color: #a8b7c9; max-width: 58rem; }
        .eyebrow {
            color: #2dd4bf;
            text-transform: uppercase;
            letter-spacing: .12em;
            font-size: .72rem;
            font-weight: 800;
            margin-bottom: .45rem;
        }
        .section-note { color: #94a3b8; margin-top: -.6rem; margin-bottom: 1rem; }
        .quality-warning {
            border-left: 4px solid #fbbf24;
            background: rgba(251,191,36,.08);
            padding: .8rem 1rem;
            border-radius: 0 12px 12px 0;
            margin: .5rem 0;
        }
        .stTabs [data-baseweb="tab-list"] { gap: .35rem; flex-wrap: wrap; }
        .stTabs [data-baseweb="tab"] {
            background: rgba(15,34,53,.75);
            border-radius: 10px;
            padding: .5rem .8rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _sidebar(options: dict[str, list[str]]) -> DashboardFilters:
    st.sidebar.markdown("## Market lens")
    st.sidebar.caption("Filters apply across every dashboard view.")

    search = st.sidebar.text_input(
        "Search",
        placeholder="Role, employer or technology",
    )
    employers = st.sidebar.multiselect("Employers", options["employers"])
    industries = st.sidebar.multiselect("Industries", options["industries"])
    provinces = st.sidebar.multiselect("Provinces", options["provinces"])
    workplace = st.sidebar.multiselect(
        "Work arrangement",
        options["workplace_types"],
    )
    levels = st.sidebar.multiselect("Role levels", options["role_levels"])

    st.sidebar.markdown("### Scope")
    target_only = st.sidebar.toggle("South African tech roles only", value=True)
    early_only = st.sidebar.toggle("Early-career roles only", value=False)
    exclude_pools = st.sidebar.toggle("Exclude talent pools", value=True)

    return DashboardFilters(
        employers=normalise_multiselect(employers),
        industries=normalise_multiselect(industries),
        provinces=normalise_multiselect(provinces),
        workplace_types=normalise_multiselect(workplace),
        role_levels=normalise_multiselect(levels),
        target_market_only=target_only,
        early_career_only=early_only,
        exclude_talent_pools=exclude_pools,
        search=search,
    )


def _count_frame(frame: pd.DataFrame, column: str, limit: int = 15) -> pd.DataFrame:
    if frame.empty or column not in frame:
        return pd.DataFrame(columns=["label", "count"])
    values = frame[column].fillna("Unspecified").astype(str).str.strip()
    values = values.mask(values.eq(""), "Unspecified")
    return (
        values.value_counts(dropna=False)
        .head(limit)
        .rename_axis("label")
        .reset_index(name="count")
    )


def _metrics(jobs: pd.DataFrame, skills: pd.DataFrame) -> None:
    employer_count = jobs["employer_id"].nunique() if not jobs.empty else 0
    early_count = int(jobs["is_early_career_target"].sum()) if not jobs.empty else 0
    technology_count = skills["technology"].nunique() if not skills.empty else 0
    flexible_share = 0.0
    if not jobs.empty:
        flexible = jobs["workplace_type"].astype(str).str.casefold().isin(
            {"remote", "hybrid"}
        )
        flexible_share = float(flexible.mean())

    columns = st.columns(5)
    columns[0].metric("Vacancies", f"{len(jobs):,}")
    columns[1].metric("Employers", f"{employer_count:,}")
    columns[2].metric("Early-career", f"{early_count:,}")
    columns[3].metric("Technologies", f"{technology_count:,}")
    columns[4].metric("Remote / hybrid", f"{flexible_share:.0%}")


def _overview(jobs: pd.DataFrame, skills: pd.DataFrame) -> None:
    _metrics(jobs, skills)
    st.markdown("### Market shape")
    st.markdown(
        '<p class="section-note">How the filtered vacancy sample is distributed.</p>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.35, 1])
    with left:
        activity = pd.DataFrame(columns=["month", "vacancies"])
        if not jobs.empty:
            dates = pd.to_datetime(jobs["last_seen_at"], errors="coerce", utc=True)
            activity = (
                jobs.assign(month=dates.dt.to_period("M").dt.to_timestamp())
                .dropna(subset=["month"])
                .groupby("month", as_index=False)["job_key"]
                .nunique()
                .rename(columns={"job_key": "vacancies"})
            )
        st.plotly_chart(
            timeline(activity, title="Vacancy activity over time"),
            use_container_width=True,
        )
    with right:
        levels = _count_frame(jobs, "effective_role_level", limit=8)
        st.plotly_chart(
            donut(levels, label="label", value="count", title="Role levels"),
            use_container_width=True,
        )

    left, right = st.columns(2)
    with left:
        employers = _count_frame(jobs, "employer_name", limit=10)
        st.plotly_chart(
            horizontal_bar(
                employers,
                label="label",
                value="count",
                title="Top hiring employers",
            ),
            use_container_width=True,
        )
    with right:
        technologies = _count_frame(skills, "technology", limit=10)
        st.plotly_chart(
            horizontal_bar(
                technologies,
                label="label",
                value="count",
                title="Most requested technologies",
            ),
            use_container_width=True,
        )


def _employers(jobs: pd.DataFrame) -> None:
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            horizontal_bar(
                _count_frame(jobs, "employer_name", 15),
                label="label",
                value="count",
                title="Vacancies by employer",
                height=520,
            ),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(
            horizontal_bar(
                _count_frame(jobs, "industry", 15),
                label="label",
                value="count",
                title="Vacancies by industry",
                height=520,
            ),
            use_container_width=True,
        )

    if not jobs.empty:
        summary = (
            jobs.groupby(["employer_name", "industry"], dropna=False)
            .agg(
                vacancies=("job_key", "nunique"),
                early_career=("is_early_career_target", "sum"),
                provinces=("province", "nunique"),
                technologies=("skill_count", "sum"),
            )
            .reset_index()
            .sort_values(["vacancies", "employer_name"], ascending=[False, True])
        )
        st.markdown("### Employer comparison")
        st.dataframe(summary, hide_index=True, use_container_width=True)


def _skills(jobs: pd.DataFrame, skills: pd.DataFrame) -> None:
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            horizontal_bar(
                _count_frame(skills, "technology", 18),
                label="label",
                value="count",
                title="Technology demand",
                height=600,
            ),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(
            horizontal_bar(
                _count_frame(skills, "capability", 18),
                label="label",
                value="count",
                title="Capability demand",
                height=600,
            ),
            use_container_width=True,
        )

    if not skills.empty:
        top_technologies = skills["technology"].value_counts().head(12).index
        matrix_source = skills[skills["technology"].isin(top_technologies)]
        matrix = pd.crosstab(
            matrix_source["effective_role_level"],
            matrix_source["technology"],
        )
        st.plotly_chart(
            heatmap(matrix, title="Technology mentions by role level"),
            use_container_width=True,
        )


def _early_career(jobs: pd.DataFrame) -> None:
    early = jobs[jobs["is_early_career_target"] == True].copy()  # noqa: E712
    if early.empty:
        st.info("No early-career vacancies match the current filters.")
        return

    columns = st.columns(4)
    columns[0].metric("Early-career roles", f"{len(early):,}")
    columns[1].metric("Employers hiring", f"{early['employer_id'].nunique():,}")
    columns[2].metric("Graduate programmes", f"{(early['graduate_programme'] == 'yes').sum():,}")
    columns[3].metric("Degree required", f"{early['degree_required'].mean():.0%}")

    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            horizontal_bar(
                _count_frame(early, "employer_name", 12),
                label="label",
                value="count",
                title="Employers hiring early-career talent",
            ),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(
            horizontal_bar(
                _count_frame(early, "province", 12),
                label="label",
                value="count",
                title="Early-career opportunities by province",
            ),
            use_container_width=True,
        )


def _locations(jobs: pd.DataFrame) -> None:
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            horizontal_bar(
                _count_frame(jobs, "province", 12),
                label="label",
                value="count",
                title="Vacancies by province",
            ),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(
            donut(
                _count_frame(jobs, "workplace_type", 8),
                label="label",
                value="count",
                title="Work arrangement",
            ),
            use_container_width=True,
        )

    st.plotly_chart(
        horizontal_bar(
            _count_frame(jobs, "location_label", 18),
            label="label",
            value="count",
            title="Top vacancy locations",
            height=580,
        ),
        use_container_width=True,
    )


def _opportunities(jobs: pd.DataFrame) -> None:
    if jobs.empty:
        st.info("No vacancies match the current filters.")
        return

    display = jobs[
        [
            "title",
            "employer_name",
            "location_label",
            "workplace_type",
            "effective_role_level",
            "skills",
            "last_seen_at",
            "application_url",
        ]
    ].copy()
    def format_skills(values: Any) -> str:
        if values is None:
            return ""
        if hasattr(values, "tolist"):
            values = values.tolist()
        if isinstance(values, (list, tuple, set)):
            return ", ".join(str(value) for value in values if str(value).strip())
        return str(values)

    display["skills"] = display["skills"].apply(format_skills)
    display = display.rename(
        columns={
            "title": "Role",
            "employer_name": "Employer",
            "location_label": "Location",
            "workplace_type": "Work arrangement",
            "effective_role_level": "Level",
            "skills": "Technologies",
            "last_seen_at": "Last seen",
            "application_url": "Apply",
        }
    )
    st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Apply": st.column_config.LinkColumn("Apply", display_text="Open role"),
            "Last seen": st.column_config.DatetimeColumn("Last seen", format="D MMM YYYY"),
        },
    )


def _quality(jobs: pd.DataFrame, report: dict[str, Any]) -> None:
    columns = st.columns(4)
    columns[0].metric("Mart rows", f"{report.get('dashboard_job_count', 0):,}")
    columns[1].metric("Skill rows", f"{report.get('dashboard_skill_row_count', 0):,}")
    columns[2].metric("Skill coverage", f"{report.get('target_skill_coverage_rate', 0):.0%}")
    columns[3].metric("Current filtered rows", f"{len(jobs):,}")

    warnings = report.get("warnings", [])
    st.markdown("### Validation warnings")
    if warnings:
        for warning in warnings:
            st.markdown(
                f'<div class="quality-warning">{str(warning).replace("_", " ").title()}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.success("No dashboard quality warnings were reported.")

    missing = report.get("missing_value_counts", {})
    if missing:
        missing_frame = pd.DataFrame(
            sorted(missing.items(), key=lambda item: item[1], reverse=True),
            columns=["Field", "Missing values"],
        )
        st.plotly_chart(
            horizontal_bar(
                missing_frame.rename(columns={"Field": "label", "Missing values": "count"}),
                label="label",
                value="count",
                title="Missing dashboard dimensions",
            ),
            use_container_width=True,
        )

    st.caption(
        "The dashboard represents configured public employer career portals, not every technology vacancy in South Africa."
    )


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_css()

    data_dir = str(Path("data/processed").resolve())
    paths = DashboardPaths.from_directory(Path(data_dir))

    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">South African technology hiring intelligence</div>
          <h1>Graduate Tech Job Market</h1>
          <p>Explore vacancies, employers, technologies and early-career access across the project’s configured public career sources.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        paths.validate()
        options = load_options(data_dir)
        filters = _sidebar(options)
        jobs, skills, quality = load_filtered_data(data_dir, filters)
    except DashboardDataError as error:
        st.error(str(error))
        st.code(
            "uv run python -m src.transformation.build\n"
            "uv run python -m src.skills.build\n"
            "uv run python -m src.analytics.build",
            language="bash",
        )
        st.stop()

    st.caption(
        f"Showing {len(jobs):,} vacancies and {len(skills):,} vacancy–technology mentions after filters."
    )

    tabs = st.tabs(
        [
            "Overview",
            "Employers",
            "Skills",
            "Early career",
            "Locations & work",
            "Opportunities",
            "Data quality",
        ]
    )
    with tabs[0]:
        _overview(jobs, skills)
    with tabs[1]:
        _employers(jobs)
    with tabs[2]:
        _skills(jobs, skills)
    with tabs[3]:
        _early_career(jobs)
    with tabs[4]:
        _locations(jobs)
    with tabs[5]:
        _opportunities(jobs)
    with tabs[6]:
        _quality(jobs, quality)


if __name__ == "__main__":
    main()
