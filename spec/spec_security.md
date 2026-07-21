# MediGuard — Security Check Specification & Implementation Plan

> **Status:** Specification only. **Do not execute yet.** This document defines *what* to audit,
> *how*, and *in what order*. Execution happens in a later, separate pass once this spec is approved.
>
> Scope: the MediGuard neuro-symbolic CDSS (`mediguard/`, `etl/`, `scripts/`, `ui/`, infra config).
> Context: M.Tech research prototype, **not** a certified medical device — but it handles
> patient-shaped data and ships a public HTTP API + React site, so it carries real attack surface.

---

## 1. Objectives

1. Find and rank every security weakness in the project across code, config, dependencies, data,
   and infrastructure.
2. Preserve the project's **safety invariant** (rules/KG are the final authority; ML/LLM never
   override a `BLOCK`). Any security control must not weaken this invariant.
3. Produce an actionable, prioritized remediation list — severity-tagged, with concrete fixes.
4. Establish repeatable checks (CI dependency + secret scanning) so regressions get caught.

**Non-goals:** penetration testing of a hosted deployment (none exists yet), formal medical-device
compliance (HIPAA/GDPR/CE), and load/DoS resilience testing beyond basic input-limit hardening.

---

## 2. Threat model

**Assets**
- Patient profile data (age, sex, pregnancy, conditions, meds, allergies, vitals) — PII-shaped even
  though currently synthetic (Synthea).
- The safety decision itself — a corrupted verdict is a *patient-harm* vector, the highest-value asset.
- Audit log (`data/audit_log.jsonl`) — regulatory-defense trail; integrity and confidentiality matter.
- Credentials: Neo4j auth, `ANTHROPIC_API_KEY` (optional), any future deployment secrets.

**Actors / entry points**
- Unauthenticated HTTP clients hitting the FastAPI service (`/recommend`, `/recommend/fhir`, `/drugs`,
  `/drug/{name}`, `/conditions`, `/health`).
- Free-text patient input → NLP extractor (untrusted string parsing).
- External services: RxNav (`etl/normalize_rxnorm.py`), optional Claude/Ollama explanation backends.
- The React UI (rendering API responses in the browser).
- Supply chain: Python deps (`pyproject.toml`) and npm deps (`ui/package.json`).

**Trust boundaries**
- Browser ⇄ FastAPI (currently `allow_origins=["*"]`, no auth).
- FastAPI ⇄ Neo4j (optional; default creds `neo4j/mediguard`).
- FastAPI/ETL ⇄ RxNav & LLM providers (outbound, over network).

**Out of scope for this pass:** physical security, insider threat, and the deferred India/MIMIC layers
(not built).

---

## 3. Scope inventory (what gets audited)

| Area | Paths | Why it matters |
|---|---|---|
| HTTP API | `mediguard/api/app.py`, `mediguard/api/fhir.py` | Public entry point, no auth today |
| Safety core | `mediguard/safety/`, `mediguard/schemas/`, `mediguard/pipeline.py` | Verdict integrity = patient safety |
| NLP input handling | `mediguard/nlp/*` | Untrusted free-text parsing |
| KG backends | `mediguard/kg/*`, `etl/load_neo4j.py` | Cypher injection, default creds |
| External calls | `etl/normalize_rxnorm.py`, `mediguard/explain/explainer.py` | SSRF, TLS, secret handling, prompt injection |
| Audit / PII | `mediguard/audit/log.py`, `data/audit_log.jsonl` | PII at rest, log integrity |
| Config / secrets | `mediguard/config.py`, `.env.example`, `.gitignore` | Secret leakage, insecure defaults |
| Frontend | `ui/src/**`, `ui/package.json` | XSS, dependency risk |
| Infra / CI | `docker-compose.yml`, `.github/workflows/ci.yml` | Hardening, scanning gaps |
| Dependencies | `pyproject.toml`, `ui/package-lock.json` | Known CVEs, supply chain |

---

## 4. Checklist by category

### 4.1 API & transport
- [ ] CORS: `allow_origins=["*"]` + `allow_methods/headers=["*"]` — over-permissive; scope to known origins.
- [ ] No authentication / authorization on any endpoint — decide required posture (API key / token / none-by-design for local demo, documented).
- [ ] No rate limiting → abuse / cost amplification (LLM backend) / DoS.
- [ ] No request-size / field-length caps on `text` and list fields (`conditions`, `current_meds`, `allergies`) → memory/CPU DoS via huge payloads.
- [ ] `/drug/{name}` returns `{"error": "not found"}` with HTTP 200 — should be 404; check for reflected-input error leaks.
- [ ] Error handling: confirm stack traces / internal paths are not returned to clients (FastAPI debug off in prod).
- [ ] Security headers absent (HSTS, X-Content-Type-Options, etc.) — note for any hosted deployment.
- [ ] No HTTPS/TLS termination configured — flag for deployment.

### 4.2 Input validation & injection
- [ ] Pydantic bounds: add validators (`age` range, string `max_length`, list `max_items`, `sex` enum).
- [ ] `_guess_system(code)` and condition/med codes flow into KG lookups — verify no injection into Neo4j or file reads.
- [ ] Cypher queries in `neo4j_backend.py` / `load_neo4j.py`: confirm **all** use parameterized queries (they appear to — verify no f-string interpolation of user data into Cypher).
- [ ] Path handling in `/conditions` reads `data/curated/conditions.json` via fixed path — confirm no user-controlled path traversal anywhere (drug names, condition codes never used to build file paths).
- [ ] NLP extractor: adversarial / pathological free-text (very long, unicode, regex-catastrophic) → ReDoS check on any regex in `nlp/`.

### 4.3 Secrets & configuration
- [ ] Neo4j default password `mediguard` hardcoded in `config.py`, `.env.example`, `docker-compose.yml` — insecure default; require override, never ship a real deployment with it.
- [ ] `ANTHROPIC_API_KEY` read from env in `explainer.py` — confirm never logged, never echoed in responses/audit.
- [ ] `.gitignore` covers `.env` and `data/audit_log.jsonl` — verify no secrets or PII already committed (git history scan).
- [ ] `load_dotenv()` swallows all exceptions — confirm it can't mask a misconfig that weakens security.

### 4.4 External service calls (SSRF / TLS / prompt injection)
- [ ] `RXNAV_BASE_URL` is env-configurable and used to build request URLs — if ever user-influenced, SSRF risk; confirm it's operator-only.
- [ ] `requests.get`/`post` calls: verify TLS verification is on (default), timeouts set (RxNav=10s ✓, Ollama=60s ✓), and responses are size-bounded / schema-validated before use.
- [ ] LLM explainers receive patient free-text indirectly via the closed fact set — assess **prompt-injection** risk: could crafted patient text alter the explanation to fabricate a safe verdict? Confirm the template explainer (default) is injection-proof by construction and LLM adapters keep facts closed.
- [ ] Confirm LLM/Ollama backends are opt-in and off by default (`MEDIGUARD_EXPLAIN_BACKEND=template`).

### 4.5 Data protection & audit integrity
- [ ] `data/audit_log.jsonl` stores condition/drug/verdict per patient; `patient_ref` defaults `"anonymous"` — verify no direct identifiers are written; assess whether even indirect data needs at-rest protection.
- [ ] Audit log is append-only by convention but file is world-writable on disk — no integrity protection (hash chain / signing) — note for regulatory-trail claim.
- [ ] Synthetic-only guarantee: confirm no real patient data path exists; document the boundary.
- [ ] File permissions on `data/` written by the app (`mkdir(parents=True)`) — check default perms.

### 4.6 Frontend (XSS / client)
- [ ] Confirm no `dangerouslySetInnerHTML` (initial read: none — API strings rendered as text/`<pre>`, which is safe). Verify across all `ui/src/**`.
- [ ] Rationale/reason strings from API rendered in `<pre>`/text nodes — confirm React auto-escaping holds everywhere; no `innerHTML`.
- [ ] API base is same-origin `/api` proxy — confirm Vite proxy config and that prod build doesn't hardcode an insecure origin.

### 4.7 Dependencies & supply chain
- [ ] Python: run `pip-audit` (or `safety`) against installed env / `pyproject.toml` for known CVEs.
- [ ] npm: run `npm audit` against `ui/package-lock.json`.
- [ ] Pin / review transitive deps; check `uvicorn[standard]`, `fastapi`, `requests`, `pydantic`, React, Vite, react-router versions for advisories.
- [ ] Verify lockfile presence & integrity (npm lock present ✓; Python has no lock — note reproducibility/supply-chain gap).

### 4.8 Infrastructure & CI
- [ ] `docker-compose.yml`: Neo4j exposes `7474`/`7687` with default creds and `apoc.*` unrestricted procedures — hardening / bind-to-localhost note.
- [ ] `.github/workflows/ci.yml`: no dependency scan, no secret scan, no SAST — add.
- [ ] CI runs on `pull_request` from forks — confirm no secrets exposed to untrusted PRs (none used today ✓, keep it that way).

### 4.9 Safety-invariant integrity (project-specific, highest priority)
- [ ] Confirm no code path lets NLP/GNN/LLM output mutate or bypass a `BLOCK`/`DOWNGRADE` verdict (re-verify the guarantee under adversarial input).
- [ ] Confirm structured overrides in `_build_profile` (client-supplied `conditions`/`meds`) can't be used to *hide* a contraindication (e.g., omit a condition to dodge a block) — this is expected (advisory tool) but must be documented as a known limitation, not a silent bypass.
- [ ] Confirm the consent gate and disclaimer are non-removable from every user-facing path.

---

## 5. Tooling

| Purpose | Tool | Command (for the execution pass) |
|---|---|---|
| Python CVEs | `pip-audit` | `pip-audit -r <(pip freeze)` or `pip-audit` in venv |
| Python SAST | `bandit` | `bandit -r mediguard etl scripts` |
| Secret scan (tree + history) | `gitleaks` / `trufflehog` | `gitleaks detect --source .` |
| npm CVEs | `npm audit` | `cd ui && npm audit` |
| Lint (already present) | `ruff` | `ruff check .` |
| Manual review | Read/Grep | targeted per §4 checklist |

> All tools are free/open-source, consistent with the project's "everything free to use" decision.
> `bandit`, `pip-audit`, `gitleaks` are **not** yet in the project — installing them is part of Phase 1 below.

---

## 6. Implementation plan (phased, do-not-execute-yet)

### Phase 0 — Prep (no findings yet)
1. Approve this spec.
2. Add security tooling as an optional dev extra in `pyproject.toml` (`bandit`, `pip-audit`); note `gitleaks` as an external binary.
3. Create `docs/security.md` (or `spec/findings_security.md`) as the report destination.

### Phase 1 — Automated scans (fast, high signal)
1. `pip-audit` — Python dependency CVEs.
2. `npm audit` — frontend dependency CVEs.
3. `bandit -r mediguard etl scripts` — Python SAST.
4. `gitleaks detect` — secrets in tree **and** git history.
5. Record raw output; triage false positives.

### Phase 2 — Manual code review (per §4)
1. API surface (§4.1, §4.2) — CORS, auth, input caps, error leaks.
2. Injection review (§4.2) — Cypher parameterization, path traversal, ReDoS in NLP regex.
3. Secrets & config (§4.3) — default creds, key handling, dotenv failure mode.
4. External calls (§4.4) — TLS, timeouts, SSRF, LLM prompt-injection.
5. Data/audit (§4.5) — PII at rest, log integrity, file perms.
6. Frontend (§4.6) — XSS sweep across `ui/src`.
7. **Safety invariant (§4.9)** — adversarial re-verification that ML/LLM can't override a BLOCK.

### Phase 3 — Triage & report
1. Assign severity (Critical / High / Medium / Low / Info) using a lightweight CVSS-style rubric.
2. Write findings to the report doc: each finding = *location, description, impact, PoC/repro sketch, fix, severity*.
3. Rank by (patient-harm potential) × (exploitability). Safety-invariant issues rank above generic web issues.

### Phase 4 — Remediation (separate, gated on approval)
1. Quick wins: input caps + Pydantic validators, CORS tighten, `/drug/{name}` → 404, security headers helper, force Neo4j password override.
2. CI hardening: add `pip-audit` + `bandit` + `gitleaks` steps to `.github/workflows/ci.yml`.
3. Documented decisions for accepted risks (e.g., "no auth: local demo only" / "structured-override omission is an accepted advisory-tool limitation").
4. Re-run Phase 1 scans to confirm clean; add regression tests where feasible.

---

## 7. Severity rubric

| Severity | Criteria (this project) |
|---|---|
| **Critical** | Can produce an unsafe medication verdict, bypass a BLOCK, or leak/execute via the safety path. |
| **High** | Remote unauth data exposure, RCE, secret disclosure, injection with real impact. |
| **Medium** | DoS via unbounded input, over-permissive CORS with a real deployment, dependency CVE reachable in our usage. |
| **Low** | Insecure defaults requiring local access, missing hardening headers on a not-yet-hosted service. |
| **Info** | Best-practice gaps, hygiene, documentation of accepted risks. |

---

## 8. Deliverables

1. This spec (`spec/spec_security.md`). ✅ (created)
2. Findings report (`docs/security.md` or `spec/findings_security.md`) — produced in the execution pass.
3. Remediation PR(s) — separate, gated.
4. Hardened CI with dependency + secret + SAST scanning.

---

## 9. Known context (from initial read — to verify in execution, not conclusions)

Fast pre-read observations to confirm during Phase 2 (**not** yet findings):
- CORS wildcard in `api/app.py:42` (comment already flags "tighten for any real deployment").
- Neo4j default password `mediguard` in three places (`config.py`, `.env.example`, `docker-compose.yml`).
- No auth / rate limit / input-size caps on the API.
- Cypher queries appear fully parameterized (good) — verify exhaustively.
- React renders API strings as text/`<pre>` with no `dangerouslySetInnerHTML` (good) — verify exhaustively.
- `.gitignore` excludes `.env` and `data/audit_log.jsonl` (good) — verify nothing sensitive already committed via history scan.
- No Python dependency lockfile — reproducibility/supply-chain note.
- CI has no security scanning stage.
