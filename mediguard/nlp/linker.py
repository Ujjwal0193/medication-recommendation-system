"""Entity linking: surface text → standard codes (SNOMED / ICD-10 / RxNorm).

Dictionary linker built from the curated conditions and drugs. Longer aliases are
matched first so "high blood pressure" wins over "pressure". This is the
"start with rule/dictionary linking, upgrade if time" path from the plan; a
SapBERT/MedCAT backend can replace it behind the same interface later.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from mediguard.schemas import CodedConcept, CodedDrug, CodingSystem

CURATED = Path(__file__).resolve().parents[2] / "data" / "curated"


@dataclass
class Match:
    start: int
    end: int
    text: str
    concept: CodedConcept | None = None
    drug: CodedDrug | None = None


class DictionaryLinker:
    def __init__(self, curated_dir: Path | None = None):
        d = curated_dir or CURATED
        self._conditions = json.loads((d / "conditions.json").read_text(encoding="utf-8"))["conditions"]
        self._drugs = json.loads((d / "drugs.json").read_text(encoding="utf-8"))["drugs"]
        self._cond_index: list[tuple[str, CodedConcept]] = []
        self._drug_index: list[tuple[str, CodedDrug]] = []
        self._build()

    def _build(self) -> None:
        for c in self._conditions:
            concept = CodedConcept(
                code=c["code"], system=CodingSystem(c["system"]), display=c["display"]
            )
            for alias in [c["display"], *c.get("aliases", [])]:
                self._cond_index.append((alias.lower(), concept))
        for d in self._drugs:
            drug = CodedDrug(name=d["name"], rxcui=d.get("rxcui"), salt=d.get("salt"), atc=d.get("atc"))
            self._drug_index.append((d["name"].lower(), drug))
            if d.get("salt"):
                self._drug_index.append((d["salt"].lower(), drug))
        # Longest alias first → greedy, specific matches win.
        self._cond_index.sort(key=lambda x: len(x[0]), reverse=True)
        self._drug_index.sort(key=lambda x: len(x[0]), reverse=True)

    @staticmethod
    def _find_all(text_lower: str, alias: str) -> list[tuple[int, int]]:
        spans = []
        for m in re.finditer(r"\b" + re.escape(alias) + r"\b", text_lower):
            spans.append((m.start(), m.end()))
        return spans

    def link_conditions(self, text: str) -> list[Match]:
        return self._link(text, self._cond_index, is_drug=False)

    def link_drugs(self, text: str) -> list[Match]:
        return self._link(text, self._drug_index, is_drug=True)

    def _link(self, text: str, index, is_drug: bool) -> list[Match]:
        low = text.lower()
        taken: list[tuple[int, int]] = []
        matches: list[Match] = []
        for alias, obj in index:
            for start, end in self._find_all(low, alias):
                if any(not (end <= ts or start >= te) for ts, te in taken):
                    continue  # overlaps an already-claimed, longer span
                taken.append((start, end))
                if is_drug:
                    matches.append(Match(start, end, text[start:end], drug=obj))
                else:
                    matches.append(Match(start, end, text[start:end], concept=obj))
        return sorted(matches, key=lambda m: m.start)
