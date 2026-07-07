"""Load curated JSON into Neo4j (optional backend).

Only needed if you use MEDIGUARD_KG_BACKEND=neo4j. Requires:
    docker compose up -d                 # Neo4j running
    pip install -e ".[neo4j]"
    python etl/load_neo4j.py

Idempotent: MERGE-based, safe to re-run.
"""

from __future__ import annotations

import json
from pathlib import Path

from mediguard.config import settings

CURATED = Path(__file__).resolve().parents[1] / "data" / "curated"


def _read(name: str) -> dict:
    return json.loads((CURATED / name).read_text(encoding="utf-8"))


def load() -> None:
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    drugs = _read("drugs.json")["drugs"]
    treats = _read("treats.json")["treats"]
    interactions = _read("interactions.json")["interactions"]
    contra = _read("contraindications.json")["contraindications"]
    classes = _read("drug_classes.json")["classes"]

    class_of: dict[str, str] = {}
    for cls, members in classes.items():
        for m in members:
            class_of[m] = cls

    with driver.session() as s:
        s.run("CREATE CONSTRAINT drug_name IF NOT EXISTS FOR (d:Drug) REQUIRE d.name IS UNIQUE")
        s.run("CREATE CONSTRAINT cond_code IF NOT EXISTS FOR (c:Condition) REQUIRE c.code IS UNIQUE")

        for d in drugs:
            d = {**d, "drug_class": class_of.get(d["name"], d.get("drug_class"))}
            s.run(
                """
                MERGE (drug:Drug {name:$name})
                SET drug += $props
                WITH drug
                FOREACH (se IN $side_effects |
                    MERGE (s:SideEffect {label:se})
                    MERGE (drug)-[:CAUSES_SIDE_EFFECT]->(s))
                FOREACH (_ IN CASE WHEN $salt IS NULL THEN [] ELSE [1] END |
                    MERGE (salt:Salt {label:$salt})
                    MERGE (drug)-[:CONTAINS_SALT]->(salt))
                """,
                name=d["name"],
                props={k: v for k, v in d.items() if not isinstance(v, list) or k in ("pros", "cons", "side_effects")},
                side_effects=d.get("side_effects", []),
                salt=d.get("salt"),
            )

        for t in treats:
            s.run(
                """
                MERGE (c:Condition {code:$code})
                MERGE (d:Drug {name:$drug})
                MERGE (c)-[r:TREATS]->(d)
                SET r.rank=$rank, r.line=$line
                """,
                code=t["condition"], drug=t["drug"], rank=t.get("rank", 99), line=t.get("line", "second"),
            )

        for it in interactions:
            s.run(
                """
                MERGE (a:Drug {name:$a})
                MERGE (b:Drug {name:$b})
                MERGE (a)-[r:INTERACTS_WITH]->(b)
                SET r.severity=$sev, r.mechanism=$mech, r.management=$mgmt
                """,
                a=it["a"], b=it["b"], sev=it["severity"],
                mech=it.get("mechanism", ""), mgmt=it.get("management", ""),
            )

        for c in contra:
            s.run(
                """
                MERGE (cond:Condition {code:$code})
                MERGE (d:Drug {name:$drug})
                MERGE (cond)-[r:CONTRAINDICATES]->(d)
                SET r.severity=$sev, r.reason=$reason
                """,
                code=c["condition"], drug=c["drug"], sev=c["severity"], reason=c.get("reason", ""),
            )

        for cls, members in classes.items():
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    s.run(
                        """
                        MATCH (a:Drug {name:$a}), (b:Drug {name:$b})
                        MERGE (a)-[r:DUPLICATE_CLASS_OF]->(b) SET r.drug_class=$cls
                        """,
                        a=members[i], b=members[j], cls=cls,
                    )

    driver.close()
    print("Neo4j load complete.")


if __name__ == "__main__":
    load()
