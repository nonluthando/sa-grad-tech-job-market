from __future__ import annotations

import json
from pathlib import Path

from src.configuration.employers import employer_index, load_employer_registry


ROOT = Path(__file__).resolve().parents[1]


def test_expanded_direct_employer_sources_are_active_lever_boards() -> None:
    employers = employer_index(
        load_employer_registry(ROOT / "config" / "employers.json")
    )
    source_payload = json.loads(
        (ROOT / "config" / "sources.json").read_text(encoding="utf-8")
    )
    sources_by_employer = {
        source["employer_id"]: source
        for source in source_payload["sources"]
    }

    expected = {
        "binance": "binance",
        "theodo": "theodo",
        "moo": "moo",
    }
    for employer_id, token in expected.items():
        source = sources_by_employer[employer_id]
        assert source["provider"] == "lever"
        assert source["token"] == token
        assert source["enabled"] is True
        assert employers[employer_id]["collection_status"] == "active"
