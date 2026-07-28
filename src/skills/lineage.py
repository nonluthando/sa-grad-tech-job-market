"""Stable lineage helpers shared by skills and analytics builds."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping


def job_text_sha256(job: Mapping[str, Any]) -> str:
    """Hash the exact title and description text used for extraction."""

    title = str(job.get("title") or "")
    description = str(job.get("description_text") or "")
    extraction_text = f"{title}\n{description}".strip()
    return hashlib.sha256(extraction_text.encode("utf-8")).hexdigest()
