"""Phase 4 acceptance: DDI predictor metrics + the confidence gate never overrides.

The single most important safety test in this phase:
    a model prediction can NEVER turn a BLOCK/DOWNGRADE verdict into something safer.
"""

import pytest

from mediguard.gnn.base import ConfidenceGate, DDIPrediction, DDIPredictor
from mediguard.gnn.predictor import SpectralDDIPredictor
from mediguard.schemas import (
    Candidate,
    CodedConcept,
    CodedDrug,
    CodingSystem,
    SafetyStatus,
    SafetyVerdict,
    Severity,
)


@pytest.fixture(scope="module")
def predictor():
    return SpectralDDIPredictor()


def _verdict(status: SafetyStatus) -> SafetyVerdict:
    cand = Candidate(
        drug=CodedDrug(name="Warfarin"),
        for_condition=CodedConcept(code="I48", system=CodingSystem.ICD10),
    )
    return SafetyVerdict(candidate=cand, status=status)


def test_predictor_returns_probabilities(predictor):
    p = predictor.predict("Warfarin", "Aspirin")
    assert 0.0 <= p.probability <= 1.0
    assert predictor.known_pair("Warfarin", "Aspirin")  # curated pair
    assert not predictor.known_pair("Levothyroxine", "Cetirizine")  # not curated


def test_metrics_reported(predictor):
    m = predictor.evaluate()
    print(f"\nDDI predictor — AUROC={m['auroc']:.3f} AUPRC={m['auprc']:.3f} "
          f"Hits@K={m['hits_at_k']}")
    assert 0.0 <= m["auroc"] <= 1.0
    assert m["auroc"] >= 0.5  # better than random on held-out links


# ---- the safety-critical invariant tests ---------------------------------- #
class _AlwaysHighPredictor(DDIPredictor):
    """Adversarial: claims every unknown pair is a certain interaction."""

    def predict(self, a, b):
        return DDIPrediction(a, b, 0.99)

    def known_pair(self, a, b):
        return False


def test_gate_never_changes_block_status():
    gate = ConfidenceGate(_AlwaysHighPredictor(), threshold=0.7)
    blocked = _verdict(SafetyStatus.BLOCK)
    out = gate.augment(blocked, current_meds=["Cetirizine", "Paracetamol"])
    assert out.status == SafetyStatus.BLOCK  # status preserved


def test_gate_never_upgrades_downgrade_to_allow():
    gate = ConfidenceGate(_AlwaysHighPredictor(), threshold=0.7)
    for status in (SafetyStatus.DOWNGRADE, SafetyStatus.WARN, SafetyStatus.ALLOW):
        out = gate.augment(_verdict(status), current_meds=["Cetirizine"])
        assert out.status == status  # never changed in any direction


def test_gate_only_adds_minor_advisory_warnings():
    gate = ConfidenceGate(_AlwaysHighPredictor(), threshold=0.7)
    out = gate.augment(_verdict(SafetyStatus.ALLOW), current_meds=["Cetirizine"])
    added = [r for r in out.reasons if r.rule_id.startswith("GNN_WARN")]
    assert added, "expected an advisory warning to be added"
    assert all(r.severity == Severity.MINOR for r in added)  # never MAJOR/CONTRA


def test_gate_stays_silent_below_threshold():
    class LowPred(DDIPredictor):
        def predict(self, a, b):
            return DDIPrediction(a, b, 0.10)

        def known_pair(self, a, b):
            return False

    gate = ConfidenceGate(LowPred(), threshold=0.7)
    out = gate.augment(_verdict(SafetyStatus.ALLOW), current_meds=["Cetirizine"])
    assert not [r for r in out.reasons if r.rule_id.startswith("GNN_WARN")]


def test_gate_defers_to_rules_on_known_pairs(predictor):
    # For a pair already in the KG, the gate stays silent (rules own it).
    gate = ConfidenceGate(predictor, threshold=0.0)
    assert gate.maybe_warn("Warfarin", "Aspirin") is None
