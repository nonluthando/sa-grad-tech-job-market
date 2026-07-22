import json

import pytest

from src.ingestion.config import load_greenhouse_sources


def test_load_greenhouse_sources_filters_other_providers(tmp_path):
    config_path = tmp_path / "sources.json"
    config_path.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Example",
                        "provider": "greenhouse",
                        "token": "example",
                        "enabled": True,
                    },
                    {
                        "name": "Other",
                        "provider": "lever",
                        "token": "other",
                        "enabled": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    sources = load_greenhouse_sources(config_path)

    assert [source.token for source in sources] == ["example"]


def test_load_greenhouse_sources_rejects_unknown_requested_token(tmp_path):
    config_path = tmp_path / "sources.json"
    config_path.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Example",
                        "provider": "greenhouse",
                        "token": "example",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown or disabled"):
        load_greenhouse_sources(config_path, {"missing"})
