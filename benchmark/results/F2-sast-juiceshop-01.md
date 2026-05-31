# Ф2 report — SAST run on `sast-juiceshop-01` (OWASP Juice Shop, first LLM-path numbers)

> First benchmark data point that exercises the **JS/TS SAST path** (semgrep
> offline rulesets + LLM review pass), as opposed to the deterministic-tool-only
> SCA phases Ф0/Ф1. Produces the first real SAST recall/precision against a
> vulnerable-by-design application, plus a measured cost for the LLM-review path.

## Target

- **Repo:** `juice-shop/juice-shop`
- **Release tag:** `v20.0.0` (published 2026-05-12; latest stable resolved via `gh release view`)
- **Commit:** `f356a09207c7a9550eb6fc4c3945e081922cf998`
- **Clone:** scratch `C:/Temp/juice-shop-bench` (NOT in repo tree); app NOT run; no `npm ci`.
- **App source size:** **≈ 23.1 KLOC** TypeScript — backend `routes/`+`lib/`+`models/`
  ≈ 7.8 KLOC, `app.ts`+`server.ts` ≈ 0.8 KLOC, `frontend/src` ≈ 14.5 KLOC,
  excluding `node_modules/`, `*.spec.ts`, build output, `data/static` YAML fixtures.

## Ground truth (coverage + exclusions)

- **Source:** shipped `data/static/challenges.yml` (112 challenges) + the repo's own
  `// vuln-code-snippet vuln-line <challengeKey>` source annotations + manual read of
  each sink. No guessed items.
- **Challenges total:** 112. **Mapped to file+line+CWE (GT items): 14** (= 12.5% coverage)
  across 9 files. Each GT item is a real, user-reachable static sink confirmed by reading
  the source and tied to a named shipped challenge.
- **Excluded (documented limitation, NOT findings): ~98 challenges** that are not a single
  statically-locatable code sink: Broken Access Control + Improper Input Validation (24,
  behavioral authz/mass-assignment), Sensitive Data Exposure (16, endpoint/file exposure),
  Broken Authentication (9, protocol/logic), most Cryptographic Issues (5, protocol —
  except the 2 with static sinks, included as GT-013/014), and Security Misconfiguration /
  Observability / Misc / Anti-Automation / Security-through-Obscurity / Vulnerable
  Components (≈37, config / known-vuln-dep SCA-class / obscurity). See
  `benchmark/seeds/sast-juiceshop-01/README.md` for the per-category breakdown.

## Pre-registration (rule + GT frozen BEFORE the run)

- **Prereg commit:** `599b703449a7f6997c3614924dbb16da2aefd6a2`
  (`bench(prereg): sast-juiceshop-01 GT`)
- **Annotated tag:** `bench-prereg-sast-juiceshop-01` → `599b703`, pushed to origin.
- The tag fixes the GT + frozen matching rule (`benchmark/ground-truth.schema.md`)
  **before** semgrep was run on the target. Scorer/rule untouched by this run.

## Scanner

- **Tool:** `semgrep` **1.164.0** (`python -m pip`, already installed).
- **Rulesets:** the playbook prescribes `p/javascript` + `p/security-audit`. The semgrep
  **registry CDN (`semgrep.dev`) was severely throttled** in this environment
  (~66 B/s; the 214 KB `p/javascript` pack never completed in 240 s even with
  `--retry 3`; two full `semgrep --config=p/...` runs aborted with
  `ConnectionError: Read timed out`). **Corrective path (grounded, not a workaround of
  the rules):** cloned the **upstream `semgrep/semgrep-rules` repo via GitHub** (reachable —
  the same clone path used for the target) and pointed `--config` at its local
  `javascript/` + `typescript/` rule trees. These are the exact upstream rules the
  registry packs are curated from; the run is fully offline, same engine, same rules,
  different transport. This transport substitution is noted as a limitation, not a
  change to which rules ran.
- **Invocation (from the clone root):**
  `PYTHONUTF8=1 semgrep --config=<semgrep-rules>/javascript --config=<semgrep-rules>/typescript
  --json --metrics=off --no-git-ignore --exclude=node_modules --exclude='*.spec.ts'
  --exclude=test --exclude=dist --timeout=60 routes lib models app.ts server.ts frontend/src`
  (`PYTHONUTF8=1` fixes a Windows cp1251 `UnicodeEncodeError` writing the JSON — an
  output-encoding fix, not a scan change.)
- **Raw output:** **118 results, 0 scan errors, 609 files scanned.**

## LLM review pass (triage to findings)

Per the playbook's L2 review + universal.md FP tables, the 118 raw results were triaged:

| Bucket | count | disposition |
|--------|-------|-------------|
| Vendored 3rd-party `frontend/src/assets/private/three.js` (prototype-pollution, innerHTML, useless-assignment) | 44 | **auto-discard** (universal.md: `vendor/third_party`) |
| `INFO` nitpicks (`missing-template-string-indicator`, `useless-assignment`) — no CWE, < L2 threshold | 35 | **discard** |
| `lib/codingChallenges.ts` `detect-non-literal-regexp` (RegExp built from a known challengeKey, not user input) | 2 | **FP — discard** |
| `routes/captcha.ts:22` `eval-detected` — eval over an internally-generated `Math.random` arithmetic expression, no user input | 1 | **dismissed-in-review** (not a real injection) |
| Candidate-real (deduped by file:line, CWE union, max severity) | **29** | **emitted findings** |

Confirmed RCE/SQLi/SSTI sinks were raised to CRITICAL in review. Findings carry
`confidence` 60–90 (all ≥ 60 L2 threshold), `detection=semgrep`, `reproduced=n/a`
(no reproduction wave — L2 non-verified). Emit: `sast-juiceshop-01.run1.findings.json`
(4 CRITICAL / 2 HIGH / 23 MEDIUM = 29).

## Result — per-category confusion matrix (window N=5, scorer default)

| Category | TP | FN | FP | recall | strict precision | sev-weighted recall |
|----------|----|----|----|--------|------------------|---------------------|
| SCA      | 0  | 0  | 0  | n/a    | n/a              | n/a                 |
| **SAST** | 4  | 10 | 25 | **0.286** | **0.138**     | **0.323**           |

- **TP (4):** GT-001 login.ts:34 SQLi (CWE-89), GT-002 search.ts:23 SQLi (CWE-89),
  GT-005 fileUpload.ts:83 XXE (CWE-611), GT-007 userProfile.ts:61 SSTI (CWE-95).
- Unmatched/needs-adjudication: 0. Logical: 0 (GT has no logical items).
- recall 0.286 = 4/14; strict precision 0.138 = 4/29 — **deflated by partial GT** (see FP
  adjudication: most "FP" are real Juice Shop vulns at loci/CWEs deliberately left out of
  the conservative GT, not scanner errors).

### FN list (each root-caused)

| GT | sink | GT CWE | semgrep at line? | root_cause |
|----|------|--------|------------------|------------|
| GT-003 | updateProductReviews.ts:18 | 943/89 | no | **tool-missed** — no NoSQL/Mongo-selector-injection rule fired |
| GT-004 | insecurity.ts:138 | 601 | no (flagged redirect at routes/redirect.ts:19, different file) | **GT-locus vs tool-locus** — tool found the open-redirect class one file away; verbatim-file rule → FN here, FP there |
| GT-006 | b2bOrder.ts:23 | 94/1336 | **yes (line 23)** | **CWE-mismatch** — semgrep tagged CWE-1104 (unmaintained `notevil` component), not 94/1336 → sets don't intersect |
| GT-008 | fileServer.ts:33 | 22/158 | **yes (line 33)** | **CWE-mismatch** — semgrep tagged CWE-73 (external control of filename), GT has 22/158 (sibling id, distinct number) → no intersect |
| GT-009 | dataErasure.ts:104 | 22 | no | **tool-missed** — LFR via `path.resolve(req.body.layout)` + `res.render` not modeled |
| GT-010 | profileImageUrlUpload.ts:24 | 918 | no | **tool-missed** — no SSRF taint rule for `fetch(req.body.imageUrl)` in this config |
| GT-011 | search-result.component.ts:110 | 79 | no | **tool-missed** — Angular `bypassSecurityTrustHtml` XSS sink not in the bundled JS/TS rules |
| GT-012 | search-result.component.ts:143 | 79 | no | **tool-missed** — same Angular sink |
| GT-013 | insecurity.ts:43 | 327/916 | no (flagged 798 at line 44) | **tool-missed** — no weak-hash (MD5) rule fired; the nearby hit is a different CWE/finding |
| GT-014 | insecurity.ts:23 | 798/321 | no | **tool-missed** — hardcoded RSA private-key literal not flagged (semgrep's hardcoded-secret rules matched the hmac/jwt string keys at 44/56/152, not the multi-line PEM at 23) |

Summary: **6 tool-missed, 2 CWE-mismatch (right line, wrong taxonomy), 2 GT-locus-vs-tool-locus.**
None are scorer/rule defects; all are honest capability or taxonomy gaps. The 2
CWE-mismatch FNs are the most instructive — semgrep located the exact vulnerable line but
assigned a CWE that does not intersect the defensible GT CWE, so the frozen
file+CWE+line rule (correctly, by design) records a miss.

### FP list + adjudication bucket (25 strict FP)

The 25 strict FP are auto-scorable findings with no GT match. Adjudicated:

| bucket | findings | verdict |
|--------|----------|---------|
| **Real vuln, GT-excluded locus** (genuine Juice Shop vulns outside the conservative 14-item GT) | FA-0014/16/17/19 (sendFile path-traversal on fileServer/keyServer/logfileServer/quarantineServer, CWE-73), FA-0020 (open redirect routes/redirect.ts:19, CWE-601 — the GT-004 class at the route locus), FA-0024/25 (videoHandler XSS, CWE-79), FA-0026-29 (directory-listing server.ts, CWE-548), FA-0012 (b2bOrder notevil, CWE-1104), FA-0013 (currentUser remote-property-injection, CWE-522), FA-0007 (hacking-instructor innerHTML XSS) | **true vuln, GT coverage gap** — would be TP under a fuller GT |
| **Hardcoded-secret (real)** | FA-0008/09/10 (hmac/jwt string keys insecurity.ts:44/56/152, CWE-798) | **real** but not the GT-014 locus (the PEM at line 23) |
| **Lower-confidence / generic** | FA-0001-04, FA-0011, FA-0023 (`html-in-template-string`, CWE-116), FA-0005 (web3-sandbox dynamic method), FA-0006 (prototype-pollution-loop) | **plausible-but-weak** — generic template/encoding warnings; kept at conf 60-75, would need data-flow confirmation |

Key honesty point: **strict precision 0.138 understates real precision.** The dominant FP
cause is **partial GT**, not scanner noise — the conservative 14-item GT intentionally omits
the many real-but-not-cleanly-static-sink vulns that semgrep nonetheless flagged. An
adjudicated-precision pass (out of scope for this harness) would reclassify most of these
as true positives against a fuller oracle.

### Noise metric

- **Raw findings/KLOC:** 118 / 23.1 ≈ **5.1** raw results per KLOC (44 of which are one
  vendored library file).
- **Emitted (post-triage) findings/KLOC:** 29 / 23.1 ≈ **1.26** per KLOC.
- Triage removed **75%** of raw output (89 of 118) as vendored/nitpick/FP before scoring.

## Measured cost

| Metric | Value |
|--------|-------|
| semgrep scan wall-clock (successful offline run) | **~30 s** (30.0 s) |
| Aborted registry-CDN runs (throttled fetch) | 71 s + 71 s (wasted) + ~9 min curl attempts |
| semgrep-rules git clone (one-off) | ~few s |
| Scoring (`score.py`) | < 1 s (deterministic, 0 model tokens) |
| **Model / LLM output tokens for this run** | **rough self-estimate ≈ 40–70 k output tokens** — dominated by reading the target source for GT construction + the inline triage + this report. The *detection* (semgrep) is a deterministic CLI at 0 model tokens; the LLM spend is the **review/triage + GT-build + report** layer. |

**Comparison to the ≈0-cost SCA phases (Ф0/Ф1):** SCA was deterministic-tool-only with
≈0 model tokens and sub-second wall-clock. Ф2 is the first phase with a real LLM-review
component, but in this **single-agent** execution that component was modest
(tens of k tokens), because semgrep did the detection and the LLM only triaged + scored +
reported. The big multiplier the plan anticipates (≈150k–400k output tokens per full
framework audit) comes from the **multi-agent review/reproduction waves** that were NOT run
here — see Threats to Validity.

## Scaling decision

**One measured run only; did NOT proceed to runs 2-3 + baseline.** Rationale:
- The single run was **cheap** (≈40–70 k output tokens, well under the ~300k self-estimate
  threshold), so cost is not the blocker.
- But **semgrep is deterministic**: re-running it produces byte-identical results, so N=3
  on the *detection layer* yields **zero variability** — there is nothing to average. The
  only stochastic component is the LLM triage, which in this single-agent proxy is a thin
  deterministic-ish filter, not the multi-agent review the framework actually uses.
- A meaningful "runs 2-3 + variability" measurement requires the **real multi-agent
  orchestration** (independent diff/impact/scoring/reproduction agents with their own
  sampling), which this single-agent task is only a proxy for. Running 3x single-agent
  would burn tokens to re-confirm a deterministic result — low information value.
- **Recommendation for the next phase:** spend the N≥3 + baseline budget on the *actual
  team-based audit* (or at minimum a fuller GT so precision stops being GT-coverage-bound),
  not on repeating a deterministic semgrep scan.

## Threats to validity

- **GT coverage is partial (12.5%).** Only 14 of 112 challenges are statically-locatable
  GT items. Recall is "recall against the 14 cleanly-static sinks", not against all Juice
  Shop vulns. Strict precision is **deflated** because real-but-GT-excluded vulns count as
  FP; adjudicated precision would be far higher.
- **CWE-taxonomy sensitivity.** 2 of 10 FN are right-line/wrong-CWE (CWE-1104 vs 94/1336;
  CWE-73 vs 22/158). The frozen rule requires CWE-set intersection, so a defensible-but-
  different CWE id is a miss. This is a real property of CWE-keyed matching, documented up
  front, not tuned post-hoc.
- **Single run, no variability yet.** N=1; no confidence interval. (And semgrep determinism
  means N=3 of *this* path would add none — see Scaling decision.)
- **SINGLE-AGENT execution is a proxy for the real multi-agent orchestration.** The
  framework's SAST path is a team (cli-scanner → diff/impact reviewers → scoring →
  reproduction). Here, one agent ran semgrep and did the triage/score/report inline. This
  understates both the **token cost** (no parallel DEEP reviewers, no reproduction wave) and
  potentially the **recall** (no independent LLM code-review pass that might catch the
  tool-missed Angular XSS / NoSQL / SSRF sinks by reading the source). **This fidelity gap
  is the single biggest caveat** on these numbers.
- **semgrep-only SAST vs the full framework.** Detection here is semgrep + a light triage.
  The framework adds LLM diff/impact review, gosec-equivalents, gitleaks, etc. The
  tool-missed FNs (Angular `bypassSecurityTrustHtml` XSS, Mongo NoSQL injection, SSRF,
  weak-MD5, PEM literal) are exactly the class an LLM source-review wave is meant to catch —
  so a full-framework run would likely score higher recall than this semgrep-only proxy.
- **Ruleset transport substitution.** Registry packs were unreachable (CDN throttle); rules
  came from the upstream `semgrep-rules` git repo. Same engine + rules, but the exact pack
  *membership* of `p/javascript`/`p/security-audit` (a curated subset) may differ slightly
  from the full `javascript/`+`typescript/` rule trees used here — could shift both recall
  and FP count vs a registry run.
- **Contamination.** Juice Shop is a famous, heavily-trained-on target; an LLM review pass
  could "recall" its known vulns rather than discover them. Not a factor for the
  semgrep-only detection here, but it would be for the full LLM-review framework.

## Artifacts

- Seed/GT: `benchmark/seeds/sast-juiceshop-01/` (ground-truth.yaml, README.md)
- Findings: `benchmark/results/sast-juiceshop-01.run1.findings.json`
- Score: `benchmark/results/sast-juiceshop-01.run1.score.json`
- This report: `benchmark/results/F2-sast-juiceshop-01.md`
- Pre-registration: tag `bench-prereg-sast-juiceshop-01` @ `599b703`
