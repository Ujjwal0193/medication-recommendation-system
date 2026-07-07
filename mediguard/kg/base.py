"""Knowledge-graph interface shared by every backend.

The rest of MediGuard depends only on this abstract class, never on NetworkX or
Neo4j directly. Swap backends via MEDIGUARD_KG_BACKEND without touching callers.

Graph model (OMOP-aligned naming):
    Nodes:  Drug, Salt, Condition, SideEffect
    Edges:  TREATS (Condition->Drug), CONTAINS_SALT (Drug->Salt),
            INTERACTS_WITH (Drug-Drug, props: severity, mechanism, management),
            CONTRAINDICATES (Condition->Drug, props: severity, reason),
            CAUSES_SIDE_EFFECT (Drug->SideEffect),
            DUPLICATE_CLASS_OF (Drug-Drug, prop: class)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class DrugProfile:
    """Everything the KG knows about one drug (returned by get_drug_profile)."""

    name: str
    rxcui: str | None = None
    salt: str | None = None
    atc: str | None = None
    drug_class: str | None = None
    purpose: str = ""
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    side_effects: list[str] = field(default_factory=list)
    dose: str = ""
    timing: str = ""
    route: str = ""
    quantity: str = ""
    pregnancy_category: str = "unknown"
    renal_caution: str = ""
    attributes: dict = field(default_factory=dict)


@dataclass
class InteractionEdge:
    drug_a: str
    drug_b: str
    severity: str
    mechanism: str = ""
    management: str = ""


@dataclass
class ContraindicationEdge:
    condition_code: str
    drug: str
    severity: str
    reason: str = ""


class KnowledgeGraph(ABC):
    """Read interface over the medication knowledge graph."""

    # --- lookups -------------------------------------------------------- #
    @abstractmethod
    def get_drug_profile(self, drug: str) -> DrugProfile | None:
        """Full profile for a drug by name (case-insensitive) or RxCUI."""

    @abstractmethod
    def drugs_for_condition(self, condition_code: str) -> list[dict]:
        """Candidate drugs treating a condition, each {drug, rank, line}."""

    @abstractmethod
    def interactions_for(self, drug: str) -> list[InteractionEdge]:
        """All interaction edges touching this drug."""

    @abstractmethod
    def interaction_between(self, drug_a: str, drug_b: str) -> InteractionEdge | None:
        """The interaction edge between two drugs, if any."""

    @abstractmethod
    def contraindications_for_drug(self, drug: str) -> list[ContraindicationEdge]:
        """All condition->drug contraindications for this drug."""

    @abstractmethod
    def contraindication(self, condition_code: str, drug: str) -> ContraindicationEdge | None:
        """The contraindication edge for a (condition, drug) pair, if any."""

    @abstractmethod
    def drug_class(self, drug: str) -> str | None:
        """Therapeutic class of a drug (for duplicate-therapy detection)."""

    @abstractmethod
    def all_drugs(self) -> list[str]:
        """Names of every drug node."""

    def close(self) -> None:  # pragma: no cover - default no-op
        """Release backend resources (Neo4j driver, etc.)."""
        return None
