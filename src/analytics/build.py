"""Build validated, dashboard-ready analytics data marts.

The canonical jobs dataset remains the source of truth. This module joins it to
skills and requirements outputs, validates the relationships between them, and
writes compact tables designed for Streamlit and DuckDB.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable, Mapping, Sequence

from src.skills.dimensions import classify_skill_dimensions
from src.skills.lineage import job_text_sha256


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
DASHBOARD_SCHEMA_VERSION = 1
EARLY_CAREER_LEVELS = {"internship", "graduate", "junior"}
UNKNOWN_VALUES = {"", "unknown", "unspecified", "ambiguous", "none"}


class AnalyticsBuildError(ValueError):
    """Raised when processed inputs violate the dashboard data contract."""


@dataclass(frozen=True)
class AnalyticsBuildResult:
    """Validated dashboard rows and their reproducible quality report."""

    jobs: tuple[dict[str, Any], ...]
    skills: tuple[dict[str, Any], ...]
    quality_report: dict[str, Any]


REQUIRED_JOB_FIELDS = {
    "job_key",
    "source_provider",
    "source_name",
    "source_job_id",
    "first_seen_at",
    "last_seen_at",
    "source_updated_at",
    "observation_count",
    "title",
    "title_normalized",
    "company",
    "employer_id",
    "employer_name",
    "parent_company",
    "industry",
    "employer_priority",
    "graduate_programme",
    "city",
    "province",
    "country",
    "workplace_type",
    "role_level",
    "inferred_role_level",
    "role_level_confidence",
    "is_early_career",
    "is_target_market",
    "is_talent_pool",
    "application_url",
    "data_quality_issues",
    "description_text",
}
REQUIRED_SKILL_FIELDS = {
    "job_key",
    "job_text_sha256",
    "skill",
    "category",
}
REQUIRED_REQUIREMENT_FIELDS = {
    "job_key",
    "job_text_sha256",
    "degree_required",
    "degree_fields",
    "minimum_experience_years",
    "maximum_experience_years",
    "soft_skills",
    "extraction_warnings",
}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalised_label(value: Any, fallback: str = "unspecified") -> str:
    text = _clean_text(value)
    return text if text else fallback


def _sorted_unique(values: Iterable[Any]) -> list[str]:
    by_key: dict[str, str] = {}
    for value in values:
        text = _clean_text(value)
        if text:
            by_key.setdefault(text.casefold(), text)
    return [by_key[key] for key in sorted(by_key)]


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Sequence):
        return _sorted_unique(value)
    return [_clean_text(value)] if _clean_text(value) else []


def _require_fields(
    rows: Sequence[Mapping[str, Any]],
    required_fields: set[str],
    dataset_name: str,
) -> None:
    for index, row in enumerate(rows):
        missing = sorted(required_fields.difference(row))
        if missing:
            raise AnalyticsBuildError(
                f"{dataset_name} row {index} is missing fields: {', '.join(missing)}"
            )


def _index_jobs(jobs: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    if not jobs:
        raise AnalyticsBuildError("jobs.parquet contains no canonical jobs")

    _require_fields(jobs, REQUIRED_JOB_FIELDS, "jobs.parquet")
    index: dict[str, Mapping[str, Any]] = {}
    for position, job in enumerate(jobs):
        job_key = _clean_text(job.get("job_key"))
        if not job_key:
            raise AnalyticsBuildError(
                f"jobs.parquet row {position} has an empty job_key"
            )
        if job_key in index:
            raise AnalyticsBuildError(
                f"jobs.parquet contains duplicate job_key {job_key!r}"
            )

        employer_id = _clean_text(job.get("employer_id"))
        employer_name = _clean_text(job.get("employer_name"))
        if not employer_id or not employer_name:
            raise AnalyticsBuildError(
                f"Job {job_key!r} is missing canonical employer metadata"
            )
        index[job_key] = job
    return index


def _normalise_skill_row(row: Mapping[str, Any]) -> dict[str, Any]:
    skill = _clean_text(row.get("skill"))
    category = _clean_text(row.get("category"))
    if not skill or not category:
        raise AnalyticsBuildError(
            "job_skills.parquet contains an empty skill or category"
        )

    default_category, default_capability = classify_skill_dimensions(
        skill,
        category,
    )
    return {
        **dict(row),
        "skill": skill,
        "category": category,
        "technology": _clean_text(row.get("technology")) or skill,
        "technology_category": (
            _clean_text(row.get("technology_category")) or default_category
        ),
        "capability": _clean_text(row.get("capability")) or default_capability,
        "evidence": _string_list(row.get("evidence")),
    }


def _index_skills(
    rows: Sequence[Mapping[str, Any]],
    job_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    _require_fields(rows, REQUIRED_SKILL_FIELDS, "job_skills.parquet")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()

    for position, raw_row in enumerate(rows):
        job_key = _clean_text(raw_row.get("job_key"))
        if job_key not in job_index:
            raise AnalyticsBuildError(
                "job_skills.parquet contains an orphan row at index "
                f"{position}: {job_key!r}"
            )
        expected_hash = job_text_sha256(job_index[job_key])
        actual_hash = _clean_text(raw_row.get("job_text_sha256"))
        if actual_hash != expected_hash:
            raise AnalyticsBuildError(
                "job_skills.parquet contains stale extraction data for "
                f"{job_key!r}"
            )

        row = _normalise_skill_row(raw_row)
        pair = (job_key, row["technology"].casefold())
        if pair in seen:
            raise AnalyticsBuildError(
                "job_skills.parquet contains duplicate job-skill pair: "
                f"{job_key!r}, {row['technology']!r}"
            )
        seen.add(pair)
        grouped[job_key].append(row)

    for job_key in grouped:
        grouped[job_key].sort(
            key=lambda row: (
                row["capability"].casefold(),
                row["technology"].casefold(),
            )
        )
    return grouped


def _index_requirements(
    rows: Sequence[Mapping[str, Any]],
    job_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    _require_fields(rows, REQUIRED_REQUIREMENT_FIELDS, "job_requirements.parquet")
    index: dict[str, Mapping[str, Any]] = {}

    for position, row in enumerate(rows):
        job_key = _clean_text(row.get("job_key"))
        if job_key not in job_index:
            raise AnalyticsBuildError(
                "job_requirements.parquet contains an orphan row at index "
                f"{position}: {job_key!r}"
            )
        expected_hash = job_text_sha256(job_index[job_key])
        actual_hash = _clean_text(row.get("job_text_sha256"))
        if actual_hash != expected_hash:
            raise AnalyticsBuildError(
                "job_requirements.parquet contains stale extraction data for "
                f"{job_key!r}"
            )
        if job_key in index:
            raise AnalyticsBuildError(
                "job_requirements.parquet contains duplicate job_key "
                f"{job_key!r}"
            )
        index[job_key] = row

    missing = sorted(set(job_index).difference(index))
    if missing:
        preview = ", ".join(repr(value) for value in missing[:5])
        suffix = "" if len(missing) <= 5 else f" (+{len(missing) - 5} more)"
        raise AnalyticsBuildError(
            "job_requirements.parquet is missing canonical jobs: "
            f"{preview}{suffix}"
        )
    return index


def _effective_role_level(job: Mapping[str, Any]) -> str:
    inferred = _clean_text(job.get("inferred_role_level")).lower()
    if inferred not in UNKNOWN_VALUES:
        return inferred

    conservative = _clean_text(job.get("role_level")).lower()
    if conservative not in UNKNOWN_VALUES:
        return conservative
    return "unspecified"


def _location_label(job: Mapping[str, Any]) -> str:
    city = _clean_text(job.get("city"))
    province = _clean_text(job.get("province"))
    country = _clean_text(job.get("country"))
    if city and province and city.casefold() != province.casefold():
        return f"{city}, {province}"
    return city or province or country or "Unspecified"


def _employer_group(job: Mapping[str, Any]) -> str:
    return (
        _clean_text(job.get("parent_company"))
        or _clean_text(job.get("employer_name"))
        or _clean_text(job.get("company"))
        or "Unspecified"
    )


def _dashboard_job_row(
    job: Mapping[str, Any],
    skills: Sequence[Mapping[str, Any]],
    requirement: Mapping[str, Any],
) -> dict[str, Any]:
    effective_level = _effective_role_level(job)
    is_target = job.get("is_target_market") is True
    early_career_lens = is_target and (
        job.get("is_early_career") is True
        or effective_level in EARLY_CAREER_LEVELS
    )
    technologies = _sorted_unique(item["technology"] for item in skills)
    capabilities = _sorted_unique(item["capability"] for item in skills)
    technology_categories = _sorted_unique(
        item["technology_category"] for item in skills
    )
    issues = _string_list(job.get("data_quality_issues"))
    extraction_warnings = _string_list(requirement.get("extraction_warnings"))

    return {
        "job_key": _clean_text(job.get("job_key")),
        "source_provider": _normalised_label(job.get("source_provider")),
        "source_name": _normalised_label(job.get("source_name")),
        "source_job_id": _normalised_label(job.get("source_job_id")),
        "first_seen_at": job.get("first_seen_at"),
        "last_seen_at": job.get("last_seen_at"),
        "source_updated_at": job.get("source_updated_at"),
        "observation_count": int(job.get("observation_count") or 1),
        "title": _normalised_label(job.get("title")),
        "title_normalized": _normalised_label(job.get("title_normalized")),
        "employer_id": _clean_text(job.get("employer_id")),
        "employer_name": _clean_text(job.get("employer_name")),
        "employer_group": _employer_group(job),
        "industry": _normalised_label(job.get("industry")),
        "employer_priority": _normalised_label(job.get("employer_priority")),
        "graduate_programme": _normalised_label(job.get("graduate_programme")),
        "city": _clean_text(job.get("city")) or None,
        "province": _clean_text(job.get("province")) or None,
        "country": _clean_text(job.get("country")) or None,
        "location_label": _location_label(job),
        "workplace_type": _normalised_label(job.get("workplace_type")),
        "effective_role_level": effective_level,
        "role_level_confidence": _normalised_label(
            job.get("role_level_confidence"),
            fallback="low",
        ),
        "is_target_market": is_target,
        "is_early_career": job.get("is_early_career") is True,
        "is_early_career_target": early_career_lens,
        "is_talent_pool": job.get("is_talent_pool") is True,
        "application_url": _clean_text(job.get("application_url")),
        "skill_count": len(technologies),
        "skills": technologies,
        "technology_categories": technology_categories,
        "capabilities": capabilities,
        "degree_required": requirement.get("degree_required") is True,
        "degree_fields": _string_list(requirement.get("degree_fields")),
        "minimum_experience_years": requirement.get("minimum_experience_years"),
        "maximum_experience_years": requirement.get("maximum_experience_years"),
        "soft_skills": _string_list(requirement.get("soft_skills")),
        "data_quality_issue_count": len(issues),
        "data_quality_issues": issues,
        "extraction_warnings": extraction_warnings,
    }


def _dashboard_skill_row(
    job: Mapping[str, Any],
    skill: Mapping[str, Any],
) -> dict[str, Any]:
    effective_level = _effective_role_level(job)
    is_target = job.get("is_target_market") is True
    early_career_lens = is_target and (
        job.get("is_early_career") is True
        or effective_level in EARLY_CAREER_LEVELS
    )
    return {
        "job_key": _clean_text(job.get("job_key")),
        "title": _normalised_label(job.get("title")),
        "employer_id": _clean_text(job.get("employer_id")),
        "employer_name": _clean_text(job.get("employer_name")),
        "employer_group": _employer_group(job),
        "industry": _normalised_label(job.get("industry")),
        "city": _clean_text(job.get("city")) or None,
        "province": _clean_text(job.get("province")) or None,
        "workplace_type": _normalised_label(job.get("workplace_type")),
        "effective_role_level": effective_level,
        "is_target_market": is_target,
        "is_early_career_target": early_career_lens,
        "is_talent_pool": job.get("is_talent_pool") is True,
        "first_seen_at": job.get("first_seen_at"),
        "last_seen_at": job.get("last_seen_at"),
        "technology": skill["technology"],
        "technology_category": skill["technology_category"],
        "capability": skill["capability"],
        "evidence": _string_list(skill.get("evidence")),
        "application_url": _clean_text(job.get("application_url")),
    }


def _count(rows: Iterable[Mapping[str, Any]], field_name: str) -> dict[str, int]:
    counts = Counter(
        _normalised_label(row.get(field_name)).strip() for row in rows
    )
    return dict(sorted(counts.items()))


def _missing_count(rows: Sequence[Mapping[str, Any]], field_name: str) -> int:
    count = 0
    for row in rows:
        value = row.get(field_name)
        if value is None:
            count += 1
        elif isinstance(value, str) and value.strip().casefold() in UNKNOWN_VALUES:
            count += 1
    return count


def _build_quality_report(
    jobs: Sequence[Mapping[str, Any]],
    skill_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    target_jobs = [row for row in jobs if row["is_target_market"]]
    early_jobs = [row for row in jobs if row["is_early_career_target"]]
    jobs_with_skills = [row for row in jobs if row["skill_count"] > 0]
    target_with_skills = [
        row for row in target_jobs if row["skill_count"] > 0
    ]
    non_talent_target_jobs = [
        row for row in target_jobs if not row["is_talent_pool"]
    ]
    target_unknown_workplace = sum(
        row["workplace_type"].casefold() in UNKNOWN_VALUES for row in target_jobs
    )
    target_missing_province = sum(not row.get("province") for row in target_jobs)

    warnings: list[str] = []
    if not target_jobs:
        warnings.append("no_target_market_jobs")
    if len(early_jobs) < 10:
        warnings.append("small_early_career_sample")
    if target_jobs and len(target_with_skills) / len(target_jobs) < 0.70:
        warnings.append("low_target_market_skill_coverage")
    if target_jobs and target_unknown_workplace / len(target_jobs) > 0.25:
        warnings.append("high_unknown_workplace_share")
    if target_jobs and target_missing_province / len(target_jobs) > 0.25:
        warnings.append("high_missing_province_share")

    first_seen_values = [
        row.get("first_seen_at") for row in jobs if row.get("first_seen_at") is not None
    ]
    last_seen_values = [
        row.get("last_seen_at") for row in jobs if row.get("last_seen_at") is not None
    ]

    def as_iso(value: Any) -> str | None:
        return value.isoformat() if isinstance(value, datetime) else (
            str(value) if value is not None else None
        )

    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "source_window_start": as_iso(min(first_seen_values)) if first_seen_values else None,
        "source_window_end": as_iso(max(last_seen_values)) if last_seen_values else None,
        "dashboard_job_count": len(jobs),
        "dashboard_skill_row_count": len(skill_rows),
        "target_market_job_count": len(target_jobs),
        "non_talent_pool_target_market_job_count": len(non_talent_target_jobs),
        "early_career_target_job_count": len(early_jobs),
        "talent_pool_job_count": sum(row["is_talent_pool"] for row in jobs),
        "jobs_with_skills_count": len(jobs_with_skills),
        "jobs_without_skills_count": len(jobs) - len(jobs_with_skills),
        "target_jobs_with_skills_count": len(target_with_skills),
        "target_skill_coverage_rate": (
            len(target_with_skills) / len(target_jobs) if target_jobs else 0.0
        ),
        "unique_technology_count": len(
            {row["technology"] for row in skill_rows}
        ),
        "employer_count": len({row["employer_id"] for row in jobs}),
        "industry_count": len({row["industry"] for row in jobs}),
        "role_level_counts": _count(jobs, "effective_role_level"),
        "workplace_type_counts": _count(jobs, "workplace_type"),
        "employer_counts": _count(jobs, "employer_name"),
        "industry_counts": _count(jobs, "industry"),
        "province_counts": _count(jobs, "province"),
        "capability_mention_counts": _count(skill_rows, "capability"),
        "technology_mention_counts": _count(skill_rows, "technology"),
        "missing_value_counts": {
            field_name: _missing_count(jobs, field_name)
            for field_name in (
                "province",
                "workplace_type",
                "effective_role_level",
                "industry",
            )
        },
        "jobs_with_data_quality_issues_count": sum(
            row["data_quality_issue_count"] > 0 for row in jobs
        ),
        "jobs_with_extraction_warnings_count": sum(
            bool(row["extraction_warnings"]) for row in jobs
        ),
        "warnings": warnings,
    }


def build_analytics_rows(
    jobs: Sequence[Mapping[str, Any]],
    skills: Sequence[Mapping[str, Any]],
    requirements: Sequence[Mapping[str, Any]],
) -> AnalyticsBuildResult:
    """Validate processed rows and produce dashboard-facing data marts."""

    job_index = _index_jobs(jobs)
    skill_index = _index_skills(skills, job_index)
    requirement_index = _index_requirements(requirements, job_index)

    dashboard_jobs: list[dict[str, Any]] = []
    dashboard_skills: list[dict[str, Any]] = []
    for job_key in sorted(job_index):
        job = job_index[job_key]
        job_skills = skill_index.get(job_key, [])
        requirement = requirement_index[job_key]
        dashboard_jobs.append(_dashboard_job_row(job, job_skills, requirement))
        dashboard_skills.extend(
            _dashboard_skill_row(job, skill) for skill in job_skills
        )

    report = _build_quality_report(dashboard_jobs, dashboard_skills)
    return AnalyticsBuildResult(
        jobs=tuple(dashboard_jobs),
        skills=tuple(dashboard_skills),
        quality_report=report,
    )


def _read_parquet(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise AnalyticsBuildError(f"Required input does not exist: {path}")
    try:
        import pyarrow.parquet as pq
    except ImportError as error:
        raise RuntimeError(
            "Analytics output requires pyarrow. Run: uv pip install -r requirements.txt"
        ) from error
    return pq.read_table(path).to_pylist()


def _jobs_schema() -> Any:
    try:
        import pyarrow as pa
    except ImportError as error:
        raise RuntimeError(
            "Analytics output requires pyarrow. Run: uv pip install -r requirements.txt"
        ) from error

    return pa.schema(
        [
            ("job_key", pa.string()),
            ("source_provider", pa.string()),
            ("source_name", pa.string()),
            ("source_job_id", pa.string()),
            ("first_seen_at", pa.timestamp("us", tz="UTC")),
            ("last_seen_at", pa.timestamp("us", tz="UTC")),
            ("source_updated_at", pa.timestamp("us", tz="UTC")),
            ("observation_count", pa.int64()),
            ("title", pa.string()),
            ("title_normalized", pa.string()),
            ("employer_id", pa.string()),
            ("employer_name", pa.string()),
            ("employer_group", pa.string()),
            ("industry", pa.string()),
            ("employer_priority", pa.string()),
            ("graduate_programme", pa.string()),
            ("city", pa.string()),
            ("province", pa.string()),
            ("country", pa.string()),
            ("location_label", pa.string()),
            ("workplace_type", pa.string()),
            ("effective_role_level", pa.string()),
            ("role_level_confidence", pa.string()),
            ("is_target_market", pa.bool_()),
            ("is_early_career", pa.bool_()),
            ("is_early_career_target", pa.bool_()),
            ("is_talent_pool", pa.bool_()),
            ("application_url", pa.string()),
            ("skill_count", pa.int64()),
            ("skills", pa.list_(pa.string())),
            ("technology_categories", pa.list_(pa.string())),
            ("capabilities", pa.list_(pa.string())),
            ("degree_required", pa.bool_()),
            ("degree_fields", pa.list_(pa.string())),
            ("minimum_experience_years", pa.int64()),
            ("maximum_experience_years", pa.int64()),
            ("soft_skills", pa.list_(pa.string())),
            ("data_quality_issue_count", pa.int64()),
            ("data_quality_issues", pa.list_(pa.string())),
            ("extraction_warnings", pa.list_(pa.string())),
        ]
    )


def _skills_schema() -> Any:
    try:
        import pyarrow as pa
    except ImportError as error:
        raise RuntimeError(
            "Analytics output requires pyarrow. Run: uv pip install -r requirements.txt"
        ) from error

    return pa.schema(
        [
            ("job_key", pa.string()),
            ("title", pa.string()),
            ("employer_id", pa.string()),
            ("employer_name", pa.string()),
            ("employer_group", pa.string()),
            ("industry", pa.string()),
            ("city", pa.string()),
            ("province", pa.string()),
            ("workplace_type", pa.string()),
            ("effective_role_level", pa.string()),
            ("is_target_market", pa.bool_()),
            ("is_early_career_target", pa.bool_()),
            ("is_talent_pool", pa.bool_()),
            ("first_seen_at", pa.timestamp("us", tz="UTC")),
            ("last_seen_at", pa.timestamp("us", tz="UTC")),
            ("technology", pa.string()),
            ("technology_category", pa.string()),
            ("capability", pa.string()),
            ("evidence", pa.list_(pa.string())),
            ("application_url", pa.string()),
        ]
    )


def _atomic_parquet(path: Path, rows: Sequence[Mapping[str, Any]], schema: Any) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as error:
        raise RuntimeError(
            "Analytics output requires pyarrow. Run: uv pip install -r requirements.txt"
        ) from error

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist([dict(row) for row in rows], schema=schema)
    with NamedTemporaryFile(
        dir=path.parent,
        suffix=".parquet",
        delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
    try:
        pq.write_table(table, temporary_path, compression="zstd")
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary_file:
        temporary_path = Path(temporary_file.name)
        temporary_file.write(content.encode("utf-8"))
    temporary_path.replace(path)


def write_outputs(
    result: AnalyticsBuildResult,
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    """Write both dashboard tables and their quality report atomically."""

    jobs_path = output_dir / "dashboard_jobs.parquet"
    skills_path = output_dir / "dashboard_skills.parquet"
    quality_path = output_dir / "dashboard-quality-report.json"
    _atomic_parquet(jobs_path, result.jobs, _jobs_schema())
    _atomic_parquet(skills_path, result.skills, _skills_schema())
    _atomic_json(quality_path, result.quality_report)
    return jobs_path, skills_path, quality_path


def build(
    input_dir: Path = DEFAULT_INPUT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> AnalyticsBuildResult:
    """Read processed Parquet inputs, validate them and write dashboard marts."""

    jobs = _read_parquet(input_dir / "jobs.parquet")
    skills = _read_parquet(input_dir / "job_skills.parquet")
    requirements = _read_parquet(input_dir / "job_requirements.parquet")
    result = build_analytics_rows(jobs, skills, requirements)
    write_outputs(result, output_dir)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build validated dashboard-ready Parquet data marts."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def print_summary(result: AnalyticsBuildResult, output_dir: Path) -> None:
    report = result.quality_report
    print("\nDashboard data-mart summary")
    print("=" * 72)
    print(f"Dashboard jobs:          {report['dashboard_job_count']}")
    print(f"Target-market jobs:      {report['target_market_job_count']}")
    print(f"Early-career target:     {report['early_career_target_job_count']}")
    print(f"Dashboard skill rows:    {report['dashboard_skill_row_count']}")
    print(f"Unique technologies:     {report['unique_technology_count']}")
    print(f"Target skill coverage:   {report['target_skill_coverage_rate']:.1%}")
    print(f"Warnings:                {report['warnings']}")
    print(f"\nOutput directory: {output_dir}")


def main() -> int:
    args = parse_args()
    try:
        result = build(args.input_dir, args.output_dir)
    except (AnalyticsBuildError, OSError, RuntimeError) as error:
        print(f"Analytics build failed: {error}", file=sys.stderr)
        return 1

    print_summary(result, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
