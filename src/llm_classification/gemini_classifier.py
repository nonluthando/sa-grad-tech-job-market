"""Gemini-assisted suggestions for fields the deterministic pipeline left unresolved.

This is a separate, manually-run, optional stage - like
``src/role_classification/ml_classifier.py``, it never changes the canonical
dataset or the deterministic classifiers. It only produces auditable
per-job suggestions for target-market jobs where ``role_level``,
``workplace_type``, or ``city`` is still unresolved, stored under a
clearly-separate ``llm_*`` name so they can never be mistaken for the
canonical, rule-derived fields.

Only the fields that are actually unresolved for a given job are read from
Gemini's response and kept - even though the response schema always asks
for all three, so every call has the same shape, an opinion on a field the
deterministic rules already resolved confidently is simply discarded.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from pydantic import BaseModel

_FALLBACK_API_KEY_PATH = Path.home() / ".config" / "gemini" / "api_key"

DEFAULT_MODEL = "gemini-3.1-flash-lite"
DEFAULT_DELAY_SECONDS = 4.0

_ROLE_LEVELS = (
    "internship",
    "graduate",
    "junior",
    "mid_level",
    "senior",
    "unspecified",
)
_WORKPLACE_TYPES = ("remote", "hybrid", "on_site", "unspecified")
_CONFIDENCE_LEVELS = ("high", "medium", "low")


class GeminiClassification(BaseModel):
    """The structured response schema Gemini is constrained to."""

    role_level: Literal[_ROLE_LEVELS]
    role_level_confidence: Literal[_CONFIDENCE_LEVELS]
    role_level_rationale: str

    workplace_type: Literal[_WORKPLACE_TYPES]
    workplace_confidence: Literal[_CONFIDENCE_LEVELS]
    workplace_rationale: str

    city: str
    city_confidence: Literal[_CONFIDENCE_LEVELS]


@dataclass(frozen=True)
class Candidate:
    """A target-market job with at least one field still unresolved."""

    job: dict[str, Any]
    needs_role_level: bool
    needs_workplace_type: bool
    needs_city: bool


def resolve_api_key() -> str:
    """Read the Gemini API key from the environment, falling back to a

    local credential file outside the repo (``~/.config/gemini/api_key``),
    so the key never has to live in a tracked file or an env var that
    isn't set up yet.
    """

    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    if _FALLBACK_API_KEY_PATH.is_file():
        key = _FALLBACK_API_KEY_PATH.read_text(encoding="utf-8").strip()
        if key:
            return key
    raise RuntimeError(
        "No Gemini API key found. Set the GEMINI_API_KEY environment "
        f"variable, or place the key in {_FALLBACK_API_KEY_PATH}."
    )


def select_candidates(jobs: Iterable[dict[str, Any]]) -> list[Candidate]:
    """Target-market jobs with role_level, workplace_type, or city unresolved.

    Mirrors the project's existing audit filters: only ``is_target_market``
    jobs are in scope, and country/``is_south_africa`` are deliberately
    excluded - they are already fully resolved for every target-market job
    in the live dataset, so there is nothing for Gemini to add there.
    """

    candidates: list[Candidate] = []
    for job in jobs:
        if job.get("is_target_market") is not True:
            continue

        needs_role_level = job.get("role_level") == "unspecified"
        needs_workplace_type = job.get("workplace_type") == "unspecified"
        needs_city = bool(job.get("is_south_africa")) and not job.get("city")

        if needs_role_level or needs_workplace_type or needs_city:
            candidates.append(
                Candidate(
                    job=job,
                    needs_role_level=needs_role_level,
                    needs_workplace_type=needs_workplace_type,
                    needs_city=needs_city,
                )
            )
    return candidates


def build_prompt(candidate: Candidate) -> str:
    job = candidate.job
    title = job.get("title") or ""
    description = job.get("description_text") or ""
    location_raw = job.get("location_raw") or ""
    company = job.get("company") or job.get("employer_name") or ""
    department = job.get("department") or ""

    return (
        "This job posting is already confirmed to be a South African "
        "technology role. Classify three things from the text below, using "
        "only evidence actually present in the text - do not guess beyond "
        "it. If the text genuinely does not say, answer \"unspecified\" "
        "(or, for city, the literal string \"unspecified\") rather than "
        "inventing an answer.\n\n"
        "1. role_level: one of internship, graduate, junior, mid_level, "
        "senior, unspecified.\n"
        "2. workplace_type: one of remote, hybrid, on_site, unspecified.\n"
        "3. city: the specific South African city this role is based in, "
        "if the text states or clearly implies one; otherwise "
        "\"unspecified\".\n\n"
        f"Company: {company}\n"
        f"Department: {department}\n"
        f"Title: {title}\n"
        f"Location as listed by the employer: {location_raw}\n\n"
        f"Description:\n{description}\n"
    )


def classify_candidate(
    client: Any,
    candidate: Candidate,
    *,
    model: str = DEFAULT_MODEL,
    max_attempts: int = 5,
    retry_delay_seconds: float = 10.0,
    sleep: Any = time.sleep,
) -> GeminiClassification:
    """Call Gemini once for this job and parse the structured response.

    ``client`` is a ``google.genai.Client`` (or any object exposing the
    same ``models.generate_content`` method) - accepted as a parameter
    rather than constructed here so tests can pass a stub with no network
    access.

    Retries on ``ServerError`` (observed in practice as frequent transient
    503 "high demand" responses from this model) with linear backoff - the
    SDK's own internal retry already runs before raising, so by the time
    this sees the error it has already failed several times.
    """

    from google.genai import errors as genai_errors
    from google.genai import types

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=GeminiClassification,
    )
    prompt = build_prompt(candidate)

    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            response = client.models.generate_content(
                model=model, contents=prompt, config=config
            )
            return GeminiClassification.model_validate_json(response.text)
        except genai_errors.ServerError as error:
            last_error = error
            if attempt < max_attempts - 1:
                sleep(retry_delay_seconds * (attempt + 1))

    assert last_error is not None
    raise last_error


def suggestion_row(
    candidate: Candidate,
    result: GeminiClassification,
) -> dict[str, Any] | None:
    """Build the output row, keeping only fields that were actually unresolved.

    Returns ``None`` if (unexpectedly) none of the candidate's unresolved
    fields ended up populated - should not happen given ``select_candidates``,
    but guards against an empty, misleading row.
    """

    job = candidate.job
    row: dict[str, Any] = {
        "job_key": job.get("job_key"),
        "title": job.get("title"),
        "company": job.get("company") or job.get("employer_name"),
    }

    added_a_field = False

    if candidate.needs_role_level:
        row["llm_suggested_role_level"] = result.role_level
        row["llm_role_level_confidence"] = result.role_level_confidence
        row["llm_role_level_rationale"] = result.role_level_rationale
        added_a_field = True

    if candidate.needs_workplace_type:
        row["llm_suggested_workplace_type"] = result.workplace_type
        row["llm_workplace_confidence"] = result.workplace_confidence
        row["llm_workplace_rationale"] = result.workplace_rationale
        added_a_field = True

    if candidate.needs_city:
        city = result.city.strip()
        if city and city.casefold() != "unspecified":
            row["llm_suggested_city"] = city
            row["llm_city_confidence"] = result.city_confidence
            added_a_field = True

    return row if added_a_field else None


def classify_candidates(
    client: Any,
    candidates: list[Candidate],
    *,
    model: str = DEFAULT_MODEL,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    max_attempts: int = 5,
    retry_delay_seconds: float = 10.0,
    sleep: Any = time.sleep,
) -> list[dict[str, Any]]:
    """Classify every candidate, pacing requests for free-tier rate limits.

    ``sleep`` is injectable so tests can run the whole loop with no real
    delay.
    """

    rows: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        if index > 0 and delay_seconds > 0:
            sleep(delay_seconds)
        result = classify_candidate(
            client,
            candidate,
            model=model,
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
            sleep=sleep,
        )
        row = suggestion_row(candidate, result)
        if row is not None:
            rows.append(row)
    return rows
