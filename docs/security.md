# MediGuard — Security Findings Report

> Execution of `spec/spec_security.md`. Date: 2026-07-08.
> Scope: `mediguard/`, `etl/`, `scripts/`, `ui/`, infra config. Research prototype (not a
> certified device), but ships a public HTTP API + React site + patient-shaped data.

---

## 0. Executive summary

**No Critical or High findings.** The safety invariant (rules/KG are final authority; ML/LLM never
override a BLOCK) holds and is enforced in two independent places (Pydantic schema validator + the
confidence gate). Automated scans found no Python CVEs and no committed secrets. The material issues
are **web-hardening gaps that only bite once the API is publicly hosted** (no auth, wildcard CORS, no
input caps, no rate limit) plus two dependency/config items.

| Severity | Count | Items |
|---|---|---|
| Critical | 0 | — |
| High | 0 | — |
| Medium | 4 | M1 unbounded API input · M2 wildcard CORS · M3 no auth/rate-limit · M4 frontend dep CVEs (esbuild/vite) |
| Low | 4 | L1 Neo4j default password · L2 no security headers · L3 `/drug/{name}` returns 200 on miss · L4 no Python lockfile |
| Info | 4 | I1 safety-asserts stripped under `-O` · I2 audit log integrity · I3 structured-override omission · I4 CI has no security scans |

**Verdict: safe for its stated use (local research demo). Do NOT expose the API publicly without the
M-series fixes.**

---

## 1. Automated scan results

### 1.1 Python dependency CVEs — `pip-audit`
```
No known vulnerabilities found
```
Clean. (`mediguard` itself skipped — not on PyPI, expected.)

### 1.2 Python SAST — `bandit -r mediguard etl scripts`
9 findings, **all Severity: Low**, 0 Medium/High. Total 2487 LOC scanned.
- 5× `B101 assert_used` — `explain/explainer.py:126`, `gnn/base.py:79`, `gnn/predictor.py:74`, plus schema/test asserts.
- 4× `B110 try_except_pass` — optional-backend fallbacks (`gnn/factory.py`, `nlp/factory.py`, `scripts/demo.py`).

The `try/except/pass` are intentional graceful degradation to the always-available backend — accepted.
The asserts feed finding **I1** below (two of them guard the safety invariant).

### 1.3 Frontend dependency CVEs — `npm audit`
2 vulnerabilities (1 moderate, 1 high) — see **M4**.
- `esbuild <=0.24.2` (GHSA-67mh-4wv8-2f99, moderate): dev server lets any site read responses.
- `vite <=6.4.2` (high): depends on the vulnerable esbuild. Transitive.

### 1.4 Secret scan — git tree + full history
No `.env`, key, credential, or `audit_log` file tracked. History grep for `sk-…` / `api_key=…` /
`password=…` patterns: **no hits**. `.env` absent on disk. `data/audit_log.jsonl` exists locally
(1.1 MB) but is correctly gitignored and untracked. Clean.

### 1.5 Injection / dangerous-sink grep
No `eval` / `exec` / `os.system` / `subprocess` / `pickle` / `yaml.load` / `shell=True` /
`verify=False` / `dangerouslySetInnerHTML` / f-string-built Cypher anywhere in app code. The only
`eval` hit is PyTorch `model.eval()` (mode switch, unrelated).

---

## 2. Findings (ranked)

### M1 — Unbounded API input (DoS) · Medium
**Location:** `mediguard/api/app.py:60` (`RecommendRequest`).
**Description:** `text: str` and the list fields (`conditions`, `current_meds`, `allergies`) have no
`max_length` / `max_items`. `age` has no range. A client can POST a multi-megabyte `text` or a
100k-element list, driving NLP regex passes and per-item KG lookups → CPU/memory exhaustion.
**Impact:** Remote unauthenticated DoS once hosted. (`PatientProfile.age` *is* bounded `ge=0,le=130`,
but the API request model that feeds it is not.)
**Repro sketch:** `POST /recommend {"text": "a"*5_000_000, "consent": true}`.
**Fix:** add Pydantic bounds to `RecommendRequest`:
`text: str = Field("", max_length=4000)`, `age: int | None = Field(None, ge=0, le=130)`,
`conditions/current_meds/allergies: … = Field(default_factory=list, max_length=64)`. Consider a body-size
limit at the ASGI/proxy layer.

### M2 — Wildcard CORS · Medium
**Location:** `mediguard/api/app.py:40-45` (`allow_origins=["*"]`, methods/headers `["*"]`).
**Description:** Any origin can call the API from a browser. Acceptable for a keyless local demo; unsafe
if the API is ever hosted with any client-side state or if it fronts a paid LLM backend.
**Impact:** Cross-origin abuse / cost amplification once deployed. The code comment already flags this.
**Fix:** drive allowed origins from an env var (`MEDIGUARD_CORS_ORIGINS`), default to
`http://localhost:5173`. Do not ship `*` to any hosted deployment.

### M3 — No authentication / rate limiting · Medium
**Location:** all endpoints in `mediguard/api/app.py`.
**Description:** Every endpoint is unauthenticated and unthrottled. Fine for `localhost`; a public host
would allow unlimited `/recommend` calls (compute + potential LLM cost) and free data enumeration.
**Impact:** Abuse / resource + cost exhaustion when hosted.
**Fix (deployment-gated):** optional API-key dependency + a rate limiter (e.g. `slowapi`). Document
"local-demo, no-auth-by-design" as the accepted posture until then.

### M4 — Frontend build-tool CVEs (esbuild / vite) · Medium
**Location:** `ui/package.json` (`vite ^5.4.0` → vulnerable `esbuild`).
**Description:** `npm audit` reports GHSA-67mh-4wv8-2f99 (esbuild dev-server response leak) + the
transitive high on vite. **Dev-server only** — does not affect the static production build.
**Impact:** A malicious website could read dev-server responses while `npm run dev` is running.
**Fix:** `cd ui && npm audit fix --force` bumps vite (breaking major — re-verify the site builds/runs),
or pin a patched vite once available. Low urgency since prod uses `vite build` static output.

### L1 — Neo4j default password · Low
**Location:** `mediguard/config.py:28`, `.env.example`, `docker-compose.yml` (`neo4j/mediguard`).
**Description:** Optional Neo4j backend ships a known default password in three places.
**Impact:** Only exploitable if someone runs the Neo4j backend and exposes port 7687 without changing it.
Default backend is embedded (no Neo4j), so most users are unaffected.
**Fix:** in `config.py`, if `MEDIGUARD_KG_BACKEND=neo4j` and password is still `mediguard`, log a loud
warning (or refuse to start in a non-dev mode). Document mandatory override. Bind compose ports to
`127.0.0.1` in the example.

### L2 — No security response headers · Low
**Location:** `mediguard/api/app.py` (no middleware for headers).
**Description:** No `X-Content-Type-Options`, `X-Frame-Options`/CSP, `Referrer-Policy`, HSTS.
**Impact:** Hardening gap; only meaningful once hosted over HTTPS.
**Fix:** add a small middleware setting the standard headers; note TLS is a deployment-layer concern.

### L3 — `/drug/{name}` returns HTTP 200 on not-found · Low
**Location:** `mediguard/api/app.py:173-178` (`return {"error": "not found"}`).
**Description:** Missing drug yields `200 OK` with an error body instead of `404`. No injection (the
name is only used for a KG dict lookup, never a file path or query string — verified), but incorrect
semantics and a minor enumeration-friendliness nit.
**Fix:** `raise HTTPException(status_code=404, detail="drug not found")`.

### L4 — No Python dependency lockfile · Low
**Location:** repo root (only `pyproject.toml`, no lock).
**Description:** Dependencies are floor-pinned (`>=`) with no lockfile → non-reproducible installs and a
supply-chain surface (a compromised/yanked transitive release changes what's installed).
**Impact:** Reproducibility + supply-chain hygiene.
**Fix:** generate and commit a lock (`pip-compile`/`uv lock`) or a `requirements.txt` with hashes for CI.

### I1 — Safety-invariant asserts stripped under `python -O` · Info
**Location:** `mediguard/explain/explainer.py:126` (drops-a-safety-reason guard),
`mediguard/gnn/base.py:79` (status-preserved guard).
**Description:** Two `assert`s that guard the safety invariant are compiled out when Python runs with
`-O`/`PYTHONOPTIMIZE`. The invariant is *also* enforced by the `Recommendation` Pydantic validator
(`schemas/core.py:207`), which is **not** an assert and always runs — so the guarantee survives even
under `-O`. These asserts are defense-in-depth, not the sole guard.
**Fix (optional, recommended for a safety system):** convert the two safety-critical asserts to explicit
`if … raise` so they hold under `-O`. Leave test/scaffolding asserts as-is.

### I2 — Audit log has no integrity protection · Info
**Location:** `mediguard/audit/log.py` (append-only JSONL, plaintext).
**Description:** The "regulatory-defense trail" is a plain append-only file with no tamper-evidence
(hash chain / signature) and default file permissions. Any local writer can edit history silently.
**Impact:** Weakens the audit-trail claim; not exploitable remotely.
**Fix (if the trail is load-bearing):** hash-chain each entry (store `prev_hash`), restrict file perms,
and document that at-rest protection is the deployment's responsibility.

### I3 — Structured overrides can omit a condition · Info
**Location:** `mediguard/api/app.py:105` (`_build_profile`).
**Description:** A client sending structured input controls which conditions/meds are present. Omitting a
condition means its contraindication won't fire. This is **inherent to an advisory tool fed by
self-reported data** — not a bypass of the engine, which correctly evaluates whatever profile it's
given. Documented here so it's an acknowledged limitation, not a silent gap.
**Fix:** none (by design). State it in user-facing docs: "output is only as complete as the input."

### I4 — CI has no security scanning · Info
**Location:** `.github/workflows/ci.yml` (lint + test only).
**Description:** No dependency scan / SAST / secret scan in CI, so the above classes can regress
unnoticed.
**Fix:** add `pip-audit`, `bandit -r mediguard etl scripts`, `npm audit`, and a secret scan
(`gitleaks`) as CI steps. See §4.

---

## 3. Verified-good (checked, no issue)

- **Safety invariant** — enforced twice: `Recommendation._enforce_safety_invariant`
  (`schemas/core.py:207`, always-on validator) blocks a non-abstaining BLOCK; `ConfidenceGate.augment`
  (`gnn/base.py:63`) provably preserves `status` and can only add MINOR advisory reasons. The
  deterministic `SafetyAuthority` takes no ML/LLM input.
- **Cypher injection** — every query in `kg/neo4j_backend.py` and `etl/load_neo4j.py` is parameterized;
  no f-string/format interpolation of user data (grep-confirmed).
- **Path traversal** — user-supplied drug names / condition codes are only used as dict keys and query
  params, never to build filesystem paths. `/conditions` reads a fixed curated path.
- **ReDoS** — NLP regex in `nlp/extractor.py` use bounded quantifiers (`\d{1,3}`, `[a-z\- ]+?` with an
  end-anchored alternation); no nested quantifiers → no catastrophic backtracking.
- **XSS** — React renders all API strings as text / inside `<pre>`; no `dangerouslySetInnerHTML` or
  `innerHTML` anywhere in `ui/src`.
- **External calls** — `requests` uses default TLS verification (no `verify=False`) with timeouts
  (RxNav 10s, Ollama 60s). `RXNAV_BASE_URL` is operator-only env, not user-influenced (no SSRF).
- **LLM prompt-injection** — default `template` explainer is injection-proof by construction (only
  concatenates closed KG facts, with a runtime groundedness check). LLM adapters are opt-in
  (`MEDIGUARD_EXPLAIN_BACKEND=template` default) and receive the same closed fact set.
- **Secrets** — `ANTHROPIC_API_KEY` read from env only, never logged or echoed in responses/audit.
- **Data at rest** — no real patient data path (Synthea synthetic only); audit log untracked & gitignored.

---

## 4. Recommended remediation order

**Do now (cheap, no deployment needed):**
1. **M1** — add Pydantic bounds to `RecommendRequest` (input caps). Highest value: closes the one
   remotely-triggerable DoS.
2. **I1** — convert the two safety-critical asserts to `if … raise` (belt-and-suspenders for a safety
   system, even though the schema validator already covers it).
3. **L3** — `/drug/{name}` → proper 404.
4. **I4** — add `pip-audit` + `bandit` + `npm audit` + secret scan to CI.

**Before any public hosting (deployment-gated):**
5. **M2** — env-driven CORS allowlist (drop `*`).
6. **M3** — API key + rate limit.
7. **L2** — security headers + TLS.
8. **L1** — force Neo4j password override / bind compose ports to localhost.

**Hygiene / when convenient:**
9. **M4** — bump vite/esbuild (re-verify build).
10. **L4** — commit a dependency lockfile.
11. **I2** — hash-chain the audit log if the trail must be tamper-evident.
12. **I3** — document the advisory-input limitation in user docs.

**Accepted risks (documented, no action):** no-auth on the local demo (until hosted), the structured-
input omission (inherent to advisory tools), optional-backend `try/except/pass` fallbacks.

---

## 5. Tooling used

`pip-audit 2.10.1` · `bandit 1.9.4` · `npm audit` · `ruff` (existing) · manual Read/Grep review ·
git tree + history secret grep (gitleaks binary unavailable; substituted equivalent pattern grep).
All free/open-source per project policy.
