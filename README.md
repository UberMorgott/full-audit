# Full Audit

Universal codebase audit system for Claude Code. Works with any project via GitHub reference.

## Quick Start

User says:
```
Сделай полный аудит. Инструкции: github.com/{user}/full-audit
```

Claude executes:
1. **Fetch this README** via WebFetch (`https://raw.githubusercontent.com/{user}/full-audit/main/README.md`)
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
| S | Specialized | On demand (API audit, etc.) | ~10-15 min |

User can request: "level 1", "level 2", "full audit" (= level 2), "deep audit" (= level 3).
Default if not specified: **level 2**.

---

## Files in This Repo

| File | Fetch when | Contents |
|------|-----------|----------|
| `README.md` | Always | This file: orchestration, workflow, report format |
| `tools.md` | First run / missing tools | Installation per stack |
| `go.md` | `go.mod` detected | Go: CLI + code review checks |
| `frontend.md` | `package.json` detected | JS/TS/Vue: CLI + code review checks |
| `universal.md` | Level 2+ | Language-agnostic reviews (security, concurrency, architecture...) |
| `api-audit.md` | Specialized request | API request redundancy audit |

> **Fetch pattern:** `https://raw.githubusercontent.com/{user}/full-audit/main/{file}`

---

## Pre-conditions

- **Clean worktree recommended.** Commit or stash before audit.
- **Run from project root** (where manifest files are).
- Level 1: any branch. Level 2+: prefer `main` or release branch.
- **Read project's `CLAUDE.md`** before any code review — it contains project-specific Code Rules.
- **Do NOT run the server.** Audit = static analysis + build checks only.

---

## Step 0: Stack Detection

Before creating tasks, detect the project stack:

1. Look for manifest files: `go.mod`, `package.json`, `Cargo.toml`, `pyproject.toml`, `requirements.txt`, `*.csproj`
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
2. **Create tasks** — `TaskCreate` per agent. Use `TaskUpdate(addBlockedBy=[...])` for wave dependencies.
3. **Spawn teammates** — `Agent(team_name="audit-{level}", name=..., model=..., prompt=...)`. Each teammate:
   - Reads `TaskList`, claims unblocked task via `TaskUpdate(owner="{name}")`
   - Executes -> `TaskUpdate(status="completed")` -> takes next
   - Goes idle when no tasks — this is normal
4. **Coordination** — messages arrive automatically. On blockers — reassign via `SendMessage`.
5. **Collect results** — compile summary + fix plan.
6. **Fixes** — after user approval only. `TeamCreate("audit-fix")` with `model="opus"` teammates.
7. **Shutdown** — `SendMessage(message={type:"shutdown_request"})` per teammate -> `TeamDelete`.

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

**Fixer:**
```
You are a teammate in audit team "{team_name}". Role: fix findings.

1. TaskList -> claim task (TaskUpdate owner="{your_name}")
2. Read project CLAUDE.md first — critical Code Rules inside
3. Fix the issue
4. Build check per stack (go build ./... / npm run build / etc.)
5. TaskUpdate(status="completed") with change summary
6. TaskList -> next. None -> idle.

MCP: Serena for editing (if available). Context7 before code with libraries. Do NOT run server.
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
cd backend && go build ./... && go vet ./...

# Frontend
cd frontend && npm run build && npm run lint

# Python
ruff check . && python -m pytest

# Rust
cargo build && cargo clippy && cargo test
```

All gates: **0 errors**. For full check — Level 1.
