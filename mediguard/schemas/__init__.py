"""Frozen data contracts shared across every MediGuard layer.

Layers consume these Pydantic models, never each other's internals or raw text.
Changing a field here is an API change — version it deliberately.
"""

from mediguard.schemas.core import (
    CONSENT_DIRECTIVE,
    Candidate,
    CandidateSource,
    CodedConcept,
    CodedDrug,
    CodingSystem,
    PatientProfile,
    PregnancyCategory,
    Recommendation,
    RuleHit,
    SafetyStatus,
    SafetyVerdict,
    Severity,
    Vitals,
)

__all__ = [
    "Candidate",
    "CandidateSource",
    "CodedConcept",
    "CodedDrug",
    "CodingSystem",
    "PatientProfile",
    "PregnancyCategory",
    "Recommendation",
    "RuleHit",
    "SafetyStatus",
    "SafetyVerdict",
    "Severity",
    "Vitals",
    "CONSENT_DIRECTIVE",
]
