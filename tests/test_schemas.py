"""Phase 0 acceptance: schemas import and the safety invariant holds."""

import pytest
from pydantic import ValidationError

from mediguard.schemas import (
    CONSENT_DIRECTIVE,
    Candidate,
    CandidateSource,
    CodedConcept,
    CodedDrug,
    CodingSystem,
    PatientProfile,
    Recommendation,
    RuleHit,
    SafetyStatus,
    SafetyVerdict,
    Severity,
    Vitals,
)


def _candidate() -> Candidate:
    return Candidate(
        drug=CodedDrug(rxcui="6809", name="metformin", salt="metformin"),
        for_condition=CodedConcept(code="73211009", system=CodingSystem.SNOMED, display="Diabetes"),
        source=CandidateSource.KG,
    )


def test_schemas_import_and_construct():
    p = PatientProfile(age=32, pregnant=True, vitals=Vitals(bp="90/60", sugar="high"))
    assert p.age == 32
    assert p.consent_captured is False
    assert isinstance(p.vitals, Vitals)


def test_patientprofile_helpers():
    p = PatientProfile(
        conditions=[CodedConcept(code="I10", system=CodingSystem.ICD10, display="Hypertension")],
        current_meds=[CodedDrug(rxcui="6809", name="metformin")],
    )
    assert p.has_condition("I10")
    assert p.has_condition("I10", CodingSystem.ICD10)
    assert not p.has_condition("I10", CodingSystem.SNOMED)
    assert p.on_drug("6809")
    assert not p.on_drug("nope")


def test_severity_ordering():
    assert Severity.CONTRAINDICATED.rank > Severity.MAJOR.rank > Severity.INFO.rank


def test_coded_drug_key_prefers_rxcui():
    assert CodedDrug(rxcui="6809", name="Metformin").key == "6809"
    assert CodedDrug(name="Metformin").key == "metformin"


def test_verdict_max_severity():
    v = SafetyVerdict(
        candidate=_candidate(),
        status=SafetyStatus.WARN,
        reasons=[
            RuleHit(rule_id="r1", severity=Severity.MINOR, message="m"),
            RuleHit(rule_id="r2", severity=Severity.MAJOR, message="m"),
        ],
    )
    assert v.max_severity == Severity.MAJOR


def test_rulehit_requires_id():
    with pytest.raises(ValidationError):
        RuleHit(rule_id="  ", severity=Severity.INFO, message="x")


def test_blocked_candidate_cannot_be_actionable_recommendation():
    v = SafetyVerdict(candidate=_candidate(), status=SafetyStatus.BLOCK)
    # Non-abstaining recommendation from a BLOCK must be rejected.
    with pytest.raises(ValidationError):
        Recommendation(candidate=v.candidate, verdict=v, abstain=False)
    # But it may be reported as an abstention (to explain the rejection).
    rec = Recommendation(candidate=v.candidate, verdict=v, abstain=True)
    assert rec.abstain is True


def test_every_recommendation_carries_disclaimer():
    v = SafetyVerdict(candidate=_candidate(), status=SafetyStatus.ALLOW)
    rec = Recommendation(candidate=v.candidate, verdict=v)
    assert rec.disclaimer == CONSENT_DIRECTIVE
    with pytest.raises(ValidationError):
        Recommendation(candidate=v.candidate, verdict=v, disclaimer="   ")
