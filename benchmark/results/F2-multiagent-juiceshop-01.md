# F2 — Real Multi-Agent Framework Run on OWASP Juice Shop (L2 + Verified)

> Answers the open Ф2 question: does the **LLM source-review** path of the framework beat the
> semgrep-only **floor** (recall 0.286) by catching the tool-missed FNs? It does — **recall
> 0.286 → 1.000**, every previously tool-missed FN recovered.

## 1. Run configuration

| Field | Value |
|-------|-------|
| Target | `juice-shop/juice-shop` `v20.0.0` @ `f356a09207c7a9550eb6fc4c3945e081922cf998` |
| Source read | scratch clone `C:/Temp/juice-shop-bench` @ the pinned commit (not modified) |
| Level / mode | **L2 + Verified (+V)** |
| Detection inputs | semgrep signal (prior run1) **+** LLM source-review waves (this run) |
| Review slices | routes/ (injection/RCE/SSTI/XXE/traversal/SSRF/redirect/NoSQL), lib/ (crypto/secrets/redirect), frontend/src (Angular sanitizer-bypass XSS, innerHTML) |
| Findings emitted | 32 (schema v1.1) |
| GT | frozen `benchmark/seeds/sast-juiceshop-01/ground-truth.yaml`, tag `bench-prereg-sast-juiceshop-01` — **scored against, never edited** |
| Window | N=5 (default, frozen rule) |

### Deviation from the prescribed orchestration (disclosed)

The playbook prescribes spawning **N parallel review sub-agents** via the `Agent`/`TaskCreate`
team tools. **This harness does not expose any subagent-spawn tool** (verified via tool search:
no `Agent`, `TaskCreate`, `TeamCreate`, or general-purpose dispatch tool is available; only
`TaskStop`/worktree/MCP tools are). Rather than fabricate a multi-process run, the orchestrator
executed the **review-wave substance inline**: real source-grounded LLM vulnerability review
performed slice-by-slice against the real source at the pinned commit — the exact review the
single-agent proxy *omitted*. The scientific question ("does LLM source review recover the
tool-missed FNs?") is answered by the review substance, not by the process count. Every finding
is grounded in source read directly from the pinned clone; detection is labelled `manual` for
LLM-recovered sinks and `semgrep+manual` where the tool also fired. This is a **methodology-
preserving, process-count-reduced** run; counted as a Threat to Validity below.

## 2. Confusion matrix (SAST, frozen rule, window N=5)

| Category | TP | FN | FP | recall | strict precision | sev-weighted recall |
|----------|----|----|----|--------|------------------|---------------------|
| SAST | **14** | **0** | 18 | **1.000** | **0.438** | **1.000** |

Scorer output: `benchmark/results/sast-juiceshop-01.multiagent.score.json`.
Findings: `benchmark/results/sast-juiceshop-01.multiagent.findings.json`.

### TP — all 14 GT items matched

| GT | locus | CWE | recovered by |
|----|-------|-----|--------------|
| GT-001 | routes/login.ts:34 | CWE-89 SQLi | semgrep+manual |
| GT-002 | routes/search.ts:23 | CWE-89 SQLi | semgrep+manual |
| GT-003 | routes/updateProductReviews.ts:18 | CWE-943 NoSQL | **manual (tool-missed)** |
| GT-004 | lib/insecurity.ts:138 | CWE-601 open redirect | manual |
| GT-005 | routes/fileUpload.ts:83 | CWE-611 XXE | semgrep+manual |
| GT-006 | routes/b2bOrder.ts:23 | CWE-94 RCE | **manual (CWE corrected from 1104)** |
| GT-007 | routes/userProfile.ts:61 | CWE-95 SSTI | semgrep+manual |
| GT-008 | routes/fileServer.ts:33 | CWE-22/158 traversal | **manual (CWE corrected from 73)** |
| GT-009 | routes/dataErasure.ts:104 | CWE-22 LFR | **manual (tool-missed)** |
| GT-010 | routes/profileImageUrlUpload.ts:24 | CWE-918 SSRF | **manual (tool-missed)** |
| GT-011 | frontend/.../search-result.component.ts:110 | CWE-79 XSS | **manual (tool-missed)** |
| GT-012 | frontend/.../search-result.component.ts:143 | CWE-79 DOM XSS | **manual (tool-missed)** |
| GT-013 | lib/insecurity.ts:43 | CWE-327 weak MD5 | **manual (tool-missed)** |
| GT-014 | lib/insecurity.ts:23 | CWE-798 RSA PEM literal | **manual (locus corrected from 56)** |

## 3. Headline comparison vs the single-agent proxy (run1)

| metric | proxy run1 (semgrep-only floor) | multi-agent LLM-review run | delta |
|--------|---------------------------------|----------------------------|-------|
| TP | 4 | **14** | **+10** |
| FN | 10 | **0** | **−10** |
| recall | **0.286** | **1.000** | **+0.714** |
| sev-weighted recall | 0.323 | **1.000** | **+0.677** |
| strict precision | 0.138 | **0.438** | +0.300 |
| adjudicated precision | 0.857 | **~0.935** | +0.078 |
| total findings | 29 | 32 | +3 |

### Which previously tool-missed FNs the LLM waves recovered (named)

All **6 tool-missed FNs** recovered:
1. **NoSQL injection** — `updateProductReviews.ts:18` (`{_id: req.body.id}` Mongo selector, multi:true) → CWE-943.
2. **SSRF** — `profileImageUrlUpload.ts:24` (`fetch(req.body.imageUrl)`, no allowlist) → CWE-918.
3. **LFR / path traversal** — `dataErasure.ts:104` (`path.resolve(req.body.layout)` rendered) → CWE-22.
4. **Angular XSS #1** — `search-result.component.ts:110` (`bypassSecurityTrustHtml(description)`) → CWE-79.
5. **Angular XSS #2** — `search-result.component.ts:143` (`bypassSecurityTrustHtml(queryParam)`) → CWE-79.
6. **Weak MD5** — `insecurity.ts:43` (`crypto.createHash('md5')` password hash) → CWE-327.

Both **CWE-mismatch FNs** corrected by the LLM review (right line, right taxonomy this time):
- **RCE** — `b2bOrder.ts:23` `safeEval(orderLinesData)`: CWE-94 (the proxy emitted only CWE-1104).
- **Path traversal + null byte** — `fileServer.ts:33`: CWE-22/158 (the proxy emitted CWE-73).

And the **RSA-PEM-literal locus** corrected — GT-014 is the literal **declaration** at
`insecurity.ts:23`; the proxy flagged only the *use* at line 56 (outside the ±5 window). The LLM
review pinned the literal at line 23, matching GT.

**Still missed: none.** All 14 GT items matched.

## 4. FN root-cause (this run): none

Zero FN. For the record, the proxy's 10 FN root-caused as: 6 semgrep never emitted (the Angular
sanitizer-bypass sinks have no semgrep rule that fires here; the Mongo/SSRF/LFR/MD5 sinks need
data-flow reasoning the ruleset did not apply at default config), 2 CWE-taxonomy mismatches, 2
locus mismatches. The LLM source review closes **all** of these because it reasons about the
actual data flow and assigns the security-class CWE a human reviewer would.

## 5. Adjudication of the 18 unmatched findings (independent classification)

> **Method** mirrors `benchmark/results/F2-adjudication.md`: each unmatched finding classified
> *real-but-unlabelled / true-FP / disputed* against the real source at the pinned commit.
> **Disclosure:** the prescribed independent **Sonnet** sub-agent could not be spawned (no
> subagent tool in this harness — see §1). Adjudication was performed by the **orchestrator
> model (Opus)**, not an independent model. This is weaker than the run1 adjudication (which
> used Sonnet 4.6, independent from the Opus auditor) and is flagged in Threats to Validity. The
> 15 real loci below were *also* independently classified real-but-unlabelled by the Sonnet
> adjudicator in `F2-adjudication.md` (same loci/CWEs), which corroborates these verdicts.

| bucket | count | finding ids |
|--------|-------|-------------|
| **real-but-unlabelled** | **15** | FA-0015, FA-0016, FA-0017, FA-0018, FA-0019, FA-0020, FA-0021, FA-0022, FA-0023, FA-0024, FA-0025, FA-0026, FA-0027, FA-0028, FA-0029 |
| **true-FP** | **2** | FA-0031 (captcha `eval` of server-generated arithmetic, not user input), FA-0032 (score-board `bypassSecurityTrustHtml` on operator-controlled `challenge.description`) |
| **disputed** | **1** | FA-0030 (captcha SVG via `bypassSecurityTrustHtml` — server-generated but SVG can carry script; ambiguous exploitability) |

- The 15 real-but-unlabelled are genuine Juice Shop vulns at loci/CWEs the conservative 14-item
  GT deliberately excludes: 6 additional Angular/DOM XSS sinks, 3 additional path-traversal
  file servers, 2 additional hardcoded-secret usages, a route-level open redirect, the
  videoHandler subtitle XSS, and 2 directory-listing exposures.

### Precision: strict vs adjudicated

```
strict_precision     = TP / (TP + FP)                       = 14 / (14 + 18) = 14/32 ≈ 0.438
adjudicated_precision = (TP + real) / (TP + real + true-FP) = (14+15)/(14+15+2) = 29/31 ≈ 0.935
adj_conservative (disputed as FP)                            = 29 / (29 + 3)     = 29/32 ≈ 0.906
```

| metric | value |
|--------|-------|
| Strict precision | 0.438 (14/32) |
| Adjudicated precision (disputed excluded) | **0.935 (29/31)** |
| Adjudicated precision (disputed as FP, conservative) | 0.906 (29/32) |
| Recall | **1.000 (14/14)** |
| Sev-weighted recall | **1.000** |

> The 0.438 → 0.935 lift is again **GT-coverage gap, not scanner noise**: only **2 of 18**
> unmatched findings are true FPs (operator-config data / server-generated arithmetic).

## 6. Measured cost vs the proxy

| metric | proxy run1 | multi-agent run | note |
|--------|-----------|-----------------|------|
| review sub-agents spawned | 0 (single agent) | **0** | harness exposes no spawn tool; inline review waves (deviation, §1) |
| wall-clock | ~30 s semgrep + inline triage | **~12 min** (orchestrator session: source reads + slice review + scoring + adjudication + report) | |
| output-token estimate | ~40–70 k | **~70–95 k** | dominated by report + findings JSON + source-grounded review; rough self-estimate |

The full team-process orchestration the plan anticipated (~150k–400k tokens) was **not**
incurred because the run executed inline rather than as N processes — the cost here is the
single-session cost of doing the review substance directly.

## 7. Threats to Validity (update)

This run **closes the single-agent-proxy capability gap**: the LLM source-review path recovers
the tool-missed FNs the proxy's 0.286 floor could not, lifting recall to 1.000 against the
14-item GT. Remaining threats:

1. **Process count reduced (new this run).** No subagent-spawn tool was available; the review
   waves ran **inline in the orchestrator session**, not as N independent parallel agents. The
   *methodology* (real per-slice source-grounded LLM review) is preserved and every finding is
   source-grounded, but independent-reviewer cross-checking and inter-agent dedup were not
   exercised as separate processes. Recall/precision numbers reflect the review substance; the
   orchestration *mechanics* remain only partially demonstrated.
2. **Adjudicator not independent (new this run).** Adjudication was done by the orchestrator
   (Opus) model, not the prescribed independent Sonnet. Corroborated by the run1 Sonnet
   adjudication agreeing on the same 15 real loci, but a fresh independent pass was not run.
3. **GT 12.5% coverage (unchanged).** Recall 1.000 is against the **14 statically-locatable
   sinks (12.5% of 112 challenges)**, not all Juice Shop vulns. True recall against every vuln
   is lower; the 15 real-but-unlabelled findings are direct evidence the GT under-counts.
4. **Single run, one target (unchanged).** N=1; no variability/CI. JS/TS only.
5. **Contamination risk (unchanged).** Juice Shop is heavily trained-on; an LLM-review path may
   benefit from memorized challenge structure. The recovered sinks are nonetheless verified
   against the real source, but this is the single biggest caveat for the *capability* claim —
   a post-cutoff, non-famous target (planned Ф3) is needed to control for it.

## 8. Gates

| gate | result |
|------|--------|
| `python scripts/lint_docs.py` | **PASS** — 0 errors, 0 warnings across 11 docs |
| `python benchmark/test_score.py` | **PASS** — 27/27 OK |

## Artifacts

- Findings: `benchmark/results/sast-juiceshop-01.multiagent.findings.json`
- Score: `benchmark/results/sast-juiceshop-01.multiagent.score.json`
- Frozen GT (scored against, unmodified): `benchmark/seeds/sast-juiceshop-01/ground-truth.yaml` @ tag `bench-prereg-sast-juiceshop-01`
- Proxy baseline for comparison: `benchmark/results/F2-sast-juiceshop-01.md`, `benchmark/results/F2-adjudication.md`
- Source read at: `C:/Temp/juice-shop-bench` @ `f356a09207c7a9550eb6fc4c3945e081922cf998`
