# Changelog

## [1.6.0] — 2026-05-28

### Added
- **Pre-audit tool integrity protocol** (tools.md) — mandatory supply chain verification before ANY audit: npm version check, maintainer identity validation, publish date verification, checksum validation, Go sumdb verification. Red flags list for compromised packages. Runs BEFORE Wave 1.
- **Automated CLI waste detection** (frontend.md, README.md) — `waste-scanner` agent now runs `knip@latest`, `purgecss@latest`, `i18n-unused@latest`, `dotenv-check@latest` CLI tools instead of manual greps. Manual reasoning checks (CSS framework utilization, dead UI features, missing i18n keys) remain as Opus-only tasks in `impact-reviewer`.
- **`waste-scanner` agent** (README.md, Wave 1, L2+) — new haiku agent that runs automated cross-reference checks CLI tools like knip miss: dependency utilization (depcheck/cargo udeps/pip-extra-reqs), CSS framework utilization, dead CSS classes, dead i18n keys, tsconfig/eslint strictness verification, env var coherence. 1 per project, runs in parallel with cli-scanners.
- **`impact-reviewer` expanded responsibilities** (README.md, Wave 2) — three new cross-file checks: serialization tag audit (fields with `json:"-"`/`@JsonIgnore`/`[NonSerialized]` that have active consumers), progress/counter data flow tracing (source to display, silent reset detection), dead UI features (state variables without reachable triggers).
- **Dead Asset Detection** (frontend.md, L2) — 6 cross-reference checks that CLI tools miss: CSS framework utilization, dead CSS classes, dead i18n/localization keys, dependency utilization audit beyond knip/depcheck, dead imports enforcement, dead UI features (state without triggers). All checks are framework-agnostic — work for React, Vue, Svelte, Angular, Solid, or vanilla JS.
- **Cross-Stack Waste Detection** (universal.md, L2) — 4 universal waste detection checks for any tech stack: config-dependency coherence (with per-stack tooling: depcheck, go mod tidy, cargo udeps, pip-extra-reqs), declared-vs-used asset audit (CSS classes, i18n keys, env vars, API routes, DB columns, feature flags, config keys), progress/counter/metric data flow verification (source-to-sink tracing, zero-value default detection), serialization tag audit (fields excluded from serialization but expected by consumers).

## [1.4.0] — 2026-05-26

### Added
- **Runtime/toolchain currency checks** — Level 1 now includes version checks for all 6 stacks: Go (`go version`), Python (`python --version`), Node.js (`node --version`), Rust (`rustc --version`), Java (`java --version`), .NET (`dotnet --version`). Each includes remediation guidance when stdlib/runtime vulns are found.
- **Stack Currency runtime bullets** (universal.md) — runtime update guidance for all stacks in Level 2+ section.
- **`uv tool run` fallback** (python.md) — tip for running audit tools via uv when not globally installed.
- **`npm audit fix` remediation** (frontend.md) — guidance on fixing npm vulnerabilities after scan.
- **Independent scoring verification** (README.md) — scoring agents now explicitly re-read code independently and verify CLAUDE.md claims, not just trust reviewer descriptions.

### Fixed
- **28 technical issues** found via ultrareview (5-agent parallel code review):
  - `tools.md`: removed npm osv-scanner typosquatting risk, fixed Trivy WARNING scope (v0.69.4→v0.69.4/5/6), noted security-scan deprecation, added missing tools (pip-licenses, pipreqs, dotnet-project-licenses).
  - `go.md`: corrected XXE advice (`d.Strict` is syntax-only, not security), fixed golangci-lint v2 `-E` flag removal, unified Quick reference section name, added fuzz target listing.
  - `frontend.md`: fixed `@axe-core/cli` package name and URL argument, moved Quick reference table to Level 2.
  - `csharp.md`: fixed `dotnet-outdated` CLI command name.
  - `universal.md`: JWT access ≤15min-1h (was ≤24h), PHP libxml updated for PHP 8+, bcrypt cost ≥13, PBKDF2 hash-specific iterations, yaml.v2/v3 deserialization clarified, MessageDigest.isEqual length caveat, Stack Currency relabeled Level 2+.
  - `python.md`: added Performance section to Level 3.
- **Command chaining bug** — `&&` chains in go.md and frontend.md Level 1 caused silent skipping when any tool found issues. Split into independent command blocks. Found during live audit of GOwebserver.
- **4 structural issues** — scoring-agent missing from Level-to-Wave table, undefined `{sha_before}/{sha_after}` placeholders, deprecated `code-reviewer` role reference, diff-scanner removed from Level 1.
- **Docs accuracy** — CHANGELOG trivy version check claim corrected, fork-friendly comment added, universal.md Level 1 absence noted.
- **Quick Start** — translated user command from Russian to English.

### Validated
- Live-tested Level 1 commands on Go project (GOwebserver) — all tools executed correctly.
- Live-tested Level 1+2 commands on Python project (chatbot) — ruff, pip-audit, bandit all functional via `uv tool run`.
- Verified govulncheck + staticcheck + go build + npm build/lint/audit on real codebases.

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
- **Trivy version check:** Added `trivy version` verification before active `trivy fs` commands (go.md, java.md, csharp.md). Files using trivy as a commented-out alternative (frontend.md, python.md, rust.md) noted but not actively checked.
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
