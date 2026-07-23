"""Load and validate configured job sources."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


SUPPORTED_COLLECTION_PROVIDERS = (
    "greenhouse",
    "lever",
    "successfactors",
    "workday",
    "oracle_hcm",
    "wp_job_manager",
)


@dataclass(frozen=True)
class ConfiguredSource:
    """One enabled public job-board source."""

    name: str
    provider: str
    token: str
    listing_url: str | None = None
    api_url: str | None = None
    host: str | None = None
    tenant: str | None = None
    site: str | None = None
    page_size: int = 25
    max_pages: int = 10
    request_delay_seconds: float = 0.2


@dataclass(frozen=True)
class GreenhouseSource:
    """A configured public Greenhouse job board."""

    name: str
    token: str


@dataclass(frozen=True)
class LeverSource:
    """A configured public Lever postings site."""

    name: str
    token: str


@dataclass(frozen=True)
class SuccessFactorsSource:
    """A configured public SAP SuccessFactors career site."""

    name: str
    token: str
    listing_url: str
    page_size: int = 25
    max_pages: int = 10
    request_delay_seconds: float = 0.2


@dataclass(frozen=True)
class WorkdaySource:
    """A configured public Workday Candidate Experience site."""

    name: str
    token: str
    host: str
    tenant: str
    site: str
    page_size: int = 20
    max_pages: int = 20
    request_delay_seconds: float = 0.1


@dataclass(frozen=True)
class OracleHCMSource:
    """A configured public Oracle Candidate Experience site."""

    name: str
    token: str
    host: str
    site: str
    page_size: int = 25
    max_pages: int = 20
    request_delay_seconds: float = 0.1


@dataclass(frozen=True)
class WPJobManagerSource:
    """A configured public WP Job Manager careers page."""

    name: str
    token: str
    listing_url: str
    api_url: str
    page_size: int = 100
    max_pages: int = 10
    request_delay_seconds: float = 0.1


def _read_raw_sources(config_path: Path) -> list[dict[str, Any]]:
    payload: Any = json.loads(config_path.read_text(encoding="utf-8"))
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError("Source configuration must contain a sources list.")

    validated: list[dict[str, Any]] = []
    for raw_source in raw_sources:
        if not isinstance(raw_source, dict):
            raise ValueError("Every configured source must be an object.")
        validated.append(raw_source)
    return validated


def _positive_int(value: Any, field_name: str, default: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")
    return value


def _nonnegative_float(value: Any, field_name: str, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative number.")
    return float(value)


def _https_url(raw_value: Any, field_name: str, provider: str) -> str:
    value = str(raw_value or "").strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(
            f"Enabled {provider} sources require an absolute HTTPS {field_name}."
        )
    return value


def _pagination_settings(
    raw_source: dict[str, Any],
    *,
    default_page_size: int,
    default_max_pages: int,
    default_delay: float,
) -> tuple[int, int, float]:
    page_size = _positive_int(
        raw_source.get("page_size"),
        "page_size",
        default_page_size,
    )
    max_pages = _positive_int(
        raw_source.get("max_pages"),
        "max_pages",
        default_max_pages,
    )
    request_delay_seconds = _nonnegative_float(
        raw_source.get("request_delay_seconds"),
        "request_delay_seconds",
        default_delay,
    )
    return page_size, max_pages, request_delay_seconds


def _successfactors_settings(raw_source: dict[str, Any]) -> tuple[str, int, int, float]:
    listing_url = _https_url(raw_source.get("url"), "url", "successfactors")
    page_size, max_pages, delay = _pagination_settings(
        raw_source,
        default_page_size=25,
        default_max_pages=10,
        default_delay=0.2,
    )
    return listing_url, page_size, max_pages, delay


def _workday_settings(raw_source: dict[str, Any]) -> tuple[str, str, str, int, int, float]:
    host = _https_url(raw_source.get("host"), "host", "workday")
    tenant = str(raw_source.get("tenant") or "").strip()
    site = str(raw_source.get("site") or "").strip()
    if not tenant or not site:
        raise ValueError("Enabled workday sources require tenant and site.")
    page_size, max_pages, delay = _pagination_settings(
        raw_source,
        default_page_size=20,
        default_max_pages=20,
        default_delay=0.1,
    )
    return host, tenant, site, page_size, max_pages, delay


def _oracle_hcm_settings(raw_source: dict[str, Any]) -> tuple[str, str, int, int, float]:
    host = _https_url(raw_source.get("host"), "host", "oracle_hcm")
    site = str(raw_source.get("site") or "").strip()
    if not site:
        raise ValueError("Enabled oracle_hcm sources require site.")
    page_size, max_pages, delay = _pagination_settings(
        raw_source,
        default_page_size=25,
        default_max_pages=20,
        default_delay=0.1,
    )
    return host, site, page_size, max_pages, delay


def _wp_job_manager_settings(
    raw_source: dict[str, Any],
) -> tuple[str, str, int, int, float]:
    listing_url = _https_url(
        raw_source.get("url"),
        "url",
        "wp_job_manager",
    )
    api_url = _https_url(
        raw_source.get("api_url"),
        "api_url",
        "wp_job_manager",
    )
    page_size, max_pages, delay = _pagination_settings(
        raw_source,
        default_page_size=100,
        default_max_pages=10,
        default_delay=0.1,
    )
    return listing_url, api_url, page_size, max_pages, delay


def _load_provider_sources(
    config_path: Path,
    *,
    provider: str,
    requested_tokens: set[str] | None,
) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    seen_tokens: set[str] = set()

    for raw_source in _read_raw_sources(config_path):
        if raw_source.get("provider") != provider:
            continue
        if not raw_source.get("enabled", True):
            continue

        name = str(raw_source.get("name") or "").strip()
        token = str(raw_source.get("token") or "").strip()
        if not name or not token:
            raise ValueError(f"Enabled {provider} sources require name and token.")
        if token in seen_tokens:
            raise ValueError(f"Duplicate {provider} source token: {token}")

        seen_tokens.add(token)
        if requested_tokens is None or token in requested_tokens:
            sources.append((name, token))

    if requested_tokens:
        configured_tokens = {token for _, token in sources}
        missing_tokens = requested_tokens - configured_tokens
        if missing_tokens:
            missing = ", ".join(sorted(missing_tokens))
            raise ValueError(
                f"Unknown or disabled {provider} source token(s): {missing}"
            )

    if not sources:
        raise ValueError(f"No enabled {provider} sources matched the request.")

    return sources


def load_greenhouse_sources(
    config_path: Path,
    requested_tokens: set[str] | None = None,
) -> list[GreenhouseSource]:
    """Return enabled Greenhouse sources, optionally filtered by board token."""

    return [
        GreenhouseSource(name=name, token=token)
        for name, token in _load_provider_sources(
            config_path,
            provider="greenhouse",
            requested_tokens=requested_tokens,
        )
    ]


def load_lever_sources(
    config_path: Path,
    requested_tokens: set[str] | None = None,
) -> list[LeverSource]:
    """Return enabled Lever sources, optionally filtered by site token."""

    return [
        LeverSource(name=name, token=token)
        for name, token in _load_provider_sources(
            config_path,
            provider="lever",
            requested_tokens=requested_tokens,
        )
    ]


def load_successfactors_sources(
    config_path: Path,
    requested_tokens: set[str] | None = None,
) -> list[SuccessFactorsSource]:
    """Return enabled SuccessFactors sources with validated pagination settings."""

    return [
        SuccessFactorsSource(
            name=source.name,
            token=source.token,
            listing_url=str(source.listing_url),
            page_size=source.page_size,
            max_pages=source.max_pages,
            request_delay_seconds=source.request_delay_seconds,
        )
        for source in load_collection_sources(
            config_path,
            requested_tokens,
            providers=("successfactors",),
        )
    ]


def load_collection_sources(
    config_path: Path,
    requested_tokens: set[str] | None = None,
    providers: Iterable[str] = SUPPORTED_COLLECTION_PROVIDERS,
) -> list[ConfiguredSource]:
    """Return enabled sources supported by the production collector."""

    requested_providers = tuple(providers)
    unsupported = set(requested_providers) - set(SUPPORTED_COLLECTION_PROVIDERS)
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise ValueError(f"Unsupported collection provider(s): {names}")

    sources: list[ConfiguredSource] = []
    seen_source_keys: set[tuple[str, str]] = set()

    for raw_source in _read_raw_sources(config_path):
        provider = str(raw_source.get("provider") or "").strip()
        if provider not in requested_providers:
            continue
        if not raw_source.get("enabled", True):
            continue

        name = str(raw_source.get("name") or "").strip()
        token = str(raw_source.get("token") or "").strip()
        if not name or not token:
            raise ValueError(f"Enabled {provider} sources require name and token.")

        source_key = (provider, token)
        if source_key in seen_source_keys:
            raise ValueError(f"Duplicate configured source: {provider}:{token}")
        seen_source_keys.add(source_key)
        if requested_tokens is not None and token not in requested_tokens:
            continue

        if provider == "successfactors":
            listing_url, page_size, max_pages, delay = _successfactors_settings(
                raw_source
            )
            sources.append(
                ConfiguredSource(
                    name=name,
                    provider=provider,
                    token=token,
                    listing_url=listing_url,
                    page_size=page_size,
                    max_pages=max_pages,
                    request_delay_seconds=delay,
                )
            )
        elif provider == "workday":
            host, tenant, site, page_size, max_pages, delay = _workday_settings(
                raw_source
            )
            sources.append(
                ConfiguredSource(
                    name=name,
                    provider=provider,
                    token=token,
                    host=host,
                    tenant=tenant,
                    site=site,
                    page_size=page_size,
                    max_pages=max_pages,
                    request_delay_seconds=delay,
                )
            )
        elif provider == "oracle_hcm":
            host, site, page_size, max_pages, delay = _oracle_hcm_settings(
                raw_source
            )
            sources.append(
                ConfiguredSource(
                    name=name,
                    provider=provider,
                    token=token,
                    host=host,
                    site=site,
                    page_size=page_size,
                    max_pages=max_pages,
                    request_delay_seconds=delay,
                )
            )
        elif provider == "wp_job_manager":
            listing_url, api_url, page_size, max_pages, delay = (
                _wp_job_manager_settings(raw_source)
            )
            sources.append(
                ConfiguredSource(
                    name=name,
                    provider=provider,
                    token=token,
                    listing_url=listing_url,
                    api_url=api_url,
                    page_size=page_size,
                    max_pages=max_pages,
                    request_delay_seconds=delay,
                )
            )
        else:
            sources.append(
                ConfiguredSource(name=name, provider=provider, token=token)
            )

    if requested_tokens:
        matched_tokens = {source.token for source in sources}
        missing_tokens = requested_tokens - matched_tokens
        if missing_tokens:
            missing = ", ".join(sorted(missing_tokens))
            raise ValueError(f"Unknown or disabled source token(s): {missing}")

    if not sources:
        raise ValueError("No enabled supported sources matched the request.")

    return sources
