"""Value objects returned by the role-classification engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassificationEvidence:
    """One explainable signal contributing to a role-level score."""

    source: str
    value: str
    weight: int
    category: str

    def as_text(self) -> str:
        sign = "+" if self.weight >= 0 else ""
        return f"{self.source}: {self.value} ({sign}{self.weight}, {self.category})"


@dataclass(frozen=True)
class RoleClassificationResult:
    """Scored seniority inference kept alongside the conservative canonical label."""

    level: str
    confidence: str
    score: int
    evidence: tuple[ClassificationEvidence, ...]
    is_talent_pool: bool
