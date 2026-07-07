"""End-to-end MediGuard pipeline: raw patient text/profile → explained, safety-checked
recommendations. This is the top-level orchestrator the API and UI call.

Flow (each arrow is a frozen-schema hand-off):
    raw text ─(NLP)→ PatientProfile
    per condition: candidates ─(SafetyAuthority)→ verdicts
                             ─(ConfidenceGate)→ verdicts + model warnings (no override)
                             ─(ConformalAbstainer)→ abstain?
                             ─(GraphRAG retrieve + Explainer)→ rationale
    every recommendation: consent directive + audit-logged.

The Safety Authority remains the sole decision-maker on safety; nothing here can
turn a BLOCK into an actionable recommendation (the Recommendation schema also
enforces this independently).
"""

from __future__ import annotations

from dataclasses import dataclass

from mediguard.audit.log import AuditLog
from mediguard.candidates.generator import CandidateGenerator
from mediguard.explain.explainer import Explainer, make_explainer
from mediguard.explain.retriever import SubgraphRetriever
from mediguard.gnn.base import ConfidenceGate
from mediguard.gnn.factory import make_ddi_predictor
from mediguard.nlp.factory import make_extractor
from mediguard.safety.engine import SafetyAuthority
from mediguard.schemas import (
    CONSENT_DIRECTIVE,
    PatientProfile,
    Recommendation,
    SafetyStatus,
)
from mediguard.uncertainty.abstain import ConformalAbstainer


@dataclass
class ConditionResult:
    condition_code: str
    condition_display: str
    abstain: bool
    abstain_reason: str
    recommendations: list[Recommendation]


class MediGuardPipeline:
    def __init__(self, *, enable_gnn: bool = True, explainer: Explainer | None = None):
        self.extractor = make_extractor()
        self.candidates = CandidateGenerator()
        self.authority = SafetyAuthority()
        self.retriever = SubgraphRetriever()
        self.explainer = explainer or make_explainer()
        self.abstainer = ConformalAbstainer()
        self.audit = AuditLog()
        self.gate = ConfidenceGate(make_ddi_predictor()) if enable_gnn else None

    # ------------------------------------------------------------------ #
    def from_text(self, text: str, *, consent_captured: bool = False) -> list[ConditionResult]:
        profile = self.extractor.extract(text, consent_captured=consent_captured)
        return self.run(profile)

    def run(self, profile: PatientProfile) -> list[ConditionResult]:
        results: list[ConditionResult] = []
        by_condition = self.candidates.for_patient(profile)

        for cond in profile.conditions:
            cands = by_condition.get(cond.code, [])
            if not cands:
                continue

            verdicts = self.authority.evaluate_all(profile, cands)
            if self.gate is not None:
                med_names = [m.name for m in profile.current_meds]
                verdicts = [self.gate.augment(v, med_names) for v in verdicts]
                # augment preserves status, so safest-first order is unchanged.

            decision = self.abstainer.decide(verdicts)

            recs: list[Recommendation] = []
            for v in verdicts:
                ctx = self.retriever.retrieve(profile, v)
                rationale = self.explainer.explain(ctx)
                # Blocked candidates are reported as abstentions (explain why rejected).
                is_abstain = decision.abstain or v.status == SafetyStatus.BLOCK
                recs.append(Recommendation(
                    candidate=v.candidate,
                    verdict=v,
                    rationale=rationale,
                    confidence=self.abstainer._confidence(v),
                    abstain=is_abstain,
                    disclaimer=CONSENT_DIRECTIVE,
                ))
                self.audit.record(v, patient_ref="pipeline")

            results.append(ConditionResult(
                condition_code=cond.code,
                condition_display=cond.display or cond.code,
                abstain=decision.abstain,
                abstain_reason=decision.reason,
                recommendations=recs,
            ))
        return results
