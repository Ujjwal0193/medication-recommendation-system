"""Central runtime configuration, sourced from environment / .env.

All defaults are free and local so a fresh clone runs with zero setup.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # optional convenience; not required
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class Settings:
    kg_backend: str = _env("MEDIGUARD_KG_BACKEND", "embedded")  # embedded | neo4j
    neo4j_uri: str = _env("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = _env("NEO4J_USER", "neo4j")
    neo4j_password: str = _env("NEO4J_PASSWORD", "mediguard")

    explain_backend: str = _env("MEDIGUARD_EXPLAIN_BACKEND", "template")  # template|claude|ollama

    rxnav_base_url: str = _env("RXNAV_BASE_URL", "https://rxnav.nlm.nih.gov/REST")

    enable_gnn: bool = _env("MEDIGUARD_ENABLE_GNN", "false").lower() == "true"
    india_layer: bool = _env("MEDIGUARD_INDIA_LAYER", "false").lower() == "true"


settings = Settings()
