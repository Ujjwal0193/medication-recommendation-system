"""Select the NLP extractor backend.

Default: dependency-free RuleBasedExtractor (works everywhere).
Optional: medspaCy-backed extractor if the `nlp` extra is installed and loads.
Both expose `.extract(text, consent_captured=...) -> PatientProfile`.
"""

from __future__ import annotations

from mediguard.nlp.extractor import RuleBasedExtractor


def make_extractor(prefer_medspacy: bool = False):
    if prefer_medspacy:
        try:
            from mediguard.nlp.extractor_medspacy import MedspacyExtractor

            return MedspacyExtractor()
        except Exception:  # noqa: BLE001 - fall back silently to the reliable extractor
            pass
    return RuleBasedExtractor()
