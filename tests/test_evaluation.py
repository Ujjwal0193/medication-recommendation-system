"""Phase 7: evaluation harness runs and the system invariant holds on synthetics."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.synthetic_patients import generate_patients
from mediguard.pipeline import MediGuardPipeline
from mediguard.schemas import SafetyStatus


def test_synthetic_generation_consistent():
    pts = generate_patients(n=50)
    assert len(pts) == 50
    for p in pts:
        # A pregnant synthetic patient must be a female of childbearing age.
        if p.pregnant:
            assert p.sex == "female" and 18 <= (p.age or 0) <= 45


def test_system_safety_invariant_over_cohort():
    """No BLOCK ever leaks as an actionable recommendation across the cohort."""
    pipe = MediGuardPipeline()
    leaked = 0
    total = 0
    for p in generate_patients(n=80):
        for cr in pipe.run(p):
            for rec in cr.recommendations:
                total += 1
                if rec.verdict.status == SafetyStatus.BLOCK and not rec.abstain:
                    leaked += 1
    assert total > 0
    assert leaked == 0, f"{leaked} blocked recommendations leaked as actionable"


def test_explanation_faithfulness_over_cohort():
    pipe = MediGuardPipeline()
    unfaithful = 0
    for p in generate_patients(n=40):
        for cr in pipe.run(p):
            for rec in cr.recommendations:
                if rec.candidate.drug.name not in rec.rationale:
                    unfaithful += 1
                if any(r.message not in rec.rationale for r in rec.verdict.reasons):
                    unfaithful += 1
    assert unfaithful == 0
