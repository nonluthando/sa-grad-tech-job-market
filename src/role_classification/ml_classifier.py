"""Optional scikit-learn second-stage classifier for ambiguous role levels.

This module never overwrites the deterministic ``role_level`` or
``inferred_role_level`` fields. It trains on jobs the existing scored
classifier (``src/role_classification/classifier.py``) already labelled
with high confidence, then produces a separate, auditable suggestion for
jobs the production rules left at ``unspecified``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


RANDOM_STATE = 42
MINIMUM_TRAINING_EXAMPLES = 10
_MIN_LABEL_COUNT_FOR_STRATIFY = 2


@dataclass(frozen=True)
class TrainingExample:
    """One confidently-labelled job, reduced to text + its label."""

    text: str
    label: str


@dataclass(frozen=True)
class TrainingResult:
    """A fitted pipeline alongside its held-out evaluation report."""

    pipeline: Pipeline
    report: dict[str, Any]


def job_text(job: dict[str, Any]) -> str:
    """Combine the fields the classifier reads into one text input."""

    title = str(job.get("title") or "")
    description = str(job.get("description_text") or "")
    return f"{title}. {description}".strip()


def build_training_examples(jobs: Iterable[dict[str, Any]]) -> list[TrainingExample]:
    """Use the deterministic scored classifier's confident output as labels.

    Only rows the existing rule-based classifier already trusts
    (``role_level_confidence == "high"`` and a resolved, non-ambiguous
    ``inferred_role_level``) become training data, so the model learns
    from the rules' clearest cases rather than their own noise.
    """

    examples: list[TrainingExample] = []
    for job in jobs:
        label = job.get("inferred_role_level")
        confidence = job.get("role_level_confidence")
        if not label or label == "ambiguous" or confidence != "high":
            continue
        text = job_text(job)
        if not text:
            continue
        examples.append(TrainingExample(text=text, label=str(label)))
    return examples


def _make_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=5000,
                    ngram_range=(1, 2),
                    min_df=2,
                    stop_words="english",
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def train_and_evaluate(
    examples: list[TrainingExample],
    *,
    test_size: float = 0.2,
) -> TrainingResult:
    """Train on a stratified split and report held-out performance."""

    if len(examples) < MINIMUM_TRAINING_EXAMPLES:
        raise ValueError(
            f"Need at least {MINIMUM_TRAINING_EXAMPLES} confidently-labelled "
            f"jobs to train a classifier; found {len(examples)}."
        )

    texts = [example.text for example in examples]
    labels = [example.label for example in examples]

    label_counts: dict[str, int] = {}
    for label in labels:
        label_counts[label] = label_counts.get(label, 0) + 1
    can_stratify = len(label_counts) > 1 and all(
        count >= _MIN_LABEL_COUNT_FOR_STRATIFY for count in label_counts.values()
    )

    split_kwargs: dict[str, Any] = {
        "test_size": test_size,
        "random_state": RANDOM_STATE,
    }
    if can_stratify:
        split_kwargs["stratify"] = labels

    X_train, X_test, y_train, y_test = train_test_split(texts, labels, **split_kwargs)

    pipeline = _make_pipeline()
    pipeline.fit(X_train, y_train)

    predictions = pipeline.predict(X_test)
    labels_seen = sorted(label_counts)
    report = {
        "training_examples": len(X_train),
        "test_examples": len(X_test),
        "label_counts": label_counts,
        "classification_report": classification_report(
            y_test,
            predictions,
            labels=labels_seen,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": {
            "labels": labels_seen,
            "matrix": confusion_matrix(
                y_test, predictions, labels=labels_seen
            ).tolist(),
        },
    }
    return TrainingResult(pipeline=pipeline, report=report)


def predict_unspecified_jobs(
    pipeline: Pipeline,
    jobs: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Suggest a level for target-market jobs the deterministic rules left unspecified.

    Mirrors ``scripts/audit_unspecified.py``'s population exactly: target-market
    jobs whose conservative ``role_level`` is still ``unspecified``. The result
    is never written back into the canonical dataset.
    """

    candidates = [
        job
        for job in jobs
        if job.get("is_target_market") is True
        and job.get("role_level") == "unspecified"
    ]
    if not candidates:
        return []

    texts = [job_text(job) for job in candidates]
    predictions = pipeline.predict(texts)
    probabilities = pipeline.predict_proba(texts)

    rows: list[dict[str, Any]] = []
    for job, predicted_label, probability_row in zip(
        candidates, predictions, probabilities
    ):
        confidence = float(max(probability_row))
        rows.append(
            {
                "job_key": job.get("job_key"),
                "title": job.get("title"),
                "company": job.get("company"),
                "ml_suggested_role_level": str(predicted_label),
                "ml_role_level_confidence": round(confidence, 4),
            }
        )
    return rows
