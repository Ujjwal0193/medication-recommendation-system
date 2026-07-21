# MediGuard — Work Done

> Living reference log. Read this first in any new session to know where the project
> stands. Updated via the `/summarizeWorkDone` slash command (appends a per-session
> entry + refreshes the status snapshot).

---

## Project objectives

MediGuard is an M.Tech project (Ujjwal Rawat, NIT Rourkela, 2025–2027): a **safe,
explainable neuro-symbolic clinical decision-support system (CDSS)** for medication
recommendation and drug-interaction checking. Built from
`MediGuard_Master_Build_Plan.md` → `MediGuard_Implementation_Plan.md`.

**Core goal / thesis sentence:** build a hybrid system where a deterministic
rules + knowledge-graph engine is the *final safety authority*, and ML/LLM
components only understand language and generate candidates — they never override
safety. The machine understands and suggests; the rules — and ultimately a human
doctor — decide.

**What it must do:**
1. Take a medicine knowledge base (purpose, salt, dose, timing, route, side effects,
   good-with / harmful-with).
2. Take a patient profile — free text ("32, pregnant, cramps + fever, low BP, high
   sugar") **and** structured fields.
3. Produce a ranked, explained recommendation with drug–drug and drug–condition
   safety checks, dosing/timing, and a mandatory consult-a-doctor consent note.

**Hard boundaries:** does not diagnose; does not replace a prescriber; every output
carries a disclaimer; research prototype, not a certified device.

**Locked decisions:** explanation = template-first pluggable (no API key); frontend =
React; India Jan Aushadhi layer = deferred (future work); patient data = Synthea
synthetic only (MIMIC-IV deferred). Everything free to use.

---

## Current status snapshot

_Last updated: 2026-07-08_

**Overall: all 8 build phases complete + full product website built. System runs,
is tested, and is demoable end-to-end.**

- **Tests:** 85 passing (pytest), ruff lint clean.
- **Runnable:** CLI demo, evaluation harness, FastAPI API, React multi-page website
  — all verified working (API verified live over HTTP; website verified in-browser).
- **Metrics:** safety 17/17 danger cases flagged (100%), 0 false alerts · NLP entity
  F1 1.00 · GNN DDI AUROC 0.99 / AUPRC 0.92 · 0 blocked recs leaked across 868 recs
  on 150 synthetic patients · explanation faithfulness 1.00.

### What exists (by layer)

| Layer | Location | State |
|---|---|---|
| Frozen schemas (safety invariant in code) | `mediguard/schemas/` | Done |
| Knowledge graph (NetworkX default + Neo4j) | `mediguard/kg/`, `data/curated/*.json` | Done, ~40 drugs |
| Safety Authority (rule engine, the guardrail) | `mediguard/safety/` | Done, 100% benchmark |
| Clinical NLP (free text → PatientProfile) | `mediguard/nlp/` | Done, F1 1.00 |
| Candidate generation | `mediguard/candidates/` | Done |
| GNN DDI predictor + confidence gate | `mediguard/gnn/` | Done, warnings-only |
| Conformal abstention | `mediguard/uncertainty/` | Done |
| GraphRAG explanation (template + LLM adapters) | `mediguard/explain/` | Done, faithful |
| Audit log + consent | `mediguard/audit/` | Done |
| End-to-end pipeline orchestrator | `mediguard/pipeline.py` | Done |
| FastAPI service + FHIR adapters | `mediguard/api/` | Done |
| React product website (Home/Demo/About/Docs) | `ui/` | Done, verified in-browser |
| Evaluation harness + synthetic patients | `scripts/evaluate.py`, `etl/` | Done |
| Docs (architecture, provenance, evaluation) | `docs/` | Done |

### How to run

```bash
# tests
.venv/Scripts/python.exe -m pytest

# CLI demo
python scripts/demo.py "32, pregnant, cramps and fever, high sugar, on warfarin"

# evaluation (regenerates docs/evaluation.md)
python scripts/evaluate.py

# full website (two terminals)
uvicorn mediguard.api.app:app --port 8000
cd ui && npm install && npm run dev      # http://localhost:5173
```

### Deferred / future work

- India Jan Aushadhi generic-substitution layer.
- MIMIC-IV benchmark recommender track (GAMENet/SafeDrug comparison).
- Real medspaCy/BioBERT NLP + PyTorch-Geometric GNN training (stubs + extras ready).
- Public deployment config (demo page needs the Python backend hosted).
- Validate curated interaction/contraindication facts against DDInter/DailyMed.

---

## Session log

_Newest entries appended below by `/summarizeWorkDone`._

### Session — 2026-07-08 (initial build)

Executed the entire implementation plan in one run, committed phase-by-phase:

- **Phase 0** — repo scaffold, frozen Pydantic contracts, safety invariant enforced
  in code, Docker/CI/venv, 8 schema tests.
- **Phase 1** — curated ~40-drug dataset + conditions/interactions/contraindications/
  classes; pluggable KG (NetworkX default + Neo4j backend); RxNav normalizer;
  provenance doc.
- **Phase 2** — deterministic Safety Authority (6 rule categories); safety benchmark
  100% (17/17), 0 false alerts; candidate generator; audit log + consent.
- **Phase 3** — clinical NLP: ConText negation/family/history + dictionary linking →
  PatientProfile; entity F1 1.00.
- **Phase 4** — DDI predictor (spectral graph embeddings; optional PyG GNN) +
  confidence gate proven never to override BLOCK; AUROC 0.99.
- **Phase 5** — GraphRAG retrieval + faithful template explainer + conformal
  abstention + end-to-end pipeline; no BLOCK leaks as actionable.
- **Phase 6** — FastAPI (+ FHIR adapters) + React dashboard; verified live over HTTP.
- **Phase 7** — evaluation harness + synthetic patients + architecture/eval docs +
  CLI demo.
- **Product website** — multi-page React site (Home, Live Demo with free-text +
  structured form, About, Docs with browsable drug KB); added `/conditions` and
  `/drug/{name}` API endpoints; verified in-browser (home renders, demo runs the
  full pipeline).

Result at end of session: 85 tests green, lint clean, website live-verified.
