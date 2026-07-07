"""Candidate generation — condition → candidate drugs from the knowledge graph.

Suggests options only; it never judges safety. The Safety Authority vets every
candidate afterward. Candidates are ordered by the KG's clinical preference rank.
"""

from __future__ import annotations

from mediguard.kg.base import KnowledgeGraph
from mediguard.kg.factory import get_kg
from mediguard.schemas import (
    Candidate,
    CandidateSource,
    CodedConcept,
    CodedDrug,
    PatientProfile,
)


class CandidateGenerator:
    def __init__(self, kg: KnowledgeGraph | None = None):
        self.kg = kg or get_kg()

    def for_condition(self, condition: CodedConcept) -> list[Candidate]:
        rows = self.kg.drugs_for_condition(condition.code)
        candidates: list[Candidate] = []
        for row in rows:
            prof = self.kg.get_drug_profile(row["drug"])
            drug = CodedDrug(
                name=row["drug"],
                rxcui=prof.rxcui if prof else None,
                salt=prof.salt if prof else None,
                atc=prof.atc if prof else None,
            )
            candidates.append(
                Candidate(drug=drug, for_condition=condition, source=CandidateSource.KG)
            )
        return candidates

    def for_patient(self, patient: PatientProfile) -> dict[str, list[Candidate]]:
        """Candidates per patient condition. Keyed by condition code."""
        out: dict[str, list[Candidate]] = {}
        for cond in patient.conditions:
            cands = self.for_condition(cond)
            if cands:
                out[cond.code] = cands
        return out
