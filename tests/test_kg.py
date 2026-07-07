"""Phase 1 acceptance: embedded KG loads and answers the profile query."""

import pytest

from mediguard.kg.embedded import EmbeddedKG


@pytest.fixture(scope="module")
def kg():
    return EmbeddedKG()


def test_all_drugs_loaded(kg):
    drugs = kg.all_drugs()
    assert 30 <= len(drugs) <= 60
    assert "Metformin" in drugs
    assert "Warfarin" in drugs


def test_full_drug_profile(kg):
    # Acceptance: one query returns the full profile.
    p = kg.get_drug_profile("Metformin")
    assert p is not None
    assert p.rxcui == "6809"
    assert p.salt and "Metformin" in p.salt
    assert p.purpose
    assert p.pros and p.cons and p.side_effects
    assert p.dose and p.timing and p.route
    assert p.pregnancy_category == "B"


def test_profile_lookup_by_rxcui_and_case(kg):
    assert kg.get_drug_profile("metformin") is not None
    assert kg.get_drug_profile("6809") is not None
    assert kg.get_drug_profile("nonexistent-drug") is None


def test_drugs_for_condition_sorted(kg):
    diab = kg.drugs_for_condition("73211009")  # Diabetes
    assert diab
    assert diab[0]["drug"] == "Metformin"  # rank 1, first-line
    assert diab[0]["rank"] <= diab[-1]["rank"]


def test_interactions_present(kg):
    warfarin = kg.interactions_for("Warfarin")
    partners = {e.drug_a for e in warfarin} | {e.drug_b for e in warfarin}
    assert "Aspirin" in partners
    edge = kg.interaction_between("Warfarin", "Aspirin")
    assert edge is not None
    assert edge.severity == "major"
    assert edge.mechanism


def test_interaction_symmetric(kg):
    assert kg.interaction_between("Aspirin", "Warfarin") is not None
    assert kg.interaction_between("Warfarin", "Aspirin") is not None


def test_contraindications(kg):
    # Warfarin in pregnancy is a hard contraindication (category X).
    c = kg.contraindication("Z33.1", "Warfarin")
    assert c is not None
    assert c.severity == "contraindicated"

    # Penicillin allergy blocks amoxicillin.
    c2 = kg.contraindication("PEN_ALLERGY", "Amoxicillin")
    assert c2 is not None
    assert c2.severity == "contraindicated"


def test_drug_class_for_duplicate_detection(kg):
    assert kg.drug_class("Ibuprofen") == "NSAID"
    assert kg.drug_class("Naproxen") == "NSAID"
    assert kg.drug_class("Lisinopril") == "ACE_inhibitor"
