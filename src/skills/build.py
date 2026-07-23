"""Build reusable skills and requirements datasets from canonical jobs."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from src.skills.extractor import extract_job_enrichment

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "jobs.parquet"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed"


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


def build(input_path: Path, output_dir: Path) -> dict[str, Any]:
    import pyarrow.parquet as pq

    jobs = pq.read_table(input_path).to_pylist()
    skill_rows: list[dict[str, Any]] = []
    requirement_rows: list[dict[str, Any]] = []
    skill_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    early_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    warnings: Counter[str] = Counter()
    company_counts: dict[tuple[str, str], int] = defaultdict(int)

    jobs_with_skills = 0
    target_with_skills = 0

    for job in jobs:
        enrichment = extract_job_enrichment(
            str(job.get("title") or ""),
            str(job.get("description_text") or ""),
        )
        warnings.update(enrichment.extraction_warnings)
        is_target = job.get("is_target_market") is True
        inferred = job.get("inferred_role_level")
        is_early_target = is_target and (
            job.get("is_early_career") is True
            or inferred in {"internship", "graduate", "junior"}
        )

        if enrichment.skills:
            jobs_with_skills += 1
            if is_target:
                target_with_skills += 1

        for item in enrichment.skills:
            skill_counts[item.skill] += 1
            category_counts[item.category] += 1
            company_counts[(str(job.get("company") or ""), item.skill)] += 1
            if is_target:
                target_counts[item.skill] += 1
            if is_early_target:
                early_counts[item.skill] += 1

            skill_rows.append({
                "job_key": job.get("job_key"),
                "company": job.get("company"),
                "title": job.get("title"),
                "city": job.get("city"),
                "province": job.get("province"),
                "role_level": job.get("role_level"),
                "inferred_role_level": inferred,
                "is_target_market": is_target,
                "is_early_career_target": is_early_target,
                "skill": item.skill,
                "category": item.category,
                "evidence": list(item.evidence),
                "application_url": job.get("application_url"),
            })

        requirement_rows.append({
            "job_key": job.get("job_key"),
            "company": job.get("company"),
            "title": job.get("title"),
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
        or job.get("inferred_role_level") in {"internship", "graduate", "junior"}
    ]

    summary_rows = []
    for skill in sorted(skill_counts):
        category = next(
            row["category"] for row in skill_rows if row["skill"] == skill
        )
        summary_rows.append({
            "skill": skill,
            "category": category,
            "all_job_count": skill_counts[skill],
            "target_market_job_count": target_counts[skill],
            "early_career_target_job_count": early_counts[skill],
            "target_market_share": (
                target_counts[skill] / len(target_jobs) if target_jobs else 0.0
            ),
        })

    company_rows = [
        {"company": company, "skill": skill, "job_count": count}
        for (company, skill), count in sorted(company_counts.items())
    ]

    _write_parquet(output_dir / "job_skills.parquet", skill_rows)
    _write_parquet(output_dir / "job_requirements.parquet", requirement_rows)
    _write_parquet(output_dir / "skills_summary.parquet", summary_rows)
    _write_parquet(output_dir / "company_skills.parquet", company_rows)

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
        "category_mention_counts": dict(sorted(category_counts.items())),
        "top_target_market_skills": [
            {"skill": skill, "job_count": count}
            for skill, count in target_counts.most_common(25)
        ],
        "top_early_career_target_skills": [
            {"skill": skill, "job_count": count}
            for skill, count in early_counts.most_common(25)
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
