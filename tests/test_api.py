"""Phase 6 acceptance: API + FHIR end-to-end."""

from fastapi.testclient import TestClient

from mediguard.api.app import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["drugs"] >= 30


def test_drugs_list():
    r = client.get("/drugs")
    assert "Metformin" in r.json()["drugs"]


def test_recommend_from_text():
    r = client.post("/recommend", json={
        "text": "58 year old man with high blood pressure and type 2 diabetes",
        "consent": True,
    })
    assert r.status_code == 200
    body = r.json()
    assert "doctor" in body["disclaimer"].lower()
    codes = {c["condition_code"] for c in body["results"]}
    assert {"I10", "73211009"} <= codes
    for cond in body["results"]:
        for rec in cond["recommendations"]:
            assert rec["rationale"]
            assert 0.0 <= rec["confidence"] <= 1.0


def test_recommend_structured_pregnancy_blocks_unsafe():
    r = client.post("/recommend", json={
        "pregnant": True,
        "conditions": ["I10"],
        "consent": True,
    })
    assert r.status_code == 200
    htn = next(c for c in r.json()["results"] if c["condition_code"] == "I10")
    blocked = [rec for rec in htn["recommendations"] if rec["status"] == "block"]
    assert blocked  # ACE/ARB blocked in pregnancy
    assert all(rec["abstain"] for rec in blocked)


def test_recommend_fhir_bundle():
    r = client.post("/recommend/fhir", json={
        "text": "50 year old with type 2 diabetes",
        "consent": True,
    })
    assert r.status_code == 200
    bundle = r.json()
    assert bundle["resourceType"] == "Bundle"
    types = {e["resource"]["resourceType"] for e in bundle["entry"]}
    assert "Patient" in types
    assert "MedicationRequest" in types
    # No blocked med is emitted as an 'active' order.
    for e in bundle["entry"]:
        res = e["resource"]
        if res["resourceType"] == "MedicationRequest":
            assert res["intent"] == "proposal"


def test_current_meds_trigger_interaction_flag():
    r = client.post("/recommend", json={
        "conditions": ["I48"],
        "current_meds": ["Aspirin"],
        "consent": True,
    })
    af = next(c for c in r.json()["results"] if c["condition_code"] == "I48")
    warfarin = next((rec for rec in af["recommendations"] if rec["drug"] == "Warfarin"), None)
    assert warfarin is not None
    # Warfarin + Aspirin is a major DDI → downgrade/warn with a reason.
    assert warfarin["status"] in ("downgrade", "warn", "block")
    assert warfarin["reasons"]
