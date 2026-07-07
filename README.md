# MediGuard

A safe, explainable **neuro-symbolic clinical decision-support system (CDSS)** for
medication recommendation and drug–drug / drug–condition interaction checking.

> **Advisory only. Not a diagnostic device, not a prescriber.** Every output ends
> with a mandatory *consult-a-doctor* consent note. Research prototype — must not be
> used for real clinical decisions without qualified clinician oversight.

## The core idea

The machine **understands and suggests**; deterministic **rules — and ultimately a
human doctor — decide**. A rule engine + knowledge graph is the final safety
authority. ML/LLM components only read language and generate candidates; they can
**never** override a safety block. This invariant is enforced in code
(`mediguard/schemas/core.py` → `Recommendation` rejects a blocked-but-actionable
suggestion).

## Architecture

```
raw text ─(NLP)→ PatientProfile ─┐
                                 ├→ Candidate ─(SAFETY AUTHORITY, veto)→ SafetyVerdict
condition ─(candidates)──────────┘                                          │
                                          (GNN warnings-only) ──────────────┤
                                                                            ▼
                                        Recommendation ←(GraphRAG explain + conformal abstain)
```

Layers talk only through the frozen Pydantic contracts in `mediguard/schemas/`.

## Quick start (zero infra — all free)

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate      Linux/Mac: source .venv/bin/activate
pip install -e ".[dev]"
pytest                      # schema + safety acceptance tests
```

The default knowledge-graph backend is **embedded NetworkX** — no database needed.

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
docker compose up -d                 # Neo4j at http://localhost:7474 (neo4j/mediguard)
# then set MEDIGUARD_KG_BACKEND=neo4j in your .env
```

### Optional heavy layers

```bash
pip install -e ".[nlp]"          # Phase 3 clinical NLP (medspaCy/scispaCy)
pip install -e ".[gnn]"          # Phase 4 GNN DDI model (PyTorch Geometric)
pip install -e ".[uncertainty]"  # Phase 5 conformal abstention (MAPIE)
```

## Configuration

Copy `.env.example` → `.env`. Every default is free and local (embedded KG,
template explainer, free RxNav API). See the file for options.

## Repository layout

| Path | What |
|---|---|
| `mediguard/schemas/` | Frozen data contracts (the API between layers) |
| `mediguard/kg/` | Knowledge graph (embedded NetworkX + Neo4j backends) |
| `mediguard/safety/` | Deterministic rule engine — **the guardrail** |
| `mediguard/nlp/` | Clinical NLP: free text → coded PatientProfile |
| `mediguard/candidates/` | Condition → candidate drugs |
| `mediguard/gnn/` | GNN DDI prediction (warnings-only) |
| `mediguard/explain/` | GraphRAG / template explanation layer |
| `mediguard/uncertainty/` | Conformal abstention |
| `mediguard/audit/` | Audit log + consent directive |
| `mediguard/api/` | FastAPI service + FHIR adapters |
| `ui/` | React demo dashboard |
| `etl/` | Data normalization + KG loaders |
| `data/` | `curated/` drug set, `mappings/`, `raw/` (gitignored) |
| `docs/` | architecture, data provenance, evaluation |

## Data sources (all free to use)

See `docs/data_provenance.md` for source, license, and caveats per dataset.
Core: **RxNorm/RxNav** (free API), **openFDA/FAERS**, **DDInter**, **SIDER**.
Patients: **Synthea** synthetic (no credentialing). India Jan Aushadhi layer: deferred.

## License

MIT (code). Datasets retain their own licenses — see `docs/data_provenance.md`.
