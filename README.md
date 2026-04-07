# Full Audit

> **Version 1.3.0** — 2026-04-07

Universal codebase audit system for Claude Code. Works with any project, any stack, via GitHub reference.

**Supported stacks:** Go, JavaScript/TypeScript (Vue, React, Svelte, Angular), Python (Django, Flask, FastAPI), Rust, Java/Kotlin (Spring Boot), C#/.NET (ASP.NET Core, Blazor).

## Quick Start

User says:
```
сделай полный аудит проекта инструкции на github.com/UberMorgott/full-audit
```

Claude executes:
1. **Fetch this README** via WebFetch (`https://raw.githubusercontent.com/UberMorgott/full-audit/main/README.md`)
2. **Read project's `CLAUDE.md`** — project-specific code rules override generic checks
3. **Detect stack** (Phase 0 below)
4. **Fetch relevant files** from this repo (stack-specific + universal)
5. **Run audit** at requested level

### Audit Levels

| Level | Name | When | Time estimate (single stack / monorepo) |
|-------|------|------|----------------------------------------|
| 1 | Quick | Every release, CI | ~5-10 min / ~10-15 min |
| 2 | Full | Per sprint | ~20-35 min / ~40-60 min |
| 3 | Deep | Major release, quarterly | ~60-90 min / ~2-3 hours |
| S | Specialized | On demand (API request audit) | ~15-25 min |

User can request: "level 1", "level 2", "full audit" (= level 2), "deep audit" (= level 3).
Default if not specified: **level 2**.

---

## Files in This Repo

| File | Fetch when | Contents |
|------|-----------|----------|
| `README.md` | Always | This file: orchestration, workflow, report format |
| `tools.md` | First run / missing tools | Installation per stack |
| `go.md` | `go.mod` detected | Go: CLI + code review checks |
| `frontend.md` | `package.json` detected | JS/TS/Vue/React: CLI + code review checks |
| `python.md` | `pyproject.toml` / `requirements.txt` detected | Python: CLI + code review checks |
| `rust.md` | `Cargo.toml` detected | Rust: CLI + code review checks |
| `java.md` | `pom.xml` / `build.gradle` detected | Java/Kotlin: CLI + code review checks |
| `csharp.md` | `*.csproj` / `*.sln` detected | C#/.NET: CLI + code review checks |
| `universal.md` | Level 2+ | Language-agnostic reviews (security, concurrency, architecture...) |
| `api-audit.md` | Specialized request, or Level 3 with API-heavy apps | API request redundancy audit |

> **Fetch pattern:** `https://raw.githubusercontent.com/{user}/full-audit/main/{file}`

---

## Pre-conditions

- **Clean worktree recommended.** Commit or stash before audit.
- **Run from project root** (where manifest files are).
- Level 1: any branch. Level 2+: prefer `main` or release branch.
- **Read project's `CLAUDE.md`** before any code review — it contains project-specific Code Rules.
- **Static analysis by default.** Do not run the server unless the project or user explicitly requires runtime testing.

## Conventions

### `skip_if` blocks

Throughout the playbooks, checks may include a `skip_if` annotation:

```
> skip_if: <condition>
```

When the condition is true, the agent should skip the check and note it in the report as "SKIPPED: reason". Common conditions:
- `skip_if: windows` — command requires Unix-specific tools not available in Git Bash
- `skip_if: no_tool(name)` — tool not installed (check via `which`/`command -v`)
- `skip_if: no_ci` — project has no CI/CD pipeline
- `skip_if: nightly_only` — requires Rust nightly toolchain

---

## Phase 0: Pre-Audit

Before starting any audit, the orchestrator performs eligibility, scope, and stack detection.

### 1. Eligibility Check (haiku agent)

Dispatch a haiku agent to verify the project is auditable:

1. **Not empty** — project has source code files (not just configs/docs)
2. **Not pure generated** — if >80% code is auto-generated (protobuf, swagger, migrations), warn user and suggest focusing on hand-written code only
3. **Has build system** — at least one manifest file detected
4. **Clean state** — no uncommitted changes that could affect results (warn, don't block)
5. **Not a fork with zero changes** — if fork, check for divergence from upstream

If project fails eligibility → report to user with reasons, do not proceed.

### 2. Scope Planning (sequential-thinking)

Before creating audit tasks, clarify scope with the user:

1. **Critical modules** — which directories/packages are highest priority?
2. **Compliance requirements** — any specific standards (SOC2, HIPAA, PCI-DSS)?
3. **Known issues** — anything already tracked that audit should skip?
4. **Time budget** — adjust level if time is constrained
5. **Focus areas** — security-only? quality-only? full?

Output: focused checklist that feeds into Wave 1+ task creation.

### Approach Proposal

Based on scope answers, present 2-3 audit strategies to the user:

| Approach | Focus | Agents | Estimated Time | Best For |
|----------|-------|--------|---------------|----------|
| **Broad Coverage** | All checks at requested level across full codebase | Full wave plan | L2: 30-60 min | Regular sprint audits |
| **Security Deep Dive** | Security checks only, all levels | Security-focused reviewers + SAST | L2: 20-40 min | Pre-release, compliance |
| **Targeted Audit** | User-specified modules/packages only | Scoped agents | L2: 15-30 min | Known problem areas, post-incident |

Present approaches with trade-offs. User selects one. Selected approach determines which agents spawn and which checks run.

### 3. Stack Detection

Before creating tasks, detect the project stack:

1. Look for manifest files: `go.mod`, `package.json`, `Cargo.toml`, `pyproject.toml`, `requirements.txt`, `*.csproj`, `*.sln`, `pom.xml`, `build.gradle`, `build.gradle.kts`
2. Determine structure: monorepo? `backend/` + `frontend/`? single app?
3. Fetch applicable stack files from this repo
4. If MCP servers available (Serena, Context7) — use them. If not — fallback to Grep/Read/Glob.

**Stack command mapping:**

| Detected | Build | Lint | Vuln scan | Tests |
|----------|-------|------|-----------|-------|
| `go.mod` | `go build ./...` | `go vet && staticcheck ./...` | `govulncheck ./...` | `go test ./...` |
| `package.json` | `npm run build` | `npm run lint` | `npm audit` | `npm test` / `npx vitest run` |
| `pyproject.toml` / `requirements.txt` | `python -m py_compile` | `ruff check .` | `pip-audit` | `pytest` |
| `Cargo.toml` | `cargo build` | `cargo clippy` | `cargo audit` | `cargo test` |
| `pom.xml` | `mvn compile` | `mvn checkstyle:check` | `mvn dependency-check:check` | `mvn test` |
| `build.gradle` / `build.gradle.kts` | `./gradlew build` | `./gradlew check` | `./gradlew dependencyCheckAnalyze` | `./gradlew test` |
| `*.csproj` / `*.sln` | `dotnet build` | `dotnet format --verify-no-changes` | `dotnet list package --vulnerable` | `dotnet test` |

---

## Architecture: Team-based Audit

```
TeamCreate("audit-{level}")
  +-- Team Lead (you, Opus) -- orchestrator
       |-- cli-scanner-{N} (haiku) -- build, lint, vuln
       |-- diff-scanner-{N} (opus) -- surface scan, obvious bugs
       |-- history-reviewer-{N} (opus) -- git blame, regressions
       |-- comment-checker (opus) -- TODO/FIXME compliance
       |-- convention-checker (opus) -- CLAUDE.md rules
       |-- impact-reviewer-{N} (opus) -- cross-file impact
       |-- web-researcher (sonnet) -- version checks, CVE
       |-- fixer-{N} (opus) -- fix findings
       +-- fix-reviewer (opus) -- reviews fix diffs
       +-- scoring-agent-{N} (haiku) -- scores findings confidence 0-100
```

### Teammate Roles

| Role | `subagent_type` | `model` | Example `name` |
|------|----------------|---------|----------------|
| CLI scanner | `general-purpose` | `haiku` | `cli-scanner-go` |
| Diff scanner | `general-purpose` | `opus` | `diff-scanner-go` |
| History reviewer | `general-purpose` | `opus` | `history-reviewer-go` |
| Comment checker | `general-purpose` | `opus` | `comment-checker` |
| Convention checker | `general-purpose` | `opus` | `convention-checker` |
| Impact reviewer | `general-purpose` | `opus` | `impact-reviewer-go` |
| Web researcher | `general-purpose` | `sonnet` | `web-researcher` |
| Fixer | `general-purpose` | `opus` | `fixer-backend` |
| Fix reviewer | `general-purpose` | `opus` | `fix-reviewer` |
| Scoring agent | `general-purpose` | `haiku` | `scoring-agent-1` |

### Orchestrator Steps

0. **Planning** — Sequential Thinking MCP (if available): waves, dependencies, skippable tasks.
0.5. **Preflight check** — verify required tools are installed before spawning CLI scanners. Run a quick check per detected stack:
    ```bash
    # Example for Go stack:
    for cmd in go staticcheck govulncheck golangci-lint gosec deadcode gitleaks semgrep; do
      command -v "$cmd" >/dev/null 2>&1 && echo "OK: $cmd" || echo "MISSING: $cmd"
    done
    ```
    If critical tools are missing, fetch `tools.md` and install before proceeding. Report missing optional tools as "SKIPPED" in the final report.
1. **Create team** — `TeamCreate(team_name="audit-{level}")`.
2. **Create tasks** — `TaskCreate` per agent. Use `TaskUpdate(addBlockedBy=[...])` for wave dependencies. Set priority: CRITICAL tasks first.
   Tasks MUST be self-contained: each TaskCreate description includes ALL file paths, context, checklist items, and instructions needed. Agents must NOT need to read other tasks, prior conversation, or external documents to complete a task. Embed relevant sections from stack files and universal.md directly in the task description.
3. **Spawn teammates** — `Agent(team_name="audit-{level}", name=..., model=..., prompt=...)`. Each teammate:
   - Reads `TaskList`, claims highest-priority unblocked task via `TaskUpdate(owner="{name}")`
   - Executes -> `TaskUpdate(status="completed")` -> takes next
   - Goes idle when no tasks — this is normal
4. **Coordination** — messages arrive automatically. On blockers — reassign via `SendMessage`.
5. **Timeout recovery** — if agent reports no progress for >5 min, Lead reassigns task to another agent or investigates blocker.
6. **Collect results** — compile summary + fix plan. **Deduplicate** findings from multiple agents (same issue found by different reviewers → merge, keep highest severity).
6.5. **Self-review & Verification Gate** — before presenting report to user:
   - **Verification Gate:** every finding has evidence (file:line, tool output or code snippet, confidence score). Remove any finding without evidence.
   - **Prohibited phrases scan:** remove "appears to be", "should be fine", "I've verified", "Everything looks good", "Tests are passing", "The fix works" without attached proof.
   - Scan for placeholders: "TBD", "TODO", "N/A" without explanation, "..."
   - Verify severity consistency: identical issues must have identical severity
   - Check all files from scope are mentioned (covered or explicitly excluded)
   - Verify Health Score matches actual findings (e.g., "PASS" security but CRITICAL findings = contradiction)
   - Remove duplicate findings (same issue reported by multiple agents)
   - Ensure every CRITICAL/HIGH has a reproduction path or evidence
7. **Fixes** — after user approval only. `TeamCreate("audit-fix")` with `model="opus"` teammates. Create feature branch before fixing.
8. **Post-fix verification** — re-run the CLI commands that originally found each issue to confirm closure.
9. **Shutdown** — `SendMessage(message={type:"shutdown_request"})` per teammate -> `TeamDelete`.

### Diff Mode (CI / incremental)

For auditing only changes since last audit (faster, ~3-5 min):

```bash
# Get changed files since last audit tag or main branch
git diff --name-only main...HEAD
# Or since last audit:
git diff --name-only audit/last-run...HEAD
```

Only run CLI scanners and code review on changed files. Useful for:
- CI pipeline integration (run on every PR)
- Post-sprint quick check
- Pre-release delta audit

### Wave Plan

> Waves are generated dynamically based on detected stacks. `{stack}.md` = the stack-specific file (go.md, frontend.md, python.md, etc.). For monorepos with N stacks, spawn 1 cli-scanner + 1 code-reviewer per stack.

```
Wave 1 — CLI + research (parallel, haiku + sonnet):
  - cli-scanner-{N} (haiku): [{stack}.md L1+L2 CLI commands]
      Per detected stack: build, lint, vuln scan, tests,
      SAST (semgrep), secrets (gitleaks), dead code, coverage
      → 1 scanner per stack (e.g., cli-scanner-go, cli-scanner-frontend)
  - cli-scanner-universal (haiku): [universal.md L2 CLI]
      git hygiene (large files, suspicious files, .gitignore)
  - web-researcher (sonnet): [universal.md Stack Currency]
      version checks, CVE search for all deps

Wave 2 — code review (parallel, opus, after Wave 1):
  - diff-scanner-{N} (opus): [{stack}.md L2 Code Review — surface scan]
      Diff-only review: obvious bugs, typos, logic errors without deep context
  - history-reviewer-{N} (opus): [{stack}.md L2 Code Review — history-aware]
      Git blame + history: regressions, reverted patterns, repeated mistakes
  - comment-checker (opus): [universal.md — comment compliance]
      Code matches its own TODO/FIXME/comments, no stale annotations
  - convention-checker (opus): [CLAUDE.md + project conventions]
      Project-specific rules from CLAUDE.md, naming, structure compliance
  - impact-reviewer-{N} (opus): [{stack}.md L2 Code Review — cross-file]
      Changes break dependent code? API contracts maintained? Import chains valid?

Scoring Phase (after final review wave, before report assembly):
  - scoring-agent-{N} (haiku): [batch of findings from Wave 2/3]
      Score each finding 0-100, filter by level threshold
      → 1 scoring agent per ~20 findings
```

<details><summary>Wave 3 — Level 3 only (after Wave 2)</summary>

```
Wave 3 — deep review (parallel, opus):
  - code-reviewer-{N} (opus): [{stack}.md L3]
      Per detected stack: all Level 3 checks from stack file
      → 1 reviewer per stack
  - code-reviewer-security (opus): [universal.md L3 — security]
      XSS, SSRF, deserialization, XXE, ReDoS,
      log injection, IDOR/BOLA/BFLA, session mgmt,
      JWT/auth, business logic abuse,
      webhook security, file upload hardening
  - code-reviewer-quality (opus): [universal.md L3 — quality]
      API contract consistency, logging & observability,
      error disclosure, overengineering, docs freshness,
      input validation, resilience, config mgmt,
      state mgmt, privacy/PII, supply chain, SBOM,
      sharp edges, variant analysis
```

</details>

### Wave Completion Criteria

Wave N is complete when ALL tasks tagged wave-N have status=completed (any outcome). Orchestrator monitors via `TaskList` polling every 30 seconds.

- If an agent is idle >5 minutes with incomplete tasks → investigate or reassign
- If a wave exceeds 2x estimated time → notify user, offer to proceed with partial results
- Wave N+1 tasks are automatically unblocked when Wave N completes

### Level-to-Wave Agent Mapping

| Agent | Level 1 | Level 2 | Level 3 |
|-------|---------|---------|---------|
| cli-scanner-{N} | ✅ | ✅ | ✅ |
| cli-scanner-universal | — | ✅ | ✅ |
| web-researcher | — | ✅ | ✅ |
| diff-scanner-{N} | ✅ | ✅ | ✅ |
| history-reviewer-{N} | — | ✅ | ✅ |
| comment-checker | — | ✅ | ✅ |
| convention-checker | — | ✅ | ✅ |
| impact-reviewer-{N} | — | ✅ | ✅ |
| Wave 3 deep reviewers | — | — | ✅ |

Level 1 (Quick): minimal agents for fast results. Level 2: full coverage. Level 3: everything including deep review.

### Parallel Execution Protocol

Formalized protocol for wave-based parallel execution:

**Agent output format (structured):**
```json
{
  "agent": "cli-scanner-go",
  "wave": 1,
  "status": "completed",
  "findings": [...],
  "skipped": [...],
  "errors": [...],
  "duration_ms": 45000
}
```

**Orchestrator integration steps:**
1. Collect all agent outputs for the wave
2. **Conflict check** — same file:line reported by multiple agents → merge, keep highest severity + all context
3. **Spot-check** — randomly verify 10-20% of findings against actual code
4. **Gap analysis** — any files/packages in scope not covered by any agent?
5. Integrate into unified findings list before next wave

### MCP Servers (if available)

| MCP | Who | Notes |
|-----|-----|-------|
| **Serena** | Lead, reviewers, fixers | `read_memory("project_overview", "code_style")` at start |
| **Context7** | Fixers | `resolve-library-id` -> `query-docs` before coding with libraries |
| **Seq. Thinking** | Lead | Wave planning, fix strategy |

> **If Serena unavailable:** use Grep for code search, Glob for file search, Read for file contents. All code review agents switch from Serena to Grep/Read.

### Teammate Prompts

**Code reviewer:**
```
You are a teammate in audit team "{team_name}". Role: code review.

1. TaskList -> claim unblocked task (TaskUpdate owner="{your_name}")
2. Execute audit task per description
3. TaskUpdate(status="completed") with findings: | Severity | File:Line | Issue | Recommendation |
4. TaskList -> next task. None -> idle (normal).

Read the project CLAUDE.md first — it has project-specific Code Rules.
MCP: Serena for code nav (if available). Fallback: Grep/Read/Glob.
```

**CLI scanner:**
```
You are a teammate in audit team "{team_name}". Role: run CLI tools.

1. TaskList -> claim task (TaskUpdate owner="{your_name}")
2. Before running each command, verify the tool exists: `command -v <tool> >/dev/null 2>&1`
   - If missing: report as "SKIPPED: <tool> not installed" and continue to next command
   - Do NOT attempt to install tools unless explicitly instructed
3. Run CLI commands from task via Bash
4. TaskUpdate(status="completed") with output summary
5. TaskList -> next. None -> idle.

Do NOT edit files. Only run commands and report.
```

**Web researcher:**
```
You are a teammate in audit team "{team_name}". Role: version & CVE research.

1. TaskList -> claim task (TaskUpdate owner="{your_name}")
2. Read manifest files (go.mod, package.json, etc.)
3. For each dependency: web search latest version, known CVEs, EOL status
4. Check runtime/framework versions against latest releases
5. TaskUpdate(status="completed") with table:
   | Dependency | Current | Latest | Status | CVEs | Notes |

Rate each: Current / Behind / EOL / Vulnerability (see universal.md Stack Currency).
Do NOT edit files. Only research and report.
```

**Fixer:**
```
You are a teammate in audit team "{team_name}". Role: fix findings.

1. TaskList -> claim task (TaskUpdate owner="{your_name}")
2. Read project CLAUDE.md first — critical Code Rules inside
3. Fix the issue
4. Build check per stack:
   - Go: go build ./... && go vet ./...
   - JS/TS: npm run build && npm run lint
   - Python: ruff check . && pytest
   - Rust: cargo build && cargo clippy
   - Java (Maven): mvn compile && mvn checkstyle:check
   - Java (Gradle): ./gradlew build && ./gradlew check
   - C#: dotnet build && dotnet format --verify-no-changes
5. TaskUpdate(status="completed") with change summary
6. TaskList -> next. None -> idle.

MCP: Serena for editing (if available). Context7 before code with libraries.
Work only in assigned directory/package to avoid conflicts.
IMPORTANT: shared/ and common packages — only ONE fixer at a time. If your task touches shared/,
check TaskList for other active shared/ tasks. If conflict — wait or notify lead.
Your fixes are reviewed in batches of 3. CRITICAL fixes get immediate review. Commit each fix separately with message: fix(audit): [SEVERITY] description
```

**Scoring agent:**
```
You are a teammate in audit team "{team_name}". Role: score findings.

1. TaskList -> claim task (TaskUpdate owner="{your_name}")
2. For each finding in the batch, evaluate:
   - Is this verified against actual code? (not hypothetical)
   - Is this pre-existing or recently introduced? (git blame)
   - Does CLAUDE.md allow this pattern?
   - Can a specific command reproduce this finding?
3. Assign confidence score 0-100 per the Confidence Scoring scale
4. TaskUpdate(status="completed") with scored findings:
   | Score | Severity | File:Line | Issue | Evidence |
5. TaskList -> next. None -> idle.

Discard findings scoring below the level threshold (L1: <75, L2: <60, L3: <40).
Do NOT edit files. Only evaluate and score.
```

### Agent Completion Statuses

Agents report task completion using `TaskUpdate` with status and metadata:

| Status | When | Orchestrator Action |
|--------|------|-------------------|
| `completed` + `outcome: "DONE"` | Task fully completed, all checks pass | Accept results, proceed to next task |
| `completed` + `outcome: "DONE_WITH_CONCERNS"` | Task done but agent found issues worth noting | Review concerns before proceeding; may spawn follow-up task |
| `completed` + `outcome: "NEEDS_CONTEXT"` | Cannot complete without additional information | Provide context via SendMessage, agent retries |
| `completed` + `outcome: "BLOCKED"` | External dependency or tool issue prevents completion | Reassign to different agent or resolve blocker |

**Example:**
```json
TaskUpdate(taskId="5", status="completed", metadata={"outcome": "DONE_WITH_CONCERNS", "concerns": "gosec reported 3 findings but 2 appear to be false positives — recommend manual review"})
```

All agent prompts should include: "When completing a task, set metadata outcome to DONE, DONE_WITH_CONCERNS (explain), NEEDS_CONTEXT (what's missing), or BLOCKED (what's blocking)."

---

## Severity Classification

| Severity | Criteria | Action |
|----------|----------|--------|
| **CRITICAL** | Exploitable vulnerability, data loss/corruption risk, crash in production, secrets exposed | Fix immediately, block release |
| **HIGH** | Security issue requiring code change, resource leak under load, data integrity risk | Fix before next release |
| **MEDIUM** | Code quality issue, missing validation, performance degradation, stale dependency | Schedule within 2 sprints |
| **LOW** | Style, minor optimization, nice-to-have improvement | Fix when convenient, expires after 2 releases if unaddressed |

---

## Confidence Scoring

Every finding goes through a confidence scoring gate before inclusion in the report.

### Scoring Scale (0-100)

| Score | Meaning | Action |
|-------|---------|--------|
| **0** | False positive, pre-existing issue, or cannot be verified | Discard |
| **25** | Possibly real but unverified. Stylistic without CLAUDE.md backing | Discard |
| **50** | Verified issue but nitpick or impractical to fix | Include in Level 3 only (below Level 2 threshold) |
| **75** | Re-verified, very likely real. Important for functionality | Include in Level 2+ |
| **100** | Absolutely confirmed with direct evidence (exit code, line number, output) | Always include |

### Scoring Process

1. Each reviewer agent produces raw findings with severity
2. Orchestrator dispatches **scoring agents** (haiku) — one per batch of findings
3. Scoring agent evaluates each finding against:
   - Is this verified against actual code? (not hypothetical)
   - Is this a pre-existing issue or introduced recently?
   - Does the CLAUDE.md mention this pattern as acceptable?
   - Can the finding be reproduced by running a specific command?
4. Findings are filtered based on **per-level minimum thresholds**:

   | Level | Minimum Score | Rationale |
   |-------|--------------|-----------|
   | 1 (Quick) | 75 | Only high-confidence findings for fast audits |
   | 2 (Full) | 60 | Balanced — include verified findings |
   | 3 (Deep) | 40 | Include lower-confidence findings for thorough review |

5. Filtered findings saved to `audit-filtered.md` in the project root (not committed to git — for reference only)

### False Positive Whitelist

Common false positives to auto-filter (score = 0):

- Pre-existing issues not related to recent changes (in Diff Mode)
- Intentional patterns documented in CLAUDE.md or code comments (e.g., `// nolint: reason`)
- Tool-level issues that CI/linter will catch separately
- Issues on non-modified lines (in Diff Mode / Quick audit)
- Test code patterns that mirror production anti-patterns intentionally
- Generated code (protobuf, swagger, ORM migrations)
- Vendor/third-party code in `vendor/`, `node_modules/`, `third_party/`

---

## Report Format

```markdown
## Audit Results [DATE]

### Health Score
| Area | Score | Details |
|------|-------|---------|
| Build & Lint | PASS/FAIL | 0 errors / N errors |
| Security (CLI) | PASS/WARN/FAIL | N vulns (H critical, M high) |
| Security (manual) | PASS/WARN/FAIL | N findings |
| Security (design) | PASS/WARN/FAIL | N sharp edges, N insecure defaults |
| Concurrency | PASS/WARN/FAIL | N races / N patterns |
| Dependencies | CURRENT/BEHIND/EOL | N outdated, N EOL |
| Code Quality | PASS/WARN | complexity, dead code |
| Overall | PASS / NEEDS WORK / CRITICAL | |

### CRITICAL (fix immediately)
1. ...

### HIGH (fix in next release)
1. ...

### MEDIUM (schedule)
1. ...

### LOW (when possible -- expires after 2 releases if unaddressed)
1. ...

### What's Good (don't touch)
- ...
```

> **Note:** Only include findings with confidence score >= threshold for the audit level (see Confidence Scoring). Each finding must show its confidence score.

### Report Integrity Rules

- **No hollow positives:** "Overall the codebase is in great shape" requires evidence (0 HIGH+, test coverage >80%, all deps current)
- **No vague negatives:** "Some security concerns" — list them specifically with file:line
- **Every PASS needs proof:** Health Score "PASS" = link to command output showing clean result
- **Every count is exact:** "N vulnerabilities" = N specific items listed below
- **Severity matches impact:** Don't inflate to look thorough, don't deflate to look positive
- **"What's Good" is specific:** Not "good code quality" but "consistent error handling pattern in pkg/api/ using middleware"

---

## Verification Gate (Iron Law)

**No claim without fresh evidence.** Every assertion in the audit report must be backed by verifiable proof.

### Rules

1. **IDENTIFY** — What command/check proves this claim?
2. **RUN** — Execute the command freshly (not from cache or memory)
3. **READ** — Read full output, check exit code
4. **VERIFY** — Does output confirm the claim?
5. **ONLY THEN** — Include in report

### Prohibited phrases (without evidence)

- "The codebase appears to be..." — run the check
- "No issues found" — show the command output
- "PASS" in Health Score — show exit code 0
- "All tests pass" — show test runner output
- "N vulnerabilities" — show scanner output with exact count
- "I've verified" — show the verification output
- "Everything looks good" — specify what was checked
- "Tests are passing" — show test runner output with count
- "The fix works" — show before/after evidence

### Agent trust policy

- CLI Scanner output → trust if exit code captured
- Code Reviewer findings → require file:line reference
- Web Researcher data → require source URL
- Fixer claims "fixed" → re-run original detection command
- **Never trust agent self-reports without independent verification**

### Evidence format

Each finding MUST include:
```
| Field | Required |
|-------|----------|
| File:Line | Yes |
| Code snippet (3-5 lines) | Yes |
| Detection method | Yes (tool name or manual review) |
| Confidence score | Yes (0-100) |
| Reproduction command | If applicable |
```

---

## Fixing Findings

After user approval:

1. `TeamCreate("audit-fix")` or add tasks to existing team
2. Create feature branch: `git checkout -b audit-fix/YYYY-MM-DD`
3. Optionally create git worktree for isolation: `git worktree add .worktrees/audit-fix -b audit-fix/YYYY-MM-DD`
4. `TaskCreate` per fix, grouped by package/directory

### Fix Task Granularity

Each fix task MUST be atomic and time-boxed:

- **Time target:** 2-5 minutes per task. If a fix takes longer, split it.
- **Exact targeting:** task description includes exact `file:line` and the specific finding ID
- **One commit per task:** each task = one failing test + one fix + one commit
- **No placeholders:** task description must contain the actual fix approach, not "fix the security issue in auth.go"
- **Template:**
  ```
  Task: Fix [FINDING-ID] — [severity] [short description]
  File: src/auth/handler.go:45
  Finding: SQL injection via string concatenation in UserQuery()
  Fix approach: Use parameterized query with $1 placeholder
  Test: Add test with malicious input `'; DROP TABLE users; --`
  Verify: `semgrep --config=p/sql-injection src/auth/`
  ```

5. **Conflict prevention:** tasks touching `shared/`, `utils/`, or cross-cutting packages must be sequential (`addBlockedBy`). One fixer at a time.
6. Spawn fixers (`model="opus"`, prompt from Fixer section)

### Fixer TDD Protocol

Each fixer MUST follow Red-Green-Refactor:

1. **RED** — Write a failing test that reproduces the found issue
2. **Verify RED** — Run test, confirm it fails for the right reason
3. **GREEN** — Write minimal fix to pass the test
4. **Verify GREEN** — All tests pass (not just the new one)
5. **REFACTOR** — Clean up if needed, re-run tests
6. **Commit** — One commit per fix with message: `fix(audit): [SEVERITY] description`

> If the finding is not testable (e.g., config change, header addition), skip TDD but still verify with the appropriate CLI command.

### TDD Rationalization Table

> **Iron Law:** No production code without a failing test first. No exceptions without documented justification reviewed by orchestrator.

| Rationalization | Reality | Correct Action |
|----------------|---------|---------------|
| "This is a one-line change" | One-line changes cause production outages | Write the test — it's also one line |
| "This is just a config change" | Config changes break deployments | Write a test that loads config and validates |
| "I'll add tests later" | Later never comes | Write the test NOW, before the fix |
| "The existing tests cover this" | If they did, the bug wouldn't exist | Add a new test for this case |
| "This is too simple to test" | Simple code has simple tests — no excuse | Write it — takes 30 seconds |
| "Testing requires too much setup" | Extract logic into a testable unit | Refactor first, then test, then fix |
| "This is a dependency/infra issue" | You can still test the boundary | Write integration test or mock boundary |

When TDD is genuinely impossible (e.g., adding HTTP header, changing log format), the fixer MUST:
1. Document WHY it's untestable in the task completion
2. Provide the CLI command that verifies the change
3. Orchestrator reviews justification — if unconvincing, sends back

### Finding Challenge Protocol

If a fixer believes an assigned finding is incorrect or not applicable:

1. **Do NOT fix it silently or skip it.** Challenge it formally.
2. `TaskUpdate(status="completed", metadata={"outcome": "DONE_WITH_CONCERNS", "challenge": "reason"})`
3. Orchestrator dispatches a **second reviewer** (different from original) to adjudicate:
   - Reviewer checks: is the finding technically valid? Is fixer's challenge justified?
   - Verdict: **CONFIRMED** (fix it) or **RETRACTED** (remove from report)
4. If CONFIRMED: reassign to fixer with adjudication context
5. If RETRACTED: remove finding, update report, note in audit-filtered.md

**When to challenge:**
- Finding is a false positive (tool misidentified the pattern)
- Code has documented justification (comment, ADR, CLAUDE.md)
- Finding is pre-existing and out of audit scope (Diff Mode)
- Recommended fix would break other functionality
- YAGNI — the recommendation isn't needed in this project's context

**Never challenge to avoid work.** Anti-Rationalization Rules apply.

### Fix Review Protocol (Two-Stage)

**Stage 1 — Spec Compliance** (after every 3 fixes or immediately for CRITICAL):
```
You are a fix spec-reviewer for audit team "{team_name}".

Review fixes between BASE_SHA ({sha_before}) and HEAD_SHA ({sha_after}):
For each fix verify: Does the fix RESOLVE the original finding?
- Finding still present after fix? → FAIL
- Fix is a band-aid (suppresses warning, doesn't address root cause)? → FAIL
- Tests added that reproduce the original issue? → Required for PASS

Output: PASS / FAIL per fix with specific reasoning.
```

**Stage 2 — Code Quality** (only after Stage 1 passes):
```
You are a fix quality-reviewer for audit team "{team_name}".

Review fixes between BASE_SHA ({sha_before}) and HEAD_SHA ({sha_after}):
For each fix verify: Does the fix introduce NEW issues?
- Security regression? Performance degradation? Broken tests?
- Follows project conventions from CLAUDE.md?
- Code is clean, minimal, no over-engineering?

Output: APPROVED / NEEDS_CHANGES with specific feedback.
```

Stage 1 MUST pass before Stage 2 runs. If Stage 1 fails → fixer retries before quality review.

**Batch review checkpoints:**
- After every 3 fixes → dispatch fix-reviewer (Stage 1 then Stage 2)
- On any CRITICAL fix → immediate review (don't batch)
- After all fixes → final full review before merge

### Post-fix Verification

Re-run the CLI commands that originally found each issue to confirm closure:

```
Orchestrator: for each fixed finding:
1. Re-run original detection command
2. Verify the finding no longer appears
3. Run full test suite — 0 regressions
4. If finding persists → reassign to fixer with context
```

### Fix Attempt Limit (STOP Rule)

**After 3 failed fix attempts on the same finding — STOP.**

1. First failure: reassign to same fixer with additional context
2. Second failure: reassign to DIFFERENT fixer with full history
3. Third failure: **STOP. Escalate to user.**
   - Report: what was tried, why it failed, likely root cause
   - Options: (a) user guidance, (b) mark WONTFIX with justification, (c) create tracking issue
   - Do NOT attempt 4th automated fix

Same rule for build/test failures: 3 failures → STOP, report to user.

### Pre-Completion Verification

Before presenting options, orchestrator MUST:
1. Run ALL quality gates (see Quality Gates section) — capture full output
2. Run `git diff --stat` to confirm scope of changes
3. Show results to user:
   ```
   Quality Gates: PASS (0 errors)
   Files changed: N files (+X, -Y lines)
   Fixes applied: M of T findings resolved
   Unresolved: list remaining findings with reasons
   ```
4. ONLY THEN present the 4 completion options

### Fix Completion

After all fixes verified:
- **Option A:** Merge locally → `git merge audit-fix/YYYY-MM-DD`
- **Option B:** Push + create PR → `gh pr create`
- **Option C:** Keep branch for manual review
- **Option D:** Discard → requires typed confirmation "discard"

Cleanup worktree if used: `git worktree remove .worktrees/audit-fix`

Team Lead: all quality gates = 0 errors → Shutdown → `TeamDelete`

---

## Quality Gates (mandatory before commit)

Run the stack-appropriate commands:

```bash
# Go
go build ./... && go vet ./...

# Frontend (JS/TS)
npm run build && npm run lint

# Python
ruff check . && pytest

# Rust
cargo build && cargo clippy -- -D warnings && cargo test

# Java (Maven)
mvn compile -q && mvn checkstyle:check -q

# Java (Gradle)
./gradlew build && ./gradlew check

# C# / .NET
dotnet build && dotnet format --verify-no-changes && dotnet test
```

All gates: **0 errors**. For full check — Level 1.

---

## License

MIT — see [LICENSE](LICENSE).
