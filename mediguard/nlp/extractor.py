"""Free text → structured PatientProfile.

Combines the dictionary linker with ConText assertion detection so that:
  - "no chest pain"                 → NOT added as a patient condition
  - "father has a heart condition"  → NOT added (family history)
  - "history of high sugar"         → added (historical but still the patient)

Also pulls age, sex, pregnancy, and simple vitals (BP/sugar qualifiers). Drug
mentions become current_meds; allergy phrases become allergies. Everything
downstream consumes the returned PatientProfile, never the raw text.

This is the dependency-free default extractor. `extractor_medspacy.py` offers an
optional medspaCy-backed variant behind the same `.extract()` signature.
"""

from __future__ import annotations

import re

from mediguard.nlp.context import Assertion, classify
from mediguard.nlp.linker import DictionaryLinker
from mediguard.schemas import CodedConcept, CodingSystem, PatientProfile, Vitals

_PREG_TRIGGERS = ("pregnant", "pregnancy", "expecting", "gestation")
_PREG_NEG = ("not pregnant", "no pregnancy", "denies pregnancy")

# Codes surfaced through dedicated PatientProfile fields (pregnant flag /
# allergies), so they must not be double-counted as ordinary conditions.
_NON_CONDITION_CODES = {"Z33.1", "PEN_ALLERGY"}


class RuleBasedExtractor:
    def __init__(self, linker: DictionaryLinker | None = None):
        self.linker = linker or DictionaryLinker()

    # ------------------------------------------------------------------ #
    def extract(self, text: str, *, consent_captured: bool = False) -> PatientProfile:
        conditions: list[CodedConcept] = []
        allergies: list[CodedConcept] = []
        current_meds = []

        # --- allergies first: an allergy mention should not become a med ---
        allergy_spans = self._allergy_spans(text)

        # --- drugs → current meds (unless inside an allergy phrase) ---
        for m in self.linker.link_drugs(text):
            if any(s <= m.start < e for s, e in allergy_spans):
                # "allergic to penicillin/amoxicillin" → allergy, not a current med
                allergies.append(CodedConcept(
                    code="PEN_ALLERGY" if "penicillin" in m.text.lower() or "amoxicillin" in m.text.lower() else m.text,
                    system=CodingSystem.LOCAL, display=f"{m.text} allergy",
                ))
                continue
            ctx = classify(text, m.start)
            if ctx.assertion in (Assertion.NEGATED, Assertion.FAMILY):
                continue
            if m.drug:
                current_meds.append(m.drug)

        # --- conditions with assertion filtering ---
        for m in self.linker.link_conditions(text):
            if m.concept and m.concept.code in _NON_CONDITION_CODES:
                continue  # pregnancy/allergy handled via dedicated fields
            ctx = classify(text, m.start)
            if ctx.assertion in (Assertion.NEGATED, Assertion.FAMILY):
                continue  # negated or family → not a patient condition
            if m.concept and not any(c.code == m.concept.code for c in conditions):
                conditions.append(m.concept)

        # --- explicit penicillin-allergy phrase → coded allergy + condition ---
        for s, e in allergy_spans:
            phrase = text[s:e].lower()
            if "penicillin" in phrase or "amoxicillin" in phrase:
                if not any(a.code == "PEN_ALLERGY" for a in allergies):
                    allergies.append(CodedConcept(code="PEN_ALLERGY", system=CodingSystem.LOCAL,
                                                  display="Penicillin allergy"))

        profile = PatientProfile(
            age=self._age(text),
            sex=self._sex(text),
            pregnant=self._pregnant(text),
            conditions=conditions,
            current_meds=current_meds,
            allergies=allergies,
            vitals=self._vitals(text),
            raw_text=text,
            consent_captured=consent_captured,
        )
        return profile

    # ------------------------------------------------------------------ #
    @staticmethod
    def _age(text: str) -> int | None:
        m = re.search(r"\b(\d{1,3})\s*(?:years?\s*old|yo|y/o|yrs?)\b", text, re.I)
        if m:
            return int(m.group(1))
        # "45F" / "58M" — age immediately followed by a sex marker
        m = re.search(r"\b(\d{1,3})\s*(?:[MF])\b", text)
        if m and 0 < int(m.group(1)) <= 120:
            return int(m.group(1))
        # leading "32, pregnant..." style
        m = re.match(r"\s*(\d{1,3})\s*[,\-]", text)
        if m and 0 < int(m.group(1)) <= 120:
            return int(m.group(1))
        return None

    @staticmethod
    def _sex(text: str) -> str | None:
        t = text.lower()
        if re.search(r"\b(female|woman|she|her)\b", t):
            return "female"
        if re.search(r"\b(male|man|he|his)\b", t):
            return "male"
        return None

    @staticmethod
    def _pregnant(text: str) -> bool | None:
        t = text.lower()
        if any(neg in t for neg in _PREG_NEG):
            return False
        for trig in _PREG_TRIGGERS:
            idx = t.find(trig)
            if idx != -1:
                ctx = classify(text, idx)
                if ctx.assertion == Assertion.NEGATED:
                    return False
                if ctx.assertion == Assertion.FAMILY:
                    continue
                return True
        return None

    @staticmethod
    def _vitals(text: str) -> Vitals:
        t = text.lower()
        bp = sugar = renal = None
        if re.search(r"\b(high|raised|elevated)\s+(bp|blood pressure)\b", t) or "hypertension" in t:
            bp = "high"
        elif re.search(r"\b(low)\s+(bp|blood pressure)\b", t) or "hypotension" in t:
            bp = "low"
        mbp = re.search(r"\b(\d{2,3})\s*/\s*(\d{2,3})\b", text)
        if mbp:
            bp = mbp.group(0)
        if re.search(r"\b(high|raised|elevated)\s+(sugar|blood sugar|glucose)\b", t) or "diabetes" in t or "diabetic" in t:
            sugar = "high"
        elif re.search(r"\b(low)\s+(sugar|blood sugar|glucose)\b", t):
            sugar = "low"
        if any(k in t for k in ("kidney disease", "renal impair", "ckd", "renal failure")):
            renal = "impaired"
        return Vitals(bp=bp, sugar=sugar, renal=renal)

    @staticmethod
    def _allergy_spans(text: str) -> list[tuple[int, int]]:
        spans = []
        for m in re.finditer(r"allergic to ([a-z\- ]+?)(?:[.,;]|$)", text, re.I):
            spans.append((m.start(1), m.end(1)))
        for m in re.finditer(r"([a-z\-]+)\s+allergy", text, re.I):
            spans.append((m.start(1), m.end(1)))
        return spans
