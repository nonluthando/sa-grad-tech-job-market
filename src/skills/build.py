"""Build reusable skills and requirements datasets from canonical jobs."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping, Sequence

from src.skills.extractor import extract_job_enrichment
from src.skills.lineage import job_text_sha256

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "jobs.parquet"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed"
EARLY_CAREER_LEVELS = {"internship", "graduate", "junior"}


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    with NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        temp_path = Path(temp.name)
        temp.write(content.encode("utf-8"))
    temp_path.replace(path)


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    with NamedTemporaryFile(dir=path.parent, suffix=".parquet", delete=False) as temp:
        temp_path = Path(temp.name)
    try:
        pq.write_table(table, temp_path, compression="zstd")
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def _employer_name(job: Mapping[str, Any]) -> str:
    return str(job.get("employer_name") or job.get("company") or "").strip()


def build_rows(
    jobs: Sequence[Mapping[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    """Extract reusable rows from canonical jobs without performing file I/O."""

    skill_rows: list[dict[str, Any]] = []
    requirement_rows: list[dict[str, Any]] = []
    skill_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    early_counts: Counter[str] = Counter()
    legacy_category_counts: Counter[str] = Counter()
    technology_category_counts: Counter[str] = Counter()
    capability_counts: Counter[str] = Counter()
    warnings: Counter[str] = Counter()
    company_counts: dict[tuple[str, str, str], int] = defaultdict(int)

    jobs_with_skills = 0
    target_with_skills = 0

    for job in jobs:
        text_sha256 = job_text_sha256(job)
        enrichment = extract_job_enrichment(
            str(job.get("title") or ""),
            str(job.get("description_text") or ""),
        )
        warnings.update(enrichment.extraction_warnings)
        is_target = job.get("is_target_market") is True
        inferred = str(job.get("inferred_role_level") or "")
        is_early_target = is_target and (
            job.get("is_early_career") is True
            or inferred in EARLY_CAREER_LEVELS
        )
        employer_id = str(job.get("employer_id") or "").strip()
        employer_name = _employer_name(job)
        parent_company = job.get("parent_company")
        industry = str(job.get("industry") or "unspecified")

        if enrichment.skills:
            jobs_with_skills += 1
            if is_target:
                target_with_skills += 1

        for item in enrichment.skills:
            skill_counts[item.technology] += 1
            legacy_category_counts[item.category] += 1
            technology_category_counts[item.technology_category] += 1
            capability_counts[item.capability] += 1
            company_counts[(employer_id, employer_name, item.technology)] += 1
            if is_target:
                target_counts[item.technology] += 1
            if is_early_target:
                early_counts[item.technology] += 1

            skill_rows.append({
                "job_key": job.get("job_key"),
                "job_text_sha256": text_sha256,
                "company": job.get("company"),
                "employer_id": employer_id,
                "employer_name": employer_name,
                "parent_company": parent_company,
                "industry": industry,
                "title": job.get("title"),
                "city": job.get("city"),
                "province": job.get("province"),
                "workplace_type": job.get("workplace_type"),
                "role_level": job.get("role_level"),
                "inferred_role_level": inferred,
                "is_target_market": is_target,
                "is_early_career_target": is_early_target,
                "skill": item.skill,
                "category": item.category,
                "technology": item.technology,
                "technology_category": item.technology_category,
                "capability": item.capability,
                "evidence": list(item.evidence),
                "application_url": job.get("application_url"),
            })

        requirement_rows.append({
            "job_key": job.get("job_key"),
            "job_text_sha256": text_sha256,
            "company": job.get("company"),
            "employer_id": employer_id,
            "employer_name": employer_name,
            "parent_company": parent_company,
            "industry": industry,
            "title": job.get("title"),
            "city": job.get("city"),
            "province": job.get("province"),
            "workplace_type": job.get("workplace_type"),
            "role_level": job.get("role_level"),
            "inferred_role_level": inferred,
            "is_target_market": is_target,
            "is_early_career_target": is_early_target,
            "degree_required": enrichment.degree_required,
            "degree_fields": list(enrichment.degree_fields),
            "minimum_experience_years": enrichment.minimum_experience_years,
            "maximum_experience_years": enrichment.maximum_experience_years,
            "soft_skills": list(enrichment.soft_skills),
            "extraction_warnings": list(enrichment.extraction_warnings),
            "application_url": job.get("application_url"),
        })

    target_jobs = [job for job in jobs if job.get("is_target_market") is True]
    early_target_jobs = [
        job for job in target_jobs
        if job.get("is_early_career") is True
        or job.get("inferred_role_level") in EARLY_CAREER_LEVELS
    ]

    first_skill_row = {
        row["technology"]: row
        for row in skill_rows
    }
    summary_rows = []
    for technology in sorted(skill_counts):
        example = first_skill_row[technology]
        summary_rows.append({
            "skill": example["skill"],
            "category": example["category"],
            "technology": technology,
            "technology_category": example["technology_category"],
            "capability": example["capability"],
            "all_job_count": skill_counts[technology],
            "target_market_job_count": target_counts[technology],
            "early_career_target_job_count": early_counts[technology],
            "target_market_share": (
                target_counts[technology] / len(target_jobs) if target_jobs else 0.0
            ),
        })

    company_rows = [
        {
            "employer_id": employer_id,
            "employer_name": employer_name,
            "company": employer_name,
            "technology": technology,
            "skill": technology,
            "job_count": count,
        }
        for (employer_id, employer_name, technology), count
        in sorted(company_counts.items())
    ]

    report = {
        "canonical_job_count": len(jobs),
        "target_market_job_count": len(target_jobs),
        "early_career_target_job_count": len(early_target_jobs),
        "job_skill_row_count": len(skill_rows),
        "unique_skill_count": len(skill_counts),
        "jobs_with_skills_count": jobs_with_skills,
        "target_jobs_with_skills_count": target_with_skills,
        "target_skill_coverage_rate": (
            target_with_skills / len(target_jobs) if target_jobs else 0.0
        ),
        "technology_category_mention_counts": dict(
            sorted(technology_category_counts.items())
        ),
        "capability_mention_counts": dict(sorted(capability_counts.items())),
        # Retained for consumers of the pre-6.2 report contract.
        "category_mention_counts": dict(sorted(legacy_category_counts.items())),
        "top_target_market_skills": [
            {"skill": technology, "job_count": count}
            for technology, count in target_counts.most_common(25)
        ],
        "top_early_career_target_skills": [
            {"skill": technology, "job_count": count}
            for technology, count in early_counts.most_common(25)
        ],
        "degree_required_target_job_count": sum(
            row["is_target_market"] and row["degree_required"]
            for row in requirement_rows
        ),
        "target_jobs_with_experience_requirement_count": sum(
            row["is_target_market"]
            and row["minimum_experience_years"] is not None
            for row in requirement_rows
        ),
        "extraction_warning_counts": dict(sorted(warnings.items())),
    }
    return (
        skill_rows,
        requirement_rows,
        summary_rows,
        company_rows,
        report,
    )


def build(input_path: Path, output_dir: Path) -> dict[str, Any]:
    import pyarrow.parquet as pq

    jobs = pq.read_table(input_path).to_pylist()
    (
        skill_rows,
        requirement_rows,
        summary_rows,
        company_rows,
        report,
    ) = build_rows(jobs)

    _write_parquet(output_dir / "job_skills.parquet", skill_rows)
    _write_parquet(output_dir / "job_requirements.parquet", requirement_rows)
    _write_parquet(output_dir / "skills_summary.parquet", summary_rows)
    _write_parquet(output_dir / "company_skills.parquet", company_rows)
    _atomic_json(output_dir / "skills-quality-report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract skills and requirements from canonical jobs."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build(args.input, args.output_dir)
    print("\nSkills extraction summary")
    print("=" * 72)
    print(f"Canonical jobs:          {report['canonical_job_count']}")
    print(f"Target-market jobs:      {report['target_market_job_count']}")
    print(f"Job-skill rows:          {report['job_skill_row_count']}")
    print(f"Unique skills:           {report['unique_skill_count']}")
    print(f"Target skill coverage:   {report['target_skill_coverage_rate']:.1%}")
    print(f"\nOutput directory: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
