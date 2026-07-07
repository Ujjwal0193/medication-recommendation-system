"""Phase 3 acceptance: entity-extraction P/R/F1 + negation/family-history handling.

Critical correctness gates:
  - "no chest pain" / "denies fever" → negated finding not added
  - "my father has a heart condition" → family history not added as patient's
"""

import json
from pathlib import Path

import pytest

from mediguard.nlp.extractor import RuleBasedExtractor

GOLD = json.loads((Path(__file__).parent / "fixtures" / "nlp_gold.json").read_text(encoding="utf-8"))["cases"]


@pytest.fixture(scope="module")
def extractor():
    return RuleBasedExtractor()


def _codes(profile) -> set[str]:
    return {c.code for c in profile.conditions}


def _meds(profile) -> set[str]:
    return {m.name for m in profile.current_meds}


@pytest.mark.parametrize("case", GOLD, ids=[c["text"][:40] for c in GOLD])
def test_forbidden_codes_never_appear(extractor, case):
    """Negated + family-history findings must NOT become patient conditions."""
    profile = extractor.extract(case["text"])
    got = _codes(profile)
    for forbidden in case.get("forbid_conditions", []):
        assert forbidden not in got, (
            f"Assertion error: {forbidden} wrongly extracted from {case['text']!r}"
        )


@pytest.mark.parametrize("case", GOLD, ids=[c["text"][:40] for c in GOLD])
def test_structured_fields(extractor, case):
    profile = extractor.extract(case["text"])
    assert profile.age == case["expect_age"], f"age mismatch for {case['text']!r}"
    assert profile.pregnant == case["expect_pregnant"], f"pregnancy mismatch for {case['text']!r}"
    for code in case.get("expect_allergy_codes", []):
        assert any(a.code == code for a in profile.allergies), f"missing allergy {code}"


def test_family_history_not_attributed(extractor):
    p = extractor.extract("My father has a heart condition but I only have a cold")
    assert not p.has_condition("I51.9"), "family-history heart condition wrongly attributed"
    assert p.has_condition("J06.9")  # the patient's own cold IS captured


def test_negation_handled(extractor):
    p = extractor.extract("45F with headache, no chest pain, denies fever")
    assert p.has_condition("25064002")  # headache present
    assert not p.has_condition("386661006")  # fever denied


def test_entity_extraction_prf1(extractor):
    """Micro-averaged precision/recall/F1 over conditions + meds across the gold set."""
    tp = fp = fn = 0
    for case in GOLD:
        profile = extractor.extract(case["text"])
        got = _codes(profile) | _meds(profile)
        gold = set(case["expect_conditions"]) | set(case["expect_meds"])
        tp += len(got & gold)
        fp += len(got - gold)
        fn += len(gold - got)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    print(f"\nNLP entity extraction — P={precision:.3f} R={recall:.3f} F1={f1:.3f} "
          f"(tp={tp} fp={fp} fn={fn})")

    # Acceptance thresholds for the dictionary linker on the gold set.
    assert precision >= 0.85, f"precision {precision:.3f} below 0.85"
    assert recall >= 0.85, f"recall {recall:.3f} below 0.85"
    assert f1 >= 0.85, f"F1 {f1:.3f} below 0.85"
