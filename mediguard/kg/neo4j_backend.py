"""Neo4j knowledge-graph backend (optional).

Only used when MEDIGUARD_KG_BACKEND=neo4j. Requires the `neo4j` extra
(`pip install -e ".[neo4j]"`) and a running Neo4j (see docker-compose.yml).
Load data first with `python etl/load_neo4j.py`.

Implements the same read interface as EmbeddedKG so callers are backend-agnostic.
"""

from __future__ import annotations

from mediguard.config import settings
from mediguard.kg.base import (
    ContraindicationEdge,
    DrugProfile,
    InteractionEdge,
    KnowledgeGraph,
)


class Neo4jKG(KnowledgeGraph):
    def __init__(self, uri: str | None = None, user: str | None = None, password: str | None = None):
        from neo4j import GraphDatabase  # imported lazily; optional dependency

        self._driver = GraphDatabase.driver(
            uri or settings.neo4j_uri,
            auth=(user or settings.neo4j_user, password or settings.neo4j_password),
        )

    def close(self) -> None:
        self._driver.close()

    def _run(self, cypher: str, **params):
        with self._driver.session() as s:
            return list(s.run(cypher, **params))

    def get_drug_profile(self, drug: str) -> DrugProfile | None:
        rows = self._run(
            """
            MATCH (d:Drug)
            WHERE toLower(d.name) = toLower($drug) OR d.rxcui = $drug
            OPTIONAL MATCH (d)-[:CAUSES_SIDE_EFFECT]->(se:SideEffect)
            RETURN d, collect(DISTINCT se.label) AS side_effects
            """,
            drug=drug,
        )
        if not rows:
            return None
        d = rows[0]["d"]
        return DrugProfile(
            name=d["name"],
            rxcui=d.get("rxcui"),
            salt=d.get("salt"),
            atc=d.get("atc"),
            drug_class=d.get("drug_class"),
            purpose=d.get("purpose", ""),
            pros=d.get("pros", []),
            cons=d.get("cons", []),
            side_effects=rows[0]["side_effects"] or d.get("side_effects", []),
            dose=d.get("dose", ""),
            timing=d.get("timing", ""),
            route=d.get("route", ""),
            quantity=d.get("quantity", ""),
            pregnancy_category=d.get("pregnancy_category", "unknown"),
            renal_caution=d.get("renal_caution", ""),
        )

    def drugs_for_condition(self, condition_code: str) -> list[dict]:
        rows = self._run(
            """
            MATCH (c:Condition {code:$code})-[t:TREATS]->(d:Drug)
            RETURN d.name AS drug, t.rank AS rank, t.line AS line
            ORDER BY t.rank
            """,
            code=condition_code,
        )
        return [{"drug": r["drug"], "rank": r["rank"], "line": r["line"]} for r in rows]

    def interactions_for(self, drug: str) -> list[InteractionEdge]:
        rows = self._run(
            """
            MATCH (a:Drug)-[i:INTERACTS_WITH]-(b:Drug)
            WHERE toLower(a.name) = toLower($drug)
            RETURN a.name AS a, b.name AS b, i.severity AS severity,
                   i.mechanism AS mechanism, i.management AS management
            """,
            drug=drug,
        )
        return [InteractionEdge(r["a"], r["b"], r["severity"], r["mechanism"] or "", r["management"] or "") for r in rows]

    def interaction_between(self, drug_a: str, drug_b: str) -> InteractionEdge | None:
        rows = self._run(
            """
            MATCH (a:Drug)-[i:INTERACTS_WITH]-(b:Drug)
            WHERE toLower(a.name)=toLower($a) AND toLower(b.name)=toLower($b)
            RETURN a.name AS a, b.name AS b, i.severity AS severity,
                   i.mechanism AS mechanism, i.management AS management
            LIMIT 1
            """,
            a=drug_a, b=drug_b,
        )
        if not rows:
            return None
        r = rows[0]
        return InteractionEdge(r["a"], r["b"], r["severity"], r["mechanism"] or "", r["management"] or "")

    def contraindications_for_drug(self, drug: str) -> list[ContraindicationEdge]:
        rows = self._run(
            """
            MATCH (c:Condition)-[x:CONTRAINDICATES]->(d:Drug)
            WHERE toLower(d.name)=toLower($drug)
            RETURN c.code AS code, d.name AS drug, x.severity AS severity, x.reason AS reason
            """,
            drug=drug,
        )
        return [ContraindicationEdge(r["code"], r["drug"], r["severity"], r["reason"] or "") for r in rows]

    def contraindication(self, condition_code: str, drug: str) -> ContraindicationEdge | None:
        rows = self._run(
            """
            MATCH (c:Condition {code:$code})-[x:CONTRAINDICATES]->(d:Drug)
            WHERE toLower(d.name)=toLower($drug)
            RETURN c.code AS code, d.name AS drug, x.severity AS severity, x.reason AS reason
            LIMIT 1
            """,
            code=condition_code, drug=drug,
        )
        if not rows:
            return None
        r = rows[0]
        return ContraindicationEdge(r["code"], r["drug"], r["severity"], r["reason"] or "")

    def drug_class(self, drug: str) -> str | None:
        rows = self._run(
            "MATCH (d:Drug) WHERE toLower(d.name)=toLower($drug) RETURN d.drug_class AS c LIMIT 1",
            drug=drug,
        )
        return rows[0]["c"] if rows else None

    def all_drugs(self) -> list[str]:
        return [r["name"] for r in self._run("MATCH (d:Drug) RETURN d.name AS name")]
