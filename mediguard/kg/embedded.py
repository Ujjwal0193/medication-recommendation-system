"""Embedded NetworkX knowledge-graph backend — the zero-infra default.

Loads the curated JSON files into an in-process MultiDiGraph. No database, no
Docker, runs everywhere. Same read interface as the Neo4j backend.
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from mediguard.kg.base import (
    ContraindicationEdge,
    DrugProfile,
    InteractionEdge,
    KnowledgeGraph,
)

CURATED_DIR = Path(__file__).resolve().parents[2] / "data" / "curated"

_DRUG_ATTR_KEYS = (
    "rxcui", "salt", "atc", "drug_class", "purpose", "pros", "cons",
    "side_effects", "dose", "timing", "route", "quantity",
    "pregnancy_category", "renal_caution",
)


def _norm(s: str) -> str:
    return s.strip().lower()


class EmbeddedKG(KnowledgeGraph):
    def __init__(self, curated_dir: Path | None = None):
        self.dir = curated_dir or CURATED_DIR
        self.g = nx.MultiDiGraph()
        self._name_by_key: dict[str, str] = {}  # lowered name OR rxcui -> canonical name
        self._class_of: dict[str, str] = {}
        self._load()

    # ------------------------------------------------------------------ #
    def _read(self, fname: str) -> dict:
        return json.loads((self.dir / fname).read_text(encoding="utf-8"))

    def _load(self) -> None:
        drugs = self._read("drugs.json")["drugs"]
        treats = self._read("treats.json")["treats"]
        inter = self._read("interactions.json")["interactions"]
        contra = self._read("contraindications.json")["contraindications"]
        classes = self._read("drug_classes.json")["classes"]

        for d in drugs:
            name = d["name"]
            self.g.add_node(name, kind="Drug", **{k: d.get(k) for k in _DRUG_ATTR_KEYS})
            self._name_by_key[_norm(name)] = name
            if d.get("rxcui"):
                self._name_by_key[d["rxcui"]] = name
            # salt + side-effect nodes
            if d.get("salt"):
                self.g.add_node(f"salt::{d['salt']}", kind="Salt", label=d["salt"])
                self.g.add_edge(name, f"salt::{d['salt']}", key="CONTAINS_SALT", label="CONTAINS_SALT")
            for se in d.get("side_effects", []):
                node = f"se::{_norm(se)}"
                self.g.add_node(node, kind="SideEffect", label=se)
                self.g.add_edge(name, node, key="CAUSES_SIDE_EFFECT", label="CAUSES_SIDE_EFFECT")

        for cls, members in classes.items():
            for m in members:
                self._class_of[_norm(m)] = cls
            # DUPLICATE_CLASS_OF edges between all pairs in a class
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    self.g.add_edge(members[i], members[j], key=f"DUP::{cls}",
                                    label="DUPLICATE_CLASS_OF", drug_class=cls)

        for t in treats:
            cond, drug = t["condition"], t["drug"]
            cnode = f"cond::{cond}"
            if cnode not in self.g:
                self.g.add_node(cnode, kind="Condition", code=cond)
            self.g.add_edge(cnode, drug, key=f"TREATS::{drug}", label="TREATS",
                            rank=t.get("rank", 99), line=t.get("line", "second"))

        for it in inter:
            self.g.add_edge(it["a"], it["b"], key=f"INT::{it['a']}::{it['b']}",
                            label="INTERACTS_WITH", severity=it["severity"],
                            mechanism=it.get("mechanism", ""), management=it.get("management", ""))

        for c in contra:
            cond, drug = c["condition"], c["drug"]
            cnode = f"cond::{cond}"
            if cnode not in self.g:
                self.g.add_node(cnode, kind="Condition", code=cond)
            self.g.add_edge(cnode, drug, key=f"CONTRA::{cond}::{drug}",
                            label="CONTRAINDICATES", severity=c["severity"],
                            reason=c.get("reason", ""))

    # ------------------------------------------------------------------ #
    def _resolve(self, drug: str) -> str | None:
        return self._name_by_key.get(_norm(drug)) or self._name_by_key.get(drug)

    def get_drug_profile(self, drug: str) -> DrugProfile | None:
        name = self._resolve(drug)
        if name is None:
            return None
        n = self.g.nodes[name]
        return DrugProfile(
            name=name,
            rxcui=n.get("rxcui"),
            salt=n.get("salt"),
            atc=n.get("atc"),
            drug_class=n.get("drug_class"),
            purpose=n.get("purpose") or "",
            pros=list(n.get("pros") or []),
            cons=list(n.get("cons") or []),
            side_effects=list(n.get("side_effects") or []),
            dose=n.get("dose") or "",
            timing=n.get("timing") or "",
            route=n.get("route") or "",
            quantity=n.get("quantity") or "",
            pregnancy_category=n.get("pregnancy_category") or "unknown",
            renal_caution=n.get("renal_caution") or "",
        )

    def drugs_for_condition(self, condition_code: str) -> list[dict]:
        cnode = f"cond::{condition_code}"
        if cnode not in self.g:
            return []
        out = []
        for _, drug, data in self.g.out_edges(cnode, data=True):
            if data.get("label") == "TREATS":
                out.append({"drug": drug, "rank": data.get("rank", 99), "line": data.get("line", "second")})
        return sorted(out, key=lambda x: x["rank"])

    def interactions_for(self, drug: str) -> list[InteractionEdge]:
        name = self._resolve(drug)
        if name is None:
            return []
        edges: list[InteractionEdge] = []
        for u, v, data in self.g.edges(data=True):
            if data.get("label") == "INTERACTS_WITH" and name in (u, v):
                edges.append(InteractionEdge(u, v, data["severity"],
                                             data.get("mechanism", ""), data.get("management", "")))
        return edges

    def interaction_between(self, drug_a: str, drug_b: str) -> InteractionEdge | None:
        a, b = self._resolve(drug_a), self._resolve(drug_b)
        if a is None or b is None:
            return None
        for u, v, data in self.g.edges(data=True):
            if data.get("label") == "INTERACTS_WITH" and {u, v} == {a, b}:
                return InteractionEdge(u, v, data["severity"],
                                       data.get("mechanism", ""), data.get("management", ""))
        return None

    def contraindications_for_drug(self, drug: str) -> list[ContraindicationEdge]:
        name = self._resolve(drug)
        if name is None:
            return []
        out = []
        for u, v, data in self.g.edges(data=True):
            if data.get("label") == "CONTRAINDICATES" and v == name:
                code = self.g.nodes[u].get("code", u.replace("cond::", ""))
                out.append(ContraindicationEdge(code, name, data["severity"], data.get("reason", "")))
        return out

    def contraindication(self, condition_code: str, drug: str) -> ContraindicationEdge | None:
        name = self._resolve(drug)
        if name is None:
            return None
        cnode = f"cond::{condition_code}"
        if cnode not in self.g:
            return None
        for _, v, data in self.g.out_edges(cnode, data=True):
            if data.get("label") == "CONTRAINDICATES" and v == name:
                return ContraindicationEdge(condition_code, name, data["severity"], data.get("reason", ""))
        return None

    def drug_class(self, drug: str) -> str | None:
        name = self._resolve(drug)
        if name is None:
            return None
        return self._class_of.get(_norm(name))

    def all_drugs(self) -> list[str]:
        return [n for n, d in self.g.nodes(data=True) if d.get("kind") == "Drug"]
