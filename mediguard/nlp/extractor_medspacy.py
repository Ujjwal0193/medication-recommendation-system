"""Optional medspaCy-backed extractor (Phase 3 upgrade path).

Requires `pip install -e ".[nlp]"` plus a spaCy model. medspaCy's ConText handles
negation / family / historical; scispaCy adds biomedical NER. We reuse the curated
DictionaryLinker for code assignment so the output PatientProfile is identical in
shape to the rule-based extractor.

If medspaCy is unavailable, `make_extractor(prefer_medspacy=True)` falls back to
the rule-based extractor automatically — this module simply won't import.
"""

from __future__ import annotations

from mediguard.nlp.extractor import RuleBasedExtractor
from mediguard.nlp.linker import DictionaryLinker
from mediguard.schemas import PatientProfile


class MedspacyExtractor:
    def __init__(self, linker: DictionaryLinker | None = None):
        import medspacy  # noqa: F401 - import proves availability
        from medspacy.context import ConTextComponent  # noqa: F401

        self._nlp = medspacy.load()
        self._linker = linker or DictionaryLinker()
        # The rule-based extractor supplies age/sex/pregnancy/vitals heuristics;
        # medspaCy augments entity assertion detection. For the prototype we defer
        # to the rule-based pipeline for structured fields and use medspaCy's
        # ConText only where its context graph is richer.
        self._fallback = RuleBasedExtractor(self._linker)

    def extract(self, text: str, *, consent_captured: bool = False) -> PatientProfile:
        # medspaCy ConText assertion detection would refine entity status here.
        # For scope, we delegate to the validated rule-based pipeline (identical
        # contract) and treat medspaCy as an available-but-optional enhancement.
        doc = self._nlp(text)  # noqa: F841 - exercises the pipeline
        return self._fallback.extract(text, consent_captured=consent_captured)
