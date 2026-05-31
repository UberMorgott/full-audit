# full-audit benchmark — recall & precision results (Ф5 synthesis)

> Single publishable artifact collating phases Ф0–Ф3 of the full-audit recall/precision
> benchmark. Every number here is quoted verbatim from a committed phase report; nothing
> is recomputed or invented in this document. Sources: `BENCHMARK-PLAN.md`,
> `benchmark/ground-truth.schema.md`, `benchmark/results/F0-sca-python-01.md`,
> `benchmark/results/F1-sca-go-01.md`, `benchmark/results/F2-sast-juiceshop-01.md`,
> `benchmark/results/F2-adjudication.md`, `benchmark/results/F2-baseline-delta.md`,
> `benchmark/results/F2-blind-juiceshop-01.md`, `benchmark/results/F3-synthetic-blind.md`.
> Audit pinned to tag `v1.10.4`; emitter schema v1.1 (`868156a`, shipped v1.10.5).

## 1. Executive summary

The benchmark measures two things a third party can check: **recall** (of known bugs, how
many the audit found) and **precision** (of what it emitted, how much is real). Categories
(SCA / SAST / logical) are scored **separately and never aggregated**. Three phases ran,
each against a ground truth (GT) + matching rule **git-tagged before the run**.

### Headline table (per category, never blended)

| Phase | Target | Scanner | Category | Recall | Strict precision | Adjudicated precision | Sev-weighted recall | Notes |
|-------|--------|---------|----------|--------|------------------|-----------------------|---------------------|-------|
| Ф0 | `sca-python-01` (6 PyPI pkgs, 38 CVEs) | pip-audit 2.10.0 | SCA | **1.000** (38/38) | **1.000** (38/38) | n/a | **1.000** | |
| Ф1 | `sca-go-01` (3 Go modules, 5 CVEs) | govulncheck v1.3.0 | SCA | **0.600** (3/5) | **1.000** (3/3) | n/a | **0.583** | |
| Ф2 proxy | OWASP Juice Shop `v20.0.0` (~23.1 KLOC) | semgrep 1.164.0 + LLM triage | SAST | 0.286 (4/14) | 0.138 (4/29) | 0.857 (24/28) | 0.323 | semgrep-only floor; single-agent proxy |
| Ф2 non-blind | OWASP Juice Shop `v20.0.0` (~23.1 KLOC) | LLM source review (manual) | SAST | ~~1.000~~ (14/14) | ~~0.438~~ (14/32) | ~~0.935~~ (29/31) | ~~1.000~~ | **answer-key-inflated / superseded** — reviewer had GT construction context |
| **Ф2 blind** | OWASP Juice Shop `v20.0.0` (~23.1 KLOC) | LLM source review (blind) | SAST | **1.000** (14/14) | **0.560** (14/25) | **1.000** (25/25) | **1.000** | **AUTHORITATIVE** — blind reviewer + independent Sonnet scorer; **training-contaminated target** |
| **F3 blind** | HiveTrack (post-cutoff synthetic, ~650 LOC) | LLM source review (blind) | SAST | **0.714** (10/14) | **0.769** (10/13) | **1.000** (13/13) | **0.743** | **MOST DEFENSIBLE** — contamination-controlled (original post-cutoff app) + blind + independent scorer |

### The one honest sentence

These numbers establish that the **pipeline works end-to-end** (SCA + SAST: scan → schema
→ frozen matching rule → score), that the **scorer discriminates real misses** (Ф1's 0.600,
Ф2 proxy's tool-missed FNs), that the **triage layer adds precision** (Ф2 baseline-delta),
that **blind LLM source review achieves 1.000 recall on Juice Shop** (Ф2 blind, but
training-contaminated), and — now with F3 controlling for contamination — that **on a
genuinely novel post-cutoff app recall drops to 0.714** (10/14) with **0 true false
positives** (adjudicated precision 1.000); they do **NOT** yet establish broad multi-stack
coverage, statistical significance (N=1 run per phase), human-validated adjudication
(adjudicator is a model), or recall on large real-world production codebases.

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

### Ф2 — SAST on OWASP Juice Shop `v20.0.0` (three runs; blind run is authoritative)

- **Target:** `juice-shop/juice-shop` `v20.0.0`, commit `f356a09207c7a9550eb6fc4c3945e081922cf998`,
  ~23.1 KLOC TS. GT = **14 statically-locatable sinks (12.5% of 112 challenges)** across 9
  files; ~98 non-static-sink challenges documented as excluded.

#### Ф2-proxy (semgrep-only floor)

- Scanner: semgrep 1.164.0 (upstream `semgrep-rules` git trees) + LLM triage: 118 raw → 29.
- **Confusion matrix (SAST, window N=5):**

  | Category | TP | FN | FP | recall | strict precision | sev-weighted recall |
  |----------|----|----|----|--------|------------------|---------------------|
  | SAST | 4 | 10 | 25 | **0.286** | **0.138** | **0.323** |

- **FN breakdown (10):** 6 tool-missed (NoSQL/Mongo, LFR, SSRF, two Angular `bypassSecurityTrustHtml`
  XSS, weak-MD5), 2 CWE-mismatch (right line, wrong taxonomy), 2 GT-locus-vs-tool-locus.
- **Adjudication (Sonnet 4.6):** 25 strict FP → 20 real-but-unlabelled / 4 true-FP / 1 disputed.
  Only 4 are actual semgrep false positives.

  | metric | value |
  |--------|-------|
  | Strict precision | 0.138 (4/29) |
  | Adjudicated precision (disputed excluded) | 0.857 (24/28) |
  | Recall | 0.286 (4/14) |
  | Sev-weighted recall | 0.323 |

#### Ф2-non-blind (answer-key-inflated — superseded)

- Scanner: LLM source review inline (same session as GT construction → not blind). **Design
  flaw: the reviewer had de-facto access to the GT construction rationale.** Results superseded
  by the blind run but kept for historical reference. Recall 1.000 / strict precision 0.438 /
  adjudicated precision 0.935. See `benchmark/results/F2-multiagent-juiceshop-01.md`.

#### Ф2-blind — AUTHORITATIVE (scored by independent Sonnet 4.6)

- **Reviewer (Opus, blind, stage 1):** produced 25 findings without ever seeing the frozen GT.
- **Scorer/adjudicator (Sonnet 4.6, independent, stage 2, THIS run):** scored and adjudicated
  independently; no involvement in findings production or GT construction.
- **Confusion matrix (SAST, window N=5):**

  | Category | TP | FN | FP | recall | strict precision | sev-weighted recall |
  |----------|----|----|----|--------|------------------|---------------------|
  | **SAST** | **14** | **0** | **11** | **1.000** | **0.560** | **1.000** |

- **FN = 0.** Blind reviewer found every GT item independently.
- **Adjudication of 11 strict FP:** all 11 are real-but-unlabelled (genuine Juice Shop vulns
  outside the conservative GT). **0 true FPs, 0 disputed.**

  | metric | value |
  |--------|-------|
  | Recall | **1.000** (14/14) |
  | Strict precision | **0.560** (14/25) |
  | Adjudicated precision | **1.000** (25/25) |
  | Sev-weighted recall | **1.000** |

- The 0.560 → 1.000 lift from strict to adjudicated precision is **entirely GT-coverage gap**:
  the blind reviewer produced zero true false positives.
- **Three-way comparison:**

  | Run | Saw GT? | TP | FN | Recall | Strict prec | Adj prec |
  |-----|---------|----|----|--------|-------------|----------|
  | Proxy (semgrep-only) | No | 4 | 10 | 0.286 | 0.138 | 0.857 |
  | Non-blind (answer-key-inflated) | Yes | 14 | 0 | ~~1.000~~ | ~~0.438~~ | ~~0.935~~ |
  | **Blind (authoritative)** | **No** | **14** | **0** | **1.000** | **0.560** | **1.000** |

### F3 — Contamination-controlled blind SAST on HiveTrack (MOST DEFENSIBLE)

- **Target:** HiveTrack (`benchmark/seeds/synthetic-vuln-01/app.py`) — original post-cutoff
  Flask app authored 2026-05, not publicly posted, not in any LLM training corpus. GT =
  **14 by-construction-exact items** (author planted each vulnerability and recorded the
  precise sink line before any reviewer or scanner saw the code).
- **Run design:** blind reviewer (Opus) + independent scorer/adjudicator (Sonnet 4.6); all
  answer-key comments stripped before review; reviewer never saw frozen GT.
- **Path-normalization note:** the blind reviewer filed findings as `"file": "app.py"` (single-file
  scope); GT stores the repo-relative path. Raw scorer: TP=0 FN=14 FP=13 (systematic artifact).
  Path-normalized analysis (adjudicator determination): TP=10 FN=4 FP=3 as reported below.
- **Confusion matrix (SAST, path-normalized, window N=5):**

  | Category | TP | FN | FP | recall | strict precision | adjudicated precision | sev-weighted recall |
  |----------|----|----|----|--------|------------------|-----------------------|---------------------|
  | **SAST** | **10** | **4** | **3** | **0.714** | **0.769** | **1.000** | **0.743** |

- **FN breakdown (4):**
  - **2 CWE-mismatch** (GT-S01-002: CWE-328 vs reviewer CWE-916 for MD5 password hash;
    GT-S01-008: CWE-94 vs reviewer CWE-1336 for SSTI) — same bug found, different taxonomy node.
  - **1 window-miss** (GT-S01-013: CWE-79 stored XSS; reviewer pinned render locus line 617,
    GT points to storage locus line 495-497; same vulnerability, 120 lines apart).
  - **1 true miss** (GT-S01-006: CWE-184 incomplete allowlist in `allowed_file()`; reviewer
    found the downstream CWE-22 traversal consequence but not the allowlist logic flaw).
- **Adjudication (3 strict FP):** all 3 are real-but-unlabelled (FA-0006 SSTI at exact GT
  locus / CWE taxonomy divergence; FA-0007 XSS at render locus; FA-0013 MD5 hash weakness
  at exact GT locus). **0 true FPs.**
- **Contamination comparison vs Ф2 blind (Juice Shop, recall 1.000, trained-on):**

  | Run | Target | Contamination? | Recall | Adj prec | Sev-wt recall |
  |-----|--------|----------------|--------|----------|---------------|
  | Ф2 blind | Juice Shop | **YES** | 1.000 | 1.000 | 1.000 |
  | **F3 blind** | **HiveTrack** | **NO** | **0.714** | **1.000** | **0.743** |

  The 0.286-point recall drop (1.000 → 0.714) is the upper bound on the contamination
  effect. Adjudicated precision holds at 1.000 on the novel target: zero hallucinated
  findings even on unseen code. Of the 4 FNs, only 1 is a genuine capability miss
  (GT-S01-006 true-miss); 3 are taxonomy/locus scoring artifacts where the bug was found.

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
  FP; adjudicated precision corrects this for FP but the **recall denominator is unchanged**,
  and true recall against all vulns would be substantially lower than the reported 1.000.
- **Juice Shop contamination — the new single biggest caveat for the blind run.** The 1.000
  blind recall may reflect the reviewer recalling Juice Shop's well-documented, challenge-
  annotated vulnerabilities from training data rather than discovering them by static analysis.
  Juice Shop is a famous, heavily-trained-on target. **A fully clean capability test needs a
  non-public / post-cutoff application** (planned Ф3). The proxy's 0.286 (semgrep-only, no LLM
  recall) is less susceptible; the blind LLM run's 1.000 is most susceptible.
- **Single run, no variability yet.** N=1 per phase; no confidence interval. LLM review has
  sampling variability; a single run cannot bound the spread.
- **Adjudicator is a model, not a human.** Blind run adjudication was Claude Sonnet 4.6
  (independent from the Opus reviewer, source-grounded), which raises confidence above strict-FP
  counting but does not match human-expert review. All 11 blind-run adjudicated-real items are
  unambiguous Juice Shop challenge loci, so model error is unlikely to affect the 1.000.
- **Inline review, no true parallel subagents.** All Ф2 runs (proxy, non-blind, blind) ran
  review in a single session; the playbook's parallel-subagent inter-agent cross-check was not
  exercised as a separate process.
- **Ruleset transport substitution (Ф2 proxy).** The semgrep registry CDN was throttled; rules
  came from the upstream `semgrep/semgrep-rules` git repo (same engine, same rules, different
  transport). The curated pack membership of `p/javascript` / `p/security-audit` may differ
  slightly, which could shift proxy recall and FP count vs a registry run.
- **Known-easy benchmark targets.** All three seeds use deliberately old, CVE-rich
  dependencies / a famous vulnerable-by-design app — easiest-case, not representative projects
  (no large transitive closure, no version-range edge cases).

## 6. What is and isn't established

**ESTABLISHED**

- The benchmark **pipeline works end-to-end** for SCA and SAST: scan → schema v1.1 findings →
  frozen pre-registered matching rule → per-category confusion matrix.
- The **scorer discriminates real misses** — Ф1's 0.600 (reachability gap) and Ф2 proxy's
  tool-missed/CWE-mismatch FNs show the instrument is not pinned at 1.0.
- The **triage layer adds precision** — Ф2 baseline-delta: +103% strict precision, −75% noise,
  0 recall loss.
- **Blind LLM source review achieves 1.000 recall and 1.000 adjudicated precision** against the
  14-item GT (Ф2 blind) — the blind reviewer (Opus) found every GT item independently; the
  independent scorer (Sonnet 4.6) confirmed zero true FPs among the 11 unmatched findings
  (all are real Juice Shop vulns outside the conservative GT). *(Note: target is training-contaminated.)*
- **The design flaw of the non-blind run is closed**: the Ф2 blind run has reviewer (Opus)
  and scorer/adjudicator (Sonnet 4.6) in separate sessions with no shared context.
- **Contamination-controlled blind capability measured on a synthetic post-cutoff target (F3):**
  recall drops to **0.714** (10/14) on a genuinely novel app. Of 4 FNs: 2 are CWE taxonomy
  near-misses (bug found, wrong CWE node), 1 is a window-miss (bug found at alternate locus),
  1 is a true capability miss. Adjudicated precision holds at **1.000** (zero hallucinated
  findings on unseen code). The contamination effect on Juice Shop recall is bounded above at
  0.286 (the gap between 1.000 and 0.714).

**NOT YET ESTABLISHED**

- **Recall on large real-world production codebases.** HiveTrack is a ~650-line synthetic app
  with planted, relatively clean vulnerabilities. Real production codebases are larger, more
  idiomatic, and have subtler bugs. Recall would likely be lower.
- **Broad multi-stack coverage** — N=1 repo per phase; only PyPI (Ф0), Go (Ф1), JS/TS (Ф2),
  Python/Flask (F3 synthetic).
- **Statistical significance** — single run per phase, no variability runs, no confidence
  intervals.
- **Human-validated adjudication** — the adjudicator is a model; no human spot-check yet.
- **True multi-agent process** — all SAST runs ran review inline in a single session; the
  playbook's parallel-subagent orchestration was not exercised.

## 7. Next steps

- **Variability runs (Ф4):** N≥3 on the contamination-controlled path (post-cutoff app or
  equivalent), reporting mean ± spread. Single-run N=1 cannot bound the recall distribution.
- **Larger / more idiomatic synthetic target:** HiveTrack is ~650 LOC with planted,
  relatively clean bugs. A larger, more realistic app would stress-test the framework on
  subtler multi-hop taint flows and more idiomatic code patterns.
- **CWE-set expansion in GT for near-miss cases:** the F3 FN analysis revealed 2 of 4 FNs
  are CWE taxonomy near-misses where both nodes are defensible (CWE-94/CWE-1336 for SSTI,
  CWE-328/CWE-916 for weak hash). Adding sibling CWEs to GT items (as a list) would
  correctly score these as TP while preserving strictness.
- **Human adjudication spot-check** — validate a sample of model-adjudicated verdicts to
  bound the model-vs-human gap.
- **True parallel-subagent orchestration** — exercise the playbook's actual team-spawn path
  to measure the inter-agent cross-check and dedup mechanics.
- **Live runs on additional stacks** (Rust, Java, C#, API-level findings) and L1/L3/monorepo
  targets per the original roadmap.

## Source artifacts

- Plan / rule: `BENCHMARK-PLAN.md`, `benchmark/ground-truth.schema.md`
- Phase reports: `benchmark/results/F0-sca-python-01.md`, `benchmark/results/F1-sca-go-01.md`,
  `benchmark/results/F2-sast-juiceshop-01.md`
- Ф2 adjudication / baseline: `benchmark/results/F2-adjudication.md`,
  `benchmark/results/F2-baseline-delta.md`
- Ф2 non-blind run (superseded): `benchmark/results/F2-multiagent-juiceshop-01.md`
- **Ф2 blind run (blind, but contaminated):** `benchmark/results/F2-blind-juiceshop-01.md`
- **F3 blind run (contamination-controlled, most defensible):** `benchmark/results/F3-synthetic-blind.md`
- Pre-registration tags: `bench-prereg-sca-python-01` @ `c802ded`,
  `bench-prereg-sca-go-01` @ `4b1cbcb`, `bench-prereg-sast-juiceshop-01` @ `599b703`,
  `bench-prereg-synthetic-01-clean` (HiveTrack)
</content>
</invoke>
