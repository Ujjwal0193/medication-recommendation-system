# MediGuard — Architecture

A neuro-symbolic clinical decision-support system. The machine understands and
suggests; deterministic rules — and ultimately a human doctor — decide.

## Data flow

```
              raw patient text  +  structured fields
                        │
                        ▼
        ┌───────────────────────────────┐
        │ 1. Clinical NLP layer         │   mediguard/nlp/
        │   ConText assertion detection │   (negation / family / historical)
        │   + dictionary entity linking │   → SNOMED / ICD-10 / RxNorm
        └───────────────┬───────────────┘
                        ▼   PatientProfile  (frozen schema)
        ┌───────────────────────────────┐
        │ 2. Candidate generation       │   mediguard/candidates/
        │   condition → candidate drugs │   (KG TREATS edges, rank-ordered)
        └───────────────┬───────────────┘
                        ▼   Candidate
        ╔═══════════════════════════════╗
        ║ 3. SAFETY AUTHORITY (guardrail)║  mediguard/safety/
        ║   deterministic rule engine    ║  DDI · contraindication · pregnancy ·
        ║   over the knowledge graph      ║  renal · duplicate · allergy
        ║   → CAN BLOCK / DOWNGRADE       ║  → SafetyVerdict  (rules always win)
        ╚═══════════════╤═══════════════╝
                        ▼
        ┌───────────────────────────────┐
        │ 4. GNN confidence gate         │   mediguard/gnn/
        │   novel-DDI warnings ONLY      │   (never overrides a verdict status)
        └───────────────┬───────────────┘
                        ▼
        ┌───────────────────────────────┐
        │ 5. Conformal abstention        │   mediguard/uncertainty/
        │   uncertain → defer to clinician│
        └───────────────┬───────────────┘
                        ▼
        ┌───────────────────────────────┐
        │ 6. GraphRAG explanation        │   mediguard/explain/
        │   retrieve subgraph → strict    │   (template default; LLM adapters)
        │   context → faithful rationale  │   + mandatory consent directive
        └───────────────┬───────────────┘
                        ▼   Recommendation  (schema rejects actionable BLOCK)
                 API / FHIR / React UI + audit log
```

## The safety invariant (enforced in three independent places)

1. **`Recommendation` schema** (`mediguard/schemas/core.py`) — a `BLOCK` verdict
   cannot become a non-abstaining recommendation; a validator raises otherwise.
2. **`ConfidenceGate.augment`** (`mediguard/gnn/base.py`) — returns a verdict with
   the *same* status; the model can only add MINOR advisory reasons.
3. **`SafetyAuthority`** (`mediguard/safety/engine.py`) — the only component that
   sets a verdict status; no ML output flows into it.

## Frozen contracts (the API between layers)

`PatientProfile → Candidate → SafetyVerdict → Recommendation`
(`mediguard/schemas/`). Every layer consumes these Pydantic models, never raw text
or another layer's internals.

## Pluggable backends (all default to free / zero-infra)

| Concern | Default | Optional |
|---|---|---|
| Knowledge graph | Embedded NetworkX | Neo4j (`[neo4j]` + Docker) |
| Clinical NLP | Rule-based + ConText | medspaCy (`[nlp]`) |
| DDI predictor | Spectral (numpy/sklearn) | PyTorch-Geometric GNN (`[gnn]`) |
| Explanation | Deterministic template | Claude / Ollama constrained LLM |
| Uncertainty | Rule-based abstention | MAPIE conformal (`[uncertainty]`) |

## Components

| Module | Responsibility |
|---|---|
| `mediguard/schemas` | Frozen data contracts + safety invariant |
| `mediguard/kg` | Knowledge-graph interface + embedded/Neo4j backends |
| `mediguard/nlp` | Free text → coded PatientProfile (negation/family aware) |
| `mediguard/candidates` | Condition → ranked candidate drugs |
| `mediguard/safety` | Deterministic rule engine (the guardrail) |
| `mediguard/gnn` | Novel-DDI prediction + confidence gate (warnings-only) |
| `mediguard/uncertainty` | Conformal-style abstention |
| `mediguard/explain` | GraphRAG retrieval + faithful explanation |
| `mediguard/audit` | Audit log + consent directive |
| `mediguard/api` | FastAPI service + FHIR adapters |
| `mediguard/pipeline.py` | End-to-end orchestrator |
| `ui/` | React (Vite) dashboard |

## Evaluation

`python scripts/evaluate.py` regenerates `docs/evaluation.md` — NLP P/R/F1,
safety coverage + false-alert rate, GNN AUROC/AUPRC/Hits@K, and a system-level
run over synthetic patients checking the safety invariant + explanation faithfulness.
```
```
