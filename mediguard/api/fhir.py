"""FHIR resource adapters — positions MediGuard for EHR interoperability.

Maps the internal schemas to FHIR R4-shaped resources (MedicationRequest,
Condition, Observation, Patient). These are simplified, valid-shaped resources
(not a full FHIR server) — the plan's "FHIR facade / future-work" signal that
elevates the project toward health-tech interoperability.
"""

from __future__ import annotations

from mediguard.schemas import PatientProfile, Recommendation


def patient_to_fhir(profile: PatientProfile, patient_id: str = "example") -> dict:
    resource: dict = {
        "resourceType": "Patient",
        "id": patient_id,
    }
    if profile.age is not None:
        resource["extension"] = [{
            "url": "http://hl7.org/fhir/StructureDefinition/patient-age",
            "valueInteger": profile.age,
        }]
    if profile.sex:
        resource["gender"] = profile.sex
    return resource


def conditions_to_fhir(profile: PatientProfile, patient_id: str = "example") -> list[dict]:
    out = []
    for c in profile.conditions:
        out.append({
            "resourceType": "Condition",
            "subject": {"reference": f"Patient/{patient_id}"},
            "code": {
                "coding": [{
                    "system": _coding_system_uri(c.system.value),
                    "code": c.code,
                    "display": c.display,
                }]
            },
            "clinicalStatus": {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                            "code": "active"}]
            },
        })
    if profile.pregnant:
        out.append({
            "resourceType": "Condition",
            "subject": {"reference": f"Patient/{patient_id}"},
            "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10",
                                 "code": "Z33.1", "display": "Pregnant state"}]},
        })
    return out


def observations_to_fhir(profile: PatientProfile, patient_id: str = "example") -> list[dict]:
    out = []
    v = profile.vitals
    for name, value, loinc in (
        ("Blood pressure", v.bp, "85354-9"),
        ("Blood glucose", v.sugar, "2339-0"),
        ("Body weight", v.weight_kg, "29463-7"),
    ):
        if value is None:
            continue
        out.append({
            "resourceType": "Observation",
            "status": "final",
            "subject": {"reference": f"Patient/{patient_id}"},
            "code": {"coding": [{"system": "http://loinc.org", "code": loinc, "display": name}]},
            "valueString": str(value),
        })
    return out


def recommendation_to_fhir(rec: Recommendation, patient_id: str = "example") -> dict:
    """A MedicationRequest reflecting the vetted recommendation.

    A blocked/abstained recommendation is emitted with intent 'proposal' and
    status 'draft' + a note — never 'active' — so downstream systems cannot treat
    it as an order.
    """
    active = not rec.abstain and rec.verdict.status.value in ("allow", "warn")
    return {
        "resourceType": "MedicationRequest",
        "status": "active" if active else "draft",
        "intent": "proposal",
        "subject": {"reference": f"Patient/{patient_id}"},
        "medicationCodeableConcept": {
            "coding": [{
                "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                "code": rec.candidate.drug.rxcui or "",
                "display": rec.candidate.drug.name,
            }]
        },
        "reasonCode": [{
            "coding": [{
                "system": _coding_system_uri(rec.candidate.for_condition.system.value),
                "code": rec.candidate.for_condition.code,
                "display": rec.candidate.for_condition.display,
            }]
        }],
        "note": [
            {"text": rec.rationale},
            {"text": rec.disclaimer},
            {"text": f"MediGuard safety status: {rec.verdict.status.value}; "
                     f"abstain={rec.abstain}; confidence={rec.confidence:.2f}"},
        ],
    }


def _coding_system_uri(system: str) -> str:
    return {
        "SNOMED": "http://snomed.info/sct",
        "ICD-10": "http://hl7.org/fhir/sid/icd-10",
        "RxNorm": "http://www.nlm.nih.gov/research/umls/rxnorm",
        "ATC": "http://www.whocc.no/atc",
    }.get(system, "http://mediguard.local/local")
