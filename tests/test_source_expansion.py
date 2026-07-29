from __future__ import annotations

import json
from pathlib import Path


SOURCES_PATH = Path("config/sources.json")
EMPLOYERS_PATH = Path("config/employers.json")


def _sources_by_token() -> dict[str, dict[str, object]]:
    payload = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    return {source["token"]: source for source in payload["sources"]}


def _employers_by_id() -> dict[str, dict[str, object]]:
    payload = json.loads(EMPLOYERS_PATH.read_text(encoding="utf-8"))
    return {employer["id"]: employer for employer in payload["employers"]}


def test_patch_65_adds_supported_official_sources() -> None:
    sources = _sources_by_token()

    bash = sources["bashdotcom"]
    assert bash["provider"] == "greenhouse"
    assert bash["employer_id"] == "tfg"
    assert bash["enabled"] is True

    firstrand = sources["firstrand"]
    assert firstrand["provider"] == "workday"
    assert firstrand["host"] == "https://firstrand.wd3.myworkdayjobs.com"
    assert firstrand["tenant"] == "firstrand"
    assert firstrand["site"] == "FRB"
    assert firstrand["employer_id"] == "firstrand"

    absa = sources["absa"]
    assert absa["provider"] == "workday"
    assert absa["host"] == "https://absa.wd3.myworkdayjobs.com"
    assert absa["tenant"] == "absa"
    assert absa["site"] == "ABSAcareersite"
    assert absa["employer_id"] == "absa"


def test_new_source_employers_are_active() -> None:
    employers = _employers_by_id()

    for employer_id in ("tfg", "firstrand", "absa"):
        assert employers[employer_id]["collection_status"] == "active"
