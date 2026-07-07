"""DDI predictor interface + the confidence gate (the safety-critical part).

The predictor flags *possible undocumented* drug-drug interactions. Per the
project's core invariant, its output is **warnings only**: it can raise a WARNING
about a pair the knowledge graph does not know, but it can NEVER downgrade a
BLOCK/DOWNGRADE from the deterministic Safety Authority to something safer.

The confidence gate enforces this: below a threshold the prediction is discarded
(defer to rules); above it, the prediction may only be surfaced as an additive
warning that sits *beside* the rule verdict, never replacing it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from mediguard.schemas import RuleHit, SafetyStatus, SafetyVerdict, Severity


@dataclass
class DDIPrediction:
    drug_a: str
    drug_b: str
    probability: float  # model's predicted interaction probability in [0,1]


class DDIPredictor(ABC):
    @abstractmethod
    def predict(self, drug_a: str, drug_b: str) -> DDIPrediction: ...

    @abstractmethod
    def known_pair(self, drug_a: str, drug_b: str) -> bool:
        """True if this pair is already in the curated KG (no novelty to add)."""


class ConfidenceGate:
    """Turns model predictions into warnings-only additions, never overrides."""

    def __init__(self, predictor: DDIPredictor, threshold: float = 0.7):
        self.predictor = predictor
        self.threshold = threshold

    def maybe_warn(self, drug_a: str, drug_b: str) -> RuleHit | None:
        """Return a WARNING RuleHit for a *novel* high-confidence interaction, else None."""
        # If the KG already documents the pair, the deterministic rules own it.
        if self.predictor.known_pair(drug_a, drug_b):
            return None
        pred = self.predictor.predict(drug_a, drug_b)
        if pred.probability < self.threshold:
            return None  # low confidence -> defer to rules, say nothing
        return RuleHit(
            rule_id=f"GNN_WARN::{drug_a}<->{drug_b}",
            severity=Severity.MINOR,  # advisory only; never MAJOR/CONTRAINDICATED
            message=(
                f"Model flags a possible undocumented interaction between {drug_a} "
                f"and {drug_b} (confidence {pred.probability:.2f}). This is an "
                f"unverified warning — not a rule-based finding. Verify clinically."
            ),
            evidence=f"gnn_probability={pred.probability:.3f} (warnings-only)",
        )

    def augment(self, verdict: SafetyVerdict, current_meds: list[str]) -> SafetyVerdict:
        """Attach model warnings to a verdict WITHOUT changing its status.

        Safety invariant: the returned verdict's status is identical to the input.
        The gate can only *add* MINOR advisory reasons; it can never make an
        unsafe verdict look safe.
        """
        cand = verdict.candidate.drug.name
        extra: list[RuleHit] = []
        for med in current_meds:
            hit = self.maybe_warn(cand, med)
            if hit is not None:
                extra.append(hit)
        if not extra:
            return verdict
        # Rebuild with the SAME status; only reasons/fired_rules grow.
        assert verdict.status in SafetyStatus  # explicit: status is preserved
        return SafetyVerdict(
            candidate=verdict.candidate,
            status=verdict.status,  # <-- never changed
            reasons=[*verdict.reasons, *extra],
            fired_rules=[*verdict.fired_rules, *[h.rule_id for h in extra]],
        )
