"""Train and evaluate the optional scikit-learn role-level classifier.

This is a separate, manually-run stage. It never changes the canonical
dataset or the deterministic classifiers; it only produces an auditable
model artifact, an evaluation report, and per-job suggestions for the
population that ``scripts/audit_unspecified.py`` already flags for review.

    python -m scripts.train_role_classifier
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "data" / "processed" / "jobs.parquet"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "data" / "models" / "role_classifier.joblib"
DEFAULT_REPORT_PATH = (
    PROJECT_ROOT / "data" / "analysis" / "ml-role-classifier-report.json"
)
DEFAULT_SUGGESTIONS_PATH = (
    PROJECT_ROOT / "data" / "analysis" / "ml-role-suggestions.csv"
)

_SUGGESTION_FIELDNAMES = [
    "job_key",
    "title",
    "company",
    "ml_suggested_role_level",
    "ml_role_level_confidence",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the second-stage role-level classifier."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument(
        "--suggestions-path", type=Path, default=DEFAULT_SUGGESTIONS_PATH
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
        import joblib
    except ImportError as error:
        raise RuntimeError(
            "Training requires scikit-learn. Run: pip install -r requirements.txt"
        ) from error

    try:
        import pyarrow.parquet as pq
    except ImportError as error:
        raise RuntimeError(
            "Training requires pyarrow. Run: pip install -r requirements.txt"
        ) from error

    from src.role_classification.ml_classifier import (
        build_training_examples,
        predict_unspecified_jobs,
        train_and_evaluate,
    )

    jobs = pq.read_table(args.dataset).to_pylist()

    examples = build_training_examples(jobs)
    result = train_and_evaluate(examples)

    args.model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(result.pipeline, args.model_path)

    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(
        json.dumps(result.report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    suggestions = predict_unspecified_jobs(result.pipeline, jobs)
    write_suggestions(args.suggestions_path, suggestions)

    print("\nRole-level classifier training")
    print("=" * 72)
    print(f"Training examples:          {result.report['training_examples']}")
    print(f"Test examples:              {result.report['test_examples']}")
    print(f"Label counts:               {result.report['label_counts']}")
    print(f"Accuracy (held-out):        {result.report['accuracy']:.3f}")
    # Headline metric, not accuracy: classes are imbalanced (e.g. "graduate"
    # and "internship" are much rarer than "junior"/"senior"), so macro-F1
    # weights every class equally instead of letting the common ones hide
    # poor performance on the rare ones.
    print(f"Macro-F1 (held-out):        {result.report['macro_f1']:.3f}")
    print(f"Weighted-F1 (held-out):     {result.report['weighted_f1']:.3f}")
    print("\nPer-class precision / recall / F1 / support:")
    for label, metrics in result.report["per_class"].items():
        print(
            f"  {label:<12} "
            f"precision={metrics['precision']:.3f}  "
            f"recall={metrics['recall']:.3f}  "
            f"f1={metrics['f1']:.3f}  "
            f"support={metrics['support']}"
        )
    print(f"\nModel:                      {args.model_path}")
    print(f"Evaluation report:          {args.report_path}")
    print(f"Unspecified jobs suggested: {len(suggestions)}")
    print(f"Suggestions:                {args.suggestions_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
