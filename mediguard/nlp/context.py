"""Clinical context detection: negation, family-history, historical.

A compact, dependency-free implementation of the ConText idea (Chapman et al.):
scan for trigger phrases that flip the assertion status of a nearby clinical
entity. This is the single correctness detail most student projects miss —
"no chest pain" and "my father has heart disease" must NOT set patient flags.

When the optional medspaCy backend is installed it supersedes this; this module
guarantees the behavior exists regardless.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Assertion(str, Enum):
    PRESENT = "present"
    NEGATED = "negated"  # "no fever"
    FAMILY = "family"  # "father has diabetes"
    HISTORICAL = "historical"  # "history of ..." (still the patient, flagged)


# Trigger phrases. Kept small and explicit for transparency.
_NEGATION = [
    "no ", "not ", "without ", "denies ", "denied ", "negative for ",
    "ruled out ", "rule out ", "free of ", "absence of ", "no history of ",
    "no evidence of ", "never had ",
]
_FAMILY = [
    "father", "mother", "brother", "sister", "sibling", "parent", "parents",
    "family history", "familial", "grandmother", "grandfather", "aunt", "uncle",
    "cousin", "son", "daughter", "wife", "husband", "spouse",
]
_HISTORICAL = ["history of", "h/o", "hx of", "previous", "past", "prior", "old"]

# How far back (in characters) a trigger can reach an entity mention.
_WINDOW = 45


@dataclass
class ContextResult:
    assertion: Assertion
    trigger: str = ""


def _preceding(text: str, start: int, phrases: list[str]) -> str | None:
    """Return the trigger phrase if one appears in the window before `start`."""
    left = text[max(0, start - _WINDOW):start].lower()
    for ph in phrases:
        # Negation words must be close and on the same clause (no clause break).
        idx = left.rfind(ph)
        if idx == -1:
            continue
        between = left[idx + len(ph):]
        # A sentence/clause boundary (. ; ,) or a coordinating conjunction ends
        # the negation/family scope: "not pregnant, has hypothyroidism" must not
        # negate hypothyroidism; "father has X but I have Y" must not tag Y family.
        if re.search(r"[.;,]|\b(but|and|however|though)\b", between):
            continue
        return ph.strip()
    return None


def classify(text: str, entity_start: int) -> ContextResult:
    """Classify the assertion status of an entity mention at `entity_start`."""
    # Family history takes precedence — it removes the finding from the patient.
    fam = _preceding(text, entity_start, _FAMILY)
    if fam:
        return ContextResult(Assertion.FAMILY, fam)

    neg = _preceding(text, entity_start, _NEGATION)
    if neg:
        return ContextResult(Assertion.NEGATED, neg)

    hist = _preceding(text, entity_start, _HISTORICAL)
    if hist:
        return ContextResult(Assertion.HISTORICAL, hist)

    return ContextResult(Assertion.PRESENT)
