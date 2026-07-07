"""GraphRAG retrieval: gather ONLY the KG facts relevant to a recommendation.

The explainer may use nothing but the facts returned here. Serializing the
retrieved subgraph into a strict, closed context is what structurally prevents
hallucination: the LLM (or template) can only restate provided facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mediguard.kg.base import KnowledgeGraph
from mediguard.kg.factory import get_kg
from mediguard.schemas import PatientProfile, SafetyVerdict


@dataclass
class EvidenceContext:
    """The closed set of facts an explanation is allowed to reference."""

    drug: str
    salt: str | None
    purpose: str
    dose: str
    timing: str
    route: str
    pregnancy_category: str
    for_condition: str
    verdict_status: str
    rule_reasons: list[str] = field(default_factory=list)
    interactions: list[str] = field(default_factory=list)
    contraindications: list[str] = field(default_factory=list)

    def as_facts(self) -> list[str]:
        """Flat list of atomic fact strings — the ONLY things an explainer may cite."""
        facts = [
            f"{self.drug} is used for: {self.purpose}." if self.purpose else "",
            f"{self.drug} contains the active ingredient {self.salt}." if self.salt else "",
            f"Typical dose: {self.dose}." if self.dose else "",
            f"Timing: {self.timing}." if self.timing else "",
            f"Route: {self.route}." if self.route else "",
            f"Pregnancy category: {self.pregnancy_category}." if self.pregnancy_category and self.pregnancy_category != "unknown" else "",
            f"Suggested for the patient's condition: {self.for_condition}." if self.for_condition else "",
        ]
        facts += [f"Safety finding: {r}" for r in self.rule_reasons]
        facts += [f"Known interaction: {i}" for i in self.interactions]
        facts += [f"Contraindication: {c}" for c in self.contraindications]
        return [f for f in facts if f]


class SubgraphRetriever:
    def __init__(self, kg: KnowledgeGraph | None = None):
        self.kg = kg or get_kg()

    def retrieve(self, patient: PatientProfile, verdict: SafetyVerdict) -> EvidenceContext:
        cand = verdict.candidate
        prof = self.kg.get_drug_profile(cand.drug.name)

        interactions = []
        for med in patient.current_meds:
            edge = self.kg.interaction_between(cand.drug.name, med.name)
            if edge:
                interactions.append(
                    f"{cand.drug.name} + {med.name} ({edge.severity}): {edge.mechanism}"
                )

        contraindications = []
        for c in self.kg.contraindications_for_drug(cand.drug.name):
            if patient.has_condition(c.condition_code) or (c.condition_code == "Z33.1" and patient.pregnant):
                contraindications.append(f"{cand.drug.name} in {c.condition_code}: {c.reason}")

        return EvidenceContext(
            drug=cand.drug.name,
            salt=prof.salt if prof else cand.drug.salt,
            purpose=prof.purpose if prof else "",
            dose=prof.dose if prof else "",
            timing=prof.timing if prof else "",
            route=prof.route if prof else "",
            pregnancy_category=prof.pregnancy_category if prof else "unknown",
            for_condition=cand.for_condition.display or cand.for_condition.code,
            verdict_status=verdict.status.value,
            rule_reasons=[r.message for r in verdict.reasons],
            interactions=interactions,
            contraindications=contraindications,
        )
