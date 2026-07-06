# RFC → full-audit v1.10.8 Integration Plan

Gap analysis of `AI_AUDIT_STANDARD_RFC.md` against the live system:
engine prompt `E:\DEV\Fullaudit\full-audit\universal.md` + workflow script `E:\DEV\Fullaudit\.claude\workflows\full-audit.js`.
Only `adopt`/`modify` proposals are carried below (with the critic's refined text); `already-done`/`reject` are in the appendix.

## Invariants (every item below preserves these)
- **Recall-first** — nothing dropped; sub-threshold / FP / failed-verification demote to `suspected_unconfirmed[]` (same schema via `cleanFinding`), never deleted. No item may add a hard-abort or a demotion that moves a verified finding out of `confirmed[]` for a missing prose field.
- **Read-only audit waves** — no writes to the repo tree; Guard phase reverts violations. All added fields are metadata, not fixes.
- **Deterministic workflow script** — no `Date.now()`/randomness/file-I/O in the script; values injected via `args`; same args → same control flow. New per-axis/cross-ref/changelog logic must be pure JS over already-computed data (or LLM-populated optional fields), never non-deterministic script authoring.
- **One structured findings object returned** — the workflow returns JSON; report rendering + report-integrity gate happen **in the conversational session**. No SVG/markdown/prose charts in the workflow output.
- **Phase 0 + fix phase stay in the session** — eligibility/stack/MCP/CLI/depth-gate and the TDD fix protocol are interactive, not in the script.
- Supporting: no-silent-defaults (`validateArgs` throws), Iron-Law fresh-evidence, StructuredOutput schema enforcement, model routing FAST=haiku / RESEARCH=sonnet / DEEP=opus.

## Honest assessment
v1.10.8 already implements the large majority of the RFC's *process* discipline and *evidence* rules: Iron-Law fresh-evidence verification, a 5-pass dedup + CVE↔GO vuln roll-up (this **exceeds** the RFC's single-merge requirement), the 8-category FP whitelist, prohibited-phrase stripping, confidence 0-100 with reproduction overrides, the severity model with a purpose-fit MEDIUM cap, scope documentation, and the recall-first two-array (`confirmed[]` / `suspected_unconfirmed[]`) output. The genuinely **new** value clusters in three narrow areas: (1) per-finding actionability the engine's README schema had but the JS port dropped or never added — `recommendation`/minimal-fix (an outright regression) and `root_cause`; (2) report organization the flat findings array lacks — `category`, per-axis health `scores`, and systemic-pattern cross-referencing; (3) a capability the engine wholly lacks — cross-run `audit_changelog`. Most of the RFC's "16 mandatory fields on **every** finding", its game-domain sections (Savegame/Modding/AI), and its rendered heatmaps directly conflict with this system's two-tier FAST→DEEP pipeline, token budgets, anti-fabrication ethic, and object-not-prose contract, and were correctly rejected or narrowed to optional/L3-only. Net: roughly **65-75% of RFC intent already satisfied**; the adopted 9 items are targeted, mostly-additive optional-field changes that respect every invariant. Two adversarial-critic passes ran per lens; where they split (PG-5, PG-6, FE-2, FE-4, FE-6, FE-10) the reconciled verdict is noted.

### RFC coverage counts per lens
| Lens | Covered (already-done) | Missing (proposals) | Conflicts |
|---|---|---|---|
| finding-evidence | 11 | 10 (FE-1..10) | 3 |
| process-gates | 14 | 6 (PG-1..6) | 3 |
| report-scoring | 6 | 8 (RS-1..8) | 2 |
| **adopted after reconciliation + dedup** | — | **9 items** (2×P0, 6×P1, 1×P2) | — |

---

## P0 — directly improves finding correctness / actionability

### P0-1 · Restore `recommendation` (minimal-fix) field  *(FE-3)*
- **WHAT** — Add **optional** `recommendation` (string: a minimal, behavior-preserving fix) to `FINDING_PROPS`; do **not** add to `FINDING_REQUIRED`; emit it in `cleanFinding`. Route reviewers' existing "problem. fix." prose into it. Never demote a finding for an empty `recommendation` (a FAST cli-scanner finding may legitimately have none). This restores engine schema_version-1.1 parity (README `recommendation` at 1021/1035) that the JS port dropped — a regression, not a new feature.
- **FILES** — `full-audit.js`: `FINDING_PROPS` (204-218), `cleanFinding` (1603-1622); reviewer prompt text `wave2Prompt` (~985) + Wave-3 reviewers to route fix-prose. `universal.md` Recommendations/YAGNI (250-278) already covers the guidance.
- **EFFORT** — S
- **RISK** — Optional field ⇒ schema stays backward-compatible, agents omitting it still validate. Low. **Smoke** (`full-audit.smoke.js`): confirm the finding-shape assertion tolerates the new optional key and `cleanFinding` still emits deterministically.

### P0-2 · Add optional `root_cause` (+ blast-radius / prevention via prompt)  *(FE-1, folds FE-2)*
- **WHAT** — Add **optional** `root_cause` string to `FINDING_PROPS`; emit in `cleanFinding`. Populate **only** from Wave-3 DEEP reviewers / adversarial-hunt (which already perform L3 RCA per `universal.md` 905-954 "Root Cause / Fix / Prevention"), **never** from the FAST scoring agent (240-char truncated input, batched 20 — cannot author RCA). **No demotion gate**: an empty `root_cause` must never change confidence/severity/bucket (would break recall-first + the verify gate's fresh-evidence-only admission at 1445). *FE-2 folded in:* instruct DEEP reviewers to state who/what breaks (blast radius) and an optional "Prevention:" clause **inside** the same `root_cause`/`detail` prose — do **not** add a separate `impact` field (name collides with the limitations `impact` at `FINDINGS_SCHEMA` 236-237).
- **FILES** — `full-audit.js`: `FINDING_PROPS` (204-218), `cleanFinding` (1603-1622); Wave-3 reviewer + adversarial-hunt prompt text (~981-986, adversarial ~1055-1064). `universal.md` L3 RCA (905-954).
- **EFFORT** — M
- **RISK** — Optional, L3-only population ⇒ no effect on L1/L2 or FAST agents. **Must wire no demotion** (recall-first guard). **Smoke**: confirm optional key tolerated; verify-gate behavior unchanged.

---

## P1 — improves report quality / traceability

### P1-1 · Optional `category` enum, JS-derived  *(RS-3 + FE-7, merged)*
- **WHAT** — Add **optional** `category` enum to `FINDING_PROPS`: `architecture|security|performance|code-quality|testing|concurrency|dependencies|tech-debt`. **Not** in `FINDING_REQUIRED` (adding it there would tool-layer-reject every current agent's findings). **Derive deterministically in Assemble** (zero agent tokens, respects determinism): `cwe`/`cve`/`advisory_id` → `security`|`dependencies` (extend `isSecurityClass` 422-425); `origin` reviewer-name → impact-reviewer→`architecture`, purpose-fit/quality→`code-quality`, concurrency→`concurrency`, ui→`code-quality`; unresolved → `code-quality`/`uncategorized`. An optional reviewer-supplied value overrides the derived one. Do **not** emit a `findings_by_category` block — the session groups by the field at render time. Drop the RFC's game-domain values (savegame/modding/ai) — no surface here; would create the hollow-positive sections the audit forbids.
- **FILES** — `full-audit.js`: `FINDING_PROPS` (204-218), Assemble derivation near summary (~1538) reusing `isSecurityClass` (422-425) + origin regex (~1571), `cleanFinding` (1603-1622).
- **EFFORT** — M
- **RISK** — Deterministic derivation keeps determinism; optional field keeps schema compatible; ambiguous-origin mislabel → default bucket (acceptable). Enabler for P1-2 / P1-3. **Smoke**: new optional key, no new top-level output key ⇒ shape unchanged.

### P1-2 · Per-axis health `scores{}` (tri-state)  *(RS-7; depends on P1-1)*
- **WHAT** — In Assemble emit an **additive** `scores{architecture,security,performance,code-quality,testing,concurrency,dependencies,tech-debt}` — do **not** touch `summary.health` (1538). Each axis = **tri-state reusing existing health semantics** over that axis's confirmed findings: `CRITICAL` if any CRITICAL member; `NEEDS_WORK` if any HIGH/MEDIUM; `PASS` if inspected and clean; `NOT_ASSESSED` when coverage shows zero inspection of that axis (an un-inspected axis is **never** a passing score). Include `member_finding_ids[]` and a count-based `rationale` string. **Drop the invented 0-100 / letter grade** (false precision — no calibrated model behind a per-severity subtraction formula).
- **FILES** — `full-audit.js`: Assemble output (~1639) after summary (1538); uses `coverage.inspected` (1647) for `NOT_ASSESSED`.
- **EFFORT** — M
- **RISK** — New top-level output key ⇒ smoke output-shape assertions may need updating. Additive; `summary.health` untouched ⇒ completion log (1659) safe. Requires P1-1 category first. This per-axis `{C,H,M,L}`+assessed structure **is** the RFC heatmap's data source (rendered in-session) — no separate `heatmap_matrix` key (see RS-4 appendix).

### P1-3 · Systemic-pattern cross-reference  *(RS-8 + PG-1 + FE-8, merged; incl. PG-5 CWE-canon)*
- **WHAT** — **(a) Prerequisite:** canonicalize the free-string `cwe` field to `/^CWE-\d+$/` inside `cleanFinding` (`cwe79`/`79` → `CWE-79`; empty stays empty). **(b)** Add a pure, deterministic `crossReferencePass(confirmed)` **after** `reconcileVulnRollup` (~1462): cluster confirmed findings sharing the same non-empty canonical CWE (and `category` once P1-1 lands); **LINK only, never merge** (dedup already owns exact/same-defect merges). Stamp **additive** `related_ids[]` on each clustered finding (add `related_ids` to `FINDING_PROPS` 204-218, pass through `cleanFinding`). Emit a thin `systemic_patterns[] = {key:'<category>:<CWE>', member_ids[], count}` output key. **Noise guards** (critics split on cross-file vs same-module): exclude SCA/advisory findings (owned by `vulnIdentityPass`/`reconcileVulnRollup`), cap cluster size (~8), default to linking within the same top-level module/dir (make the cross-file toggle configurable) so a generic CWE (e.g. CWE-79) can't form a codebase-wide noise-clique. **Drop** any JS-authored `suggested_systemic_fix`/`why_it_matters` prose — that is LLM synthesis, left to the in-session render/fix phase; L3 reviewers already emit "Pattern: systemic/isolated" (`universal.md` 948-950).
- **FILES** — `full-audit.js`: `cleanFinding` (1603-1622, CWE canon + `related_ids`), new pass after `reconcileVulnRollup` (~1462), `FINDING_PROPS` (204-218), Assemble output (~1639, `systemic_patterns`).
- **EFFORT** — M-L
- **RISK** — Over-linking on generic CWE → noise (mitigated by module-scope + size cap). LINK-not-merge preserves recall. CWE canonicalization is **upstream** of `groupBySameDefect`'s key (661) — verify dedup still behaves after normalization. New output key ⇒ smoke shape update.

### P1-4 · `methodology` provenance block  *(RS-2)*
- **WHAT** — In Assemble emit `methodology = {waves_run:[phases actually executed — level gating already determines this], tools_ran_ok:[...toolsRanOk], tools_incomplete:[tools whose limitation carries NEVER_SUPPRESS_STATUS — the timed-out/errored set], threshold:THRESHOLD[L], mcp_used:[live servers from a.tool_status.mcp]}`. Rename away from `tools_run` (collides with the per-agent field). **Carry `tools_incomplete`** so the block cannot overstate coverage — `toolsRanOk` (built 1564-1565, currently never surfaced) is success-only by FIX-A design (1560-1563); emitting it alone would re-introduce the exact overstatement the BUG-7/FIX-A apparatus prevents. **Drop** the `model_tiers` restatement (static config — belongs in docs).
- **FILES** — `full-audit.js`: Assemble output (~1639); `toolsRanOk` (1564-1565); `THRESHOLD`, `a.tool_status.mcp`.
- **EFFORT** — S
- **RISK** — New output key ⇒ smoke shape update. Omitting `tools_incomplete` would regress coverage-honesty. Additive, deterministic.

### P1-5 · Deterministic advisory `reference_url`  *(PG-3)*
- **WHAT** — In `cleanFinding`, deterministically construct an **optional** `reference_url` from the **already-verified** ids the pipeline holds — emit **only** when `f.cve`/`f.advisory_id` is set: `CVE-XXXX`→`nvd.nist.gov/vuln/detail/<id>`, `GO-XXXX`→`pkg.go.dev/vuln/<id>`, `GHSA-XXXX`→`github.com/advisories/<id>`. Fabrication-proof (built from a verified id, not a guessed URL); needs **no** change to the schema agents return and **no** agent prompt change. (Chosen over the agent-populated free-form `references[]` shape — avoids fabricated/variable-quality URLs, aligns with the system's anti-fabrication ethic.)
- **FILES** — `full-audit.js`: `cleanFinding` (1603-1622).
- **EFFORT** — S
- **RISK** — Very low — purely derived from existing verified ids; empty when no advisory id. **Smoke**: optional key tolerated.

### P1-6 · Cross-run `audit_changelog` via injected `prev_audit`  *(RS-6)*
- **WHAT** — Accept **optional** `prev_audit` as an **already-parsed OBJECT injected via `args`** (Phase 0 reads the prior run and injects it, exactly like `date`/`commit`) — do **not** open a file from the script (the script is I/O-free: only `agent()` + args). Add it to `validateArgs` (302-327) as optional. In Assemble emit `audit_changelog {new[], resolved[], persisting[]}` matched on the most stable identity available (prefer `advisory_id`/`cve`, then `cwe`+`file`, fall back to `normTitle`+`file` with an "uncertain"/heuristic note for fuzzy title-only matches). **Coverage-gate resolution:** classify `resolved` **only** when the file WAS inspected this run (`coverage.inspected` 1647) — a finding absent because its file wasn't inspected is `not_reassessed`, not resolved. Define `regressed[]` **only** when the prior artifact carries its own `audit_changelog.resolved` (current ∩ prior.resolved); otherwise omit that bucket. Absent arg → block omitted, zero behavior change.
- **FILES** — `full-audit.js`: `validateArgs` (302-327, optional `prev_audit`), Assemble output (~1639), uses `coverage.inspected` (1647). Phase 0 (conversational session) wires reading + injecting the prior run.
- **EFFORT** — L
- **RISK** — Fragile matching → false resolved/new churn (mitigated by stable-key preference + coverage gate + "uncertain" tag). New arg **must stay optional** (no-silent-default; `validateArgs` must not require it). Object-injection (not file I/O) preserves the deterministic, I/O-free invariant. New output key ⇒ smoke shape update; **smoke must still pass with `prev_audit` absent**.

---

## P2 — nice-to-have

### P2-1 · Title-only hedging lint  *(PG-4)*
- **WHAT** — At assembly, lint the **TITLE only** (titles must be declarative) of confirmed findings for claim-hedging tokens (`appears to`, `seems to`, `might be`, `possibly`, `may allow`, `likely`); record a count/list in `coverage.uncertainty_notes` (1651). **Never auto-delete** (hedging is legitimate in remediation prose). Do **not** scan the `detail`/remediation body (would fire on nearly every well-written finding — "you should sanitize", "likely exploitable"). Complements `PROHIBITED_PHRASES` (49-53), which strips only 11 fixed phrases and misses bare hedge words.
- **FILES** — `full-audit.js`: assembly near `stripPhrases` (1480-1486) / `coverage.uncertainty_notes` (1651).
- **EFFORT** — S
- **RISK** — Scope creep into `detail` → noise; keep title-only. Flag-not-delete preserves recall. `uncertainty_notes` capped at 50 (1651) — ensure lint entries don't crowd out real notes. **Smoke**: no output-shape change (reuses existing key).

---

## Execution order (each batch ends by running `full-audit.smoke.js`)

**Batch 1 — actionability field restorations (P0, lowest risk, engine parity).**
Items: P0-1 `recommendation`, P0-2 `root_cause` (+blast/prevention prompt). Both = optional `FINDING_PROPS` + `cleanFinding` + reviewer-prompt edits; no output-shape change, no gate. → run `full-audit.smoke.js`.

**Batch 2 — category + derived aggregates (interdependent; do together).**
Items: P1-1 `category` (must land first), then P1-3 systemic cross-ref (needs CWE-canon + category), then P1-2 per-axis `scores` (needs category). Adds `related_ids` (optional field) + two new output keys (`systemic_patterns`, `scores`). → update smoke shape assertions; run `full-audit.smoke.js`.

**Batch 3 — independent additive output blocks (leaf changes).**
Items: P1-4 `methodology`, P1-5 `reference_url`, P2-1 hedging lint. Independent of each other and of Batches 1-2. → run `full-audit.smoke.js`.

**Batch 4 — cross-run capability (touches `validateArgs` + Phase 0 wiring).**
Item: P1-6 `audit_changelog`. Isolated last because it adds an optional arg + a new output key and requires Phase 0 session wiring. Test both with `prev_audit` present and absent. → run `full-audit.smoke.js`.

---

## Appendix — rejected / already-done / folded (traceability)

| ID | Verdict | One-line reason |
|---|---|---|
| RS-1 Executive Summary | reject (both) | Every field re-projects existing data (`summary.health`, sorted `findings[]`, `suspected`+`not_inspected` counts); exec-summary is a session render concern. |
| RS-4 Heatmap matrix | reject / subsumed | No separate key — P1-1 `category` + P1-2 per-axis `scores` **are** the category×severity data; heatmap rendered in-session (object-not-prose contract). |
| RS-5 Remediation roadmap | reject (both) | Severity→timeline bucketing is a fixed convention derivable in-session from the already-severity-sorted findings; leverage-ordering folded into P1-3. |
| PG-2 Consolidated quality_gate object | reject (both) | Every criterion already guaranteed by construction (schema-required snippet, unconditional dedup/sort, scored confidence) ⇒ gate can never fail; ceremony + output bloat. |
| PG-5 Enum re-assert + normTitle-on-titles | reject | `detection_method`/`severity` already enum-enforced at schema layer; `normTitle` on emitted titles mangles display text. **CWE-canonicalization nugget folded into P1-3** as its prerequisite. |
| PG-6 Alternatives prompt guidance | reject (split: 1 modify / 1 reject) | Spirit already covered by RCA Phase 4 (`universal.md` 931-934) + YAGNI Check (252-278) + terse "problem. fix." discipline; low value; the actionable core is P0-1. |
| FE-2 `impact`/blast_radius field | folded → P0-2 | Name collides with limitations `impact`; kept as a who/what-breaks + Prevention clause inside the `root_cause`/`detail` prose, not a new field. |
| FE-4 `architectural_fix` field | reject (split: 1 fold / 1 reject) | Per-finding arch field reopens the rewrite-creep the purpose-fit MEDIUM cap (1404) closes; long-term guidance lives in arch-reviewer's own finding + optional Prevention clause in P0-2. |
| FE-5 `regression_risk` field | reject (both) | Regression risk is a property of a *proposed fix*, which a read-only audit never produces; speculative (violates no-guesses-as-facts); belongs to the separate in-session fix phase. |
| FE-6 `expected`/`actual` fields | reject (split: 1 reject / 1 narrow-modify) | Marginal: `actual` already captured as repro/verify `evidence`; `expected` needs intended behavior the repro-agent can't observe (intent-fabrication risk); mostly-empty for non-behavioral findings. |
| FE-9 `symbol` field | reject (both) | Audit runs at a pinned commit and is consumed immediately, so line-drift resilience is moot; `file:line`+3-5-line `snippet` already localize; `get_symbols_overview` can't cheaply return the enclosing symbol of an arbitrary line. |
| FE-10 `needs_manual_verification` | already-done | Signal already on the finding via `repro_tag='unverified: requires runtime'` / `reproduced='skipped_runtime'` / `demoted_reason`; only new part is rendering a "manual verification required" **label in-session** — no schema/js change. |

*Conflicts noted by the lenses (game-domain sections Savegame/Modding/AI; rendered graphs/heatmaps in the workflow output; literal "16 fields on every finding"; hard-aborting quality gate; literal "delete unsupported claims") were all resolved by adopting only the language-agnostic / additive / render-layer subset — never by weakening the recall-first, deterministic-script, or object-not-prose invariants.*
