from __future__ import annotations

import pytest
from google.genai import errors as genai_errors

from src.llm_classification.gemini_classifier import (
    GeminiClassification,
    classify_candidate,
    classify_candidates,
    select_candidates,
    suggestion_row,
)


def _job(**overrides):
    base = {
        "job_key": "job-1",
        "title": "Platform Engineer",
        "company": "Acme",
        "description_text": "Build things.",
        "location_raw": "Cape Town",
        "department": "Engineering",
        "is_target_market": True,
        "role_level": "unspecified",
        "workplace_type": "unspecified",
        "is_south_africa": True,
        "city": None,
    }
    base.update(overrides)
    return base


def _result(**overrides) -> GeminiClassification:
    base = dict(
        role_level="junior",
        role_level_confidence="medium",
        role_level_rationale="Mentions a bursary and no prior experience required.",
        workplace_type="hybrid",
        workplace_confidence="high",
        workplace_rationale="States '3 days in office, 2 remote'.",
        city="Cape Town",
        city_confidence="high",
    )
    base.update(overrides)
    return GeminiClassification(**base)


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeModels:
    def __init__(self, results: list[GeminiClassification]):
        self._results = list(results)
        self.calls = 0

    def generate_content(self, *, model, contents, config):
        self.calls += 1
        result = self._results.pop(0)
        return _FakeResponse(result.model_dump_json())


class _FlakyModels:
    """Raises ServerError a fixed number of times before succeeding."""

    def __init__(self, failures_before_success: int, result: GeminiClassification):
        self._remaining_failures = failures_before_success
        self._result = result
        self.calls = 0

    def generate_content(self, *, model, contents, config):
        self.calls += 1
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise genai_errors.ServerError(503, {"error": {"message": "high demand"}})
        return _FakeResponse(self._result.model_dump_json())


class _FakeClient:
    def __init__(self, results: list[GeminiClassification]):
        self.models = _FakeModels(results)


class _FlakyClient:
    def __init__(self, failures_before_success: int, result: GeminiClassification):
        self.models = _FlakyModels(failures_before_success, result)


def test_select_candidates_requires_target_market():
    jobs = [
        _job(job_key="a", is_target_market=True, role_level="unspecified"),
        _job(job_key="b", is_target_market=False, role_level="unspecified"),
        _job(
            job_key="c",
            is_target_market=True,
            role_level="junior",
            workplace_type="remote",
            city="Cape Town",
        ),
    ]
    candidates = select_candidates(jobs)
    assert [c.job["job_key"] for c in candidates] == ["a"]


def test_select_candidates_flags_each_unresolved_field_independently():
    job = _job(
        role_level="senior",
        workplace_type="unspecified",
        is_south_africa=True,
        city=None,
    )
    [candidate] = select_candidates([job])
    assert candidate.needs_role_level is False
    assert candidate.needs_workplace_type is True
    assert candidate.needs_city is True


def test_select_candidates_excludes_jobs_with_nothing_unresolved():
    job = _job(role_level="junior", workplace_type="remote", city="Cape Town")
    assert select_candidates([job]) == []


def test_select_candidates_never_flags_city_outside_south_africa():
    job = _job(role_level="junior", workplace_type="remote", is_south_africa=False, city=None)
    assert select_candidates([job]) == []


def test_suggestion_row_only_includes_fields_that_were_unresolved():
    job = _job(role_level="unspecified", workplace_type="hybrid", city="Cape Town")
    [candidate] = select_candidates([job])
    result = _result()

    row = suggestion_row(candidate, result)

    assert row is not None
    assert row["llm_suggested_role_level"] == "junior"
    assert "llm_suggested_workplace_type" not in row
    assert "llm_suggested_city" not in row


def test_suggestion_row_includes_all_three_when_all_unresolved():
    job = _job(role_level="unspecified", workplace_type="unspecified", city=None)
    [candidate] = select_candidates([job])
    result = _result()

    row = suggestion_row(candidate, result)

    assert row["llm_suggested_role_level"] == "junior"
    assert row["llm_suggested_workplace_type"] == "hybrid"
    assert row["llm_suggested_city"] == "Cape Town"


def test_suggestion_row_drops_city_when_gemini_says_unspecified():
    job = _job(role_level="junior", workplace_type="hybrid", city=None)
    [candidate] = select_candidates([job])
    result = _result(city="unspecified", city_confidence="low")

    row = suggestion_row(candidate, result)

    assert row is None


def test_classify_candidates_paces_requests_and_skips_first_delay():
    jobs = [
        _job(job_key="a", role_level="unspecified"),
        _job(job_key="b", role_level="unspecified"),
    ]
    candidates = select_candidates(jobs)
    client = _FakeClient([_result(), _result()])
    sleeps: list[float] = []

    rows = classify_candidates(
        client, candidates, delay_seconds=2.5, sleep=sleeps.append
    )

    assert len(rows) == 2
    assert sleeps == [2.5]
    assert client.models.calls == 2


def test_classify_candidates_zero_delay_never_sleeps():
    jobs = [_job(job_key="a", role_level="unspecified")]
    candidates = select_candidates(jobs)
    client = _FakeClient([_result()])
    sleeps: list[float] = []

    classify_candidates(client, candidates, delay_seconds=0, sleep=sleeps.append)

    assert sleeps == []


def test_resolve_api_key_prefers_environment_variable(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    from src.llm_classification.gemini_classifier import resolve_api_key

    assert resolve_api_key() == "env-key"


def test_resolve_api_key_raises_when_nothing_is_configured(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import src.llm_classification.gemini_classifier as module

    monkeypatch.setattr(module, "_FALLBACK_API_KEY_PATH", tmp_path / "missing")

    with pytest.raises(RuntimeError, match="No Gemini API key"):
        module.resolve_api_key()


def test_classify_candidate_retries_transient_server_errors():
    job = _job(role_level="unspecified")
    [candidate] = select_candidates([job])
    client = _FlakyClient(failures_before_success=2, result=_result())
    sleeps: list[float] = []

    result = classify_candidate(
        client, candidate, retry_delay_seconds=1.0, sleep=sleeps.append
    )

    assert result.role_level == "junior"
    assert client.models.calls == 3
    assert sleeps == [1.0, 2.0]


def test_classify_candidate_gives_up_after_max_attempts():
    job = _job(role_level="unspecified")
    [candidate] = select_candidates([job])
    client = _FlakyClient(failures_before_success=10, result=_result())
    sleeps: list[float] = []

    with pytest.raises(genai_errors.ServerError):
        classify_candidate(
            client,
            candidate,
            max_attempts=3,
            retry_delay_seconds=1.0,
            sleep=sleeps.append,
        )

    assert client.models.calls == 3
    assert sleeps == [1.0, 2.0]
