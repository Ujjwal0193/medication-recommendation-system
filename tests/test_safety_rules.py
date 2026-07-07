"""Phase 2 acceptance: the Safety Authority flags 100% of the danger benchmark.

Also verifies the false-alert rate on a must-allow set (alert-fatigue proxy).
"""

import json
from pathlib import Path

import pytest

from mediguard.safety.engine import SafetyAuthority
from mediguard.schemas import (
    Candidate,
    CodedConcept,
    CodedDrug,
    CodingSystem,
    PatientProfile,
    SafetyStatus,
    Vitals,
)

FIXTURE = Path(__file__).parent / "fixtures" / "danger_cases.json"
_CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))

_STATUS_RANK = {
    SafetyStatus.ALLOW: 0,
    SafetyStatus.WARN: 1,
    SafetyStatus.DOWNGRADE: 2,
    SafetyStatus.BLOCK: 3,
}


@pytest.fixture(scope="module")
def authority():
    return SafetyAuthority()


def _build_patient(spec: dict) -> PatientProfile:
    return PatientProfile(
        age=spec.get("age"),
        pregnant=spec.get("pregnant"),
        conditions=[CodedConcept(**c) for c in spec.get("conditions", [])],
        current_meds=[CodedDrug(**m) for m in spec.get("current_meds", [])],
        allergies=[CodedConcept(**a) for a in spec.get("allergies", [])],
        vitals=Vitals(**spec.get("vitals", {})),
    )


def _build_candidate(case: dict) -> Candidate:
    fc = case["for_condition"]
    return Candidate(
        drug=CodedDrug(name=case["candidate"]),
        for_condition=CodedConcept(
            code=fc["code"],
            system=CodingSystem(fc["system"]),
            display=fc.get("display", ""),
        ),
    )


@pytest.mark.parametrize("case", _CASES["must_flag"], ids=[c["name"] for c in _CASES["must_flag"]])
def test_dangerous_combinations_are_flagged(authority, case):
    patient = _build_patient(case["patient"])
    candidate = _build_candidate(case)
    verdict = authority.evaluate(patient, candidate)

    expected = SafetyStatus(case["expect_min_status"])
    assert _STATUS_RANK[verdict.status] >= _STATUS_RANK[expected], (
        f"{case['name']}: expected >= {expected.value}, got {verdict.status.value}. "
        f"Reasons: {[r.message for r in verdict.reasons]}"
    )
    # Anything flagged must carry at least one surfaced reason.
    assert verdict.reasons, f"{case['name']}: flagged with no reason"


@pytest.mark.parametrize("case", _CASES["must_allow"], ids=[c["name"] for c in _CASES["must_allow"]])
def test_safe_combinations_are_allowed(authority, case):
    patient = _build_patient(case["patient"])
    candidate = _build_candidate(case)
    verdict = authority.evaluate(patient, candidate)
    assert verdict.status == SafetyStatus.ALLOW, (
        f"{case['name']}: expected allow, got {verdict.status.value} "
        f"({[r.message for r in verdict.reasons]})"
    )


def test_full_danger_list_coverage(authority):
    """Acceptance metric: 100% of known-danger cases caught; false-alert rate = 0."""
    missed = []
    for case in _CASES["must_flag"]:
        v = authority.evaluate(_build_patient(case["patient"]), _build_candidate(case))
        if _STATUS_RANK[v.status] < _STATUS_RANK[SafetyStatus(case["expect_min_status"])]:
            missed.append(case["name"])

    false_alerts = []
    for case in _CASES["must_allow"]:
        v = authority.evaluate(_build_patient(case["patient"]), _build_candidate(case))
        if v.status != SafetyStatus.ALLOW:
            false_alerts.append(case["name"])

    total = len(_CASES["must_flag"])
    caught = total - len(missed)
    print(f"\nSafety benchmark: {caught}/{total} dangerous combos flagged "
          f"({100*caught/total:.0f}%); false-alert rate "
          f"{len(false_alerts)}/{len(_CASES['must_allow'])}.")
    assert not missed, f"Missed dangerous cases: {missed}"
    assert not false_alerts, f"False alerts on safe cases: {false_alerts}"


def test_blocked_verdict_cannot_be_actionable(authority):
    from pydantic import ValidationError

    from mediguard.schemas import Recommendation

    patient = PatientProfile(age=30, pregnant=True)
    candidate = Candidate(
        drug=CodedDrug(name="Warfarin"),
        for_condition=CodedConcept(code="I48", system=CodingSystem.ICD10),
    )
    verdict = authority.evaluate(patient, candidate)
    assert verdict.status == SafetyStatus.BLOCK
    with pytest.raises(ValidationError):
        Recommendation(candidate=candidate, verdict=verdict, abstain=False)
