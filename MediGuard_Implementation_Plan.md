# MediGuard — Implementation Plan

Concrete engineering roadmap derived from `MediGuard_Master_Build_Plan.md`.
This document translates the academic blueprint into buildable milestones, a repo
layout, task lists, and acceptance criteria. **No code is written yet** — this is
the plan to approve before execution.

---

## 0. Guiding principles (locked before coding)

1. **Safety Authority is final.** The deterministic rule engine + KG can veto/downgrade
   any candidate. ML/LLM never overrides it. Every module boundary enforces this.
2. **Build the safe core first, add intelligence outward.** Order: KG → rules → NLP →
   GNN → explanation → UI. Each layer is independently demoable.
3. **Small & correct beats big & shallow.** Target **30–50 outpatient drugs** across
   diabetes, hypertension, pain/fever, common infections. Extensibility is future work.
4. **Contract-first between layers.** Define `PatientProfile`, `Candidate`, `SafetyVerdict`,
   `Recommendation` as typed schemas (Pydantic) before wiring modules. Layers consume
   schemas, never raw text or each other's internals.
5. **Every output ends with the consult-a-doctor consent note + audit log.** Non-negotiable.

---

## 1. Tech stack decisions (concrete versions/choices)

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.11 | Pin in `pyproject.toml` / `.python-version` |
| Package mgmt | `uv` or Poetry | Reproducible lockfile |
| Clinical NLP | medspaCy + ConText (primary), scispaCy `en_ner_bc5cdr_md`, optional BioBERT | medspaCy is the correctness backbone |
| Entity linking | MedCAT or SapBERT → RxNorm/SNOMED/ICD-10 | Start rule/dictionary linking, upgrade if time |
| Knowledge graph | Neo4j 5.x (Docker) | Cypher; OMOP-aligned node/edge names |
| Rule engine | Experta (Rete) | Fallback: plain-Python rule functions if Experta friction is high |
| GNN | PyTorch Geometric | SafeDrug / MPNP-DDI style, DDI link prediction |
| Uncertainty | MAPIE (conformal prediction) | Model-agnostic abstention |
| Explanation | GraphRAG over Neo4j + constrained LLM | LLM sees only retrieved subgraph facts |
| API | FastAPI | FHIR-shaped resources (MedicationRequest, Condition, Observation) |
| Frontend | Streamlit (demo) | React only if time allows |
| Infra | Docker + docker-compose | Neo4j + app; optional Snakemake ETL |
| Testing | pytest | Safety test suite is a first-class deliverable |

**Open decisions to confirm with user before Phase 2** (see §8).

---

## 2. Repository layout (to be created in Phase 0)

```
medication-system/
├─ pyproject.toml / uv.lock
├─ docker-compose.yml            # Neo4j + app
├─ .env.example                  # Neo4j creds, LLM API key, feature flags
├─ README.md
├─ data/
│  ├─ raw/                       # downloaded source dumps (gitignored)
│  ├─ curated/                   # the 30–50 drug set, hand-verified CSV/JSON
│  └─ mappings/                  # Jan Aushadhi ↔ salt ↔ RxCUI
├─ etl/
│  ├─ normalize_rxnorm.py        # names/salts → RxCUI
│  ├─ load_neo4j.py              # curated data → graph
│  └─ build_janaushadhi_map.py
├─ mediguard/
│  ├─ schemas/                   # Pydantic contracts (PatientProfile, Candidate, ...)
│  ├─ nlp/                       # medspaCy pipeline + linking
│  ├─ kg/                        # Neo4j client + Cypher queries
│  ├─ candidates/                # condition → candidate drugs
│  ├─ safety/                    # Experta rules (THE guardrail)
│  ├─ gnn/                       # PyG DDI model + confidence gate
│  ├─ explain/                   # GraphRAG + constrained LLM
│  ├─ uncertainty/              # conformal abstention
│  ├─ audit/                     # audit log + consent directive
│  └─ api/                       # FastAPI app, FHIR adapters
├─ ui/                           # Streamlit app
├─ tests/
│  ├─ test_safety_rules.py       # known-dangerous-combos benchmark
│  ├─ test_nlp_extraction.py     # negation/family-history cases
│  └─ fixtures/                  # synthetic patients, gold entities
└─ docs/
   ├─ architecture.md
   ├─ data_provenance.md         # source, license, caveats per dataset
   └─ evaluation.md
```

---

## 3. Data contracts (define first, in `mediguard/schemas/`)

```
PatientProfile:
  age: int
  pregnant: bool | None
  sex: str | None
  conditions: list[CodedConcept]      # SNOMED/ICD-10
  current_meds: list[CodedDrug]        # RxCUI
  allergies: list[CodedConcept]
  vitals: {bp: str|None, sugar: str|None, weight_kg: float|None, renal: str|None}
  raw_text: str
  consent_captured: bool

Candidate:
  drug: CodedDrug         # RxCUI + name
  salt: str
  for_condition: CodedConcept
  source: "kg" | "guideline" | "ml"

SafetyVerdict:
  candidate: Candidate
  status: "allow" | "warn" | "block" | "downgrade"
  reasons: list[RuleHit]  # rule_id, severity, message, evidence
  fired_rules: list[str]

Recommendation:
  candidate: Candidate
  verdict: SafetyVerdict
  rationale: str          # GraphRAG output, evidence-grounded
  confidence: float
  abstain: bool
  disclaimer: str         # mandatory consent directive
```

These schemas are the API between every phase. Freeze them early; version if changed.

---

## 4. Phased build (mapped to semester plan, made concrete)

### Phase 0 — Bootstrap (Week 0, ~2 days)
- Init repo, `pyproject.toml`, Docker Neo4j via compose, `.env.example`.
- Define all Pydantic schemas in `mediguard/schemas/`.
- CI stub: pytest + lint on push.
- **Acceptance:** `docker-compose up` gives a live empty Neo4j; `pytest` runs green on schema import tests.
- **Also start now (external, slow):** apply for MIMIC-IV + UMLS credentials.

### Phase 1 — Data + Knowledge Graph (blueprint Phase 2)
- Curate the 30–50 drug list (spreadsheet: purpose, pros, cons, side_effects, salt,
  dose, timing, route, quantity). Hand-verify.
- ETL: normalize names/salts → RxCUI (RxNav API); build Jan Aushadhi ↔ salt ↔ RxCUI map.
- Load nodes (`Drug`, `Salt`, `Condition`, `SideEffect`) and edges (`TREATS`,
  `CONTAINS_SALT`, `INTERACTS_WITH{severity,mechanism}`, `CONTRAINDICATES`,
  `CAUSES_SIDE_EFFECT`, `DUPLICATE_CLASS_OF`) into Neo4j. OMOP-aligned naming.
- **Acceptance:** one Cypher query returns a drug's full profile + its interactions +
  contraindications. `docs/data_provenance.md` lists source+license+caveat per dataset.

### Phase 2 — Safety Authority (blueprint Phase 3, the de-risking milestone)
- Implement Experta rule base (or plain-Python fallback) across the 5 categories:
  drug–drug interaction, drug–condition contraindication (pregnancy X = hard block),
  dose/frequency, duplicate therapy, population-specific (geriatric/pediatric/pregnancy).
- Reads `PatientProfile` + `Candidate`, queries KG, emits `SafetyVerdict`.
- Alert-fatigue ranking: severity-sort, suppress low-value alerts.
- Build the **safety benchmark test suite**: a held-out list of known dangerous combos
  + pregnancy/age contraindications the engine MUST flag.
- **Acceptance:** `pytest tests/test_safety_rules.py` — 100% of the known-danger list
  flagged, false-alert rate measured. This alone is a demoable safe system.

### Phase 3 — Clinical NLP layer (blueprint Phase 4)
- medspaCy + ConText pipeline: negation, historical, family-history detection.
- scispaCy/BioBERT NER for biomedical entities where rules fall short.
- Entity linking → SNOMED/ICD-10/RxNorm. Implement the input→code→safety-action table
  from the blueprint (§3.1) as code + tests.
- Output: free-text → validated `PatientProfile`.
- **Acceptance:** on a gold fixture set, report entity-extraction P/R/F1 and negation
  accuracy; "father has heart condition" does NOT set patient cardiac flag.

### Phase 4 — GNN DDI model (blueprint Phase 5, novelty)
- Train SafeDrug/MPNP-DDI-style PyG model on BioSNAP/DrugBank pairs (drug molecular graphs).
- **Confidence gate:** predictions are warnings-only; below threshold → defer to rules.
  The GNN can never flip a rule `block` to `allow`.
- **Acceptance:** report Hits@K / AUPRC / AUROC; a test proving GNN output cannot
  override a `SafetyVerdict.block`.

### Phase 5 — GraphRAG explanation + guardrails (blueprint Phase 6)
- Vetted `Recommendation` → Cypher → extract subgraph → serialize to strict context →
  constrained LLM writes rationale using only that context.
- Conformal abstention (MAPIE): large/uncertain prediction set → "defer to clinician."
- Hard-append consent directive; write audit log (which rules fired) per request.
- **Acceptance:** rationale cites only KG facts (faithfulness check); abstention triggers
  on synthetic ambiguous cases; every output carries disclaimer + audit entry.

### Phase 6 — API, UI, FHIR (blueprint Phase 7)
- FastAPI: `POST /recommend` (patient in → explained, safety-checked recs out).
- FHIR adapters: map to MedicationRequest / Condition / Observation.
- Streamlit dashboard: structured + free-text input → ranked explained recommendations
  + disclaimer.
- **Acceptance:** end-to-end demo from raw patient input to consent-noted report.

### Phase 7 — Evaluation + thesis (blueprint Phase 8)
- Full test-case suite (typical + edge). Optional pharmacist/clinician review.
- Metrics dashboard: NLP P/R/F1; rule coverage + false-alert rate; GNN Hits@K/AUPRC;
  (optional) recommender Jaccard/F1/PRAUC/DDI-rate vs GAMENet/SafeDrug/MoleRec.
- Explanation faithfulness + abstention correctness.
- **Acceptance:** `docs/evaluation.md` populated with all metrics; thesis draft.

---

## 5. Build order dependency graph

```
Phase 0 (schemas, infra)
   └─> Phase 1 (KG)  ──> Phase 2 (Safety Authority)  ← core safe system, demoable
                     └─> Phase 3 (NLP) ──┐
                                         ├─> Phase 5 (GraphRAG explain) ──> Phase 6 (API/UI)
                     Phase 4 (GNN) ──────┘                                      └─> Phase 7 (eval)
```
Phases 2, 3, 4 can partly overlap once the KG (Phase 1) exists. Phase 2 is the critical
de-risking milestone — prioritize it.

---

## 6. Risk register + mitigations

| Risk | Mitigation |
|---|---|
| MIMIC-IV/UMLS approval slow or denied | Apply Day 1; fallback to Synthea/SymCat synthetic patients — project still stands |
| DrugBank/MedDRA licensing | Use free layers (RxNorm, DailyMed, openFDA, DDInter, SIDER); document limits |
| Indian Kaggle data noisy/scraped | Validate every entry against RxNorm; mark as non-authoritative in provenance doc |
| Experta friction (unmaintained-ish) | Plain-Python rule functions fallback with same `SafetyVerdict` contract |
| GNN training data/compute heavy | Scope to link-prediction on curated pairs; it's warnings-only, not on critical path |
| Scope creep beyond 30–50 drugs | Hard-freeze drug list end of Phase 1; extra drugs = future work |
| Cited work retracted (e.g. KGDNet 2024) | Cite SafeDrug/GAMENet/G-BERT/MoleRec instead |

---

## 7. Cross-cutting deliverables (maintained every phase)

- **Safety test suite** grows with each rule/feature; never regresses.
- **Audit log** on every recommendation from Phase 5 onward.
- **`docs/data_provenance.md`** updated whenever a dataset is added.
- **Limitations section** kept live: small drug set, no clinical validation, scraped Indian data.
- **Consent directive** appended to every user-facing output from Phase 2 demos onward.

---

## 8. Decisions needed before Phase 1 execution

1. **LLM for explanation layer** — Claude API (recommended, latest models), local model
   (Llama/Mistral for offline/privacy), or defer explanation to a template until Phase 5?
2. **Frontend** — Streamlit only (fast, recommended) or invest in React?
3. **India layer scope** — include Jan Aushadhi generic-substitution now (novelty +
   social impact, low cost) or defer? Blueprint strongly recommends including it.
4. **MIMIC-IV** — pursue the benchmark recommender track, or synthetic-only? Affects
   whether we chase the Jaccard/F1/DDI-rate quartet vs GAMENet/SafeDrug.

---

*Implementation plan only. Nothing executed. Approve/adjust §8 decisions and phase
ordering, then Phase 0 bootstrap begins.*
