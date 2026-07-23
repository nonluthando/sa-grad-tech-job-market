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


def test_load_collection_sources_includes_greenhouse_and_lever(tmp_path):
    from src.ingestion.config import load_collection_sources

    config_path = tmp_path / "sources.json"
    config_path.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Greenhouse Example",
                        "provider": "greenhouse",
                        "token": "greenhouse-example",
                        "enabled": True,
                    },
                    {
                        "name": "Lever Example",
                        "provider": "lever",
                        "token": "LeverExample",
                        "enabled": True,
                    },
                    {
                        "name": "HTML Example",
                        "provider": "html_listing_page",
                        "token": "html-example",
                        "enabled": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    sources = load_collection_sources(config_path)

    assert [(source.provider, source.token) for source in sources] == [
        ("greenhouse", "greenhouse-example"),
        ("lever", "LeverExample"),
    ]


def test_collection_token_filter_is_resolved_across_providers(tmp_path):
    from src.ingestion.config import load_collection_sources

    config_path = tmp_path / "sources.json"
    config_path.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Greenhouse Example",
                        "provider": "greenhouse",
                        "token": "greenhouse-example",
                    },
                    {
                        "name": "Lever Example",
                        "provider": "lever",
                        "token": "LeverExample",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    sources = load_collection_sources(config_path, {"LeverExample"})

    assert len(sources) == 1
    assert sources[0].provider == "lever"


def test_load_collection_sources_includes_successfactors_settings(tmp_path):
    from src.ingestion.config import load_collection_sources

    config_path = tmp_path / "sources.json"
    config_path.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Example Bank",
                        "provider": "successfactors",
                        "token": "example-bank",
                        "url": "https://jobs.example.test/go/All/123/",
                        "page_size": 20,
                        "max_pages": 7,
                        "request_delay_seconds": 0.1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    source = load_collection_sources(config_path)[0]

    assert source.provider == "successfactors"
    assert source.listing_url == "https://jobs.example.test/go/All/123/"
    assert source.page_size == 20
    assert source.max_pages == 7
    assert source.request_delay_seconds == 0.1


def test_successfactors_source_requires_https_url(tmp_path):
    from src.ingestion.config import load_collection_sources

    config_path = tmp_path / "sources.json"
    config_path.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Example Bank",
                        "provider": "successfactors",
                        "token": "example-bank",
                        "url": "http://jobs.example.test/go/All/123/",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="absolute HTTPS"):
        load_collection_sources(config_path)


def test_load_collection_sources_includes_new_provider_settings(tmp_path):
    from src.ingestion.config import load_collection_sources
    config_path = tmp_path / "sources.json"
    config_path.write_text(json.dumps({"sources": [
        {"name":"Digi","provider":"workday","token":"digi","host":"https://wd.test","tenant":"t","site":"s"},
        {"name":"ACI","provider":"oracle_hcm","token":"aci","host":"https://oracle.test","site":"CX"},
        {"name":"BET","provider":"wp_job_manager","token":"bet","url":"https://bet.test/jobs","api_url":"https://bet.test/ajax"},
    ]}), encoding="utf-8")
    sources = load_collection_sources(config_path)
    assert [source.provider for source in sources] == ["workday", "oracle_hcm", "wp_job_manager"]
    assert sources[0].tenant == "t"
    assert sources[1].site == "CX"
    assert sources[2].api_url == "https://bet.test/ajax"
