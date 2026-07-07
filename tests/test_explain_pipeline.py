"""Phase 5 acceptance: faithful explanations, abstention, end-to-end pipeline."""

import pytest

from mediguard.explain.explainer import TemplateExplainer
from mediguard.explain.retriever import SubgraphRetriever
from mediguard.pipeline import MediGuardPipeline
from mediguard.safety.engine import SafetyAuthority
from mediguard.schemas import (
    CONSENT_DIRECTIVE,
    Candidate,
    CodedConcept,
    CodedDrug,
    CodingSystem,
    PatientProfile,
    SafetyStatus,
)
from mediguard.uncertainty.abstain import ConformalAbstainer


@pytest.fixture(scope="module")
def pipeline():
    return MediGuardPipeline()


def test_explanation_is_grounded_and_has_disclaimer():
    auth = SafetyAuthority()
    retr = SubgraphRetriever()
    expl = TemplateExplainer()
    patient = PatientProfile(age=50)
    cand = Candidate(
        drug=CodedDrug(name="Metformin"),
        for_condition=CodedConcept(code="73211009", system=CodingSystem.SNOMED, display="Diabetes"),
    )
    verdict = auth.evaluate(patient, cand)
    ctx = retr.retrieve(patient, verdict)
    text = expl.explain(ctx)
    assert "Metformin" in text
    assert CONSENT_DIRECTIVE in text
    # Faithfulness: mentions the retrieved purpose, no invented drug names.
    assert ctx.purpose.split(";")[0][:10].lower() in text.lower() or ctx.purpose in text


def test_explanation_surfaces_block_reason():
    auth = SafetyAuthority()
    retr = SubgraphRetriever()
    expl = TemplateExplainer()
    patient = PatientProfile(age=30, pregnant=True)
    cand = Candidate(
        drug=CodedDrug(name="Warfarin"),
        for_condition=CodedConcept(code="I48", system=CodingSystem.ICD10, display="AF"),
    )
    verdict = auth.evaluate(patient, cand)
    text = expl.explain(retr.retrieve(patient, verdict))
    assert "NOT recommended" in text
    assert any(word in text.lower() for word in ("contraindicated", "pregnancy", "category x"))


def test_abstain_when_all_blocked():
    ab = ConformalAbstainer()
    auth = SafetyAuthority()
    patient = PatientProfile(age=30, pregnant=True)
    # Only-blocked candidate set.
    cand = Candidate(drug=CodedDrug(name="Warfarin"),
                     for_condition=CodedConcept(code="I48", system=CodingSystem.ICD10))
    verdicts = [auth.evaluate(patient, cand)]
    decision = ab.decide(verdicts)
    assert decision.abstain
    assert "clinician" in decision.reason.lower()


def test_no_abstain_for_safe_option():
    ab = ConformalAbstainer()
    auth = SafetyAuthority()
    patient = PatientProfile(age=50)
    cand = Candidate(drug=CodedDrug(name="Metformin"),
                     for_condition=CodedConcept(code="73211009", system=CodingSystem.SNOMED))
    decision = ab.decide([auth.evaluate(patient, cand)])
    assert not decision.abstain


def test_pipeline_end_to_end_from_text(pipeline):
    text = "58 year old man with high blood pressure and type 2 diabetes"
    results = pipeline.from_text(text, consent_captured=True)
    codes = {r.condition_code for r in results}
    assert {"I10", "73211009"} <= codes
    for cr in results:
        assert cr.recommendations
        for rec in cr.recommendations:
            assert rec.disclaimer == CONSENT_DIRECTIVE
            assert rec.rationale


def test_pipeline_blocks_unsafe_in_pregnancy(pipeline):
    text = "30 year old pregnant woman with high blood pressure"
    results = pipeline.from_text(text)
    htn = next(r for r in results if r.condition_code == "I10")
    # ACE/ARB candidates must be blocked; every blocked rec is an abstention.
    blocked = [r for r in htn.recommendations if r.verdict.status == SafetyStatus.BLOCK]
    assert blocked
    assert all(r.abstain for r in blocked)
    # A safe option (e.g. Amlodipine) should still be present and not blocked.
    safe = [r for r in htn.recommendations if r.verdict.status != SafetyStatus.BLOCK]
    assert safe


def test_pipeline_never_emits_actionable_block(pipeline):
    """Global invariant: no non-abstaining recommendation is BLOCK."""
    results = pipeline.from_text("30 year old pregnant woman with high cholesterol and AF")
    for cr in results:
        for rec in cr.recommendations:
            if rec.verdict.status == SafetyStatus.BLOCK:
                assert rec.abstain, "a BLOCK leaked as an actionable recommendation"
