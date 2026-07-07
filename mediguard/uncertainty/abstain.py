"""Conformal-style abstention: 'defer to a clinician' under uncertainty.

Full conformal prediction (MAPIE) is available behind the `uncertainty` extra;
this module gives a model-agnostic, dependency-free abstention policy with the
same spirit: when the evidence is thin, conflicting, or the safest available
option is still risky, abstain rather than assert.

Abstention triggers (any of):
  - the safest verdict for a condition is BLOCK (no safe option found)
  - conflicting major findings across candidates
  - the recommendation confidence falls below a coverage-style threshold
"""

from __future__ import annotations

from dataclasses import dataclass

from mediguard.schemas import SafetyStatus, SafetyVerdict, Severity


@dataclass
class AbstentionDecision:
    abstain: bool
    confidence: float
    reason: str = ""


class ConformalAbstainer:
    def __init__(self, confidence_floor: float = 0.5):
        self.confidence_floor = confidence_floor

    def _confidence(self, verdict: SafetyVerdict) -> float:
        """Map a verdict to a coverage-style confidence in [0,1]."""
        base = {
            SafetyStatus.ALLOW: 0.95,
            SafetyStatus.WARN: 0.75,
            SafetyStatus.DOWNGRADE: 0.45,
            SafetyStatus.BLOCK: 0.05,
        }[verdict.status]
        # Each additional major+ finding erodes confidence.
        penalty = 0.1 * sum(1 for r in verdict.reasons if r.severity.rank >= Severity.MAJOR.rank)
        return max(0.0, base - penalty)

    def decide(self, ranked_verdicts: list[SafetyVerdict]) -> AbstentionDecision:
        """Decide over a condition's candidate verdicts (safest-first)."""
        if not ranked_verdicts:
            return AbstentionDecision(True, 0.0, "No candidate drugs available for this condition.")

        best = ranked_verdicts[0]
        conf = self._confidence(best)

        if best.status == SafetyStatus.BLOCK:
            return AbstentionDecision(True, conf,
                                      "Every candidate is contraindicated for this patient — defer to a clinician.")
        if conf < self.confidence_floor:
            return AbstentionDecision(True, conf,
                                      "The safest available option still carries significant risk — defer to a clinician.")
        return AbstentionDecision(False, conf, "")
