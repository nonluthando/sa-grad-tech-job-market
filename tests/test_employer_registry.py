import json
from pathlib import Path

import pytest

from src.configuration.employers import (
    employer_index,
    iter_employers,
    load_employer_registry,
    validate_collectable_sources,
    validate_employer_registry,
    validate_source_links,
)


ROOT = Path(__file__).resolve().parents[1]


def test_repository_employer_registry_is_valid():
    payload = load_employer_registry(ROOT / "config" / "employers.json")

    assert payload["schema_version"] == 1
    assert len(payload["employers"]) >= 30
    assert "amazon-aws" in employer_index(payload)


def test_every_configured_source_links_to_registered_employer():
    employer_payload = load_employer_registry(ROOT / "config" / "employers.json")
    sources_payload = json.loads(
        (ROOT / "config" / "sources.json").read_text(encoding="utf-8")
    )
    validate_source_links(sources_payload, employer_payload)


def test_active_registry_entries_match_configured_sources():
    employer_payload = load_employer_registry(ROOT / "config" / "employers.json")
    sources_payload = json.loads(
        (ROOT / "config" / "sources.json").read_text(encoding="utf-8")
    )

    configured_ids = {
        source["employer_id"] for source in sources_payload["sources"]
    }
    active_ids = {
        employer["id"]
        for employer in iter_employers(
            employer_payload, collection_status="active"
        )
    }

    assert active_ids == configured_ids


def test_registry_rejects_duplicate_ids():
    payload = {
        "schema_version": 1,
        "employers": [
            {
                "id": "duplicate",
                "name": "Employer One",
                "parent_company": None,
                "brands": [],
                "industry": "Software",
                "head_office_city": None,
                "country": "South Africa",
                "listed_company": False,
                "remote_scope": "south_africa",
                "graduate_programme": "unknown",
                "priority": "tier_1",
                "collection_status": "candidate",
            },
            {
                "id": "duplicate",
                "name": "Employer Two",
                "parent_company": None,
                "brands": [],
                "industry": "Software",
                "head_office_city": None,
                "country": "South Africa",
                "listed_company": False,
                "remote_scope": "south_africa",
                "graduate_programme": "unknown",
                "priority": "tier_2",
                "collection_status": "candidate",
            },
        ],
    }

    with pytest.raises(ValueError, match="Duplicate employer id"):
        validate_employer_registry(payload)


def test_source_link_validation_rejects_unknown_employer():
    employer_payload = load_employer_registry(ROOT / "config" / "employers.json")
    sources_payload = {
        "sources": [
            {
                "name": "Unknown",
                "token": "unknown",
                "employer_id": "not-registered",
            }
        ]
    }

    with pytest.raises(ValueError, match="missing employer registry links"):
        validate_source_links(sources_payload, employer_payload)


def test_collectable_source_validation_rejects_candidate_employer():
    employer_payload = {
        "schema_version": 1,
        "employers": [
            {
                "id": "candidate",
                "name": "Candidate Employer",
                "parent_company": None,
                "brands": [],
                "industry": "Software",
                "head_office_city": None,
                "country": "South Africa",
                "listed_company": False,
                "remote_scope": "south_africa",
                "graduate_programme": "unknown",
                "priority": "tier_2",
                "collection_status": "candidate",
            }
        ],
    }
    sources_payload = {
        "sources": [
            {
                "name": "Candidate Employer",
                "provider": "greenhouse",
                "token": "candidate",
                "employer_id": "candidate",
                "enabled": True,
            }
        ]
    }

    with pytest.raises(ValueError, match="require active employers"):
        validate_collectable_sources(
            sources_payload,
            employer_payload,
            supported_providers=("greenhouse",),
        )
