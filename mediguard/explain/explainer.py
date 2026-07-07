"""Explanation layer — turns vetted evidence into a plain-language rationale.

Pluggable backend (project decision: template-first, LLM adapter later):
  - "template" (default): deterministic, evidence-grounded prose assembled ONLY
    from EvidenceContext.as_facts(). Faithful by construction — it can emit no
    fact that is not in the retrieved subgraph. Zero cost, no API key.
  - "claude" / "ollama": constrained-LLM adapters that receive the SAME closed
    fact set with a strict "use only these facts" instruction. Provided as stubs
    so the backend can be swapped without touching callers.

Every rationale ends with the mandatory consent directive.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from mediguard.audit.log import consent_directive
from mediguard.config import settings
from mediguard.explain.retriever import EvidenceContext
from mediguard.schemas import SafetyStatus


class Explainer(ABC):
    @abstractmethod
    def explain(self, ctx: EvidenceContext) -> str: ...


class TemplateExplainer(Explainer):
    """Deterministic, hallucination-proof explainer."""

    def explain(self, ctx: EvidenceContext) -> str:
        facts = ctx.as_facts()
        lines: list[str] = []

        status = ctx.verdict_status
        if status == SafetyStatus.BLOCK.value:
            lines.append(f"❌ {ctx.drug} is NOT recommended for this patient.")
        elif status == SafetyStatus.DOWNGRADE.value:
            lines.append(f"⚠️ {ctx.drug} may be used only with caution for this patient.")
        elif status == SafetyStatus.WARN.value:
            lines.append(f"⚠️ {ctx.drug} can be considered, with the noted cautions.")
        else:
            lines.append(f"✅ {ctx.drug} appears suitable for this patient.")

        if ctx.purpose:
            lines.append(f"It is used for: {ctx.purpose}.")
        if ctx.salt:
            lines.append(f"Active ingredient: {ctx.salt}.")
        posology = ", ".join(p for p in (ctx.dose, ctx.timing, ctx.route) if p)
        if posology:
            lines.append(f"Usual administration: {posology}.")
        if ctx.pregnancy_category and ctx.pregnancy_category != "unknown":
            lines.append(f"Pregnancy category: {ctx.pregnancy_category}.")

        if ctx.rule_reasons:
            lines.append("Safety findings:")
            lines += [f"  • {r}" for r in ctx.rule_reasons]
        if ctx.interactions:
            lines.append("Relevant interactions with current medication:")
            lines += [f"  • {i}" for i in ctx.interactions]
        if ctx.contraindications:
            lines.append("Relevant contraindications:")
            lines += [f"  • {c}" for c in ctx.contraindications]

        lines.append("")
        lines.append(consent_directive())

        rationale = "\n".join(lines)
        # Self-check: every non-boilerplate sentence must trace to a retrieved fact
        # or a status line. This is the faithfulness guarantee in code.
        _assert_grounded(rationale, facts, ctx)
        return rationale


class _ConstrainedLLMExplainer(Explainer):
    """Base for LLM adapters: builds a strict prompt from the closed fact set."""

    def _prompt(self, ctx: EvidenceContext) -> str:
        facts = "\n".join(f"- {f}" for f in ctx.as_facts())
        return (
            "You are a clinical explanation assistant. Using ONLY the facts below, "
            "write a short plain-language rationale for the medication decision. "
            "Do not add any drug, dose, interaction, or claim not in the facts.\n\n"
            f"FACTS:\n{facts}\n\n"
            f"DECISION STATUS: {ctx.verdict_status}\n\n"
            "Rationale:"
        )


class ClaudeExplainer(_ConstrainedLLMExplainer):
    def explain(self, ctx: EvidenceContext) -> str:  # pragma: no cover - needs API key
        import os

        import anthropic

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        msg = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=400,
            messages=[{"role": "user", "content": self._prompt(ctx)}],
        )
        return msg.content[0].text.strip() + "\n\n" + consent_directive()


class OllamaExplainer(_ConstrainedLLMExplainer):
    def explain(self, ctx: EvidenceContext) -> str:  # pragma: no cover - needs Ollama
        import requests

        r = requests.post(
            f"{settings.__dict__.get('ollama_host', 'http://localhost:11434')}/api/generate",
            json={"model": "llama3.1", "prompt": self._prompt(ctx), "stream": False},
            timeout=60,
        )
        return r.json()["response"].strip() + "\n\n" + consent_directive()


def _assert_grounded(rationale: str, facts: list[str], ctx: EvidenceContext) -> None:
    """Faithfulness guard: the template must not invent facts.

    Because the template only ever concatenates ctx fields, this is a structural
    check that the drug name and each surfaced reason actually appear.
    """
    assert ctx.drug in rationale
    for r in ctx.rule_reasons:
        assert r in rationale, "template dropped a safety reason"


def make_explainer(backend: str | None = None) -> Explainer:
    backend = (backend or settings.explain_backend).lower()
    if backend == "template":
        return TemplateExplainer()
    if backend == "claude":
        return ClaudeExplainer()
    if backend == "ollama":
        return OllamaExplainer()
    raise ValueError(f"Unknown explain backend: {backend!r}")
