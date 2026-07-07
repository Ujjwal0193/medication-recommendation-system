"""Synthetic patient generation for evaluation (free, no credentialing).

The plan chose Synthea synthetic patients over restricted MIMIC-IV. Synthea proper
is a Java tool; for a self-contained, dependency-free evaluation set we generate
clinically-plausible synthetic patients over the prototype's condition/drug scope.
Each patient is internally consistent (age, pregnancy, comorbidities, current meds)
so it exercises the full pipeline including the safety edge cases.

For a heavier run, real Synthea FHIR bundles can be dropped into data/raw/synthea/
and adapted — the pipeline consumes PatientProfile, so only a thin FHIR->profile
mapper would be needed (future work).
"""

from __future__ import annotations

import random

from mediguard.schemas import CodedConcept, CodedDrug, CodingSystem, PatientProfile, Vitals

_CONDITIONS = [
    ("73211009", CodingSystem.SNOMED, "Diabetes mellitus"),
    ("I10", CodingSystem.ICD10, "Hypertension"),
    ("E78.5", CodingSystem.ICD10, "Hyperlipidemia"),
    ("I50.9", CodingSystem.ICD10, "Heart failure"),
    ("N18.9", CodingSystem.ICD10, "Chronic kidney disease"),
    ("K21.9", CodingSystem.ICD10, "GERD"),
    ("J06.9", CodingSystem.ICD10, "Respiratory infection"),
    ("N39.0", CodingSystem.ICD10, "UTI"),
    ("386661006", CodingSystem.SNOMED, "Fever"),
    ("22253000", CodingSystem.SNOMED, "Pain"),
    ("E03.9", CodingSystem.ICD10, "Hypothyroidism"),
    ("F32.9", CodingSystem.ICD10, "Depression"),
]
_MEDS = ["Metformin", "Amlodipine", "Lisinopril", "Atorvastatin", "Aspirin",
         "Warfarin", "Omeprazole", "Sertraline", "Levothyroxine", "Clopidogrel"]


def generate_patients(n: int = 200, seed: int = 42) -> list[PatientProfile]:
    rng = random.Random(seed)
    patients: list[PatientProfile] = []
    for _ in range(n):
        age = rng.randint(18, 88)
        sex = rng.choice(["female", "male"])
        pregnant = bool(sex == "female" and 18 <= age <= 45 and rng.random() < 0.15)

        k = rng.choice([1, 1, 2, 2, 3])
        conds = rng.sample(_CONDITIONS, k)
        conditions = [CodedConcept(code=c, system=s, display=d) for c, s, d in conds]

        n_meds = rng.choice([0, 0, 1, 1, 2, 3])
        meds = rng.sample(_MEDS, min(n_meds, len(_MEDS)))
        current_meds = [CodedDrug(name=m) for m in meds]

        renal = "impaired" if any(c.code == "N18.9" for c in conditions) else None
        sugar = "high" if any(c.code == "73211009" for c in conditions) else None
        bp = "high" if any(c.code == "I10" for c in conditions) else None

        patients.append(PatientProfile(
            age=age, sex=sex, pregnant=pregnant if pregnant else None,
            conditions=conditions, current_meds=current_meds,
            vitals=Vitals(bp=bp, sugar=sugar, renal=renal),
            raw_text=f"[synthetic] {age}yo {sex}", consent_captured=True,
        ))
    return patients


if __name__ == "__main__":
    pts = generate_patients()
    print(f"Generated {len(pts)} synthetic patients.")
    print("Example:", pts[0].model_dump(mode="json"))
