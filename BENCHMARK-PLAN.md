# Benchmark Plan — measuring full-audit recall & precision

> **Goal:** turn "we re-checked it ourselves" into numbers a third party will believe — **recall** (of known bugs, how many the audit actually found) and **precision** (of what it emitted, how much is real vs noise).
> **Core thesis:** self-deception is easy here, so **half this plan is about measuring honestly**, not about "run on Juice Shop and count."
> **Pinned:** audit pinned to tag `v1.10.4`; targets pinned to exact commits. Model fixed per run (record run-id). Status: draft, pre-registration not yet tagged.

## Decisions (locked)
- **Adjudicator of unmatched findings = independent model / separate pass**, NOT the model that produced the audit. Disclosed in Threats-to-Validity. (Closes the fox-guarding-henhouse hole that otherwise invalidates adjudicated-precision.)
- **Logical/LLM findings are manual-adjudication only** — not fed to the automated confusion matrix (they lack CWE/line precision; auto-matching would either under-count or invite rule-tuning).
- **Baseline = same pinned tool versions (`versions.lock`) at default config, deduplicated union, no LLM.** Isolates the framework delta = LLM review + scoring + FP-cut + dedup. (Not "bare tools with defaults" — that conflates tool version with orchestration; not raw un-deduped union — that unfairly tanks baseline precision.)
- **Source of truth for version consistency = CHANGELOG top entry** (already enforced in CI via `scripts/check_readme_version.py`, step 0 below — DONE).

## Step 0 — version-check (DONE, independent of benchmark)
- `scripts/check_readme_version.py`: asserts README header / "currently `vX.Y.Z`" / both `e.g.` example tags == CHANGELOG top entry; `--tag`/`GITHUB_REF_TYPE=tag` also checks git tag. Regex-anchored (no hardcoded line numbers); `<release-tag>` placeholder ignored.
- Wired into `.github/workflows/lint.yml` (the `on: [push, pull_request]` gate). Forgotten bump now fails CI. Shipped `9499049` on `main`.

## Step 0b — emitter enrichment (DONE — shipped v1.10.5, `868156a`)
- Was the gating blocker: `audit-bugs.json` (schema 1.0) carried `file + line(single int) + severity + detection + confidence + reproduced` but no `cwe`/`cve`/`end_line` → CVE/CWE auto-match couldn't run.
- **Shipped (schema v1.1, additive/back-compat):** finding objects gain optional `cwe` (from detecting tool's CWE/OWASP mapping), `cve` (for SCA findings: osv-scanner/govulncheck/`*-audit`), `end_line` (multi-line range; `line` stays the start). `schema_version` 1.0→1.1. Spec + integrity rules + example updated (README Report Format); existing required fields/invariants unchanged. CI green.
- Scoring script can now join on `{file, line..end_line, cwe, cve, severity}` per the pre-registered rule.

## 1. Benchmark design — 80% of the value

### Three ground-truth types (measure SEPARATELY, never blend)
| Type | Ground truth | Cost | Tests |
|------|--------------|------|-------|
| **SCA / CVE-recall** | repos pinned to deps with published CVEs; oracle = NVD/OSV CVE list, auto-scored | cheapest, cleanest | mostly osv-scanner/govulncheck, NOT LLM review |
| **SAST / code-recall** | deliberately-vulnerable apps w/ documented inventory (Juice Shop, NodeGoat, django.nV, WebGoat) | medium | code-review waves |
| **Real historical bugs** | repo at the commit *just before* a known bug's fix (esp. security fixes w/ CVE + fixing PR); oracle = "audit must flag what that PR later fixed" | highest signal, highest prep cost | full pipeline |

### Definitions + matching rule — pre-register BEFORE any runs
- **TP** = audit finding matched to a ground-truth item; **FN** = GT item the audit missed; **FP** = finding with no GT match.
- **Matching rule:** same file ± N lines AND same vuln class (CWE) / same CVE. SCA matches on CVE-id; SAST on CWE + line-window; logical = manual only (see Decisions).
- **No accuracy** — TN undefinable in open audit. Recall/precision only.
- **Pre-registration is an artifact, not a promise:** commit the ground-truth YAML + matching rule + metric defs to the repo and **git-tag it BEFORE running** (e.g. `bench-prereg-v1`). Makes "we didn't tune the rule to flatter results" externally verifiable.

### Traps (each with antidote)
1. **Incomplete oracle.** Audit will find real bugs absent from your labelled list; calling them FP under-counts precision. → unmatched findings go to adjudication in 3 buckets: *real-but-unlabelled / true-FP / disputed*. Report **precision twice: strict and adjudicated**. Adjudicator = independent model/pass (locked).
2. **Contamination.** Juice Shop + famous CVEs are in training data — the model may *recall* answers, not *find* them. → **primary anti-cheat = a private/obfuscated seed** (inject known vuln patterns into a fresh private repo: controllable, repeatable, provably out-of-training). post-cutoff CVE (after the model's Jan-2026 cutoff) = secondary (hard to source, cutoff drifts). Report contamination risk **per category** — it inflates the logical/LLM bucket most (scanners are tool-deterministic).
3. **Framework vs scanners?** To prove orchestration adds value, need a **baseline** (see Decisions: same pinned tools, default config, deduped union, no LLM). Delta = dedup + scoring + FP-cut + LLM-only logical findings. Else you're benchmarking semgrep.
4. **Stochasticity.** LLM non-deterministic. Run each repo **N=3–5×**, report mean ± spread. Fix model, level (e.g. L2 +V), run-id. One run ≠ proof.

## 2. Metrics reported
- Recall **per category** (SCA/CVE, SAST, logical) — never aggregated.
- Precision: **strict** + **adjudicated**.
- **Severity-weighted recall** (missing a CRITICAL ≫ a nitpick) — needs an explicit **CVSS↔band crosswalk** (oracle CVSS ↔ audit CRITICAL/HIGH/MEDIUM/LOW), baked into ground truth.
- Noise: findings / KLOC.
- **Delta = framework − baseline.**
- Cost: tokens + wall-clock per repo/level.
- Run-to-run stability.
- **FN root-cause tag** (most useful output): each FN tagged — tool-not-run / `skip_if`-fired / LLM-saw-and-dismissed / scored-below-threshold. Turns the scoreboard into a backlog.

## 3. Candidate repos (supported stacks; exact commits chosen at start)
- **JS/TS:** OWASP Juice Shop (rich inventory), NodeGoat.
- **Python:** django.nV, or Django/Flask pinned to CVE deps.
- **Go:** few "vulnerable by design" — use a Go project at a pre-fix CVE commit, or a repo with a govulncheck-detectable dep hole.
- **Cross-stack SCA:** any repo with an old lockfile full of known CVEs (objective osv-scanner oracle).
- **+1 private/obfuscated seed** (primary contamination control) and/or **+1 post-cutoff CVE fix** (secondary).

## 4. Harness
- Pin audit → tag `v1.10.4`; targets → exact commits.
- Standard invocation (level, verified on/off); log tokens / time / run-id.
- Scoring hook = `audit-bugs.json` (machine-readable, schema v1.1 — `cwe`/`cve`/`end_line` available as of Step 0b). Script joins findings ↔ ground-truth YAML (`file, line_start, line_end, cwe, cve, severity`) by the pre-registered rule → confusion matrix per category.

## 5. Phasing (so it actually ships)
- **Ф0** — harness + GT schema + scoring script on ONE repo (prove the pipeline). Pick an **SCA case** so Ф0 shares machinery with Ф1.
- **Ф1** — SCA-only benchmark (cheap, objective, fast win: clean recall numbers for the vuln path).
- **Ф2** — SAST on vulnerable apps.
- **Ф3** — real CVE pre-fix commits, incl. post-cutoff (hard, high-signal).
- **Ф4** — baseline (deduped pinned scanners) + variability runs.
- **Ф5** — report w/ Threats-to-Validity section + publish results in repo. ← this is what buys external credibility.

## 6. Threats to Validity (MANDATORY — this section IS the credibility)
State up front: incomplete oracle; contamination (per-category); small repo N; stochasticity; "known/easy" benchmark apps; framework-vs-scanner confound; **adjudicator is a model not a human** (independent pass, but disclose). An honest limitations list convinces harder than pretty numbers without one.

## Cost reality + estimate (plan's blind spot)
- Matrix = repos × N-runs × levels × (framework + baseline). Even minimal Ф1: 3 repos × 3 runs × (L2+V framework + baseline) ≈ **18 full audits**, each = dozens of agents. The benchmark can cost more than all dev to date.
- **Order-of-magnitude estimate (uncalibrated — Ф0 must measure real numbers, do not trust this for budgeting):**
  - One L2+V framework audit ≈ Phase-0 enum + ~3-5 parallel review-wave agents + reproduction wave (verified) + scoring/report agents. Rough guess **~150k-400k output tokens / audit** depending on repo size (KLOC) and finding count. SCA-only paths are cheaper (fewer LLM review waves).
  - One baseline run (deduped pinned scanners, no LLM) is near-zero model cost — mostly wall-clock + a thin parse/dedup script.
  - **Minimal Ф1** (3 repos × 3 framework runs + 1 baseline) ≈ 9 framework audits ≈ **~1.5M-3.5M output tokens**, plus adjudication passes (independent model over unmatched findings: small, ~tens of k each).
  - **Full matrix (Ф0-Ф4, multiple stacks × levels × N)** scales 5-10× that → plausibly **10M+ tokens**; likely budget-gated. Size each phase before committing.
- **Mandatory:** Ф0 logs actual tokens+wall-clock per audit; recompute this table from measured data before authorizing Ф1, and again before Ф3/Ф4. Treat the numbers above as placeholders, not a budget.

## Minimal defensible version (if resource-tight)
- Step 0b (emitter) → Ф0 + Ф1 on 3 repos, 3 runs, baseline for one.
- First defensible SCA-path numbers in a couple of evenings.
- What makes it defensible is **#1 (independent adjudicator)** + **pre-registration git-tag**, not the runs themselves.
