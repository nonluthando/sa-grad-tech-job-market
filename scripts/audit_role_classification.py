"""Export the scored role classification for target-market jobs."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "data" / "processed" / "jobs.parquet"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "analysis" / "role-classification-audit.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export explainable role-level scoring for target-market jobs."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    import pyarrow.parquet as pq

    jobs = [
        job
        for job in pq.read_table(args.dataset).to_pylist()
        if job.get("is_target_market") is True
    ]

    fields = [
        "company",
        "title",
        "role_level",
        "inferred_role_level",
        "role_level_score",
        "role_level_confidence",
        "is_talent_pool",
        "role_level_score_evidence",
        "application_url",
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for job in sorted(jobs, key=lambda item: (item["company"], item["title"])):
            row = {field: job.get(field) for field in fields}
            row["role_level_score_evidence"] = " | ".join(
                job.get("role_level_score_evidence") or []
            )
            writer.writerow(row)

    levels = Counter(job.get("inferred_role_level") for job in jobs)
    confidence = Counter(job.get("role_level_confidence") for job in jobs)

    print("\nRole classification audit")
    print("=" * 72)
    print(f"Target-market jobs: {len(jobs)}")
    print(f"Levels:             {dict(sorted(levels.items()))}")
    print(f"Confidence:         {dict(sorted(confidence.items()))}")
    print(f"Talent pools:       {sum(bool(job.get('is_talent_pool')) for job in jobs)}")
    print(f"\nCSV: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
