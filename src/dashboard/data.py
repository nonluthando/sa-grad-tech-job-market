"""DuckDB-backed access to dashboard-ready Parquet data marts.

The Streamlit layer deliberately contains no transformation logic. This module
validates the Patch 6.2 outputs, builds parameterised filters and lets DuckDB
query the Parquet files directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "processed"
DatasetName = Literal["jobs", "skills"]


class DashboardDataError(RuntimeError):
    """Raised when dashboard inputs are missing or fail their data contract."""


@dataclass(frozen=True)
class DashboardPaths:
    """Paths to the three Patch 6.2 dashboard outputs."""

    jobs: Path
    skills: Path
    quality: Path

    @classmethod
    def from_directory(cls, directory: Path = DEFAULT_DATA_DIR) -> "DashboardPaths":
        return cls(
            jobs=directory / "dashboard_jobs.parquet",
            skills=directory / "dashboard_skills.parquet",
            quality=directory / "dashboard-quality-report.json",
        )

    def missing(self) -> tuple[Path, ...]:
        return tuple(
            path
            for path in (self.jobs, self.skills, self.quality)
            if not path.is_file()
        )

    def validate(self) -> None:
        missing = self.missing()
        if missing:
            names = ", ".join(path.name for path in missing)
            raise DashboardDataError(
                "Dashboard data has not been built. Missing: " + names
            )


@dataclass(frozen=True)
class DashboardFilters:
    """Global dashboard filters shared by jobs and skills queries."""

    employers: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()
    provinces: tuple[str, ...] = ()
    workplace_types: tuple[str, ...] = ()
    role_levels: tuple[str, ...] = ()
    target_market_only: bool = True
    early_career_only: bool = False
    exclude_talent_pools: bool = True
    search: str = ""


FILTER_COLUMNS = {
    "employers": "employer_name",
    "industries": "industry",
    "provinces": "province",
    "workplace_types": "workplace_type",
    "role_levels": "effective_role_level",
}

OPTION_FIELDS = {
    "employers": "employer_name",
    "industries": "industry",
    "provinces": "province",
    "workplace_types": "workplace_type",
    "role_levels": "effective_role_level",
}


def _sql_path(path: Path) -> str:
    """Return a quoted DuckDB-safe local path literal."""

    return str(path.resolve()).replace("'", "''").replace("\\", "/")


def _placeholders(values: Sequence[str]) -> str:
    return ", ".join("?" for _ in values)


def build_where_clause(
    filters: DashboardFilters,
    *,
    dataset: DatasetName,
    alias: str = "d",
) -> tuple[str, list[Any]]:
    """Build a parameterised WHERE clause for one dashboard dataset."""

    conditions: list[str] = []
    parameters: list[Any] = []

    for attribute, column in FILTER_COLUMNS.items():
        values = tuple(
            str(value).strip()
            for value in getattr(filters, attribute)
            if str(value).strip()
        )
        if values:
            conditions.append(
                f"{alias}.{column} IN ({_placeholders(values)})"
            )
            parameters.extend(values)

    if filters.target_market_only:
        conditions.append(f"{alias}.is_target_market = TRUE")
    if filters.early_career_only:
        conditions.append(f"{alias}.is_early_career_target = TRUE")
    if filters.exclude_talent_pools:
        conditions.append(f"{alias}.is_talent_pool = FALSE")

    search = filters.search.strip().casefold()
    if search:
        searchable = [
            f"LOWER(COALESCE({alias}.title, '')) LIKE ?",
            f"LOWER(COALESCE({alias}.employer_name, '')) LIKE ?",
        ]
        if dataset == "skills":
            searchable.append(
                f"LOWER(COALESCE({alias}.technology, '')) LIKE ?"
            )
        conditions.append("(" + " OR ".join(searchable) + ")")
        pattern = f"%{search}%"
        parameters.extend(pattern for _ in searchable)

    if not conditions:
        return "", parameters
    return " WHERE " + " AND ".join(conditions), parameters


def load_quality_report(path: Path) -> dict[str, Any]:
    """Read and minimally validate the analytics quality report."""

    if not path.is_file():
        raise DashboardDataError(f"Missing quality report: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DashboardDataError(
            f"Could not read dashboard quality report: {error}"
        ) from error

    required = {
        "schema_version",
        "dashboard_job_count",
        "dashboard_skill_row_count",
        "warnings",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise DashboardDataError(
            "Dashboard quality report is missing: " + ", ".join(missing)
        )
    return payload


def _import_duckdb() -> Any:
    try:
        import duckdb
    except ImportError as error:
        raise DashboardDataError(
            "DuckDB is required for the dashboard. Install requirements.txt."
        ) from error
    return duckdb


class DashboardRepository:
    """Query dashboard Parquet marts without loading the full files eagerly."""

    def __init__(self, paths: DashboardPaths | None = None) -> None:
        self.paths = paths or DashboardPaths.from_directory()

    def validate(self) -> None:
        self.paths.validate()
        load_quality_report(self.paths.quality)

    def quality_report(self) -> dict[str, Any]:
        return load_quality_report(self.paths.quality)

    def _read_sql(self, dataset: DatasetName, alias: str = "d") -> str:
        path = self.paths.jobs if dataset == "jobs" else self.paths.skills
        return f"read_parquet('{_sql_path(path)}') AS {alias}"

    def _query(self, sql: str, parameters: Sequence[Any] = ()) -> Any:
        duckdb = _import_duckdb()
        connection = duckdb.connect(database=":memory:")
        try:
            return connection.execute(sql, list(parameters)).df()
        except Exception as error:
            raise DashboardDataError(f"Dashboard query failed: {error}") from error
        finally:
            connection.close()

    def filter_options(self) -> dict[str, list[str]]:
        """Return stable global filter choices from the jobs mart."""

        self.paths.validate()
        result: dict[str, list[str]] = {}
        relation = self._read_sql("jobs")
        for name, field in OPTION_FIELDS.items():
            sql = f"""
                SELECT DISTINCT {field} AS value
                FROM {relation}
                WHERE {field} IS NOT NULL
                  AND TRIM(CAST({field} AS VARCHAR)) <> ''
                  AND LOWER(TRIM(CAST({field} AS VARCHAR))) NOT IN
                      ('unknown', 'unspecified', 'none')
                ORDER BY value
            """
            frame = self._query(sql)
            result[name] = [str(value) for value in frame["value"].tolist()]
        return result

    def jobs(self, filters: DashboardFilters) -> Any:
        """Return filtered vacancy rows ordered by latest observation."""

        self.paths.validate()
        where, parameters = build_where_clause(filters, dataset="jobs", alias="j")
        sql = f"""
            SELECT *
            FROM {self._read_sql('jobs', alias='j')}
            {where}
            ORDER BY last_seen_at DESC NULLS LAST, employer_name, title
        """
        return self._query(sql, parameters)

    def skills(self, filters: DashboardFilters) -> Any:
        """Return filtered vacancy-technology rows."""

        self.paths.validate()
        where, parameters = build_where_clause(filters, dataset="skills", alias="s")
        sql = f"""
            SELECT *
            FROM {self._read_sql('skills', alias='s')}
            {where}
            ORDER BY technology, employer_name, title
        """
        return self._query(sql, parameters)

    def top_values(
        self,
        field: str,
        filters: DashboardFilters,
        *,
        dataset: DatasetName = "jobs",
        limit: int = 15,
    ) -> Any:
        """Aggregate a supported dashboard dimension inside DuckDB."""

        supported = {
            "employer_name",
            "employer_group",
            "industry",
            "province",
            "city",
            "workplace_type",
            "effective_role_level",
            "technology",
            "capability",
            "technology_category",
        }
        if field not in supported:
            raise ValueError(f"Unsupported dashboard dimension: {field}")
        if limit < 1:
            raise ValueError("limit must be at least 1")

        alias = "d"
        where, parameters = build_where_clause(
            filters,
            dataset=dataset,
            alias=alias,
        )
        sql = f"""
            SELECT {alias}.{field} AS label, COUNT(*) AS count
            FROM {self._read_sql(dataset, alias=alias)}
            {where}
            AND {alias}.{field} IS NOT NULL
            AND TRIM(CAST({alias}.{field} AS VARCHAR)) <> ''
            GROUP BY {alias}.{field}
            ORDER BY count DESC, label
            LIMIT ?
        """ if where else f"""
            SELECT {alias}.{field} AS label, COUNT(*) AS count
            FROM {self._read_sql(dataset, alias=alias)}
            WHERE {alias}.{field} IS NOT NULL
              AND TRIM(CAST({alias}.{field} AS VARCHAR)) <> ''
            GROUP BY {alias}.{field}
            ORDER BY count DESC, label
            LIMIT ?
        """
        return self._query(sql, [*parameters, limit])


def normalise_multiselect(values: Iterable[Any]) -> tuple[str, ...]:
    """Convert Streamlit multiselect output into stable immutable filters."""

    return tuple(
        dict.fromkeys(
            str(value).strip() for value in values if str(value).strip()
        )
    )
