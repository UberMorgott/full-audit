# Ф2 baseline + framework delta — `sast-juiceshop-01`

> Baseline = raw semgrep, **no triage**, all 118 results taken as findings.
> Framework-proxy = `run1` (post-LLM-triage, 29 emitted findings).
> Delta = value of the triage/orchestration layer.

## Scanner + rule source

- **Tool:** semgrep **1.164.0** (same binary as Ф2 run)
- **Rulesets:** upstream `semgrep/semgrep-rules` git clone at `C:/Temp/semgrep-rules/`
  (`javascript/` + `typescript/` trees) — same transport substitution as Ф2 (registry
  CDN throttled at ~66 B/s; git clone reachable). Same engine, same upstream rules.
- **Invocation:** identical to Ф2 (PYTHONUTF8=1, --json --metrics=off --no-git-ignore
  --exclude=node_modules --exclude='*.spec.ts' --exclude=test --exclude=dist --timeout=60;
  targets: routes lib models app.ts server.ts frontend/src)
- **Scan wall-clock:** ~30 s (identical to Ф2)
- **Raw output:** 118 results, 0 scan errors, 609 files scanned (byte-identical to Ф2
  — semgrep is deterministic)

## Baseline confusion matrix (SAST, window N=5)

All 118 raw results taken as findings (no discards). Of the 118:

| bucket | count | routing |
|--------|-------|---------|
| With CWE (auto-scorable) | 59 | scored as TP/FP |
| Without CWE (no taxonomy) | 59 | adjudication bucket (NOT counted as FP per schema rule) |

| metric | value |
|--------|-------|
| TP | **4** |
| FN | **10** |
| FP (auto-scorable, no GT match) | **55** |
| Needs adjudication (no CWE) | 59 |
| recall | **0.286** (4/14) |
| strict precision | **0.068** (4/59 auto-scorable) |
| sev-weighted recall | **0.323** |
| findings/KLOC (noise) | **5.11** (118 / 23.1) |

TP matches: GT-001 (login.ts SQLi), GT-002 (search.ts SQLi), GT-005 (fileUpload.ts XXE),
GT-007 (userProfile.ts SSTI) — identical to run1; the same 4 GT items matched regardless
of triage.

### CWE-less findings (59 — adjudication, not strict FP)

Per the pre-registered matching rule: a finding with no `cwe`/`cve` that matches nothing
is **NOT** a strict FP — it routes to the adjudication bucket. These 59 are:

- 33 × `missing-template-string-indicator` (INFO, correctness nitpick, no CWE)
- 26 × `useless-assignment` (INFO, correctness nitpick, no CWE)

All are INFO-level non-security findings that the Ф2 triage discarded. Because they carry
no CWE, they are indistinguishable to the scorer from logical-class unmatched findings and
go to manual adjudication — they are NOT auto-FP. This means the auto-scorable FP count
is 55, not 114; and the correct denominator for strict precision is 59 (4 TP + 55 FP).

## Delta: baseline vs framework-proxy (run1)

| metric | baseline (raw, 118) | framework-proxy run1 (29) | delta |
|--------|--------------------|-----------------------------|-------|
| TP | 4 | 4 | **0** |
| FN | 10 | 10 | **0** |
| FP (auto-scorable) | 55 | 25 | **−30** |
| Adj (no CWE) | 59 | 0 | **−59** |
| recall | 0.286 | 0.286 | **+0.000** |
| strict precision | 0.068 | 0.138 | **+0.070** (+103%) |
| sev-weighted recall | 0.323 | 0.323 | **+0.000** |
| total findings (noise) | 118 | 29 | **−89** (−75%) |
| findings/KLOC | 5.11 | 1.26 | **−3.85** |

## Honest interpretation

**Triage improved precision (+103% relative) with zero recall loss.** The triage layer
removed 89 of 118 raw results (75%) — dropping all 59 CWE-less nitpicks and 30
auto-scorable FP — while retaining all 4 TP that the raw scanner found. Strict precision
doubled (0.068 → 0.138) and noise fell from 5.1 to 1.3 findings/KLOC.

However, this gain should be read carefully:

- **Recall ceiling is a tool limit, not a triage limit.** All 10 FN are tool-missed or
  CWE-mismatch at the scanner level; triage cannot recover what semgrep did not emit.
  Both the baseline and run1 are bounded by the scanner's 4-of-14 detection ceiling.

- **Precision is still GT-deflated.** The dominant FP cause in both baseline and run1 is
  **partial GT coverage**, not scanner noise — most of the 25 run1 FP (and many of the 55
  baseline FP) are real Juice Shop vulns at loci/CWEs outside the conservative 14-item GT.
  Adjudicated precision against a fuller oracle would be substantially higher for both.

- **Single-agent proxy, not the full framework.** The "framework" here is one agent running
  semgrep + inline LLM triage. The real multi-agent orchestration (independent diff/impact/
  scoring/reproduction waves) is not exercised. The delta measures the **triage layer value**,
  not the full orchestration value. A full-framework run could push recall higher (the
  tool-missed Angular XSS, SSRF, NoSQL FNs are exactly what an LLM source-review wave
  targets) but this run does not demonstrate that.

- **59 CWE-less results in baseline route to adjudication, not FP.** Per the pre-registered
  schema rule, findings without CWE/CVE are not auto-scored as FP. The "true" baseline FP
  count against the auto-scorable denominator is 55/59 (not 114/118). Reporting both as
  adjudication makes the baseline strictly precision 0.068, comparable to run1's 0.138.

## Artifacts

- Baseline findings: `benchmark/results/sast-juiceshop-01.baseline.findings.json`
  (118 findings, schema v1.1, detection=semgrep, no triage)
- Baseline score: `benchmark/results/sast-juiceshop-01.baseline.score.json`
  (scorer output: SAST TP=4, FN=10, FP=55, adj=59)
- Framework-proxy run1 (reference): `benchmark/results/sast-juiceshop-01.run1.findings.json`
- Framework-proxy score (reference): `benchmark/results/sast-juiceshop-01.run1.score.json`
- This report: `benchmark/results/F2-baseline-delta.md`
