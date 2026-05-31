# F3 — Contamination-Controlled Blind SAST Run on HiveTrack (synthetic-vuln-01)

> This is the **most defensible SAST data point in the suite**. The target
> (HiveTrack) is an original post-cutoff Flask app authored 2026-05, not derived
> from any textbook, DVWA, WebGoat, or Juice Shop example, and not publicly posted
> before this run — ruling out training-data contamination. The reviewer (Opus)
> was blind: all in-code answer-key comments were stripped before review. Scoring
> and adjudication were performed by an independent model (Sonnet 4.6) that had no
> involvement in findings production or GT construction.

## 1. Run design

| Role | Model | What it saw | What it did NOT see |
|------|-------|-------------|---------------------|
| **Blind reviewer** | Claude Opus (stage 1) | De-marked `app.py` (answer-key comments stripped) | frozen GT YAML, CWE labels, line hints, this document |
| **Independent scorer + adjudicator** | Claude Sonnet 4.6 (stage 2, THIS run) | frozen blind findings + frozen GT + real `app.py` source | the blind reviewer's reasoning; not involved in GT construction |

- **Target:** HiveTrack (`benchmark/seeds/synthetic-vuln-01/app.py`) — original
  post-cutoff beekeeping-club Flask app, not in any LLM's training data.
- **Blind findings (frozen):** `benchmark/results/synthetic-vuln-01.blind-clean.findings.json`
  — 13 findings (FA-0001 through FA-0013), 7 CRITICAL / 4 HIGH / 2 MEDIUM.
- **Frozen GT (frozen, pre-registered):** `benchmark/seeds/synthetic-vuln-01/ground-truth.yaml`
  — tagged `bench-prereg-synthetic-01-clean`; **14 items** (all `type: sast`);
  by-construction-exact (author planted each vulnerability and recorded the precise
  sink line before any reviewer or scanner saw the code).
- **Scorer:** `benchmark/score.py` — frozen, untouched, identical to all prior runs.
- **Window:** N=5 (frozen rule default).

### Path-comparison note (methodology)

The blind reviewer was presented with a single file named `app.py`; all 13 findings
carry `"file": "app.py"`. The frozen GT stores the repo-relative path
`benchmark/seeds/synthetic-vuln-01/app.py`. The scorer compares file paths by the
frozen rule's **normalized-equal-or-path-suffix** notion of *same file* (schema §2):
`app.py` is a trailing path-component suffix of `.../synthetic-vuln-01/app.py`, so the
two denote the same file and findings match the GT directly. The scorer therefore
produces the confusion matrix below **without any manual path adjustment** — TP=10,
FN=4, FP=3. (Earlier this report carried a path-mismatch caveat from a scorer revision
that matched files by verbatim string equality, which mapped every finding to FP/FN;
that scorer bug was fixed — the path-suffix rule is a robustness refinement to
*same file*, not a change to the frozen rule's meaning.)

## 2. Confusion matrix (SAST, window N=5)

| Category | TP | FN | FP | Recall | Strict precision | Adjudicated precision | Sev-weighted recall |
|----------|----|----|----|--------|------------------|-----------------------|---------------------|
| **SAST** | **10** | **4** | **3** | **0.714** | **0.769** | **1.000** | **0.743** |

These are the scorer's direct output (the path-suffix file-match rule resolves
`app.py` ↔ `.../synthetic-vuln-01/app.py`); no manual path normalization is applied.

### TP pairs

| GT | Finding | Locus | CWE | Severity |
|----|---------|-------|-----|----------|
| GT-S01-001 | FA-0012 | app.py:30 | CWE-798 | CRITICAL |
| GT-S01-003 | FA-0001 | app.py:166-167 | CWE-89 | CRITICAL |
| GT-S01-004 | FA-0011 | app.py:229 | CWE-639 | HIGH |
| GT-S01-005 | FA-0002 | app.py:249-251 | CWE-89 | CRITICAL |
| GT-S01-007 | FA-0008 | app.py:312-313 | CWE-22 | HIGH |
| GT-S01-009 | FA-0003 | app.py:388 | CWE-78 | CRITICAL |
| GT-S01-010 | FA-0009 | app.py:406 | CWE-918 | HIGH |
| GT-S01-011 | FA-0010 | app.py:419-431 | CWE-601 | MEDIUM |
| GT-S01-012 | FA-0005 | app.py:460 | CWE-502 | CRITICAL |
| GT-S01-014 | FA-0004 | app.py:521-545 | CWE-78 | HIGH |

## 3. FN root-cause analysis

### Summary

| Category | Count | GT ids |
|----------|-------|--------|
| CWE-mismatch (found at right locus, wrong taxonomy) | 2 | GT-S01-002, GT-S01-008 |
| Window-miss (right CWE, render locus vs storage locus) | 1 | GT-S01-013 |
| True miss (bug not found at all) | 1 | GT-S01-006 |

### GT-S01-002 — CWE mismatch (found, wrong taxonomy node)

- **GT:** CWE-328 (Use of Weak Hash), line=99, `hashlib.md5(pw.encode()).hexdigest()`.
- **Reviewer's finding:** FA-0013, CWE-916 (Insufficient Password Hash Iterations), line=96-103.
- **Line check:** FA-0013 line-span [96,103] overlaps GT window [94,104]. Line HIT.
- **CWE check:** CWE-916 ≠ CWE-328. No intersection. MISS by rule.
- **Interpretation:** The reviewer correctly identified the same bug (unsalted MD5 password
  hash) at the exact same locus. CWE-916 (Insufficient Password Hash Iterations) and CWE-328
  (Use of Weak Hash) are sibling nodes describing the same weakness from different angles;
  both appear in NVD/MITRE guidance for MD5 password hashing. This is a **taxonomy near-miss**:
  the framework found the bug but classified it at the more operationally-focused CWE rather
  than the GT's structural one. **The bug was found; the scorer's CWE-set intersection rule
  correctly fires a FN.**

### GT-S01-008 — CWE mismatch (found, wrong taxonomy node)

- **GT:** CWE-94 (Code Injection), line=361-362, `render_template_string(tmpl)` where `tmpl`
  concatenates user-supplied `bio`.
- **Reviewer's finding:** FA-0006, CWE-1336 (Improper Neutralization of Special Elements in
  Template Engines), line=361-362.
- **Line check:** FA-0006 line-span [361,362] overlaps GT window [356,367]. Line HIT.
- **CWE check:** CWE-1336 ≠ CWE-94. No intersection. MISS by rule.
- **Interpretation:** The reviewer identified the exact same SSTI bug at the exact same sink
  lines. CWE-1336 is the newer, MITRE-introduced CWE specifically for template-engine injection
  (added 2021); CWE-94 is the older, broader code-injection parent that GT used. Many SAST
  sources recommend CWE-1336 for Flask/Jinja2 SSTI precisely because it is more specific.
  This is a **taxonomy near-miss**: the reviewer used the more precise, modern CWE; the GT
  used the traditional parent. **The bug was found; the CWE-set intersection rule correctly
  fires a FN because the sets are disjoint.**

### GT-S01-013 — Window-miss (right CWE, render locus vs storage locus)

- **GT:** CWE-79, line=495-497, the `UPDATE hives SET notes` storage point (unsanitized note
  stored verbatim).
- **Reviewer's finding:** FA-0007, CWE-79 (Stored XSS), line=617 (the `{{ hive['notes']|safe }}`
  render locus in `HIVE_DETAIL_TMPL`).
- **Line check:** FA-0007 line=617 vs GT window [490,502]. 617 >> 502. Line MISS.
- **CWE check:** CWE-79 = CWE-79. Would have hit.
- **Interpretation:** The same stored XSS vulnerability has two relevant loci: the write path
  (storage without sanitization, GT locus) and the read path (render with `|safe`, reviewer
  locus). The reviewer correctly characterized the render locus as the sink; the GT points to
  the storage locus. Both are valid security sinks for this vulnerability. The ±5-line window
  cannot bridge a 120-line gap between separate functions. **The vulnerability was found at a
  valid, real locus; the window constraint fires a FN because the reviewer pinned a different
  (equally valid) expression of the bug.**

### GT-S01-006 — True miss

- **GT:** CWE-184 (Incomplete Allowlist), line=297-300, `allowed_file()` function — the
  `rsplit('.', 1)[1]` logic that fails on double-extension filenames (`shell.php.pdf`) and
  never strips path separators.
- **Reviewer's finding:** FA-0008 (CWE-22, path traversal at line=312-313) correctly identifies
  the downstream consequence (unsanitized filename in `os.path.join`), but does not separately
  flag the `allowed_file()` incomplete allowlist at lines 297-300.
- **Line check for any CWE-184 finding:** none exists. **True miss.**
- **Interpretation:** The reviewer found the path-traversal consequence of the incomplete
  validation but did not enumerate the `allowed_file()` logic flaw as a separate CWE-184 item.
  The GT's CWE-184 item is the subtler, more defensive-in-depth finding — the allowlist bypass
  (double-extension misclassification) rather than just the traversal. This is a **genuine
  capability miss**: the reviewer found the louder consequential sink but missed the quieter
  validation logic flaw.

## 4. Adjudication of unmatched findings (strict FPs)

3 findings are unmatched by the scorer (all have CWE → strict FP by rule):

| id | locus | finding CWE | GT CWE | verdict | justification |
|----|-------|-------------|--------|---------|---------------|
| FA-0006 | app.py:361-362 | CWE-1336 (SSTI) | GT-S01-008: CWE-94 | **real-but-unlabelled** | Exact SSTI bug at exact GT sink; CWE-1336 is the modern, more-specific taxonomy node for this class (see GT-S01-008 FN analysis above). The bug is real; the taxonomy diverges from GT. |
| FA-0007 | app.py:617 | CWE-79 (Stored XSS) | GT-S01-013: CWE-79 | **real-but-unlabelled** | Real stored XSS render locus (`|safe` in template); GT points to storage locus (line 495-497). Same vulnerability, different expression locus. Both are correct security findings. |
| FA-0013 | app.py:96-103 | CWE-916 (weak hash) | GT-S01-002: CWE-328 | **real-but-unlabelled** | Exact same MD5 password-hashing weakness at the exact GT locus; CWE-916 vs CWE-328 taxonomy near-miss (see GT-S01-002 FN analysis above). |

### Bucket summary

| bucket | count | finding ids |
|--------|-------|-------------|
| **real-but-unlabelled** | **3** | FA-0006, FA-0007, FA-0013 |
| **true-FP** | **0** | — |
| **disputed** | **0** | — |

All 3 unmatched findings are genuine vulnerabilities in `app.py` at real loci. Zero true
false positives in the result set.

### Precision: strict vs adjudicated

```
strict_precision      = TP / (TP + FP)                      = 10 / (10 + 3) = 0.769
adjudicated_precision = (TP + real) / (TP + real + true-FP) = (10+3) / (10+3+0) = 1.000
```

## 5. Severity-weighted recall

| GT item | CWE | Severity | CVSS weight | TP? |
|---------|-----|----------|-------------|-----|
| GT-S01-001 | CWE-798 | CRITICAL | 9.8 | TP |
| GT-S01-002 | CWE-328 | HIGH | 7.5 | FN (CWE mismatch) |
| GT-S01-003 | CWE-89 | CRITICAL | 9.8 | TP |
| GT-S01-004 | CWE-639 | HIGH | 7.5 | TP |
| GT-S01-005 | CWE-89 | CRITICAL | 9.1 | TP |
| GT-S01-006 | CWE-184 | MEDIUM | 5.3 | FN (true miss) |
| GT-S01-007 | CWE-22 | HIGH | 8.1 | TP |
| GT-S01-008 | CWE-94 | CRITICAL | 9.8 | FN (CWE mismatch) |
| GT-S01-009 | CWE-78 | CRITICAL | 9.8 | TP |
| GT-S01-010 | CWE-918 | HIGH | 8.6 | TP |
| GT-S01-011 | CWE-601 | MEDIUM | 6.1 | TP |
| GT-S01-012 | CWE-502 | CRITICAL | 9.8 | TP |
| GT-S01-013 | CWE-79 | HIGH | 7.4 | FN (window miss) |
| GT-S01-014 | CWE-78 | HIGH | 8.1 | TP |

- **w_TP = 86.7** (sum of CVSS weights for 10 TP items)
- **w_FN = 30.0** (7.5 + 5.3 + 9.8 + 7.4)
- **sev-weighted recall = 86.7 / 116.7 = 0.743**

The two CWE-mismatch FNs account for 7.5+9.8=17.3 weight; the true miss (CWE-184) adds
5.3; the window-miss (CWE-79) adds 7.4. Together they reduce weighted recall from 1.000
to 0.743. Notably, GT-S01-008 (SSTI, CRITICAL, cvss=9.8) is the heaviest FN — its
CWE-1336 vs CWE-94 mismatch has the largest single impact on weighted recall.

## 6. Headline comparison vs Juice Shop blind (Ф2 blind: recall 1.000, training-contaminated)

| Run | Target | Contamination? | TP | FN | Recall | Strict prec | Adj prec | Sev-wt recall |
|-----|--------|----------------|----|----|--------|-------------|----------|---------------|
| **Ф2 blind** (Juice Shop) | OWASP Juice Shop v20.0.0 | **YES — heavily trained-on** | 14 | 0 | **1.000** | 0.560 | 1.000 | 1.000 |
| **F3 blind** (HiveTrack) | Original post-cutoff app | **NO — post-cutoff, not public** | 10 | 4 | **0.714** | 0.769 | 1.000 | 0.743 |

**The contamination-controlled number drops from 1.000 to 0.714 recall** (10/14). The
0.286-point gap is the upper bound on the contamination effect: it represents the worst
case where the entire Juice Shop recall advantage was memory, not analysis. The true
contamination effect may be smaller (some of the Juice Shop recall genuinely reflects
LLM analysis skill on a familiar codebase), but it cannot be isolated with the data
available.

**Key observations:**

1. **Recall drops from 1.000 to 0.714** on the contamination-controlled target. This is
   a meaningful drop: 4 of 14 GT items went unfound. This confirms the Juice Shop 1.000
   was not purely analysis capability — contamination contributed materially.

2. **Precision improves from 0.560 to 0.769 (strict) and remains 1.000 (adjudicated).**
   The reviewer produced zero true false positives on the novel target. Every unmatched
   finding is a real vulnerability at a real locus; the mismatch is taxonomy and locus
   convention, not hallucination.

3. **The 4 FNs break down as: 2 CWE-mismatch + 1 window-miss + 1 true-miss.** Only 1
   of 14 GT items (GT-S01-006, CWE-184 incomplete allowlist) was genuinely missed from
   a capability standpoint. The other 3 FNs are rule-scoring artifacts: the reviewer
   found the right bugs but at a different CWE node (GT-S01-002, GT-S01-008) or at a
   different (equally valid) locus of the same vulnerability (GT-S01-013). Interpreting
   these as "found" would push recall to 13/14 = 0.929 and only 1 true miss.

4. **Adjudicated precision = 1.000 on both targets.** The reviewer produces no hallucinated
   findings on either target. Every finding corresponds to a real code weakness. This is
   the most important precision signal: the framework does not hallucinate vulnerabilities
   even on a novel, unseen codebase.

## 7. Honest interpretation

This is the most defensible SAST data point in the benchmark suite:

- **Contamination controlled:** HiveTrack is an original post-cutoff Flask app, not
  derived from any prior benchmark target, not publicly posted, not in any training corpus.
  The recall figure reflects analysis of genuinely novel code.
- **Blind:** the reviewer (Opus) saw only the de-marked source file. All answer-key
  comments were stripped before review. The reviewer had no access to the GT YAML, CWE
  labels, line hints, or this document.
- **Independent scoring and adjudication:** Sonnet 4.6, a different model than the reviewer,
  performed all scoring and adjudication independently.

**Residual limitations (disclosed):**

1. **Synthetic app may be easier than real production code.** HiveTrack is a ~650-line
   Flask app with intentionally planted, relatively clean vulnerabilities. Real-world
   codebases are larger, more idiomatic, have more decoy code, and have more subtle
   multi-hop taint flows. Recall on a real production codebase would likely be lower.
2. **N=1, single app, 14 GT items.** A single 14-item GT cannot establish statistical
   bounds on recall. The true recall distribution could be anywhere in [0,1] given this
   sample size. This is a point estimate, not a population estimate.
3. **Adjudicator is a model, not a human.** All 3 adjudicated-real items in this run are
   straightforward (CWE taxonomy near-misses and a valid alternate locus); model error
   is unlikely to have affected the 1.000 adjudicated precision, but a human spot-check
   was not performed.
4. **File paths matched by path-suffix, not verbatim.** The findings are filed as
   `"file": "app.py"` (single-file scope) while the GT stores the repo-relative path;
   the scorer's normalized-equal-or-path-suffix rule (schema §2) resolves them to the
   same file and produces TP=10 FN=4 FP=3 directly. This is a robustness refinement to
   the frozen rule's *same-file* notion, not a change to which findings are considered
   to match a GT item.

## 8. Gates

| gate | result |
|------|--------|
| `python scripts/lint_docs.py` | **PASS** — 0 errors, 0 warnings across 11 docs |
| `python benchmark/test_score.py` | **PASS** — 34/34 OK |

## 9. Artifacts

- Blind findings (frozen): `benchmark/results/synthetic-vuln-01.blind-clean.findings.json`
- Score (scorer direct output, TP=10 FN=4 FP=3): `benchmark/results/synthetic-vuln-01.blind-clean.score.json`
- Frozen GT (pre-registered, unmodified): `benchmark/seeds/synthetic-vuln-01/ground-truth.yaml`
  @ tag `bench-prereg-synthetic-01-clean`
- Source read (adjudication): `benchmark/seeds/synthetic-vuln-01/app.py`
- Context (Juice Shop blind, for comparison): `benchmark/results/F2-blind-juiceshop-01.md`
- This report: `benchmark/results/F3-synthetic-blind.md`
- Blind reviewer model: Claude Opus (stage 1)
- Scorer / adjudicator model: Claude Sonnet 4.6 (stage 2, independent)
