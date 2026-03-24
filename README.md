# Full Audit

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
3. **Detect stack** (Step 0 below)
4. **Fetch relevant files** from this repo (stack-specific + universal)
5. **Run audit** at requested level

### Audit Levels

| Level | Name | When | Time estimate |
|-------|------|------|---------------|
| 1 | Quick | Every release, CI | ~5 min |
| 2 | Full | Per sprint | ~15-25 min |
| 3 | Deep | Major release, quarterly | ~40-60 min |
| S | Specialized | On demand (API request audit) | ~10-15 min |

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

---

## Step 0: Stack Detection

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
       |-- code-reviewer-{N} (opus) -- security, concurrency via Serena/Grep
       +-- web-researcher (sonnet) -- version checks, CVE
```

### Teammate Roles

| Role | `subagent_type` | `model` | Example `name` |
|------|----------------|---------|----------------|
| CLI scanner | `general-purpose` | `haiku` | `cli-scanner-1` |
| Code reviewer | `general-purpose` | `opus` | `code-reviewer-1` |
| Web researcher | `general-purpose` | `sonnet` | `web-researcher` |
| Fixer | `general-purpose` | `opus` | `fixer-backend` |

### Orchestrator Steps

0. **Planning** — Sequential Thinking MCP (if available): waves, dependencies, skippable tasks.
1. **Create team** — `TeamCreate(team_name="audit-{level}")`.
2. **Create tasks** — `TaskCreate` per agent. Use `TaskUpdate(addBlockedBy=[...])` for wave dependencies. Set priority: CRITICAL tasks first.
3. **Spawn teammates** — `Agent(team_name="audit-{level}", name=..., model=..., prompt=...)`. Each teammate:
   - Reads `TaskList`, claims highest-priority unblocked task via `TaskUpdate(owner="{name}")`
   - Executes -> `TaskUpdate(status="completed")` -> takes next
   - Goes idle when no tasks — this is normal
4. **Coordination** — messages arrive automatically. On blockers — reassign via `SendMessage`.
5. **Timeout recovery** — if agent reports no progress for >5 min, Lead reassigns task to another agent or investigates blocker.
6. **Collect results** — compile summary + fix plan. **Deduplicate** findings from multiple agents (same issue found by different reviewers → merge, keep highest severity).
7. **Post-fix verification** — after fixes, re-run the CLI commands that originally found the issue to confirm closure.
8. **Fixes** — after user approval only. `TeamCreate("audit-fix")` with `model="opus"` teammates. Create feature branch before fixing.
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

### Wave Example (Go + Vue monorepo)

```
Wave 1 (parallel):
  - cli-scanner-1: go build, go vet, staticcheck, golangci-lint
  - cli-scanner-2: npm run build, npm run lint, vue-tsc
  - web-researcher: version checks

Wave 2 (parallel, after Wave 1):
  - code-reviewer-1: Go security review (OWASP + STRIDE)
  - code-reviewer-2: Go concurrency + resource leaks
  - code-reviewer-3: Frontend security + performance

Wave 3 (after Wave 2, Level 3 only):
  - code-reviewer-1: universal checks (business logic, sharp edges)
  - code-reviewer-2: API contract consistency + cross-layer trace
```

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
2. Run CLI commands from task via Bash
3. TaskUpdate(status="completed") with output summary
4. TaskList -> next. None -> idle.

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
```

---

## Severity Classification

| Severity | Criteria | Action |
|----------|----------|--------|
| **CRITICAL** | Exploitable vulnerability, data loss/corruption risk, crash in production, secrets exposed | Fix immediately, block release |
| **HIGH** | Security issue requiring code change, resource leak under load, data integrity risk | Fix before next release |
| **MEDIUM** | Code quality issue, missing validation, performance degradation, stale dependency | Schedule within 2 sprints |
| **LOW** | Style, minor optimization, nice-to-have improvement | Fix when convenient, expires after 2 releases if unaddressed |

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

---

## Fixing Findings

After user approval:

1. `TeamCreate("audit-fix")` or add tasks to existing team
2. `TaskCreate` per fix, grouped by package/directory
3. **Conflict prevention:** tasks touching `shared/`, `utils/`, or cross-cutting packages must be sequential (`addBlockedBy`). One fixer at a time.
4. Spawn fixers (`model="opus"`, prompt from Fixer section)
5. Each fixer: reads project CLAUDE.md -> fixes -> build check -> next task
6. Team Lead: all quality gates = 0 errors
7. Shutdown -> `TeamDelete`

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
