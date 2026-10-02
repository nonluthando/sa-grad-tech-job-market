import pytest

from src.role_classification.ml_classifier import (
    TrainingExample,
    build_training_examples,
    job_text,
    predict_unspecified_jobs,
    train_and_evaluate,
)


def _job(**overrides):
    base = {
        "title": "Software Engineer",
        "description_text": "Build things.",
        "inferred_role_level": "junior",
        "role_level_confidence": "high",
        "role_level": "junior",
        "is_target_market": True,
        "job_key": "job-1",
        "company": "Acme",
    }
    base.update(overrides)
    return base


def test_job_text_combines_title_and_description():
    job = _job(title="Junior Developer", description_text="Write Python code.")
    assert job_text(job) == "Junior Developer. Write Python code."


def test_build_training_examples_filters_low_confidence_and_ambiguous():
    jobs = [
        _job(inferred_role_level="junior", role_level_confidence="high"),
        _job(inferred_role_level="senior", role_level_confidence="low"),
        _job(inferred_role_level="ambiguous", role_level_confidence="high"),
        _job(inferred_role_level=None, role_level_confidence="high"),
    ]
    examples = build_training_examples(jobs)
    assert len(examples) == 1
    assert examples[0].label == "junior"


_TRAINING_TEXTS = {
    "internship": [
        "Internship Software Developer. Join our internship program building web apps.",
        "Graduate Internship IT. A structured internship for recent graduates in IT support.",
        "Summer Internship Engineer. Internship opportunity for students in engineering.",
        "Internship Data Analyst. Internship assisting the data team with reporting.",
    ],
    "junior": [
        "Junior Software Developer. Junior role writing Python and SQL.",
        "Junior Data Analyst. Junior analyst supporting dashboards and reports.",
        "Junior Network Engineer. Junior engineer maintaining network infrastructure.",
        "Junior QA Tester. Junior tester validating releases before launch.",
    ],
    "senior": [
        "Senior Software Engineer. Senior engineer leading architecture decisions.",
        "Senior Data Scientist. Senior scientist designing machine learning systems.",
        "Senior DevOps Engineer. Senior engineer owning cloud infrastructure at scale.",
        "Lead Backend Engineer. Senior lead responsible for backend platform reliability.",
    ],
    "mid_level": [
        "Software Engineer II. Mid-level engineer building backend services.",
        "Data Analyst II. Mid-level analyst owning reporting pipelines.",
        "Network Engineer II. Mid-level engineer supporting production networks.",
        "QA Engineer II. Mid-level tester automating regression suites.",
    ],
}


def _confident_jobs():
    jobs = []
    for label, texts in _TRAINING_TEXTS.items():
        for text_index, text in enumerate(texts):
            title, description = text.split(". ", 1)
            jobs.append(
                _job(
                    job_key=f"{label}-{text_index}",
                    title=title,
                    description_text=description,
                    inferred_role_level=label,
                    role_level_confidence="high",
                )
            )
    return jobs


def test_train_and_evaluate_produces_a_usable_pipeline():
    examples = build_training_examples(_confident_jobs())
    result = train_and_evaluate(examples, test_size=0.25)

    assert (
        result.report["training_examples"] + result.report["test_examples"]
        == len(examples)
    )
    assert set(result.report["label_counts"]) == set(_TRAINING_TEXTS)
    assert "classification_report" in result.report
    assert "confusion_matrix" in result.report

    prediction = result.pipeline.predict(
        ["Senior Principal Engineer leading the platform team."]
    )
    assert prediction[0] in _TRAINING_TEXTS


def test_train_and_evaluate_requires_minimum_examples():
    with pytest.raises(ValueError, match="at least 10"):
        train_and_evaluate(
            [TrainingExample(text="Junior Developer", label="junior")] * 5
        )


def test_predict_unspecified_jobs_only_targets_the_audit_population():
    examples = build_training_examples(_confident_jobs())
    result = train_and_evaluate(examples, test_size=0.25)

    candidate = _job(
        job_key="unspecified-1",
        title="Graduate Software Developer",
        description_text="Join our graduate intake building internal tools.",
        role_level="unspecified",
        is_target_market=True,
    )
    not_target_market = _job(
        job_key="skip-1",
        role_level="unspecified",
        is_target_market=False,
    )
    already_classified = _job(
        job_key="skip-2",
        role_level="junior",
        is_target_market=True,
    )

    suggestions = predict_unspecified_jobs(
        result.pipeline, [candidate, not_target_market, already_classified]
    )

    assert len(suggestions) == 1
    row = suggestions[0]
    assert row["job_key"] == "unspecified-1"
    assert row["ml_suggested_role_level"] in _TRAINING_TEXTS
    assert 0.0 <= row["ml_role_level_confidence"] <= 1.0


def test_predict_unspecified_jobs_returns_empty_without_candidates():
    examples = build_training_examples(_confident_jobs())
    result = train_and_evaluate(examples, test_size=0.25)

    suggestions = predict_unspecified_jobs(
        result.pipeline, [_job(role_level="junior", is_target_market=True)]
    )
    assert suggestions == []
