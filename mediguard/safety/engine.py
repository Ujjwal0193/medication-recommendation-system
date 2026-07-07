"""Safety Authority engine — the final decision-maker on candidate safety.

Runs every rule over (patient, candidate), collects RuleHits, then maps the worst
severity to a SafetyStatus. This is the deterministic guardrail: no ML/LLM output
reaches here, and nothing downstream may turn a BLOCK into an actionable rec (the
Recommendation schema enforces that separately).

Severity → status:
    CONTRAINDICATED           -> BLOCK
    MAJOR                     -> DOWNGRADE  (usable only if nothing safer exists)
    MODERATE / MINOR          -> WARN
    (no hits)                 -> ALLOW

Alert-fatigue handling: hits are severity-sorted and de-duplicated; sub-threshold
INFO/MINOR noise can be suppressed from the surfaced reasons (still logged in
fired_rules for the audit trail).
"""

from __future__ import annotations

from mediguard.kg.base import KnowledgeGraph
from mediguard.kg.factory import get_kg
from mediguard.safety.rules import ALL_RULES, Rule
from mediguard.schemas import (
    Candidate,
    PatientProfile,
    RuleHit,
    SafetyStatus,
    SafetyVerdict,
    Severity,
)

# Minimum severity to surface a reason to the user (alert-fatigue suppression).
# Everything is still recorded in fired_rules for the audit log.
_SURFACE_THRESHOLD = Severity.MINOR


def _status_for(max_sev: Severity) -> SafetyStatus:
    if max_sev == Severity.CONTRAINDICATED:
        return SafetyStatus.BLOCK
    if max_sev == Severity.MAJOR:
        return SafetyStatus.DOWNGRADE
    if max_sev in (Severity.MODERATE, Severity.MINOR):
        return SafetyStatus.WARN
    return SafetyStatus.ALLOW


class SafetyAuthority:
    def __init__(self, kg: KnowledgeGraph | None = None, rules: list[Rule] | None = None,
                 surface_threshold: Severity = _SURFACE_THRESHOLD):
        self.kg = kg or get_kg()
        self.rules = rules or ALL_RULES
        self.surface_threshold = surface_threshold

    def evaluate(self, patient: PatientProfile, candidate: Candidate) -> SafetyVerdict:
        raw_hits: list[RuleHit] = []
        fired: list[str] = []
        for rule in self.rules:
            for hit in rule(patient, candidate, self.kg):
                raw_hits.append(hit)
                fired.append(hit.rule_id)

        # De-duplicate by rule_id (a rule may report the same finding twice).
        seen: set[str] = set()
        hits: list[RuleHit] = []
        for h in sorted(raw_hits, key=lambda x: x.severity.rank, reverse=True):
            if h.rule_id in seen:
                continue
            seen.add(h.rule_id)
            hits.append(h)

        max_sev = hits[0].severity if hits else Severity.INFO
        status = _status_for(max_sev)

        # Alert-fatigue: surface only reasons at/above threshold, but never hide
        # a BLOCK/DOWNGRADE driver.
        surfaced = [
            h for h in hits
            if h.severity.rank >= self.surface_threshold.rank
            or h.severity in (Severity.MAJOR, Severity.CONTRAINDICATED)
        ]

        return SafetyVerdict(
            candidate=candidate,
            status=status,
            reasons=surfaced,
            fired_rules=fired,
        )

    def evaluate_all(self, patient: PatientProfile, candidates: list[Candidate]) -> list[SafetyVerdict]:
        """Evaluate a list of candidates, returning verdicts ranked safest-first.

        Ordering: ALLOW < WARN < DOWNGRADE < BLOCK by max severity. This lets the
        candidate-generation / explanation layers prefer the safest viable option.
        """
        verdicts = [self.evaluate(patient, c) for c in candidates]
        order = {
            SafetyStatus.ALLOW: 0,
            SafetyStatus.WARN: 1,
            SafetyStatus.DOWNGRADE: 2,
            SafetyStatus.BLOCK: 3,
        }
        return sorted(verdicts, key=lambda v: (order[v.status], v.max_severity.rank))
