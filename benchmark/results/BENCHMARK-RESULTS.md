# full-audit benchmark — recall & precision results (Ф5 synthesis)

> Single publishable artifact collating phases Ф0–Ф2 of the full-audit recall/precision
> benchmark. Every number here is quoted verbatim from a committed phase report; nothing
> is recomputed or invented in this document. Sources: `BENCHMARK-PLAN.md`,
> `benchmark/ground-truth.schema.md`, `benchmark/results/F0-sca-python-01.md`,
> `benchmark/results/F1-sca-go-01.md`, `benchmark/results/F2-sast-juiceshop-01.md`,
> `benchmark/results/F2-adjudication.md`, `benchmark/results/F2-baseline-delta.md`.
> Audit pinned to tag `v1.10.4`; emitter schema v1.1 (`868156a`, shipped v1.10.5).

## 1. Executive summary

The benchmark measures two things a third party can check: **recall** (of known bugs, how
many the audit found) and **precision** (of what it emitted, how much is real). Categories
(SCA / SAST / logical) are scored **separately and never aggregated**. Three phases ran,
each against a ground truth (GT) + matching rule **git-tagged before the run**.

### Headline table (per category, never blended)

| Phase | Target | Scanner | Category | Recall | Strict precision | Adjudicated precision | Sev-weighted recall |
|-------|--------|---------|----------|--------|------------------|-----------------------|---------------------|
| Ф0 | `sca-python-01` (6 PyPI pkgs, 38 CVEs) | pip-audit 2.10.0 | SCA | **1.000** (38/38) | **1.000** (38/38) | n/a | **1.000** |
| Ф1 | `sca-go-01` (3 Go modules, 5 CVEs) | govulncheck v1.3.0 | SCA | **0.600** (3/5) | **1.000** (3/3) | n/a | **0.583** |
| Ф2 | OWASP Juice Shop `v20.0.0` (~23.1 KLOC) | semgrep 1.164.0 + LLM triage | SAST | **0.286** (4/14) | **0.138** (4/29) | **0.857** (24/28) | **0.323** |

### The one honest sentence

These numbers establish that the **pipeline works end-to-end** (SCA + SAST: scan → schema
→ frozen matching rule → score), that the **scorer discriminates real misses** (Ф1's 0.600,
Ф2's tool-missed FNs), and that the **triage layer adds precision** (Ф2 baseline-delta) —
they do **NOT** yet establish the **real multi-agent framework's capability** (Ф2 ran a
single-agent semgrep-only proxy: its 0.286 recall is a tool-only **floor**, not the
framework's number), nor broad multi-stack coverage, nor statistical significance (N=1 run
per phase), nor human-validated adjudication (the adjudicator is a model).

## 2. Methodology

- **Pre-registration (artifact, not promise).** For each phase the GT YAML + the frozen
  matching rule (`benchmark/ground-truth.schema.md`) were committed and **annotated-tagged
  before the scanner was ever run**, so the rule cannot have been tuned to flatter results:
  - `bench-prereg-sca-python-01` → `c802dedf6981cbaa01c3bdef0728e81a344a318b` (Ф0)
  - `bench-prereg-sca-go-01` → `4b1cbcb75397062997d1b631414aa0b821cf8945` (Ф1)
  - `bench-prereg-sast-juiceshop-01` → `599b703449a7f6997c3614924dbb16da2aefd6a2` (Ф2)
  - In every phase the scorer (`score.py`) and the schema doc were untouched by the run.
- **Frozen matching rule** (verbatim from the schema, §2; CWE/CVE ids canonicalized on both
  sides before set-intersection):
  - **SCA** — match iff `norm(set(finding.cve)) ∩ norm(set(gt.cve)) ≠ ∅`. File/line ignored
    (dependency-level).
  - **SAST** — match iff `finding.file == gt.file` (verbatim) **AND** CWE id sets intersect
    **AND** the finding's line span overlaps the GT span widened by window `N` (**default 5**).
  - **logical** — **excluded from automated matching**; manual/independent adjudication only
    (logical findings lack CWE/line precision; auto-matching would under-count or invite
    rule-tuning).
- **Outcome buckets** (schema §2): **TP** = matched GT↔finding; **FN** = GT item (sca/sast)
  with no match; **strict FP** = auto-scorable finding (carries a cwe/cve) matching no GT;
  **needs-adjudication** = finding with no cwe/cve and no match (NOT counted as FP); no TN
  (undefinable in open audit) → recall/precision only.
- **Metrics** (schema §3): `recall = TP/(TP+FN)`; `strict precision = TP/(TP+FP)`;
  `sev-weighted recall = Σweight(TP)/Σweight(TP∪FN)` using the CVSS↔band crosswalk
  (CRITICAL 10 / HIGH 7 / MEDIUM 4 / LOW 1; `weight = cvss if present else band_weight`).
- **Independent-model adjudication.** Unmatched SAST findings were adjudicated by **Claude
  Sonnet 4.6** — deliberately a **different model than the Opus auditor** that produced the
  findings — into three buckets: *real-but-unlabelled / true-FP / disputed*. Adjudicated
  precision folds the real-but-unlabelled findings back in; disputed are excluded from the
  denominator. (This closes the fox-guarding-henhouse hole; disclosed as a model, not a
  human, in Threats to Validity.)
- **Baseline definition** (locked, plan §Decisions): same pinned tool versions at default
  config, deduplicated union, **no LLM** — isolates the framework delta = LLM triage + scoring
  + FP-cut + dedup. For Ф2 the baseline = **raw semgrep, no triage, all 118 results as
  findings**.

## 3. Per-phase results

### Ф0 — SCA pipeline on `sca-python-01` (pipeline + coverage check)

- **Target:** controlled seed pinning 6 old PyPI packages (Jinja2 2.10, PyYAML 5.1,
  requests 2.19.1, urllib3 1.24, Flask 0.12.2, cryptography 2.3); **N=38** distinct
  `(package, CVE)` GT items from osv.dev. Scanner: pip-audit 2.10.0.
- **Confusion matrix (SCA, window N=5):**

  | Category | TP | FN | FP | recall | strict precision | sev-weighted recall |
  |----------|----|----|----|--------|------------------|---------------------|
  | SCA | 38 | 0 | 0 | **1.000** | **1.000** | **1.000** |

- **Interpretation (cited from Ф0):** `GT \ pip-audit = ∅` (no FN); the one extra id
  `CVE-2025-50460` is an **alias** of the GT CVE-2020-1747 on a single advisory row → folded
  in → **0 FP**. The two CVE-less cryptography GHSA advisories are documented *non-FN by
  design* (the CVE-only rule cannot express them; pip-audit also reported them). The result
  is a **pipeline + coverage check, NOT an independent capability measure** — GT (osv.dev)
  and pip-audit's DB share OSV/PyPA lineage (see Threats §SCA circularity).
- **Cost:** ~1.3 s scanner wall-clock; **≈ 0 model tokens** (deterministic CLI).

### Ф1 — SCA on `sca-go-01` (Go / govulncheck lineage-break)

- **Target:** buildable Go module pinning 3 modules (jwt-go v3.2.0+incompatible, gogo/protobuf
  v1.3.1, golang.org/x/text v0.3.0); **N=5** osv.dev CVEs (the **full** present set regardless
  of reachability). Scanner: govulncheck v1.3.0, which applies **reachability analysis**.
- **Confusion matrix (SCA, window N=5):**

  | Category | TP | FN | FP | recall | strict precision | sev-weighted recall |
  |----------|----|----|----|--------|------------------|---------------------|
  | SCA | 3 | 2 | 0 | **0.600** | **1.000** | **0.583** |

- **Interpretation (cited from Ф1):** the seed deliberately splits vulnerable symbols into
  reachable vs unreachable call paths. The 2 FN (CVE-2020-14040 x/text unicode/transform;
  CVE-2021-3121 gogo/protobuf plugin/unmarshal) are **honest, non-contrived** — present and
  vulnerable per osv.dev, but unreachable so govulncheck (by design) does not flag them.
  `recall = 0.600 (< 1.0) by design` — the instrument is **not pinned at 1.0**; the scorer
  registers a real coverage gap. sev-weighted recall 0.583 = `22.5/38.6` (slightly below raw
  recall because the heaviest miss is CVSS 8.6). Strict precision 1.000 — no third-party FP.
  ~150 Go stdlib/toolchain advisories are out-of-scope (track the local toolchain, not the
  seed's deps) → no phantom FP.
- **Cost:** ~1.1 s scanner wall-clock; **≈ 0 model tokens** (deterministic CLI).

### Ф2 — SAST on OWASP Juice Shop `v20.0.0` (first LLM-path numbers)

- **Target:** `juice-shop/juice-shop` `v20.0.0`, commit `f356a09207c7a9550eb6fc4c3945e081922cf998`,
  ~23.1 KLOC TS. GT = **14 statically-locatable sinks (12.5% of 112 challenges)** across 9
  files; ~98 non-static-sink challenges documented as excluded. Scanner: semgrep 1.164.0
  (upstream `semgrep-rules` git trees) + an LLM triage pass that cut 118 raw → 29 emitted
  findings.
- **Confusion matrix (SAST, window N=5):**

  | Category | TP | FN | FP | recall | strict precision | sev-weighted recall |
  |----------|----|----|----|--------|------------------|---------------------|
  | SAST | 4 | 10 | 25 | **0.286** | **0.138** | **0.323** |

- **TP (4):** GT-001 login.ts:34 SQLi (CWE-89), GT-002 search.ts:23 SQLi (CWE-89),
  GT-005 fileUpload.ts:83 XXE (CWE-611), GT-007 userProfile.ts:61 SSTI (CWE-95).
- **FN breakdown (10, cited from Ф2):** 6 tool-missed (NoSQL/Mongo, LFR, SSRF, two Angular
  `bypassSecurityTrustHtml` XSS, weak-MD5), 2 CWE-mismatch (right line, wrong taxonomy:
  CWE-1104 vs 94/1336; CWE-73 vs 22/158), 2 GT-locus-vs-tool-locus. None are scorer/rule
  defects — honest capability or taxonomy gaps.
- **Adjudication (independent, Sonnet 4.6 — cited from F2-adjudication):** the 25 strict FP
  resolve to **20 real-but-unlabelled / 4 true-FP / 1 disputed**. Only **4 are actual semgrep
  false positives** (operator-config data, ABI-derived field names, guarded bracket access,
  guarded challenge-check). The 20 real-but-unlabelled are genuine Juice Shop vulns at
  loci/CWEs the conservative 14-item GT deliberately excluded.

  | metric | value |
  |--------|-------|
  | Strict precision | 0.138 (4/29) |
  | Adjudicated precision (disputed excluded) | **0.857 (24/28)** |
  | Adjudicated precision (disputed as FP, conservative) | 0.828 (24/29) |
  | Recall (unchanged) | 0.286 (4/14) |
  | Sev-weighted recall (unchanged) | 0.323 |

  Honest driver: the **0.138 → 0.857 lift is GT-coverage gap, not scanner accuracy** — strict
  precision understates real precision because real-but-GT-excluded vulns count as FP.
- **Cost:** ~30 s semgrep wall-clock; **≈ 40–70 k output tokens** (self-estimate), dominated by
  GT-build source reading + inline triage + report — *not* detection (semgrep = 0 model tokens).

## 4. The framework − baseline delta (Ф2)

Baseline = raw semgrep, no triage, all 118 results as findings (59 auto-scorable with CWE,
59 CWE-less routed to adjudication, not FP). Framework-proxy = run1 (29 emitted).

| metric | baseline (raw, 118) | framework-proxy run1 (29) | delta |
|--------|---------------------|---------------------------|-------|
| TP | 4 | 4 | **0** |
| FN | 10 | 10 | **0** |
| FP (auto-scorable) | 55 | 25 | **−30** |
| recall | 0.286 | 0.286 | **+0.000** |
| strict precision | 0.068 | 0.138 | **+0.070 (+103%)** |
| sev-weighted recall | 0.323 | 0.323 | **+0.000** |
| total findings (noise) | 118 | 29 | **−89 (−75%)** |
| findings/KLOC | 5.11 | 1.26 | **−3.85** |

- **Result:** triage roughly **doubled strict precision (+103% relative)** and cut **noise
  −75%** with **zero recall loss** (all 4 TP retained; 89 of 118 raw results dropped as
  vendored/nitpick/FP).
- **Honest caveat (cited from F2-baseline-delta):** this measures the **triage layer of a
  SINGLE-AGENT PROXY**, *not* the full multi-agent orchestration (independent diff/impact/
  scoring/reproduction waves were not exercised). The recall ceiling is a **tool limit, not a
  triage limit** — triage cannot recover what semgrep never emitted. A full-framework run
  could push recall higher (the tool-missed Angular XSS / SSRF / NoSQL FNs are exactly what an
  LLM source-review wave targets), but this run does not demonstrate that.

## 5. Threats to Validity (the credibility core)

- **SCA circularity (Ф0).** GT is built from osv.dev and pip-audit's DB is sourced from the
  **same OSV/PyPA advisory ecosystem** — shared lineage. The 1.000/1.000 is a
  **pipeline + coverage check, not an independent capability measure**. An independent oracle
  (NVD-only, or a different-DB scanner) would be needed for a capability claim.
- **SCA lineage only partially broken (Ф1).** govulncheck's `vuln.go.dev` and osv.dev still
  share advisory identity upstream; what differs is the **reachability filter** govulncheck
  adds on top, which is what produces the honest FN. So Ф1 is a **reachability** independence
  (a weak capability signal), not a fully independent oracle. A raw-listing scanner
  (osv-scanner/trivy) would likely score ~1.0 here.
- **SAST GT partial coverage (Ф2, 12.5%).** Only 14 of 112 challenges are cleanly
  statically-locatable GT items. Recall is "recall against the 14 static sinks", not against
  all Juice Shop vulns. Strict precision is **deflated** — real-but-GT-excluded vulns count as
  FP; adjudicated precision (0.857) corrects this for FP but the **recall denominator is
  unchanged**, and true recall against all vulns would be substantially lower than 0.286.
- **Single-agent proxy ≠ real framework (the single biggest caveat).** Ф2 ran one agent
  doing semgrep + inline triage/score/report. The framework's real SAST path is a multi-agent
  team (cli-scanner → diff/impact reviewers → scoring → reproduction). This understates both
  token cost and potentially recall. **The 0.286 recall is a semgrep-only FLOOR** — the real
  multi-agent LLM-review path is **NOT yet measured and could exceed it** (it targets exactly
  the tool-missed Angular XSS / NoSQL / SSRF / weak-MD5 / PEM-literal FNs).
- **Single run, no variability yet.** N=1 per phase; no confidence interval. semgrep is
  deterministic (byte-identical re-runs), so N=3 of *this* path adds nothing — meaningful
  variability requires the real multi-agent orchestration with its own sampling.
- **Adjudicator is a model, not a human.** F2 adjudication was Claude Sonnet 4.6 (independent
  from the Opus auditor, source-grounded), which raises confidence above strict-FP counting but
  does not match human-expert review — borderline exploitability verdicts are provisional.
- **Ruleset transport substitution (Ф2).** The semgrep registry CDN was throttled (~66 B/s);
  rules came from the upstream `semgrep/semgrep-rules` git repo (same engine, same rules,
  different transport). The exact curated *pack membership* of `p/javascript` /
  `p/security-audit` may differ slightly from the full rule trees used, which could shift both
  recall and FP count vs a registry run.
- **Known-easy benchmark targets.** All three seeds use deliberately old, CVE-rich
  dependencies / a famous vulnerable-by-design app — easiest-case, not representative projects
  (no large transitive closure, no version-range edge cases). Juice Shop is also a
  heavily-trained-on target (contamination risk for any LLM-review path, though N/A for the
  deterministic SCA scanners and the semgrep-only Ф2 detection).

## 6. What is and isn't established

**ESTABLISHED**

- The benchmark **pipeline works end-to-end** for SCA and SAST: scan → schema v1.1 findings →
  frozen pre-registered matching rule → per-category confusion matrix.
- The **scorer discriminates real misses** — Ф1's 0.600 (reachability gap) and Ф2's
  tool-missed/CWE-mismatch FNs show the instrument is not pinned at 1.0.
- The **triage layer adds precision** — Ф2 baseline-delta: +103% strict precision, −75% noise,
  0 recall loss.
- **Adjudicated precision is high (0.857)** under independent-model adjudication, with the lift
  driven by GT-coverage gap, not scanner accuracy (only 4 of 25 strict FP are true FP).

**NOT YET ESTABLISHED**

- The **real multi-agent framework's capability** — Ф2 is a single-agent semgrep-only proxy;
  its recall is a floor, not the framework's number.
- **Broad multi-stack coverage** — N=1 repo per phase; only PyPI (Ф0), Go (Ф1), JS/TS (Ф2).
- **Statistical significance** — single run per phase, no variability runs, no confidence
  intervals.
- **Human-validated adjudication** — the adjudicator is a model; no human spot-check yet.

## 7. Next steps

- **Fuller ground truth** for the SAST target so precision stops being GT-coverage-bound (the
  dominant driver of the strict-vs-adjudicated gap).
- **Real multi-agent framework run** (the key open item) — the actual team-based orchestration
  vs this single-agent proxy; needs an orchestration/cost decision (the plan anticipates
  ~150k–400k output tokens per full L2+V framework audit).
- **More stacks** — Ф3: real CVE pre-fix commits including post-cutoff CVEs (highest signal,
  highest prep cost; the primary contamination control).
- **Variability runs** — Ф4: N≥3 on the real multi-agent path (not the deterministic semgrep
  proxy) + a deduped-pinned-scanner baseline, reporting mean ± spread.
- **Human adjudication spot-check** — a human security reviewer validates a sample of the
  model-adjudicated verdicts to bound the model-vs-human gap.

## Source artifacts

- Plan / rule: `BENCHMARK-PLAN.md`, `benchmark/ground-truth.schema.md`
- Phase reports: `benchmark/results/F0-sca-python-01.md`, `benchmark/results/F1-sca-go-01.md`,
  `benchmark/results/F2-sast-juiceshop-01.md`
- Ф2 adjudication / baseline: `benchmark/results/F2-adjudication.md`,
  `benchmark/results/F2-baseline-delta.md`
- Pre-registration tags: `bench-prereg-sca-python-01` @ `c802ded`,
  `bench-prereg-sca-go-01` @ `4b1cbcb`, `bench-prereg-sast-juiceshop-01` @ `599b703`
</content>
</invoke>
