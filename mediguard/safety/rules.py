"""Deterministic safety rules — THE guardrail.

Each rule is a small, transparent function: (PatientProfile, Candidate, KG) -> list[RuleHit].
Rules are pure and side-effect-free so an examiner can read exactly why a candidate
was blocked. This is the plain-Python rule base (the plan's sanctioned fallback for
Experta, which does not support Python 3.12+). The Facts/Rules separation Experta
gives is preserved here: patient+candidate are the facts, these functions the rules.

Severity → status mapping is applied by the engine, not the rules. A rule only
reports *what* it found and *how severe*; the engine decides allow/warn/block.

Rule categories (from the blueprint):
    1. Drug–drug interaction
    2. Drug–condition contraindication (pregnancy X = hard block)
    3. Dose / population (pregnancy, pediatric, geriatric, renal)
    4. Duplicate therapy (same class)
    5. Allergy
"""

from __future__ import annotations

from collections.abc import Callable

from mediguard.kg.base import KnowledgeGraph
from mediguard.schemas import Candidate, PatientProfile, RuleHit, Severity

# A rule takes the facts + KG and returns any hits it found.
Rule = Callable[[PatientProfile, Candidate, KnowledgeGraph], list[RuleHit]]

_SEV = {
    "minor": Severity.MINOR,
    "moderate": Severity.MODERATE,
    "major": Severity.MAJOR,
    "contraindicated": Severity.CONTRAINDICATED,
}


def _sev(name: str) -> Severity:
    return _SEV.get(name.lower(), Severity.MODERATE)


# --------------------------------------------------------------------------- #
# 1. Drug–drug interaction: candidate vs each current med
# --------------------------------------------------------------------------- #
def rule_drug_drug_interaction(p: PatientProfile, c: Candidate, kg: KnowledgeGraph) -> list[RuleHit]:
    hits: list[RuleHit] = []
    cand = c.drug.name
    for med in p.current_meds:
        edge = kg.interaction_between(cand, med.name)
        if edge is None:
            continue
        hits.append(
            RuleHit(
                rule_id=f"DDI::{cand}<->{med.name}",
                severity=_sev(edge.severity),
                message=(
                    f"{cand} interacts with current medication {med.name} "
                    f"({edge.severity}): {edge.mechanism}. {edge.management}"
                ),
                evidence=f"INTERACTS_WITH severity={edge.severity}; {edge.mechanism}",
            )
        )
    return hits


# --------------------------------------------------------------------------- #
# 2. Drug–condition contraindication (incl. pregnancy hard block)
# --------------------------------------------------------------------------- #
def rule_drug_condition_contraindication(p: PatientProfile, c: Candidate, kg: KnowledgeGraph) -> list[RuleHit]:
    hits: list[RuleHit] = []
    cand = c.drug.name

    # Explicit condition codes on the profile.
    condition_codes = [cond.code for cond in p.conditions]
    # Pregnancy may be flagged as a boolean rather than a condition code.
    if p.pregnant:
        condition_codes.append("Z33.1")

    for code in condition_codes:
        edge = kg.contraindication(code, cand)
        if edge is None:
            continue
        hits.append(
            RuleHit(
                rule_id=f"CONTRA::{code}::{cand}",
                severity=_sev(edge.severity),
                message=f"{cand} is contraindicated given the patient's condition "
                        f"({code}): {edge.reason}",
                evidence=f"CONTRAINDICATES severity={edge.severity}; {edge.reason}",
            )
        )
    return hits


# --------------------------------------------------------------------------- #
# 3. Population / pregnancy category direct from the drug profile
# --------------------------------------------------------------------------- #
def rule_pregnancy_category(p: PatientProfile, c: Candidate, kg: KnowledgeGraph) -> list[RuleHit]:
    if not p.pregnant:
        return []
    prof = kg.get_drug_profile(c.drug.name)
    if prof is None:
        return []
    cat = (prof.pregnancy_category or "").upper()
    if cat == "X":
        return [RuleHit(
            rule_id=f"PREG_X::{c.drug.name}",
            severity=Severity.CONTRAINDICATED,
            message=f"{c.drug.name} is pregnancy category X — absolutely "
                    f"contraindicated in pregnancy.",
            evidence="pregnancy_category=X",
        )]
    if cat == "D" or "third_trimester" in cat.lower():
        return [RuleHit(
            rule_id=f"PREG_D::{c.drug.name}",
            severity=Severity.MAJOR,
            message=f"{c.drug.name} carries significant fetal risk in pregnancy "
                    f"(category {prof.pregnancy_category}); avoid unless benefit outweighs risk.",
            evidence=f"pregnancy_category={prof.pregnancy_category}",
        )]
    return []


# --------------------------------------------------------------------------- #
# 4. Renal caution
# --------------------------------------------------------------------------- #
def rule_renal_caution(p: PatientProfile, c: Candidate, kg: KnowledgeGraph) -> list[RuleHit]:
    renal = (p.vitals.renal or "").lower()
    has_ckd = p.has_condition("N18.9") or renal in {"impaired", "low", "poor"} \
        or any(k in renal for k in ("ckd", "impair"))
    if not has_ckd:
        return []
    prof = kg.get_drug_profile(c.drug.name)
    if prof is None or not prof.renal_caution:
        return []
    text = prof.renal_caution.lower()
    # Contraindication-strength renal language -> block; else warn.
    if "contraindicated" in text or "avoid" in text:
        sev = Severity.MAJOR
    else:
        sev = Severity.MODERATE
    return [RuleHit(
        rule_id=f"RENAL::{c.drug.name}",
        severity=sev,
        message=f"Renal caution for {c.drug.name}: {prof.renal_caution}",
        evidence=f"renal_caution={prof.renal_caution}",
    )]


# --------------------------------------------------------------------------- #
# 5. Duplicate therapy (candidate shares a discouraged class with a current med)
# --------------------------------------------------------------------------- #
def rule_duplicate_therapy(p: PatientProfile, c: Candidate, kg: KnowledgeGraph) -> list[RuleHit]:
    cand_class = kg.drug_class(c.drug.name)
    if cand_class is None:
        return []
    hits: list[RuleHit] = []
    for med in p.current_meds:
        if med.name.lower() == c.drug.name.lower():
            continue
        if kg.drug_class(med.name) == cand_class:
            hits.append(RuleHit(
                rule_id=f"DUP::{cand_class}::{c.drug.name}<->{med.name}",
                severity=Severity.MODERATE,
                message=f"Duplicate therapy: {c.drug.name} and current medication "
                        f"{med.name} are both {cand_class}. Avoid combining two drugs "
                        f"of the same class.",
                evidence=f"DUPLICATE_CLASS_OF class={cand_class}",
            ))
    return hits


# --------------------------------------------------------------------------- #
# 6. Allergy (candidate belongs to an allergy class the patient reacts to)
# --------------------------------------------------------------------------- #
def rule_allergy(p: PatientProfile, c: Candidate, kg: KnowledgeGraph) -> list[RuleHit]:
    hits: list[RuleHit] = []
    cand_class = (kg.drug_class(c.drug.name) or "").lower()
    for allergy in p.allergies:
        atext = (allergy.display or allergy.code).lower()
        # Penicillin-class allergy vs penicillin-class drug.
        if "penicillin" in atext and cand_class == "penicillin":
            hits.append(RuleHit(
                rule_id=f"ALLERGY::penicillin::{c.drug.name}",
                severity=Severity.CONTRAINDICATED,
                message=f"{c.drug.name} is a penicillin — patient has a documented "
                        f"penicillin allergy. Risk of anaphylaxis.",
                evidence=f"allergy={atext}; drug_class=penicillin",
            ))
        # Direct name match (allergic to this exact drug).
        elif atext and atext in c.drug.name.lower():
            hits.append(RuleHit(
                rule_id=f"ALLERGY::direct::{c.drug.name}",
                severity=Severity.CONTRAINDICATED,
                message=f"Patient reports allergy to {allergy.display or allergy.code}, "
                        f"matching candidate {c.drug.name}.",
                evidence=f"allergy={atext}",
            ))
    return hits


# Registry, evaluated in order. Add rules here; the engine iterates all of them.
ALL_RULES: list[Rule] = [
    rule_allergy,
    rule_drug_condition_contraindication,
    rule_pregnancy_category,
    rule_drug_drug_interaction,
    rule_renal_caution,
    rule_duplicate_therapy,
]
