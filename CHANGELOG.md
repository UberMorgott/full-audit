# Changelog

## [1.3.0] — 2026-04-07

### Added
- **Scoring Agent** — new role in architecture: haiku agents score findings 0-100 between review waves and report assembly. Includes prompt template and wave placement.
- **Scoring Phase** — explicit phase between Wave 2/3 and report assembly for confidence scoring.
- **4-Status Agent Completion Protocol** — agents report DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED via TaskUpdate metadata instead of binary "completed".
- **Finding Challenge Protocol** — fixers can formally challenge incorrect findings; second reviewer adjudicates (CONFIRMED/RETRACTED).
- **Two-Stage Fix Review** — Stage 1: spec compliance (does fix resolve finding?), Stage 2: code quality (does fix introduce new issues?). Stage 1 must pass before Stage 2.
- **Pre-Completion Verification** — orchestrator runs quality gates and shows results before presenting fix completion options.
- **Audit Approach Options** — Phase 0 presents 2-3 strategies (Broad Coverage / Security Deep Dive / Targeted Audit) with trade-offs for user selection.
- **Wave Completion Criteria** — explicit definition: all wave-N tasks completed, 30s polling, 5min idle timeout, 2x time overflow notification.
- **Container & Image Security** (universal.md) — Dockerfile audit, image scanning, runtime security, K8s/Compose orchestration checks.
- **CI/CD Pipeline Security** (universal.md) — secret management, action pinning, branch protection, build integrity.
- **Cryptographic Key Management** (universal.md) — key storage, rotation, derivation, TLS config, certificate management.
- **Concurrency Safety** (universal.md) — data races, deadlocks, resource lifecycle, concurrency patterns (language-agnostic).
- **Proactive Self-Check** (universal.md) — agent completion checklist: evidence, no hedging, confidence scores, SKIP count validation.
- **Root Cause STOP Rule** (universal.md) — escalate after 3 failed hypotheses instead of continuing to guess.
- **Stack file cross-references** — all 7 stack files now reference: confidence scoring, false positive detection, CLI verification, YAGNI, anti-rationalization, reviewer role mapping.
- **Quick reference vulnerability tables** — added to java.md, csharp.md, frontend.md (go.md, rust.md, python.md already had them).
- **2026 technology patterns** — Virtual Threads (java.md), NativeAOT (csharp.md), Server Components + Service Workers (frontend.md), uv (python.md/tools.md), Bun (frontend.md), GraphQL + gRPC (api-audit.md), cargo-vet + MSRV (rust.md), log/slog (go.md), GraalVM (java.md).
- **GraphQL audit patterns** (api-audit.md) — query depth, complexity, introspection, N+1, persisted queries, field-level auth.
- **gRPC audit patterns** (api-audit.md) — deadline propagation, streaming backpressure, interceptors, reflection, error codes.
- **Version pinning recommendation** (tools.md) — pin tool versions in CI for reproducibility.
- **uv package manager** (tools.md) — added as Python tool alternative.

### Changed
- **Verification Gate** wired into orchestrator step 6.5 (was standalone policy section).
- **Self-review step** expanded with prohibited phrases scan and verification gate integration.
- **Fix Review Protocol** split into two stages (spec compliance → code quality) instead of single-pass.
- **Phase 0 Scope Planning** now includes audit approach proposals (Broad/Security/Targeted).
- **Task creation rule** — TaskCreate descriptions must be fully self-contained.
- **Go encoding/xml XXE** guidance corrected (universal.md) — was inaccurate about default vulnerability.
- **Stack Currency** section completed with output format and action thresholds (universal.md).
- **dotnet-outdated-tool** naming fixed in csharp.md to match tools.md.
- **api-audit.md** — replaced project-specific "AG API" examples with generic ones.
- **Semgrep in csharp.md** — changed from "Or" alternative to "Also recommended" alongside .NET analyzers.

### Fixed
- **Go `encoding/xml` XXE claim** — corrected: Go's encoding/xml does NOT resolve external entities by default (was stated as "vulnerable by default").

## [1.2.0] — 2026-04-07

### Added
- **Wave 0: Eligibility & Scope Planning** — pre-audit checks (empty project, generated code, fork detection) and scope clarification with user before starting.
- **5 Specialized Code Reviewers** — replaced single code-reviewer with: diff-scanner (surface bugs), history-reviewer (regressions via git blame), comment-checker (stale TODO/FIXME), convention-checker (CLAUDE.md compliance), impact-reviewer (cross-file breakage).
- **Confidence Scoring (0-100)** — every finding scored by haiku agents; findings <60 filtered from report. False positive whitelist for common auto-discards.
- **False Positive Detection** (universal.md) — auto-discard rules, verification-required patterns, stack-specific FP lists for Go, Python, JS/TS, Rust, Java, C#.
- **CLI Finding Verification Protocol** (universal.md) — 5-step verification for every CLI tool finding before report inclusion.
- **YAGNI Check for Recommendations** (universal.md) — mandatory verification that recommendations are actually needed in project context.
- **Anti-Rationalization Rules** (universal.md) — 12-rule table preventing agents from skipping checks or softening findings.
- **Root Cause Analysis** (universal.md) — 4-phase protocol for CRITICAL/HIGH findings: investigation, pattern analysis, impact assessment, prevention recommendation.
- **Fixer TDD Protocol** — Red-Green-Refactor cycle for every fix: write failing test → fix → verify → commit.
- **Fix Review Protocol** — SHA-based diff review after every 3 fixes; immediate review for CRITICAL fixes.
- **Git Worktree Isolation** — optional `--isolated` mode: fixes in separate worktree with merge/PR/discard options.
- **Verification Gate (Iron Law)** — no claim without fresh evidence. Prohibited phrases, agent trust policy, required evidence format.
- **Self-Review Step** — orchestrator scans report for placeholders, severity inconsistencies, coverage gaps before presenting.
- **Anti-Performative Reporting** — report integrity rules: no hollow positives, no vague negatives, every PASS needs proof.
- **Parallel Execution Protocol** — structured agent output format (JSON), conflict check, spot-check, gap analysis between waves.
- **Fix Completion Options** — merge locally / push+PR / keep branch / discard (with typed confirmation).

### Changed
- **Teammate Roles table** — expanded from 4 to 9 roles (added diff-scanner, history-reviewer, comment-checker, convention-checker, impact-reviewer, fix-reviewer).
- **Fixing Findings section** — complete rewrite with TDD, batch review, SHA-based verification, worktree isolation, completion options.
- **Orchestrator Steps** — added self-review step (6.5) between result collection and fix phase.
- **Wave 2 architecture** — 5 specialized reviewers instead of generic code-reviewer-{N}.

## [1.1.0] — 2026-03-24

### Security
- **Trivy:** Updated security notice — v0.69.5 and v0.69.6 also compromised (secondary attack 2026-03-22). Added timeline, safe versions for trivy-action and setup-trivy, GHSA reference.
- **Trivy version check:** Added `trivy version` verification comment before every `trivy fs` command across all stack files (go.md, frontend.md, python.md, rust.md, java.md, csharp.md).
- **TruffleHog:** Fixed install instructions — `pip install trufflehog` installs abandoned v2 (2021). Updated to Go binary install via install script, `go install`, or Homebrew.

### Added
- **Preflight check (Wave 0.5):** New orchestrator step to verify required tools are installed before spawning CLI scanners. Includes example check script and SKIP reporting for missing tools.
- **`skip_if` convention:** Standardized conditional skip blocks throughout playbooks. Documented in README with common conditions (windows, no_tool, no_ci, nightly_only).
- **Rust vulnerability patterns table:** Added "Quick reference" grep-pattern table (10 patterns) matching Go's existing table format.
- **Python vulnerability patterns table:** Added "Quick reference" grep-pattern table (10 patterns).
- **Python middleware order checks:** Added Django MIDDLEWARE order, Flask before_request order, FastAPI add_middleware reverse-order checks.
- **API audit example output:** Added example amplification table for Cross-Layer Trace agent.
- **Kotlin coroutines in Level 2:** Moved `GlobalScope.launch` and `runBlocking` checks from Level 3 Kotlin-specific section to Level 2 Concurrency (HIGH severity, not just L3).
- **CHANGELOG.md:** Version tracking for playbook changes.
- **Version badge** in README header.

### Changed
- **Time estimates:** Adjusted to realistic ranges — split into single-stack vs monorepo columns. Level 3 deep audit: 60-90 min (single) / 2-3 hours (monorepo).
- **Insecure defaults regex:** Narrowed `getenv` fallback pattern to only match security-sensitive env vars (SECRET, PASSWORD, TOKEN, KEY, PRIVATE, CREDENTIAL). Prevents false positives on PORT, HOST fallbacks.
- **Git Hygiene (Windows):** Added `skip_if: windows` note for large-files command with simpler alternative. Clarified Git Bash compatibility.
- **CLI scanner prompt:** Added tool existence check (`command -v`) before running each command, with SKIP reporting.
- **dotnet-outdated:** Fixed package name to `dotnet-outdated-tool` in tools.md.
- **Rust fuzz/miri:** Added `skip_if: nightly_only` annotations.

### Fixed
- **.gitignore:** Extended with common test artifacts (node_modules, __pycache__, .venv, target, bin, obj).

## [1.0.0] — 2026-03-23

Initial release. 6 stack files + universal + api-audit + tools + README.
