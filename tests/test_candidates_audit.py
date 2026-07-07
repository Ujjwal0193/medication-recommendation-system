"""Candidate generation + audit log."""

import json
import tempfile
from pathlib import Path

from mediguard.audit.log import AuditLog, consent_directive
from mediguard.candidates.generator import CandidateGenerator
from mediguard.safety.engine import SafetyAuthority
from mediguard.schemas import CodedConcept, CodingSystem, PatientProfile


def test_candidates_for_diabetes_ranked():
    gen = CandidateGenerator()
    cond = CodedConcept(code="73211009", system=CodingSystem.SNOMED, display="Diabetes")
    cands = gen.for_condition(cond)
    assert cands
    assert cands[0].drug.name == "Metformin"
    # RxCUI enriched from the KG profile.
    assert cands[0].drug.rxcui == "6809"


def test_candidates_for_patient_groups_by_condition():
    gen = CandidateGenerator()
    p = PatientProfile(conditions=[
        CodedConcept(code="I10", system=CodingSystem.ICD10, display="Hypertension"),
        CodedConcept(code="73211009", system=CodingSystem.SNOMED, display="Diabetes"),
    ])
    grouped = gen.for_patient(p)
    assert set(grouped) == {"I10", "73211009"}
    assert all(grouped.values())


def test_audit_log_records_fired_rules():
    gen = CandidateGenerator()
    auth = SafetyAuthority()
    p = PatientProfile(age=30, pregnant=True)
    cand = gen.for_condition(
        CodedConcept(code="I10", system=CodingSystem.ICD10, display="Hypertension")
    )[0]
    verdict = auth.evaluate(p, cand)

    with tempfile.TemporaryDirectory() as d:
        log = AuditLog(Path(d) / "audit.jsonl")
        entry = log.record(verdict, patient_ref="test-1")
        assert entry["drug"] == cand.drug.name
        assert "fired_rules" in entry
        lines = (Path(d) / "audit.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["status"] == verdict.status.value


def test_consent_directive_nonempty():
    assert "doctor" in consent_directive().lower()
