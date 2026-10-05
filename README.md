# MediGuard

**A safe, explainable neuro-symbolic clinical decision-support system for medication recommendation and drug-interaction checking.**
M.Tech project · NIT Rourkela

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PyTorch Geometric](https://img.shields.io/badge/PyG-GNN-EE4C2C?logo=pytorch&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-optional-4581C3?logo=neo4j&logoColor=white)
![React](https://img.shields.io/badge/React-UI-61DAFB?logo=react&logoColor=black)
![License: MIT](https://img.shields.io/badge/License-MIT-green)

> **Advisory only. Not a diagnostic device, not a prescriber.** Every output ends
> with a mandatory *consult-a-doctor* consent note. Research prototype; must not be
> used for real clinical decisions without qualified clinician oversight.

## Why this project

Most ML recommenders in healthcare are black boxes that can confidently suggest something dangerous. MediGuard is built around one rule:

**The machine understands and suggests; deterministic rules, and ultimately a human doctor, decide.**

A rule engine over a medical knowledge graph is the final safety authority. ML and LLM components only read language and generate candidates; they can **never** override a safety block. This invariant is enforced in code (`mediguard/schemas/core.py`: a `Recommendation` that is blocked but still actionable is rejected at construction) and checked by the test suite.

## Results

| Layer | What is measured | Result |
|---|---|---|
| Whole system | Blocked recommendations leaked (150 synthetic patients, 868 recommendations) | **0** |
| Whole system | Explanation faithfulness | **1.000** |
| Safety engine | Known-dangerous combinations flagged | **17 / 17** |
| Safety engine | False-alert rate on safe combinations | **0 / 4** |
| GNN drug-interaction model | AUROC / AUPRC on held-out links | **0.985 / 0.922** |
| Clinical NLP | Entity extraction F1; negation and family-history accuracy (8 gold cases) | **1.000** |

Full numbers and how to regenerate them: [`docs/evaluation.md`](docs/evaluation.md).

**Honest limitations:** curated set of about 40 drugs (not authoritative), synthetic patients only (Synthea), small gold sets for NLP, dictionary-based NLP by default. These are listed so the numbers are read in context.

## Architecture

```
raw text ─(NLP)→ PatientProfile ─┐
                                 ├→ Candidate ─(SAFETY AUTHORITY, veto)→ SafetyVerdict
condition ─(candidates)──────────┘                                          │
                                          (GNN warnings-only) ──────────────┤
                                                                            ▼
                                        Recommendation ←(GraphRAG explain + conformal abstain)
```

- **Clinical NLP** turns free text ("32, pregnant, on warfarin…") into a coded patient profile, handling negation and family history.
- **Knowledge graph** of drugs, conditions and interactions (embedded NetworkX by default, Neo4j optional).
- **Safety authority** is a deterministic rule engine with veto power over every candidate.
- **GNN** (PyTorch Geometric) predicts likely drug–drug interactions, but can only add warnings, never approve.
- **Conformal prediction** (MAPIE) lets the system abstain when it is not confident.
- **GraphRAG / template explainer** produces a rationale traceable to graph facts.
- **Audit log + consent directive** on every output.

Layers talk only through frozen Pydantic contracts in `mediguard/schemas/`.

## Quick start (zero infrastructure, all free)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/Mac: source .venv/bin/activate
pip install -e ".[dev]"
pytest                      # schema + safety acceptance tests
```

The default knowledge-graph backend is embedded NetworkX, so no database is needed.

### See it run

```bash
python scripts/demo.py "32, pregnant, cramps and fever, high sugar, on warfarin"
python scripts/evaluate.py          # regenerates docs/evaluation.md with all metrics
```

### Full web demo (API + React UI)

```bash
uvicorn mediguard.api.app:app --port 8000     # terminal 1
cd ui && npm install && npm run dev           # terminal 2 → http://localhost:5173
```

### Optional Neo4j backend

```bash
docker compose up -d                 # Neo4j at http://localhost:7474
# then set MEDIGUARD_KG_BACKEND=neo4j in your .env
```

### Optional heavy layers

```bash
pip install -e ".[nlp]"          # clinical NLP (medspaCy / scispaCy)
pip install -e ".[gnn]"          # GNN drug-interaction model (PyTorch Geometric)
pip install -e ".[uncertainty]"  # conformal abstention (MAPIE)
```

## Configuration

Copy `.env.example` to `.env`. Every default is free and local (embedded KG, template explainer, free RxNav API).

## Repository layout

| Path | What |
|---|---|
| `mediguard/schemas/` | Frozen data contracts (the API between layers) |
| `mediguard/kg/` | Knowledge graph (embedded NetworkX + Neo4j backends) |
| `mediguard/safety/` | Deterministic rule engine: **the guardrail** |
| `mediguard/nlp/` | Clinical NLP: free text → coded PatientProfile |
| `mediguard/candidates/` | Condition → candidate drugs |
| `mediguard/gnn/` | GNN drug-interaction prediction (warnings only) |
| `mediguard/explain/` | GraphRAG / template explanation layer |
| `mediguard/uncertainty/` | Conformal abstention |
| `mediguard/audit/` | Audit log + consent directive |
| `mediguard/api/` | FastAPI service + FHIR adapters |
| `ui/` | React demo dashboard |
| `etl/` | Data normalization + KG loaders |
| `data/` | `curated/` drug set, `mappings/`, `raw/` (gitignored) |
| `docs/` | Architecture, data provenance, evaluation |
| `tests/` | Schema, safety and acceptance tests |

## Data sources (all free to use)

**RxNorm / RxNav** (free API), **openFDA / FAERS**, **DDInter**, **SIDER**; patients from **Synthea** (synthetic, no credentialing). See [`docs/data_provenance.md`](docs/data_provenance.md) for license and caveats per dataset.

## License

MIT (code). Datasets keep their own licenses; see `docs/data_provenance.md`.
