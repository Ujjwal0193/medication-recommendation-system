# Data Provenance & Licensing

Every dataset MediGuard uses, its source, license, and caveats. **All sources are
free to use.** The prototype ships with a hand-curated, verifiable dataset rather
than bulk-importing any single licensed database.

## What ships in the repo

`data/curated/*.json` — a hand-authored, cross-checked dataset for ~40 common
outpatient drugs across diabetes, hypertension, pain/fever, and common infections.
The clinical facts (doses, pregnancy categories, interactions, contraindications)
were compiled from standard, publicly available pharmacology references and are
**verified, not scraped**. Drug identity (RxCUI) is checked against the free NLM
RxNav API (`etl/normalize_rxnorm.py`).

| File | Contents |
|---|---|
| `drugs.json` | ~40 drugs: purpose, pros, cons, side effects, salt, dose, timing, route, quantity, pregnancy category, renal caution |
| `conditions.json` | Conditions/symptoms with SNOMED CT / ICD-10 codes + free-text aliases |
| `treats.json` | Condition → candidate drug edges with clinical preference rank |
| `interactions.json` | Drug–drug interactions with severity, mechanism, management |
| `contraindications.json` | Drug–condition contraindications (pregnancy X = hard block) |
| `drug_classes.json` | Therapeutic-class membership for duplicate-therapy detection |

## Free external sources (used / referenced)

| Source | Role | Access | License / caveat |
|---|---|---|---|
| **RxNorm / RxNav API** (NLM) | Drug/salt name → RxCUI normalization | Free public API, no key (`etl/normalize_rxnorm.py`) | US Government work; free. Verified live during Phase 1. |
| **DailyMed** (NLM) | Drug label facts (dosing, contraindications, pregnancy) | Free download/API | Public domain. Used as a reference for curated facts. |
| **openFDA / FAERS** | Adverse-event / pharmacovigilance signals | Free API, no key | Public. For future ADR enrichment. |
| **DDInter 2.0** | Drug–drug interaction records + management text | Free download | Open, license-friendly. Recommended validation source for `interactions.json`. |
| **SIDER** | Drug → side-effect pairs | Free download | Free for research. For future side-effect enrichment. |
| **SNOMED CT / ICD-10** | Condition coding | Codes used illustratively | SNOMED needs a (free) UMLS license for bulk use; we use individual codes only. |
| **Synthea** | Synthetic patient generation (Phase 7 eval) | Free, open-source | No credentialing needed. Chosen over MIMIC-IV per project decision. |

## Deliberately excluded (licensing / cost)

- **DrugBank full DDI/severity + MedDRA** — require paid/registered licenses. Not used.
- **MIMIC-IV** — restricted (credentialing + CITI + DUA). **Deferred** by project
  decision; Synthea synthetic patients are used instead.
- **India Jan Aushadhi / PMBJP layer** — **deferred** by project decision (future work).
- **Scraped Kaggle Indian medicine datasets** — non-authoritative snapshots; excluded.

## Caveats (state these in the thesis)

1. The curated set is **small (~40 drugs)** and scoped to common outpatient use.
   Extensibility to thousands is future work.
2. Clinical facts are compiled from public references for a **research prototype**
   and are **not a substitute for an authoritative drug database**. Before any real
   use, validate `interactions.json` against **DDInter** and labels against **DailyMed**.
3. Pregnancy categories use the **legacy US-FDA A/B/C/D/X** scheme for clarity;
   the current FDA labeling rule (PLLR) is narrative. X = absolute contraindication.
4. RxCUIs are verified against RxNav but the mapping can drift as RxNorm updates;
   re-run `etl/normalize_rxnorm.py` before a demo.
5. One KG-medication paper (**KGDNet, 2024**) was retracted — cite **SafeDrug /
   GAMENet / G-BERT / MoleRec** instead.

## Regenerating / verifying

```bash
python etl/normalize_rxnorm.py          # verify RxCUIs against free RxNav API
python etl/normalize_rxnorm.py --write  # refresh any drifted RxCUIs
# Optional Neo4j backend:
docker compose up -d && python etl/load_neo4j.py
```
