"""Employer registry loading, validation and source resolution.

The registry separates stable employer metadata from provider-specific
collection settings. Configured sources reference employers by ``employer_id``
so collection and transformation can share one canonical company identity.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


VALID_PRIORITIES = {"tier_1", "tier_2", "tier_3"}
VALID_COLLECTION_STATUSES = {"active", "candidate", "paused", "retired"}
VALID_REMOTE_SCOPES = {
    "south_africa",
    "africa",
    "emea",
    "global",
    "multi_country",
    "unknown",
}
REQUIRED_FIELDS = {
    "id",
    "name",
    "parent_company",
    "brands",
    "industry",
    "head_office_city",
    "country",
    "listed_company",
    "remote_scope",
    "graduate_programme",
    "priority",
    "collection_status",
}


def load_employer_registry(path: str | Path = "config/employers.json") -> dict[str, Any]:
    """Load and validate the employer registry."""

    registry_path = Path(path)
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    validate_employer_registry(payload)
    return payload


def employer_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return employers keyed by their stable registry ID."""

    return {employer["id"]: employer for employer in payload["employers"]}


def validate_employer_registry(payload: dict[str, Any]) -> None:
    """Raise ``ValueError`` when registry structure or values are invalid."""

    if payload.get("schema_version") != 1:
        raise ValueError("config/employers.json must use schema_version 1")

    employers = payload.get("employers")
    if not isinstance(employers, list) or not employers:
        raise ValueError("Employer registry must contain a non-empty employers list")

    seen_ids: set[str] = set()
    seen_names: set[str] = set()

    for position, employer in enumerate(employers):
        if not isinstance(employer, dict):
            raise ValueError(f"Employer at index {position} must be an object")

        missing = REQUIRED_FIELDS.difference(employer)
        if missing:
            missing_fields = ", ".join(sorted(missing))
            raise ValueError(
                f"Employer at index {position} is missing fields: {missing_fields}"
            )

        employer_id = employer["id"]
        if not isinstance(employer_id, str) or not employer_id.strip():
            raise ValueError(f"Employer at index {position} has an invalid id")
        if employer_id != employer_id.strip() or employer_id != employer_id.lower():
            raise ValueError(
                f"Employer id must be trimmed lowercase text: {employer_id!r}"
            )
        if employer_id in seen_ids:
            raise ValueError(f"Duplicate employer id: {employer_id}")
        seen_ids.add(employer_id)

        name = employer["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Employer {employer_id} has an invalid name")
        normalised_name = name.strip().casefold()
        if normalised_name in seen_names:
            raise ValueError(f"Duplicate employer name: {employer['name']}")
        seen_names.add(normalised_name)

        if employer["priority"] not in VALID_PRIORITIES:
            raise ValueError(
                f"Employer {employer_id} has invalid priority: {employer['priority']}"
            )
        if employer["collection_status"] not in VALID_COLLECTION_STATUSES:
            raise ValueError(
                f"Employer {employer_id} has invalid collection_status: "
                f"{employer['collection_status']}"
            )
        if employer["remote_scope"] not in VALID_REMOTE_SCOPES:
            raise ValueError(
                f"Employer {employer_id} has invalid remote_scope: "
                f"{employer['remote_scope']}"
            )
        if not isinstance(employer["brands"], list):
            raise ValueError(f"Employer {employer_id} brands must be a list")
        if not isinstance(employer["listed_company"], bool):
            raise ValueError(
                f"Employer {employer_id} listed_company must be a boolean"
            )


def validate_source_links(
    sources_payload: dict[str, Any],
    employer_payload: dict[str, Any],
) -> None:
    """Ensure every configured source references a registered employer."""

    known_ids = set(employer_index(employer_payload))
    missing_links: list[str] = []

    sources = sources_payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("Source configuration must contain a sources list")

    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("Every configured source must be an object")
        employer_id = source.get("employer_id")
        if not isinstance(employer_id, str) or employer_id not in known_ids:
            missing_links.append(source.get("token") or source.get("name") or "<unknown>")

    if missing_links:
        joined = ", ".join(sorted(missing_links))
        raise ValueError(f"Sources with missing employer registry links: {joined}")


def validate_collectable_sources(
    sources_payload: dict[str, Any],
    employer_payload: dict[str, Any],
    *,
    supported_providers: Iterable[str],
) -> None:
    """Reject enabled production sources whose employers are not active.

    Candidate, paused and retired employers remain useful registry records, but
    they may not be collected until their status is explicitly changed to
    ``active``.
    """

    validate_source_links(sources_payload, employer_payload)
    employers = employer_index(employer_payload)
    supported = set(supported_providers)
    blocked: list[str] = []

    for source in sources_payload["sources"]:
        if not source.get("enabled", True):
            continue
        if source.get("provider") not in supported:
            continue

        employer_id = source["employer_id"]
        status = employers[employer_id]["collection_status"]
        if status != "active":
            token = source.get("token") or source.get("name") or "<unknown>"
            blocked.append(f"{token} ({employer_id}: {status})")

    if blocked:
        joined = ", ".join(sorted(blocked))
        raise ValueError(f"Enabled sources require active employers: {joined}")


def source_employer_index(
    sources_payload: dict[str, Any],
) -> dict[tuple[str, str], str]:
    """Return ``(provider, token)`` source keys mapped to employer IDs."""

    index: dict[tuple[str, str], str] = {}
    for source in sources_payload.get("sources", []):
        provider = str(source.get("provider") or "").strip()
        token = str(source.get("token") or "").strip()
        employer_id = str(source.get("employer_id") or "").strip()
        if not provider or not token or not employer_id:
            continue

        key = (provider, token)
        if key in index:
            raise ValueError(f"Duplicate configured source: {provider}:{token}")
        index[key] = employer_id

    return index


def iter_employers(
    payload: dict[str, Any],
    *,
    priority: str | None = None,
    collection_status: str | None = None,
) -> Iterable[dict[str, Any]]:
    """Yield employers matching optional registry filters."""

    for employer in payload["employers"]:
        if priority is not None and employer["priority"] != priority:
            continue
        if (
            collection_status is not None
            and employer["collection_status"] != collection_status
        ):
            continue
        yield employer
