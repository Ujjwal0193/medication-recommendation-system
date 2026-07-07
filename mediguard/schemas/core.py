"""Core Pydantic contracts for the MediGuard pipeline.

These are the *only* objects that cross layer boundaries:

    raw text ─(NLP)→ PatientProfile
    condition ─(candidates)→ Candidate
    (PatientProfile, Candidate) ─(safety)→ SafetyVerdict
    SafetyVerdict ─(explain)→ Recommendation

Safety invariant encoded here: a ``SafetyVerdict`` with status ``BLOCK`` can
never be turned into an allowed recommendation. See ``Recommendation`` validators.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

# --------------------------------------------------------------------------- #
# Mandatory consent / disclaimer text. Appended to every user-facing output.
# --------------------------------------------------------------------------- #
CONSENT_DIRECTIVE = (
    "IMPORTANT: MediGuard is an educational decision-support prototype, not a "
    "diagnostic device or a prescriber. This output is advisory only. Consult a "
    "qualified doctor or pharmacist before taking, stopping, or changing any "
    "medication."
)


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #
class CodingSystem(str, Enum):
    """Standard terminologies used for coded concepts."""

    SNOMED = "SNOMED"
    ICD10 = "ICD-10"
    RXNORM = "RxNorm"
    ATC = "ATC"
    LOCAL = "LOCAL"  # provisional / uncoded, pre-linking


class Severity(str, Enum):
    """Clinical severity of a rule hit. Ordered least → most severe."""

    INFO = "info"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CONTRAINDICATED = "contraindicated"

    @property
    def rank(self) -> int:
        order = [
            Severity.INFO,
            Severity.MINOR,
            Severity.MODERATE,
            Severity.MAJOR,
            Severity.CONTRAINDICATED,
        ]
        return order.index(self)


class SafetyStatus(str, Enum):
    """Outcome the Safety Authority assigns to a candidate."""

    ALLOW = "allow"
    WARN = "warn"
    DOWNGRADE = "downgrade"
    BLOCK = "block"


class PregnancyCategory(str, Enum):
    """US-FDA-style pregnancy risk category (legacy A/B/C/D/X scheme).

    X is an absolute contraindication in pregnancy → hard block.
    """

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    X = "X"
    UNKNOWN = "unknown"


class CandidateSource(str, Enum):
    KG = "kg"
    GUIDELINE = "guideline"
    ML = "ml"


# --------------------------------------------------------------------------- #
# Coded concepts
# --------------------------------------------------------------------------- #
class CodedConcept(BaseModel):
    """A clinical concept mapped to a standard terminology (or LOCAL if unlinked)."""

    code: str
    system: CodingSystem = CodingSystem.LOCAL
    display: str = ""

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.display or self.code} [{self.system.value}:{self.code}]"


class CodedDrug(BaseModel):
    """A drug identified by RxNorm RxCUI where possible, plus its active salt."""

    rxcui: str | None = None
    name: str
    salt: str | None = None
    atc: str | None = None

    @property
    def key(self) -> str:
        """Stable identity used as a graph key: RxCUI if present, else lowered name."""
        return self.rxcui or self.name.strip().lower()


class Vitals(BaseModel):
    bp: str | None = None  # e.g. "150/95" or qualitative "high"/"low"
    sugar: str | None = None  # e.g. "180" or "high"/"low"
    weight_kg: float | None = None
    renal: str | None = None  # e.g. "normal", "impaired", eGFR value


# --------------------------------------------------------------------------- #
# PatientProfile — output of the NLP layer, input to everything downstream
# --------------------------------------------------------------------------- #
class PatientProfile(BaseModel):
    age: int | None = Field(default=None, ge=0, le=130)
    sex: str | None = None
    pregnant: bool | None = None
    conditions: list[CodedConcept] = Field(default_factory=list)
    current_meds: list[CodedDrug] = Field(default_factory=list)
    allergies: list[CodedConcept] = Field(default_factory=list)
    vitals: Vitals = Field(default_factory=Vitals)
    raw_text: str = ""
    consent_captured: bool = False

    def has_condition(self, code: str, system: CodingSystem | None = None) -> bool:
        for c in self.conditions:
            if c.code == code and (system is None or c.system == system):
                return True
        return False

    def on_drug(self, key: str) -> bool:
        return any(m.key == key for m in self.current_meds)


# --------------------------------------------------------------------------- #
# Candidate — a proposed drug for a condition, pre-safety-check
# --------------------------------------------------------------------------- #
class Candidate(BaseModel):
    drug: CodedDrug
    for_condition: CodedConcept
    source: CandidateSource = CandidateSource.KG


# --------------------------------------------------------------------------- #
# SafetyVerdict — output of the Safety Authority (the guardrail)
# --------------------------------------------------------------------------- #
class RuleHit(BaseModel):
    rule_id: str
    severity: Severity
    message: str
    evidence: str = ""  # KG fact / source supporting the hit

    @field_validator("rule_id")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("rule_id must be non-empty")
        return v


class SafetyVerdict(BaseModel):
    candidate: Candidate
    status: SafetyStatus
    reasons: list[RuleHit] = Field(default_factory=list)
    fired_rules: list[str] = Field(default_factory=list)

    @property
    def is_blocked(self) -> bool:
        return self.status == SafetyStatus.BLOCK

    @property
    def max_severity(self) -> Severity:
        if not self.reasons:
            return Severity.INFO
        return max((r.severity for r in self.reasons), key=lambda s: s.rank)


# --------------------------------------------------------------------------- #
# Recommendation — final user-facing object, enforces the safety invariant
# --------------------------------------------------------------------------- #
class Recommendation(BaseModel):
    candidate: Candidate
    verdict: SafetyVerdict
    rationale: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    abstain: bool = False
    disclaimer: str = CONSENT_DIRECTIVE

    @model_validator(mode="after")
    def _enforce_safety_invariant(self) -> Recommendation:
        # A blocked candidate must never be presented as a usable recommendation.
        # It may still be *reported* (abstain=True) to explain why it was rejected,
        # but it can never be an actionable, non-abstaining suggestion.
        if self.verdict.is_blocked and not self.abstain:
            raise ValueError(
                "Safety invariant violated: a BLOCKED candidate cannot be a "
                "non-abstaining recommendation. Set abstain=True or drop it."
            )
        if not self.disclaimer.strip():
            raise ValueError("Every recommendation must carry the consent directive.")
        return self
