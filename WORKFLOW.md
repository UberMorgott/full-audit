# full-audit Dynamic Workflow

Maintainer reference for `.claude/workflows/full-audit.js` — the source of truth.
Every name/field below is matched to that file. Where this doc and the code could
appear to disagree, the **code wins**; such points are flagged inline as **[discrepancy]**.

---

## 1. What this is

- A reusable Claude Code **Dynamic Workflow** living at `.claude/workflows/full-audit.js`.
- It runs the heavy, **read-only** audit waves + scoring of the full-audit system (**v1.14.2 engine**) and returns **ONE structured findings object**.
- It is **NOT** the audit logic rewritten. The following are preserved **verbatim from the full-audit README v1.14.2**:
  - severity scale and confidence scale
  - report format / integrity rules
  - false-positive (FP) whitelist
  - Iron-Law verification gate
  - prohibited unverified phrases
- The workflow changes only the **ORCHESTRATION mechanism** (how agents are fanned out across waves and how results are merged).
- **Recall-first features are layered ON TOP** (they EXTEND, never replace):
  - `suspected_unconfirmed[]` — sub-threshold / FP / failed-verification findings are demoted, never dropped
  - `coverage{}` block — what was inspected vs. not, bug classes out of static reach, uncertainty notes
  - **adversarial hunt** (Wave 3) — assume-a-bug-exists reasoning
  - **depth funnel** — spend effort on critical modules + prior-signal zones, but still touch all scope once
- Source comment (lines 16-23) states this explicitly: domain logic preserved, recall-first additions layered on.

---

## 2. Session vs Workflow split (the hard boundary)

A background workflow returns only a **final result** and **cannot prompt mid-run**, so everything interactive stays in the conversational session.

### IN SESSION (NOT in the script)
- **Phase 0**:
  - eligibility check
  - stack detection
  - MCP/CLI health checks
  - briefing
  - depth + approach selection
  - install-command approval
- **The entire fix phase**:
  - TDD
  - challenge protocol
  - two-stage fix review
  - 3-attempt STOP rule
- **Every user-approval gate.**

### IN THE WORKFLOW (the script)
```
Wave 1   CLI scan + version/CVE research
   ->
Wave 2   code review (diff / history / impact / comment / convention)
   ->
Wave 2.5 reproduction  (verified mode or L3)
   ->
Wave 3   deep reviewers + adversarial hunt  (L3 only)
   ->
Scoring  confidence 0-100, reproduction override, threshold filter, recall-first demotion
   ->
Verify   Iron-Law fresh-evidence re-run on CRITICAL/HIGH + security
   ->
Assemble coverage + audit_limitations + summary -> structured output
```
(The `phases` array at the top of the file, lines 4-13, mirrors this exactly: Validate, Wave 1, Wave 2, Wave 2.5, Wave 3, Scoring, Verify, Assemble.)

### Known Phase-0 bug to guard
- The session **sometimes skips asking audit depth/approach and silently defaults**. This is the bug to defend against.
- Phase 0 **MUST hard-gate** the depth/approach question.
- The workflow **ABORTS** (throws) if `args.level` / `args.approach` are missing or invalid — there is **NO silent default**. See `validateArgs()` (lines 288-313) and the abort at lines 506-509:
```js
const verrs = validateArgs(args)
if (verrs.length) {
  throw new Error('full-audit: invalid args — aborting (no silent defaults):\n- ' + verrs.join('\n- '))
}
```

---

## 3. How Phase 0 produces `args`

Phase 0 (in session) assembles the `args` object that the workflow consumes. The **full input contract** is enforced by `validateArgs()` and read throughout the prompt builders. Every field:

| Field | Type / shape | Notes (from code) |
|---|---|---|
| `stack` | `{ type, packages: [{ root, stacks:[], manifests:[] }] }` | `packages[]` must be non-empty array (validation). `(stack, package)` pairs expanded at line 543-544; only stacks present in `STACK_TOOLS` are kept. |
| `scope` | `{ paths, critical_modules, exclusions, focus, compliance }` | `paths` must be an array; `focus` must be `security` \| `quality` \| `full`. `critical_modules`, `exclusions`, `compliance` are optional (default `[]` in header). |
| `scope.product_purpose` | string (**optional**) | The project's stated purpose/intent. Consumed **only** by the L3 `purpose-fit` reviewer (line 472, `(a.scope && a.scope.product_purpose) \|\| ''`). If absent, the **feature-relevance** sub-check (#1) is **skipped** and a limitation `{ capability:"product_purpose", status:"not provided", impact:"feature-relevance check skipped" }` is recorded. **Not** enforced by `validateArgs()`. |
| `level` | `1` \| `2` \| `3` \| `'S'` | No default — validated against `[1,2,3,'S']`. |
| `verified` | bool | the **+V** flag. Drives Wave 2.5 even outside L3 (`runRepro = a.verified || isL3`, line 518). |
| `approach` | `broad` \| `security` \| `targeted` | No default. `security` (or `focus==='security'`) sets `securityOnly` (line 545), which trims Wave-3 quality/arch/ui reviewers. |
| `tool_status` | `{ mcp:{...}, cli:{...} }` | **mcp**: per-server `{ live, prefix }` for `serena`, `playwright`, `context7`, and `sequential_thinking`. **cli**: per-tool `{ installed, version }`. Both `mcp` and `cli` required. |
| `project_rules` | string (CLAUDE.md text or `''`) | Must be **present** even if empty. Sliced to 4000 chars in the header; OVERRIDES generic checks. |
| `project_root` | string (absolute path) | Required, non-empty. |
| `spec_root` | string (absolute path) | Path to full-audit checklist files (`go.md`, `universal.md`, `frontend.md`, ...). Agents read `{spec_root}/{stack}.md`. |
| `commit` | string | HEAD sha, or the literal `"uncommitted"`. Required (may be empty string per `typeof === 'string'` check). |
| `date` | string `YYYY-MM-DD` | **Passed in** because `Date.now()` is unavailable in workflow scripts. Required. |
| `artifact_dir` | string (optional) | If omitted, defaults to `<project_root>/audit` (line 515, platform separator chosen from `project_root`). |
| `git_baseline` | string (**optional**) | `git status --porcelain` captured by Phase 0 **before** the run. Consumed only by the **Guard** phase: if present, the read-only guard reverts (via `git checkout -- <file>`) any tracked file the audit changed that is NOT in this baseline; if absent, the guard **reports only** (no auto-revert, to avoid clobbering pre-existing user edits). **Not** enforced by `validateArgs()`. |
| `stack_profile` | `{ has_http_surface, has_auth, has_db, has_container, has_package_manager, has_runtime_config, is_runnable }` (**optional**) | Phase-0 capability vector (all booleans). Threaded into every agent's `header()` as the STACK PROFILE block — an absent capability makes its universal.md/stack.md web-service/NuGet sections a **clean documented SKIP** (one-line limitation), never a finding/BLOCKER/re-review. `is_runnable=false` also steers Wave 2.5 to static verification (`STATIC_CONFIRMED`) instead of runtime pretence. **Not** hard-enforced by `validateArgs()` (only shape-checked when present); omit → every capability treated as UNKNOWN (apply a section only when the read code exhibits its trigger). |

> **[discrepancy] `tool_status.mcp` key naming:** the brief lists `sequential_thinking` under `mcp`. The code's `mcpBlock()` reads `m.sequential_thinking.live` (underscore) for the fixed `mcp__sequential-thinking__sequentialthinking` tool, and reads `m.serena` / `m.playwright` / `m.context7` `{ live, prefix }` for the others. So the key is `sequential_thinking` (underscore), consistent with the brief.

> **[discrepancy] `tool_status` keys are NOT validated individually.** `validateArgs()` only checks that `a.tool_status.mcp` and `a.tool_status.cli` exist (lines 302-303). Missing per-server entries default to `{}` and are treated as **DOWN** (graceful degradation), not an abort.

### Concrete example `args` (small single-stack Go project, L2)
```json
{
  "stack": {
    "type": "single",
    "packages": [
      { "root": "E:/DEV/acme/svc", "stacks": ["go"], "manifests": ["go.mod"] }
    ]
  },
  "scope": {
    "paths": ["E:/DEV/acme/svc"],
    "critical_modules": ["internal/auth", "internal/billing"],
    "exclusions": ["vendor/", "**/*_gen.go"],
    "focus": "full",
    "compliance": []
  },
  "level": 2,
  "verified": false,
  "approach": "broad",
  "tool_status": {
    "mcp": {
      "serena":              { "live": true,  "prefix": "mcp__plugin_serena_serena__" },
      "playwright":          { "live": false },
      "context7":            { "live": true,  "prefix": "mcp__plugin_context7_context7__" },
      "sequential_thinking": { "live": true }
    },
    "cli": {
      "go":            { "installed": true,  "version": "1.23.0" },
      "staticcheck":   { "installed": true,  "version": "v0.7.0" },
      "govulncheck":   { "installed": true,  "version": "v1.3.0" },
      "golangci-lint": { "installed": true,  "version": "v2.12.2" },
      "gosec":         { "installed": false }
    }
  },
  "project_rules": "# Project rules\n- errors wrapped with %w\n- no panics in library code\n",
  "project_root": "E:/DEV/acme/svc",
  "spec_root": "E:/DEV/Fullaudit/full-audit",
  "commit": "d861964",
  "date": "2026-06-05"
}
```

### On invalid args
- The script **aborts via `throw`** with a clear message that **lists each validation failure** as a bullet (lines 507-509). No silent default is ever applied.

---

## 4. Output contract

The workflow `return`s one object (lines 722-741), assembled in the **Assemble** phase. Each finding passes through `cleanFinding()` (lines 711-720).

### Top-level shape
```js
{
  schema_version: '1.1',
  audit: { level, verified, approach, focus, date, commit, scope },   // scope = scope.paths
  artifact_dir,                 // all on-disk junk lives here; delete to clean up; add to .gitignore
  summary: { critical, high, medium, low, health },
  findings: [ /* confirmed, sorted */ ],
  suspected_unconfirmed: [ /* demoted, same shape, NEVER dropped */ ],
  coverage: { inspected, not_inspected, bug_classes_out_of_static_reach, uncertainty_notes, note },
  audit_limitations: [ { capability, status, impact } ],
  read_only_violations: { repo_is_git, changed_files, reverted, note },  // read-only Guard result
}
```

- `summary.health` (line 705): `CRITICAL` if any critical; else `NEEDS_WORK` if any high+medium; else `PASS`.

### Per-finding shape (from `cleanFinding`)
- `id` — `FA-0001` style, zero-padded, assigned by `tag()` (line 522).
- `severity` — `CRITICAL` \| `HIGH` \| `MEDIUM` \| `LOW` (may be adjusted by scoring/reproduction).
- `file`, `line`, `end_line?`
- `cwe?`, `cve?` (emitted only when non-empty)
- `title`, `detail` (both run through `stripPhrases`), `snippet` (3-5 line excerpt)
- `detection_method` — `tool` \| `manual` \| `adversarial`
- `confidence` — `0-100`
- `reproduced` — lowercased repro result or `'n/a'` (admits `'static-verified'` from a `STATIC_CONFIRMED` verdict)
- `verification_command` — string or `null` (repurposed `repro_command`: the grep/read that PROVES the claim on static-only stacks, or the failing test / CLI for runnable code)
- `repro_tag?` — `'reproduced'` \| `'static-verified'` \| `'unverified'` \| `'unverified: requires runtime'`
- `related_invariant?` / `design_ref?` — canon/invariant + design-doc linkage (architecture/canon findings)
- `evidence_commits?` — git SHAs cited as evidence (history/regression reviewers)
- `evidence?` — from scoring (`s.evidence`)
- `verify_command?`, `verify_exit`, `verify_evidence?` — from the Verify gate
- `origin` — wave/agent that produced it, e.g. `wave2:impact-reviewer-go`
- `demoted_reason?` — set when verification gate demotes (`'verification gate: fresh evidence did not confirm'`)

> **[discrepancy / clarification] `suspected_unconfirmed` is NOT a separate schema.** The brief says it has "the same shape" — confirmed: it is produced by the **same `cleanFinding`** mapper (line 729). There is no separate `needs-human` flag field; the **semantics** ("needs human") are carried by the array name plus `demoted_reason` / low `confidence` / `repro_tag`.

### `coverage` block
- `inspected` — de-duped union of every agent's `inspected[]`
- `not_inspected` — in-scope-but-not-read + why
- `bug_classes_out_of_static_reach` — from agents' `bug_classes_out_of_reach`
- `uncertainty_notes` — de-duped, capped at **50** entries (line 734)
- `note` — fixed string clarifying that "clean" means "inspected and found nothing in named classes", not silence.

### `audit_limitations`
- Array of `{ capability, status, impact }`, **de-duped** by `capability|status` (lines 708-709). Sources: every agent's `limitations[]`, plus orchestrator-added limitations (e.g. Playwright-absent at L3).

### `read_only_violations`
- Produced by the **Guard** phase (runs unconditionally, all levels; no-op when not a git repo or nothing changed).
- Shape `{ repo_is_git, changed_files, reverted, note }`:
  - `repo_is_git` — false when `project_root` is not a git repo (guard is then a clean no-op).
  - `changed_files` — repo-relative paths the audit appears to have modified (not in `git_baseline`); `[]` if none.
  - `reverted` — files actually restored via `git checkout -- <file>`. Non-empty **only** when `git_baseline` was supplied; `[]` in report-only mode.
  - `note` — short human summary.
- When `changed_files` is non-empty, the guard also pushes a `read-only integrity` entry into `audit_limitations`.

### Recall-first guarantee
- **Nothing is silently discarded.** Sub-threshold, `FALSE_POSITIVE` verdict, and failed-verification findings are **demoted to `suspected_unconfirmed`** instead of deleted (scoring loop lines 659-660; verify gate line 681).

### What the session does with this object
- The **session** renders the markdown report from this object and runs the **final report-integrity gate**. The workflow does not emit markdown or write the report file.

---

## 5. Model routing & waves

### Model tiers (lines 25-26)
| Tier | Model | Used by |
|---|---|---|
| `FAST` | `haiku` | cli-scanner(s), cli-scanner-universal, waste-scanner, scoring-agent |
| `RESEARCH` | `sonnet` | web-researcher |
| `DEEP` | `opus` | all Wave-2 reviewers, reproduction-agent, all Wave-3 reviewers, adversarial-hunt, verify-gate |

### Per-level wave matrix (from the gating conditions in code)
| | **L1** | **L2** | **L3** | **'S'** |
|---|---|---|---|---|
| Wave 1 (cli/universal/waste/research) | cli-scanner per stack **only** | full Wave 1 | full Wave 1 | full Wave 1 |
| Wave 2 (deep review) | — (skipped) | yes | yes | yes |
| Wave 2.5 (reproduction) | — | **only if `verified`** | **always** | only if `verified` |
| Wave 3 (deep + adversarial) | — | — | yes | — |
| Scoring agent | **no agent** — reviewers self-apply `>=75` inline | yes | yes | yes |
| Threshold | **75** | **60** | **40** | **60** |

Notes tied to the code:
- **L1**: `if (L !== 1)` skips universal/waste/web-researcher in Wave 1 (lines 552-556) and skips Wave 2 entirely (line 562). L1 has **no scoring agent**; raw tool findings are treated as confirmed (lines 629-632).
- **Wave 1 universal/waste/research** only run when `L !== 1`.
- **Wave 2.5** gate: `runRepro = a.verified || isL3` (line 518). Operates on CRITICAL/HIGH findings, batched **~10 per reproduction-agent** (line 581).
- **Wave 3** gate: `if (isL3)` (line 617) — L3 only. Adds stack `code-reviewer` + `logic-reviewer` per stack, `code-reviewer-security`, and (unless `securityOnly`) `code-reviewer-quality`, `arch-reviewer`, **`purpose-fit`** (line 630), conditional `ui-reviewer`, plus the **adversarial hunt** (batched ~12 zones per agent).
- **`purpose-fit` reviewer** (DEEP, L3, inside the `if (!securityOnly)` block — so **skipped when `approach==='security'` or `focus==='security'`**, alongside quality/arch/ui). Covers three high-FP scope-coherence classes (`purposeFitPrompt`, lines 471-483):
  1. **Feature relevance** (feature creep / boat anchor) — working, **reachable** features/modules/endpoints/screens NOT traceable to `scope.product_purpose`. This is **NOT** dead code (waste-scanner covers unreachable/unused). **Skipped + limitation recorded** if `product_purpose` is absent.
  2. **Tech/pattern adoption consistency** — a declared tech/pattern half-adopted or run alongside a parallel implementation (e.g. Tailwind on half the UI + hand CSS elsewhere; two HTTP clients; two state stores). Cites file:line for each side.
  3. **Redundant defenses & log noise** — guards/logs for impossible states, dead defensive branches with no reachable trigger, leftover debug logging. Excludes legitimate defense-in-depth (untrusted input, concurrency, external I/O).
  - **HIGH false-positive class.** Severity is **hard-capped at MEDIUM in code** (line 679: `purpose-fit` origin + `CRITICAL`/`HIGH` -> `MEDIUM`); never CRITICAL/HIGH. Defaults **LOW**, never inflated. Uncertain calls are STILL emitted -> demote to `suspected_unconfirmed` (recall-first, needs human). `detection_method:"manual"`, `origin "wave3:purpose-fit"`.
  - Canonical checklist lives in `{spec_root}/universal.md` section **"Level 3: Purpose-Fit & Scope-Coherence"**.
- **Scoring** batches **~20 findings per scoring-agent** (line 634). Threshold from `THRESHOLD = { 1:75, 2:60, 3:40, S:60 }` (line 29).
- **Reproduction override** (applied after scoring, before threshold):
  - `REPRODUCED` -> confidence floor **90**, tag `reproduced`
  - `STATIC_CONFIRMED` -> confidence floor **85**, tag `static-verified`, **severity UNCHANGED** (a structurally-certain runtime-latent finding is NOT demoted — severity is decoupled from reproduction-confidence). For non-runnable stacks (`is_runnable=false`), Wave 2.5 verifies the structural claim by code read instead of faking a runtime run; the reproduction/verify prompts classify `STATIC_CONFIRMED` / `SKIPPED_RUNTIME` / `NOT_REPRODUCED` accordingly.
  - `NOT_REPRODUCED` -> confidence cap **25**, **severity -1**, tag `unverified`
  - `SKIPPED_RUNTIME` -> confidence unchanged, tag `unverified: requires runtime`

> **[discrepancy] 'S' threshold is explicit, not "routed like L2".** The brief calls 'S' "routed like L2 thresholds". In code `THRESHOLD.S` is its own key `= 60` (equal to L2). Behaviorally identical, but it is an explicit entry, and 'S' also follows L2-style wave gating because `L !== 1` is true and `isL3` is false. The `cliScannerPrompt` level expansion (line 406) gives 'S' the `['L1','L2']` ladder (same as L2).

---

## 6. MCP-inheritance finding (explicit research question)

- **FINDING:** workflow-spawned subagents **DO inherit the session's MCP connections**. They can reach all session-connected MCP tools via **ToolSearch** (per the Workflow tool contract). So **no need to pre-collect MCP outputs in the session**.
- **Implemented approach:** agents **discover their MCP tool prefix at runtime**. `mcpBlock()` (lines 322-345) tells each agent the **expected** prefix + liveness from `args.tool_status.mcp`, then instructs it to confirm the exact prefix via `ToolSearch query "<server>"`. Plugin installs expose:
  - `mcp__plugin_serena_serena__`
  - `mcp__plugin_playwright_playwright__`
  - `mcp__plugin_context7_context7__`
  - Sequential-Thinking is **fixed**: `mcp__sequential-thinking__sequentialthinking` (constant `SEQ_THINKING`, line 56).
- **Caveat recorded:** interactively-authenticated MCP servers (e.g. claude.ai Gmail / Calendar / Drive) may be **ABSENT in headless / cron runs**. The four audit MCPs (Serena / Playwright / Context7 / Sequential-Thinking) are **plugin servers** and are available.
- **Graceful degradation** (each gap recorded as an Audit Limitation, lines 337-341):
  - **Serena down** -> fall back to Grep / Read / Glob (no semantics — slower)
  - **Playwright down** -> SKIP live DOM checks entirely
  - **Context7 down** -> proceed without live docs; flag higher error risk
  - **Sequential-Thinking down** -> linear reasoning

Which roles get which MCP servers (from the prompt-builder `mcpServers` args):
- `web-researcher` -> `context7`
- Wave-2 reviewers -> `serena`
- `ui-reviewer` -> `playwright`
- `adversarial-hunt` -> `serena`, `sequential-thinking`
- Wave-3 `code-reviewer`, `code-reviewer-security`, `code-reviewer-quality` -> `serena`, `context7`; `logic-reviewer`, `arch-reviewer` -> `serena`
- `scoring-agent` -> `serena`
- cli-scanner / universal / waste / reproduction / verify-gate -> **no MCP** (`[]`), pure CLI/file work.

---

## 7. Artifact folder (single-folder cleanup)

- All on-disk junk subagents create — scratch tests, scanner reports (e.g. `gitleaks --report-path`), per-agent raw findings dumps, temp files — is confined to **ONE folder: `args.artifact_dir`** (default `<project_root>/audit`).
- Subfolders referenced in the header (lines 377-381):
  - `raw/` — each agent writes its StructuredOutput JSON to `{artifact_dir}/raw/{role}.json` for background-run visibility
  - `scratch/` — reproduction-agent test/scratch files go here only
  - `tmp/` — `$TMP` / `$ARTIFACT` expand to `{artifact_dir}/tmp`
- **Cleanup:** delete `artifact_dir` to clean up; add it to `.gitignore`.
- The **workflow script itself has NO filesystem access** — this discipline is enforced via the **agent prompt headers** (the ARTIFACTS rule), not by the script.

---

## 8. How to save & invoke as a command

- It already lives at `.claude/workflows/full-audit.js` (**project-level, checked into the repo**).
- Invoke via the **Workflow tool by name** with args:
```js
Workflow({ name: 'full-audit', args: { /* the Phase-0 args object from section 3 */ } })
```
- Since **"ultracode"** is the standing opt-in to author/run workflows, the session runs this as part of the audit flow. **ultracode is the LAUNCH trigger, not a different artifact** — same `full-audit.js`.
- **Iterate:** edit the `.js`, re-invoke. Same `args` -> same control flow (deterministic; no `Date.now()`/randomness — `date` is injected, IDs are sequential).
- **Resuming:** use `resumeFromRunId` to resume a killed or edited run rather than restarting from Wave 1.

---

## 9. Iteration notes / known limitations

- **First draft** — intended to be exercised on real projects and corrected in parallel.
- **`purpose-fit` reviewer is NEW and high-FP** — added to Wave 3 (L3, non-security-only). Severity is code-capped at MEDIUM and it defaults LOW, but it is expected to over-fire; **intended to be tuned on real runs** (raise/lower the bar per class, sharpen the adoption-consistency and redundant-defense heuristics). Its **feature-relevance** sub-check is only meaningful when `scope.product_purpose` is supplied; without it that sub-check is skipped and a limitation is recorded.
- **Pin sync:** the per-stack tool catalog `STACK_TOOLS` (lines 61-175) and `UNIVERSAL_CLI` / `WASTE_STEPS` pins **must stay in sync with the full-audit `versions.lock`**. The workflow embeds a **representative subset**; agents also read `{spec_root}/{stack}.md` for the full **level-scoped** checklist.
- **'S' (specialized/API) level:** accepted by validation and routed with L2-equivalent thresholds, but the **API-specific 3-reviewer team (`api-audit.md`) is not yet specialized** in the wave plan. **TODO.** (In code, 'S' simply flows through the L2 path: Wave 1+2, scoring, verify; no api-specific agents are spawned.)
- **ui-reviewer** runs only if a **frontend stack is present AND Playwright is live AND a dev server URL is reachable**; otherwise it is skipped and a limitation is recorded:
  - frontend present + Playwright live -> `ui-reviewer` spawned (line 608)
  - frontend present + Playwright down -> orchestrator records `{ capability: 'Playwright UI', status: 'not available', impact: 'L3 functional UI testing skipped' }` (line 609)
  - the **dev-server reachability** check itself happens **inside the ui-reviewer agent** (`uiReviewerPrompt`, lines 464-469): no reachable URL -> agent SKIPs and records its own limitation.

> **[discrepancy] ui-reviewer is also gated by `!securityOnly`.** It lives inside the `if (!securityOnly)` block (lines 602-610). So in a `security` approach / `security` focus, the ui-reviewer (and quality/arch reviewers) are **not** spawned even at L3 with a live frontend — the brief's "frontend present AND Playwright live AND URL reachable" is necessary but the **`!securityOnly`** condition also applies.

---

## Appendix: domain constants preserved from the README (do not silently edit)

- `FP_WHITELIST` (lines 36-44) — 7 entries; matched findings are dropped / score 0.
- `PROHIBITED_PHRASES` (lines 47-51) — stripped from `title`/`detail` via `stripPhrases` (lines 688-694), replaced with `[unverified-claim removed]`.
- `IRON_LAW` (lines 347-350) — the 5-step "no claim without fresh evidence" gate, embedded in every agent header and re-run by the Verify phase.
- JSON schemas (`FINDINGS_SCHEMA`, `SCORING_SCHEMA`, `REPRO_SCHEMA`, `VERIFY_SCHEMA`, lines 202-283) — enforced at the StructuredOutput tool layer; a finding missing a required field is rejected before it can enter output (the agent retries).
