"""Gemini-assisted suggestions for role_level/workplace_type/city left unresolved.

This is a separate, manually-run stage. It never changes the canonical
dataset or the deterministic classifiers; it only produces an auditable
per-job suggestions CSV for the target-market jobs that are still missing
role_level, workplace_type, or city.

    python -m scripts.classify_with_gemini
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "data" / "processed" / "jobs.parquet"
DEFAULT_SUGGESTIONS_PATH = (
    PROJECT_ROOT / "data" / "analysis" / "gemini-classification-suggestions.csv"
)
DEFAULT_REPORT_PATH = (
    PROJECT_ROOT / "data" / "analysis" / "gemini-classification-report.json"
)

_SUGGESTION_FIELDNAMES = [
    "job_key",
    "title",
    "company",
    "llm_suggested_role_level",
    "llm_role_level_confidence",
    "llm_role_level_rationale",
    "llm_suggested_workplace_type",
    "llm_workplace_confidence",
    "llm_workplace_rationale",
    "llm_suggested_city",
    "llm_city_confidence",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ask Gemini to suggest role_level/workplace_type/city for "
            "target-market jobs the deterministic rules left unresolved."
        )
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--suggestions-path", type=Path, default=DEFAULT_SUGGESTIONS_PATH
    )
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument(
        "--model",
        default=None,
        help="Gemini model to use (default: gemini_classifier.DEFAULT_MODEL).",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=None,
        help=(
            "Pause between requests, to stay under free-tier rate limits "
            "(default: gemini_classifier.DEFAULT_DELAY_SECONDS)."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Classify at most this many candidates (useful for a quick test run).",
    )
    return parser.parse_args()


def write_suggestions(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=_SUGGESTION_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()

    try:
        import pyarrow.parquet as pq
    except ImportError as error:
        raise RuntimeError(
            "This script requires pyarrow. Run: pip install -r requirements.txt"
        ) from error

    try:
        from google import genai
    except ImportError as error:
        raise RuntimeError(
            "This script requires google-genai. Run: pip install -r requirements.txt"
        ) from error

    from src.llm_classification.gemini_classifier import (
        DEFAULT_DELAY_SECONDS,
        DEFAULT_MODEL,
        classify_candidates,
        resolve_api_key,
        select_candidates,
    )

    model = args.model or DEFAULT_MODEL
    delay_seconds = (
        args.delay_seconds if args.delay_seconds is not None else DEFAULT_DELAY_SECONDS
    )

    jobs = pq.read_table(args.dataset).to_pylist()
    candidates = select_candidates(jobs)
    if args.limit is not None:
        candidates = candidates[: args.limit]

    needs_role_level = sum(1 for c in candidates if c.needs_role_level)
    needs_workplace_type = sum(1 for c in candidates if c.needs_workplace_type)
    needs_city = sum(1 for c in candidates if c.needs_city)

    print("\nGemini-assisted classification")
    print("=" * 72)
    print(f"Candidates:                 {len(candidates)}")
    print(f"  needing role_level:        {needs_role_level}")
    print(f"  needing workplace_type:    {needs_workplace_type}")
    print(f"  needing city:              {needs_city}")
    print(f"Model:                      {model}")
    print(f"Delay between requests:     {delay_seconds}s")

    if not candidates:
        print("Nothing to classify.")
        return 0

    client = genai.Client(api_key=resolve_api_key())
    rows = classify_candidates(
        client, candidates, model=model, delay_seconds=delay_seconds
    )

    args.suggestions_path.parent.mkdir(parents=True, exist_ok=True)
    write_suggestions(args.suggestions_path, rows)

    report = {
        "candidates": len(candidates),
        "needing_role_level": needs_role_level,
        "needing_workplace_type": needs_workplace_type,
        "needing_city": needs_city,
        "suggestions_written": len(rows),
        "model": model,
    }
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"\nSuggestions written:        {len(rows)}")
    print(f"Suggestions:                {args.suggestions_path}")
    print(f"Report:                     {args.report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
