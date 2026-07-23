"""Explainable role-seniority scoring."""

from src.role_classification.classifier import classify_role
from src.role_classification.models import (
    ClassificationEvidence,
    RoleClassificationResult,
)

__all__ = [
    "ClassificationEvidence",
    "RoleClassificationResult",
    "classify_role",
]
