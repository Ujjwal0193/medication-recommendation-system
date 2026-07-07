"""FastAPI service — patient in → explained, safety-checked recommendations out.

Endpoints:
    GET  /health
    GET  /drugs                 → curated drug names
    POST /recommend             → run the full pipeline (text and/or structured)
    POST /recommend/fhir        → same, returned as FHIR resources

Run:  uvicorn mediguard.api.app:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from mediguard.api.fhir import (
    conditions_to_fhir,
    observations_to_fhir,
    patient_to_fhir,
    recommendation_to_fhir,
)
from mediguard.kg.factory import get_kg
from mediguard.pipeline import MediGuardPipeline
from mediguard.schemas import (
    CONSENT_DIRECTIVE,
    CodedConcept,
    CodedDrug,
    CodingSystem,
    PatientProfile,
    Vitals,
)

app = FastAPI(
    title="MediGuard API",
    version="0.1.0",
    description="Safe, explainable medication decision support (advisory only).",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo; tighten for any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline: MediGuardPipeline | None = None


def pipeline() -> MediGuardPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = MediGuardPipeline()
    return _pipeline


# --------------------------------------------------------------------------- #
# Request / response models
# --------------------------------------------------------------------------- #
class RecommendRequest(BaseModel):
    text: str = ""
    # Optional structured overrides (merged onto NLP output).
    age: int | None = None
    sex: str | None = None
    pregnant: bool | None = None
    conditions: list[str] = Field(default_factory=list, description="ICD-10/SNOMED codes")
    current_meds: list[str] = Field(default_factory=list, description="drug names")
    allergies: list[str] = Field(default_factory=list)
    bp: str | None = None
    sugar: str | None = None
    renal: str | None = None
    consent: bool = False


class RecReason(BaseModel):
    severity: str
    message: str


class RecOut(BaseModel):
    drug: str
    rxcui: str | None
    status: str
    abstain: bool
    confidence: float
    rationale: str
    reasons: list[RecReason]


class ConditionOut(BaseModel):
    condition_code: str
    condition_display: str
    abstain: bool
    abstain_reason: str
    recommendations: list[RecOut]


class RecommendResponse(BaseModel):
    disclaimer: str
    profile: dict
    results: list[ConditionOut]


# --------------------------------------------------------------------------- #
def _build_profile(req: RecommendRequest) -> PatientProfile:
    """NLP-extract from text, then apply any structured overrides."""
    if req.text:
        profile = pipeline().extractor.extract(req.text, consent_captured=req.consent)
    else:
        profile = PatientProfile(consent_captured=req.consent)

    if req.age is not None:
        profile.age = req.age
    if req.sex is not None:
        profile.sex = req.sex
    if req.pregnant is not None:
        profile.pregnant = req.pregnant

    kg = get_kg()
    for code in req.conditions:
        if not profile.has_condition(code):
            profile.conditions.append(CodedConcept(code=code, system=_guess_system(code)))
    for name in req.current_meds:
        prof = kg.get_drug_profile(name)
        profile.current_meds.append(CodedDrug(name=name, rxcui=prof.rxcui if prof else None))
    for a in req.allergies:
        profile.allergies.append(CodedConcept(
            code="PEN_ALLERGY" if "penicillin" in a.lower() else a,
            system=CodingSystem.LOCAL, display=a,
        ))
    if req.bp or req.sugar or req.renal:
        profile.vitals = Vitals(
            bp=req.bp or profile.vitals.bp,
            sugar=req.sugar or profile.vitals.sugar,
            renal=req.renal or profile.vitals.renal,
        )
    return profile


def _guess_system(code: str) -> CodingSystem:
    if code[:1].isalpha() and any(ch.isdigit() for ch in code):
        return CodingSystem.ICD10
    if code.isdigit():
        return CodingSystem.SNOMED
    return CodingSystem.LOCAL


# --------------------------------------------------------------------------- #
@app.get("/health")
def health() -> dict:
    return {"status": "ok", "drugs": len(get_kg().all_drugs())}


@app.get("/drugs")
def drugs() -> dict:
    return {"drugs": sorted(get_kg().all_drugs())}


@app.get("/conditions")
def conditions() -> dict:
    """Conditions the system can reason over (for structured-input dropdowns)."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "data" / "curated" / "conditions.json"
    data = json.loads(path.read_text(encoding="utf-8"))["conditions"]
    return {"conditions": [
        {"code": c["code"], "system": c["system"], "display": c["display"]}
        for c in data if c["code"] not in ("Z33.1", "PEN_ALLERGY")
    ]}


@app.get("/drug/{name}")
def drug_detail(name: str) -> dict:
    """Full curated profile for one drug (for the docs/drug-browser page)."""
    p = get_kg().get_drug_profile(name)
    if p is None:
        return {"error": "not found"}
    return {
        "name": p.name, "rxcui": p.rxcui, "salt": p.salt, "drug_class": p.drug_class,
        "purpose": p.purpose, "pros": p.pros, "cons": p.cons, "side_effects": p.side_effects,
        "dose": p.dose, "timing": p.timing, "route": p.route,
        "pregnancy_category": p.pregnancy_category, "renal_caution": p.renal_caution,
    }


@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest) -> RecommendResponse:
    profile = _build_profile(req)
    results = pipeline().run(profile)
    out = [
        ConditionOut(
            condition_code=cr.condition_code,
            condition_display=cr.condition_display,
            abstain=cr.abstain,
            abstain_reason=cr.abstain_reason,
            recommendations=[
                RecOut(
                    drug=rec.candidate.drug.name,
                    rxcui=rec.candidate.drug.rxcui,
                    status=rec.verdict.status.value,
                    abstain=rec.abstain,
                    confidence=rec.confidence,
                    rationale=rec.rationale,
                    reasons=[RecReason(severity=r.severity.value, message=r.message)
                             for r in rec.verdict.reasons],
                )
                for rec in cr.recommendations
            ],
        )
        for cr in results
    ]
    return RecommendResponse(
        disclaimer=CONSENT_DIRECTIVE,
        profile=profile.model_dump(mode="json"),
        results=out,
    )


@app.post("/recommend/fhir")
def recommend_fhir(req: RecommendRequest) -> dict:
    profile = _build_profile(req)
    results = pipeline().run(profile)
    bundle_entries = [patient_to_fhir(profile)]
    bundle_entries += conditions_to_fhir(profile)
    bundle_entries += observations_to_fhir(profile)
    for cr in results:
        for rec in cr.recommendations:
            bundle_entries.append(recommendation_to_fhir(rec))
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": r} for r in bundle_entries],
        "meta": {"disclaimer": CONSENT_DIRECTIVE},
    }
