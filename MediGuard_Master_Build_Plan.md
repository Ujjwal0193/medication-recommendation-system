# MediGuard — Master Build Plan
### A Safe, Explainable Medication-Recommendation & Drug-Interaction Decision-Support System
**M.Tech Project Blueprint — synthesized from 4 deep-research reports**
Prepared for: Ujjwal Rawat · NIT Rourkela · M.Tech 2025–2027

---

## 0. How to read this document

Your four research reports agree on ~80% of the design and disagree (usefully) on the rest. This document merges them into **one opinionated plan**: what to build, in what order, with which tools, and how to defend it academically. Where the reports differed, I picked the option that is *safest*, *achievable in two semesters*, and *strongest on a resume*, and I say why.

The single most important decision, which all four reports converge on:

> **Build a hybrid "neuro-symbolic" system where a deterministic rules + knowledge-graph engine is the final safety authority, and ML/LLM components only understand language and generate candidates — never override safety.** The LLM never has the last word on safety; the rules do.

This is what makes the project safe *and* smart at the same time, and it is the sentence you will repeat in your thesis defense.

---

## 1. What you are actually building (scope)

A **Clinical Decision Support System (CDSS)** — explicitly *advisory*, not diagnostic, not a prescriber. It:

1. Takes a **medicine knowledge base** (purpose, pros/cons, side effects, salt/active ingredient, dose, timing, route, "good with" / "harmful with").
2. Takes a **patient profile** — free-text ("32, pregnant, cramps + fever, low BP, high sugar") **and** structured fields (age, pregnancy, diabetes, BP, heart condition, current meds, allergies).
3. Produces a **ranked, explained medication suggestion** with drug–drug and drug–condition safety checks, dosing/timing, and a **mandatory "consult a doctor before proceeding" consent note**.

**Scope discipline (from the Perplexity report — take this seriously):** do **not** try to cover all medicines. Target **30–50 commonly used outpatient drugs** across a few domains — diabetes, hypertension, pain/fever, common infections. A small, correct, well-explained system beats a huge, shallow one for both grading and safety. You can claim "extensible to thousands" as future work.

**Hard boundaries to state in the report (all four reports insist on these):**
- The system does **not** diagnose.
- The system does **not** replace a prescriber; it flags issues and suggests options for discussion.
- Every output ends with a disclaimer + doctor-review directive.
- It is a research prototype, **not** a certified medical device.

---

## 2. The recommended architecture (the "MediGuard" pipeline)

This is the consensus architecture across all four reports, merged. Data flows top to bottom; the **Safety Authority can veto anything**.

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. INPUT + CONSENT                                              │
│    Free-text report + structured fields (age, pregnancy, BP,   │
│    sugar, heart condition, current meds, allergies)            │
│    → consent captured, disclaimer shown up front               │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. CLINICAL NLP LAYER  (understands the patient)               │
│    medspaCy + ConText (negation/family/history)                │
│    + scispaCy / BioBERT NER → entity linking                   │
│    → maps "sugar"→Diabetes(SNOMED), "BP"→Hypertension(ICD-10), │
│      drug names → RxNorm RxCUI (salt normalization)            │
│    OUTPUT: a clean, coded, structured patient profile          │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. CANDIDATE GENERATION  (suggests options)                    │
│    Condition → candidate drugs via Knowledge Graph             │
│    (optionally: guideline lookup, e.g. WHO first-line; and/or  │
│     a simple ML ranker / recommender)                          │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌═════════════════════════════════════════════════════════════════┐
║ 4. SAFETY AUTHORITY  (deterministic — THE GUARDRAIL)           ║
║    Rule engine (Experta/Rete) + Knowledge Graph (Neo4j)        ║
║    For every candidate, check:                                 ║
║      • Drug–drug interactions vs current meds (severity)       ║
║      • Drug–condition contraindications (pregnancy/age/renal)  ║
║      • Duplicate-therapy (two drugs same class)                ║
║      • Dose limits vs age/weight/renal function                ║
║    → CAN BLOCK / DOWNGRADE any candidate. Rules always win.    ║
║    (Optional GNN flags UNKNOWN interactions as WARNINGS only.) ║
└═════════════════════════════════════════════════════════════════┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. EXPLANATION LAYER  (GraphRAG / constrained LLM)             │
│    LLM receives ONLY vetted candidates + retrieved KG facts,   │
│    writes plain-language rationale ("Drug Y treats X; contains │
│    salt Z; safe given your profile; take after food")          │
│    Constrained to retrieved evidence → no hallucination        │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. UNCERTAINTY + HUMAN-IN-THE-LOOP                             │
│    Low confidence / conflicting rules → "defer to clinician"   │
│    Always append: consult-a-doctor note + audit log            │
└─────────────────────────────────────────────────────────────────┘
```

### Why this specific shape (the defensible logic)
- **Pure LLM** → hallucinates dosages/contraindications. Unsafe. ❌
- **Pure GNN/ML recommender** → accurate but a black box, and needs restricted hospital data (MIMIC). Hard to explain in a viva. ⚠️
- **Pure rules/KG** → safe and explainable but can't read free text or generalize. ⚠️
- **Hybrid (this)** → NLP reads the patient, KG+rules guarantee safety, LLM explains, GNN adds research novelty. ✅ Best of all four.

---

## 3. Component-by-component method guide

### 3.1 Clinical NLP layer — "understand the patient"
**Goal:** turn `"32, pregnant, severe cramps and fever, history of low BP and high sugar"` into coded facts, correctly handling negation ("no chest pain") and family history ("my father has a heart condition" ≠ patient has it).

**Recommended stack (merged best-of):**
- **medspaCy + ConText algorithm** — purpose-built for clinical text; handles negation, historical, and family-history context. This is your primary pipeline (from the Neuro-Symbolic report). It's the single most important correctness detail most students miss.
- **scispaCy** (`en_ner_bc5cdr_md`) and/or **BioBERT / ClinicalBERT** for stronger biomedical NER where medspaCy rules fall short. Fine-tuned BERT beats zero-shot LLMs for entity extraction.
- **Entity linking** to standard codes: conditions → **SNOMED CT / ICD-10**, drugs/salts → **RxNorm RxCUI**. (MedCAT or SapBERT for linking.)

**Output contract:** a structured `PatientProfile` object — `{age, pregnant, conditions:[SNOMED...], current_meds:[RxCUI...], vitals:{bp, sugar}, allergies:[...]}`. Everything downstream consumes this, not raw text.

**Map these patient inputs explicitly (build this table into your code + thesis):**

| Patient says | Coded as | Safety action it triggers |
|---|---|---|
| "sugar" | Diabetes Mellitus (SNOMED 73211009) | anti-diabetic contraindication + glycemic-impact check |
| "high/low BP" | Hypertension I10 / Hypotension I95 | NSAID / beta-blocker cardiovascular rules |
| "fever" | Pyrexia (SNOMED 386661006) | acute symptom → antipyretic search |
| "cramps" | Muscle cramp (SNOMED 55300003) | acute symptom → analgesic/relaxant search |
| "pregnant" | Pregnancy (ICD-10 Z33.1) | **CRITICAL: teratogen filter (block category X)** |
| "heart condition" | Cardiac disease (ICD-10 I51.9) | **CRITICAL: cardiovascular interaction checks** |

### 3.2 Knowledge base + knowledge graph — "the facts"
**Recommended:** a **Neo4j property graph** (all four reports converge here; graph beats SQL because a patient→condition→drug→salt→interaction→side-effect chain is naturally multi-hop).

**Node types:** `Drug`, `ActiveIngredient(Salt)`, `Condition`, `SideEffect`, `Patient`.
**Edge types:** `TREATS`, `CONTAINS_SALT`, `INTERACTS_WITH` (props: severity, mechanism), `CONTRAINDICATES` (Condition→Drug), `CAUSES_SIDE_EFFECT`, `DUPLICATE_CLASS_OF`.

**Model it to a standard so it's not toy-grade:** align node/edge semantics loosely to the **OMOP Common Data Model** (Person, Condition, Drug, Observation). Mentioning OMOP + FHIR in the thesis signals professional maturity.

**`Drug` node carries exactly your requested attributes:** purpose, pros, cons, side_effects, salt, dose, timing, route, quantity.

### 3.3 The Safety Authority — rules engine (the heart of "safe")
**Recommended:** **Experta** (Python, CLIPS-inspired, uses the **Rete** algorithm, forward-chaining). It cleanly separates **Facts** (patient data) from **Rules** (clinical knowledge) — exactly the transparency an examiner wants. (Alternatives: Drools, or plain Python functions per rule category if Experta feels heavy — Perplexity's pragmatic fallback.)

**Rule categories to implement (focused, ~from all four reports):**
1. **Drug–drug interaction:** A `INTERACTS_WITH` B (major) + patient on both → block/monitor.
2. **Drug–condition contraindication:** patient has C + drug contraindicated in C → do-not-use. (Pregnancy category **X = hard block**; C/D = warn.)
3. **Dose/frequency:** dose > max for age/weight/renal → overdose flag.
4. **Duplicate therapy:** two drugs same class (two NSAIDs, two ACE-inhibitors) → flag.
5. **Population-specific:** geriatric/pediatric dose limits; pregnancy/lactation restrictions.

**Design principle — alert fatigue (Perplexity + GPT):** don't fire every trivial alert. Rank by severity, suppress low-value noise. This is a *named research contribution* you can claim.

### 3.4 DDI prediction with GNN (the "research novelty" component)
Static databases miss undocumented multi-drug interactions. Add a **Graph Neural Network** (PyTorch Geometric) that represents drugs as molecular graphs (atoms=nodes, bonds=edges) and predicts unknown interactions. Reference architectures: **SafeDrug**, **Decagon/BioSNAP**, **MPNP-DDI** (co-attention over substructures), **KGNN**.

**Critical safety rule:** the GNN's predictions are **warnings only**. If GNN confidence < threshold → defer to the deterministic rules. The neural net **never** overrides the symbolic guardrail. (This "confidence gate" is itself a citable safety design.)

### 3.5 Explanation layer — GraphRAG / constrained LLM
Use the LLM **only to explain**, never to decide safety. Workflow (GraphRAG, from the Neuro-Symbolic report):
1. Turn the vetted result into a Cypher query over Neo4j.
2. Extract the relevant subgraph (drug → salt → contraindications → posology).
3. Serialize graph paths into a strict context ("Symptom X treated by Y; Y contains Z; Z safe for condition W").
4. LLM writes the final report **using only that context** → hallucination is structurally prevented.

Then hard-append the **medical consent directive** to every output.

### 3.6 Uncertainty + human-in-the-loop
- **Conformal prediction** (model-agnostic, formal coverage guarantees) → when the prediction set is large/uncertain, output "defer to clinician." This is the academically respectable uncertainty method (cite it).
- Always: disclaimer, doctor-review note, and an **audit log** of which rules fired (doubles as your explainability evidence and your regulatory defense).

---

## 4. Datasets — what to use and the honest caveats

**Use a layered stack** (not one dataset). This is the merged recommendation:

| Layer | Dataset | Gives you | Access / caveat |
|---|---|---|---|
| Backbone / normalization | **RxNorm** (NLM) | standardized drug/salt names, RxCUIs, ATC | free API (RxNav) |
| Drug attributes | **DrugBank**, **DailyMed** | purpose, targets, labels, dosing, contraindications, pregnancy category | DrugBank: **academic free on application, commercial = paid**; DailyMed free |
| Interactions | **DDInter 2.0**, **TWOSIDES/OFFSIDES** | DDI records + mechanisms + management text | DDInter open & license-friendly ✅ |
| Side effects | **SIDER**, **BioSNAP (ChSe-Decagon)** | drug→ADR pairs, side-effect network for the GNN | free download |
| Pharmacovigilance | **openFDA / FAERS** | adverse-event signals | free API |
| Terminology hub | **UMLS** (SNOMED CT, ICD-10, MedDRA, RxNorm) | entity linking | free w/ license |
| Benchmark (optional) | **MIMIC-IV** (PhysioNet) | real EHR to train/benchmark a recommender + cite standard metrics | **restricted: credentialing + CITI course + DUA — apply EARLY** |
| **India layer** | **Jan Aushadhi / PMBJP product list** (~2,000 generics) + Kaggle "A-Z Medicine Dataset of India" / "250k Medicines…" | Indian brand↔salt mapping, affordable generic substitutes | Kaggle sets are **scraped, CC-BY-NC, noisy — validate against RxNorm** |

**My concrete recommendation for *your* scope:**
- **Core (must):** RxNorm + DailyMed/openFDA + DDInter + SIDER, curated down to your 30–50 drugs.
- **India differentiator (strongly recommended):** add the **Jan Aushadhi/PMBJP** mapping — branded → generic salt → affordable Jan Aushadhi code. This is your *novelty + social-impact* angle and costs little to add.
- **GNN training:** BioSNAP/DrugBank pairs.
- **MIMIC-IV:** only if you want to reproduce/benchmark GAMENet/SafeDrug. Apply on day 1 because approval is slow. If it doesn't come through, pivot to synthetic patients (SymCat + Synthea) — the project still stands.

**Caveats you must write in the thesis (credibility-builders, from the Claude report):**
- MIMIC is ICU/inpatient, small drug space (~131 drugs) — a benchmark component, not the whole system.
- Indian Kaggle/1mg data is a scraped snapshot, non-authoritative — validate, don't trust blindly.
- DrugBank full DDI/severity + MedDRA need licenses; the free RxNav interaction API is limited.
- One KG-medication paper (KGDNet, 2024) was **retracted** — prefer SafeDrug/GAMENet/G-BERT/MoleRec as citations.

---

## 5. Recommended tech stack

| Layer | Tool |
|---|---|
| Language | **Python** (your strength) |
| Clinical NLP | **medspaCy + ConText**, scispaCy, BioBERT/ClinicalBERT |
| Knowledge graph | **Neo4j** (Cypher), OMOP-aligned schema |
| Rule engine | **Experta** (Rete) — or Drools / plain-Python fallback |
| GNN | **PyTorch Geometric** (SafeDrug / MPNP-DDI style) |
| Explanation | GraphRAG over Neo4j + a constrained LLM |
| Uncertainty | Conformal prediction (MAPIE) |
| API | **FastAPI** (REST); model patient/med data as **FHIR** resources (MedicationRequest, Condition, Observation) |
| Frontend | **Streamlit** (fast demo) or React (polished) |
| Infra | Docker; optional Snakemake ETL to load Neo4j |

Adding **FHIR** (even as a facade/future-work) and **OMOP** is what elevates this from "student project" to "health-tech engineer" on a resume.

---

## 6. Phased execution plan (two semesters)

This merges the Claude staged plan, the Neuro-Symbolic semester map, and Perplexity's phases. **Build the safe core first, add intelligence outward.**

### Semester 3 — Research, core, and logic
**Phase 1 (Weeks 1–3) — Foundations & literature.**
- Read the CDSS + medication-recommendation literature; write user stories ("given diabetic + hypertensive on drug X, is adding Y safe?").
- **Apply for MIMIC-IV / UMLS credentials now** (slow approvals).
- Deliverable: synopsis + topic approval + a baseline IEEE paper to anchor against (IEEE JBHI is a good target venue).

**Phase 2 (Weeks 3–6) — Data + knowledge graph.**
- Curate 30–50 drugs. Normalize to RxNorm. Load DrugBank/DailyMed/DDInter/SIDER attributes + the Jan Aushadhi salt mapping into a Dockerized Neo4j.
- Deliverable: a queryable KG; a Cypher query that returns a drug's full profile + interactions.

**Phase 3 (Weeks 6–10) — The Safety Authority (deterministic core).**
- Implement the Experta rule base: interactions, contraindications, dose, duplicates, pregnancy/age.
- **Benchmark:** it must correctly flag a held-out list of known dangerous combinations + pregnancy/age contraindications. *This alone is already a safe, demonstrable system* — a huge de-risking milestone.
- Deliverable: working backend inference engine (interim review demo).

**Phase 4 (Weeks 8–12) — Clinical NLP layer.**
- Wire up medspaCy+ConText → scispaCy/BioBERT → SNOMED/ICD/RxNorm linking. Handle negation & family history.
- Deliverable: free-text → structured `PatientProfile`, with entity-extraction F1 reported.

### Semester 4 — Intelligence, integration, thesis
**Phase 5 (Weeks 1–4) — GNN DDI model (novelty).**
- Train SafeDrug/MPNP-DDI-style GNN on BioSNAP/DrugBank; add the **confidence gate** (warnings-only, deference to rules).
- Deliverable: DDI predictions with Hits@K / AUPRC; evidence it never overrides the guardrail.

**Phase 6 (Weeks 3–7) — GraphRAG explanation + guardrails.**
- Build the constrained GraphRAG explainer; add conformal-prediction abstention; hard-code the consent directive + audit log.
- Deliverable: end-to-end plain-language recommendation with citations to KG facts.

**Phase 7 (Weeks 6–10) — API, UI, FHIR.**
- FastAPI service, FHIR-shaped resources, Streamlit/React dashboard: patient in → explained, safety-checked recommendation + disclaimer out.
- Deliverable: full demo, input to consent report.

**Phase 8 (Weeks 9–14) — Evaluation + thesis.**
- Test-case suite (typical + edge cases); ideally an informal review by a pharmacist/clinician.
- Metrics: NLP precision/recall; rule coverage; GNN Hits@K/AUPRC; (optional) recommender Jaccard/F1/PRAUC/DDI-rate vs GAMENet/SafeDrug baselines.
- Write the 60–70 page thesis; viva.

---

## 7. Evaluation metrics (what to actually measure)

- **NLP layer:** entity-extraction Precision / Recall / F1; negation-detection accuracy.
- **Rule engine:** % of known unsafe combinations correctly flagged; false-alert rate (alert-fatigue proxy).
- **GNN DDI:** AUROC, AUPRC, Hits@K.
- **Recommender (if MIMIC used):** **Jaccard, Average-F1, PRAUC, DDI-rate** — the standard quartet. Compare to published GAMENet ≈ J0.52/F1 0.66/DDI 0.089, SafeDrug ≈ J0.52/F1 0.68/DDI 0.066, MoleRec ≈ J0.53/PRAUC 0.78/DDI 0.069.
- **System:** explanation faithfulness (does the rationale match the KG facts?); abstention correctness.

---

## 8. Safety, ethics & regulatory framing (don't skip — it's a grading + resume asset)

- **Framing:** an *educational / decision-support* tool that lets a human independently review the basis of every recommendation. This mirrors the **US FDA "Non-Device CDS" criteria** (esp. the "independently review the basis" criterion) and **India's CDSCO SaMD draft guidance (Oct 2025)**. Say explicitly it is **not** a diagnostic device.
- **Guardrails already in the design:** deterministic veto, warnings-only ML, conformal abstention, mandatory disclaimer, audit log, human-in-the-loop.
- **Privacy:** treat any patient data as sensitive; if you demo with real-ish profiles, keep them synthetic/de-identified (HIPAA/GDPR spirit).
- **Explicitly list limitations** in the thesis: small drug set, no real clinical validation, scraped Indian data. Stating limits *raises* your credibility.

---

## 9. Resume framing & publication angle

**One-line resume bullet:**
> Built an explainable, safety-first **neuro-symbolic clinical decision-support system** for medication recommendation and drug–drug/drug–condition interaction checking — combining clinical NLP (medspaCy/BioBERT), a Neo4j knowledge graph with a deterministic Experta rule engine as the safety authority, a PyTorch-Geometric GNN for novel-interaction prediction, and a constrained GraphRAG explanation layer with conformal-prediction uncertainty and a mandatory human-in-the-loop consent workflow.

**Supporting bullets:**
- Engineered a knowledge graph mapping global drug data (DrugBank/DDInter/SIDER) to India's **Jan Aushadhi (PMBJP)** generics to recommend affordable salt-equivalent alternatives.
- Built a clinical NLP pipeline (medspaCy + ConText) parsing free-text patient reports into SNOMED/ICD/RxNorm-coded profiles with negation and family-history handling.
- Designed a FHIR-shaped FastAPI service, positioning the system for EHR interoperability.

**Publishable novelty angles (pick one to emphasize):**
1. **India generic-substitution layer** bridged to global drug ontologies (novel dataset integration + social impact).
2. **Deterministic-veto hybrid** (KG+rules + GNN warnings + conformal abstention) — a *safety-architecture* contribution.
3. **Drug–condition contraindication reasoning** (pregnancy/age/comorbidity) added on top of the classic medication-recommendation task, which most MIMIC models ignore.

**Target venues:** IEEE JBHI, JAMIA/JBI, AMIA, or health workshops at KDD/AAAI/NeurIPS.

---

## 10. The one-paragraph summary (your elevator pitch)

> MediGuard is a neuro-symbolic clinical decision-support system that reads a patient's free-text report and structured profile, understands it with clinical NLP, and recommends medication through a knowledge graph — but every suggestion must pass a deterministic rule engine that checks drug–drug interactions, drug–condition contraindications (pregnancy, age, comorbidities), dosing, and duplicate therapy before it is ever shown. A graph neural network flags undocumented interactions as warnings, a constrained GraphRAG layer explains each recommendation using only verified facts, conformal prediction triggers "defer to a clinician" under uncertainty, and every output carries a mandatory consult-your-doctor consent note. It is deliberately safe by construction: the machine understands and suggests, but the rules — and ultimately a human doctor — decide.

---

*This blueprint synthesizes four independent deep-research reports. It is an engineering/academic plan, not medical advice. The system it describes is a research prototype and must not be used for real clinical decisions without qualified clinician oversight and formal validation.*
