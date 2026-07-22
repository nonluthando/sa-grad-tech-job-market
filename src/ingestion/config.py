"""Load and validate configured job sources."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GreenhouseSource:
    """A configured public Greenhouse job board."""

    name: str
    token: str


def load_greenhouse_sources(
    config_path: Path,
    requested_tokens: set[str] | None = None,
) -> list[GreenhouseSource]:
    """Return enabled Greenhouse sources, optionally filtered by board token."""

    payload: Any = json.loads(config_path.read_text(encoding="utf-8"))
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError("Source configuration must contain a sources list.")

    sources: list[GreenhouseSource] = []
    seen_tokens: set[str] = set()

    for raw_source in raw_sources:
        if not isinstance(raw_source, dict):
            raise ValueError("Every configured source must be an object.")
        if raw_source.get("provider") != "greenhouse":
            continue
        if not raw_source.get("enabled", True):
            continue

        name = str(raw_source.get("name") or "").strip()
        token = str(raw_source.get("token") or "").strip()
        if not name or not token:
            raise ValueError("Enabled Greenhouse sources require name and token.")
        if token in seen_tokens:
            raise ValueError(f"Duplicate Greenhouse board token: {token}")

        seen_tokens.add(token)
        if requested_tokens is None or token in requested_tokens:
            sources.append(GreenhouseSource(name=name, token=token))

    if requested_tokens:
        configured_tokens = {source.token for source in sources}
        missing_tokens = requested_tokens - configured_tokens
        if missing_tokens:
            missing = ", ".join(sorted(missing_tokens))
            raise ValueError(f"Unknown or disabled Greenhouse source token(s): {missing}")

    if not sources:
        raise ValueError("No enabled Greenhouse sources matched the request.")

    return sources
