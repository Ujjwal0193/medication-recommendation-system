"""Return the configured knowledge-graph backend.

Default is the embedded NetworkX backend (zero infra). Set
MEDIGUARD_KG_BACKEND=neo4j to use a running Neo4j instead.
"""

from __future__ import annotations

from functools import lru_cache

from mediguard.config import settings
from mediguard.kg.base import KnowledgeGraph
from mediguard.kg.embedded import EmbeddedKG


def make_kg(backend: str | None = None) -> KnowledgeGraph:
    backend = (backend or settings.kg_backend).lower()
    if backend == "embedded":
        return EmbeddedKG()
    if backend == "neo4j":
        from mediguard.kg.neo4j_backend import Neo4jKG  # lazy import; optional dep

        return Neo4jKG()
    raise ValueError(f"Unknown KG backend: {backend!r} (use 'embedded' or 'neo4j')")


@lru_cache(maxsize=1)
def get_kg() -> KnowledgeGraph:
    """Process-wide singleton KG (cached)."""
    return make_kg()
