# Changelog

> Each entry describes the state **at that version**. Earlier entries are historical — behavior may have been superseded by a later release. Always read the latest version's docs for current behavior.

## [1.10.6] — 2026-05-31

### Fixed
- **Phase-0 enumeration / package-manager detection exit-code hygiene** (README Phase-0 + frontend.md PM-detect) — a bare multi-candidate `ls web/pnpm-lock.yaml web/yarn.lock web/package-lock.json web/bun.lockb` returns exit 2 whenever any candidate is absent (always — only one lockfile exists), poisoning the `;`-chained Phase-0 block with a false "Exit code 2" on a fully successful enumeration (and risking a wrongful abort in harnesses that treat non-zero as fatal). Caught on a live Go+Vue monorepo audit. Guarded the detection so it cannot set the block exit code (`|| true` / per-file `[ -f ]` loop + explicit success); DEFECT-1 (chained/piped exit-code) lineage.

## [1.10.5] — 2026-05-31

### Added
- **`audit-bugs.json` schema v1.1 — taxonomy fields for benchmarking** (README Report Format) — finding objects gain three optional fields: `cwe` (CWE id(s), populated from the detecting tool's mapping), `cve` (CVE id(s), populated for dependency/SCA findings), and `end_line` (last line of a multi-line finding; `line` stays the start). Bumped `schema_version` 1.0→1.1. Additive and back-compatible: existing required fields and the per-finding integrity invariants are unchanged. Enables automated recall/precision scoring (match findings to ground truth by CVE for SCA and by CWE+line for SAST).

## [1.10.4] — 2026-05-31

### Fixed
- **External audit remediation (5 findings, doc-only)** — applied an external FIX-DIRECTIVES review against v1.10.3 (2 MEDIUM + 3 LOW, all in README.md, no behavior change). Independently re-verified via a 6-agent adversarial workflow (all PASS) + `lint_docs.py` PASS.
- **FA-0001 run reproduction at L1+V** (README § Level-to-Wave Agent Mapping) — the `reproduction-agent-{N}` row marked the **L1** column `—` (never runs), contradicting § Verified Mode (L1+V *does* reproduce) and Wave 2.5 "runs under verified"; an orchestrator reading the table at "level 1 verified" silently dropped the `+V`. L1 cell `—`→`+V` (off by default, runs only under +V; L3 stays `yes`/always-on).
- **FA-0002 scope the no-co-author rule** (README § Fixer step 6) — the unqualified "No AI attribution / co-author lines" contradicted the repo's own history; scoped to "**on fix commits written by the audit into the target repo**", so the rule governs audit-generated fix commits, not this repo's maintenance history.
- **FA-0003 `<release-tag>` placeholder** (README § Quick Start step 1) — the example raw URL hardpinned `v1.10.3` (needed a hand-bump every release); replaced with the `<release-tag>` placeholder, matching § Files.
- **FA-0004 prefer trivy/checkov over deprecated tfsec** (README stack-command-mapping `*.tf` row) — the summary row led with `tfsec .`, which `infra.md`/`versions.lock` mark DEPRECATED; now leads `trivy config` / `checkov` (tfsec stays as the optional second opinion in infra.md).
- **FA-0005 header date** (README header) — aligned the header date with the release date.

## [1.10.3] — 2026-05-31

### Fixed
- **First live run of the frontend stack** (against a real Vue3 + Vite + Tailwind4 + pnpm project) — fixed 7 instruction defects. All doc-only; the v1.10.x features (reproduction wave / Wave 2.5, verified mode `+V`, `audit-bugs.json`, monorepo D9, SCA re-run-scanner D10) all re-validated working on this run.
- **F7 package-manager detection preamble** (frontend.md, + README stack-command-mapping + waste-scanner) — frontend.md was npm-centric but real Vue projects use pnpm/yarn/bun; added a preamble: detect the PM from the lockfile (`pnpm-lock.yaml`/`yarn.lock`/`bun.lockb`/`package-lock.json`) and substitute it in every command; `npx` works under any PM (ships with Node), `pnpm dlx` is the pnpm-native form. Covers F1 + F7 systemically.
- **F1 lockfile-aware vuln scan** (frontend.md L1 + README stack-map Vuln cell) — plain `npm audit` hard-fails (`ENOLOCK`) on a non-npm lockfile and silently scans nothing, missing real vulns; now lockfile-aware: `pnpm audit` / `yarn npm audit` (Berry) / `yarn audit` (classic) / `bun audit` / `npm audit`; `skip_if: no_tool`.
- **F2 `vue-tsc -b --noEmit` for solution-style tsconfig** (frontend.md L2 TS check + dead-asset TS step) — plain `vue-tsc --noEmit` on a solution-style root tsconfig (`files: []` + `references`) checks the EMPTY file set (0 output, exit 0) and false-PASSes, hiding all app type errors; use `-b` (build mode) to resolve project references, matching real Vue `build`/`type-check` scripts.
- **F3 purgecss Tailwind-4 caveat/skip** (frontend.md purgecss step + universal.md JS/TS FP table) — on Tailwind 4 (`@tailwindcss/vite`)/CSS-in-JS/build-time-CSS plugins, utilities are generated at build (not in source CSS), so purgecss false-flags the entire stylesheet as dead; added `skip_if: tailwind>=4 or build-time-CSS-plugin` + fall back to the manual template-usage grep. Kept the command for plain/static CSS.
- **F4 knip dist exclusion** (frontend.md waste-scanner step 1 + README waste-scanner) — Wave-1 build runs before the waste-scanner, so `dist/` exists and config-less knip reports build artifacts as unused files (~62 FPs); run knip before the build OR exclude `dist`/build dirs; added `--no-progress`.
- **F5 purgecss PowerShell `$env:TEMP`** (frontend.md purgecss step) — `$TMPDIR` is unset on Windows PowerShell (it's `$env:TEMP`); the PS-facing command now uses `$env:TEMP\purgecss`, bash keeps a temp dir (`${TMPDIR:-/tmp}/purgecss`), so both shells have a valid output dir.
- **F6 tests PowerShell twin** (frontend.md L1 Tests block) — the bash `grep`/`if` tests block had `skip_if: windows` but no real PS detector (unlike the L3 dev-server block); added a PowerShell twin (`Select-String` to detect vitest/jest/Angular in package.json scripts → run the detected runner), so Windows runs the check instead of skipping.

## [1.10.2] — 2026-05-31

### Fixed
- **First live run of the Python stack** — fixed 7 instruction defects + 1 Windows signal caught running the audit against a real aiogram/FastAPI chatbot. All doc-only; the v1.10.0/1.10.1 features (reproduction wave / Wave 2.5, verified mode `+V`, `audit-bugs.json`, osv-scanner-missing SCA fallback, Phase-0 infra tool enumeration) all re-validated working on this run.
- **DEFECT-P1 build/lint scope-to-source** (python.md L1 + README stack-command-mapping + Quality Gates) — a bare `.` walks non-code trees (e.g. a `data/` knowledge base), flooding output and exceeding Windows MAX_PATH; scope to source roots (`compileall src tests`, `ruff check src tests`) or `extend-exclude` data/asset/KB dirs.
- **DEFECT-P2 pip-audit project scope** (python.md) — bare `pip-audit` scans the active venv (mixes project deps with installed audit tools); prescribe `pip-audit -r requirements.txt` (or a project-only venv) and flag unpinned `>=` requirements resolving to latest, not the deployed version.
- **DEFECT-P3 semgrep offline rulesets** (python.md, parity with go.md v1.9.1) — `--config=auto` needs network and dies offline (exit 2, zero output); offline rulesets (`p/python`, `p/security-audit`, `p/secrets`) now primary, `--config=auto` demoted to online-only, added `skip_if: no_tool(semgrep)` + no-network fallback to bandit (offline SAST twin).
- **DEFECT-P4 mypy L2 informational** (python.md L1 note + new L2 step + README Quality Gates) — untyped projects (no mypy config) missed type-checking until L3; mypy now runs informationally at L2 (`mypy src --ignore-missing-imports`, best-effort) to catch real type bugs earlier.
- **DEFECT-P5 vulture framework-callback FP** (universal.md Python FP table) — `vulture --min-confidence 80` flags framework-dispatch callback params (aiogram/aiogram-dialog handler args `button`/`widget`/`start_data`, Django views, pydantic `@field_validator cls`) as unused (~40 FPs); added an ignore row — required by the dispatch contract, not dead.
- **DEFECT-P6 infra no_tool manual-review fallback** (infra.md L1/L2 + README infra note) — every infra tool (hadolint/trivy/checkov) is tool-gated; added a runnable manual-review checklist (non-root `USER`, digest-pinned base image, no `0.0.0.0` bind, no inline creds, resource limits) mirroring the osv-scanner no_tool fallback.
- **DEFECT-P7 gitleaks Windows choco cross-ref** (python.md) — the install line showed only `go install ...` (needs Go toolchain); added `Windows: choco install gitleaks --version=8.30.1 (see tools.md)`.
- **Windows long-path clone note** (README Pre-conditions) — Windows clones of repos with deep trees / very long filenames (e.g. `data/kb/`) can fail `git checkout` with "Filename too long" (MAX_PATH); enable `git config core.longpaths true` (and OS long-path support) before cloning, or scope to source dirs.

## [1.10.1] — 2026-05-31

### Fixed
- **Second live run remediation** — fixed 10 instruction defects caught running the audit against a real Go marketplace monorepo. All doc-only; the new v1.10.0 features (reproduction wave / Wave 2.5, verified mode `+V`, `infra.md`, `audit-bugs.json`) all validated working on this run.
- **DEFECT-1 piped-exit-code caution** (go.md + README stack-command-mapping) — piping a tool into `| head`/`| grep`/`| tail` clobbers `$?` (reflects the pipe stage, not the tool), silently masking failures the CLI-scanner trust policy depends on; capture exit before any pipe (`cmd; ec=$?` / `set -o pipefail`; PowerShell `$LASTEXITCODE`).
- **DEFECT-2 osv-scanner-missing SCA fallback** (README waste-scanner step 0 + web-researcher note + infra.md) — when the sole universal SCA is absent, per-stack vuln tools (govulncheck/`npm audit`/`pip-audit`/`cargo audit`) cover their own ecosystem; note remaining cross-ecosystem coverage as an Audit Limitation.
- **DEFECT-3 golangci-config precedence** (go.md) — if the repo has `.golangci.yml`/`.golangci.yaml`, run `golangci-lint run ./...` (honors config) and report active linters; the explicit `--enable` list is ONLY for config-less repos.
- **DEFECT-4 fuzz/race Windows-guard wording** (go.md) — reworded the bash `skip_if: windows` so Windows runs the PowerShell twin instead of skipping the check entirely; PS fuzz twin now guards the zero-`*_test.go` case (no `Select-String -Path $null` throw).
- **DEFECT-5 gitleaks tracked/ignored/untracked tie-break** (go.md SK3) — explicit precedence: tracked (`git ls-files --error-unmatch` exit 0) ⇒ REAL regardless of check-ignore; else ignored ⇒ INFO; else untracked-and-not-ignored ⇒ INFO-pending.
- **DEFECT-6 deadcode test-helper FPs** (go.md) — test-only helpers (`testutil`, `Setup*`/`Seed*`) called only from `_test.go` / behind build tags are commonly mis-reported unreachable; cross-check `_test.go` callers before reporting.
- **DEFECT-7 gosec //nolint post-filter** (go.md gosec + README False-Positive Whitelist) — gosec does not honor inline `//nolint:gosec`; post-filter its findings against those directives before scoring.
- **DEFECT-8 Phase-0 infra tool enumeration** (README Step 2c) — when infra/CI artifacts are detected, extend the Go-only tool-check list with the infra.md tools (hadolint, trivy, checkov, tfsec, kube-linter, actionlint, zizmor) + osv-scanner.
- **DEFECT-9 monorepo node_modules/vendor exclusion** (README monorepo handling) — exclude `node_modules/`, `vendor/`, `.git/`, and build/dist dirs when enumerating package-root manifests (avoids 100+ phantom roots).
- **DEFECT-10 SCA/CVE reproduction method** (README Wave 2.5 plan + reproduction-agent prompt) — for SCA/CVE findings, reproduction = re-run the scanner, capture exit code + the pinned vulnerable version from the lockfile (no fabricated test).

## [1.10.0] — 2026-05-30

### Added
- **Reproduction wave (Wave 2.5)** — new `reproduction-agent`; independently reproduces every CRITICAL/HIGH finding via a failing test or CLI command before it is trusted. Static-by-default (never starts servers/DBs; live-runtime-only findings → `SKIPPED: requires runtime`). REPRODUCED floors score at 90; NOT_REPRODUCED caps at 25 (−1 severity); conflict rule re-runs once when scoring ≥75 disagrees.
- **Verified mode (`+V`)** — orthogonal trust axis: level sets depth, verified mode sets trust. Runs Wave 2.5. OFF by default at L1/L2; ALWAYS ON at L3. Request via "verified"/"+V".
- **`infra.md`** — Docker / Kubernetes / Terraform / GitHub Actions auditing (hadolint, trivy config, checkov, tfsec, kube-linter, actionlint, zizmor). Phase 0 now detects `Dockerfile`/`*.tf`/workflows/K8s manifests and fetches it.
- **osv-scanner SCA layer** — lockfile-accurate CVEs across all ecosystems as the first dependency check in the waste-scanner step.
- **PR mode** — audit a pull request by number via a detached worktree + `gh` base-branch resolution; implies Diff-Mode scope.
- **Machine-readable `audit-bugs.json`** — structured artifact alongside the markdown report (not committed); integrity rules tie it to the markdown findings.
- **Explicit monorepo step** in Phase 0 (enumerate package roots, scope with user, per-package agents); documented the `versions.lock` contract.

## [1.9.1] — 2026-05-30

### Fixed
- **First live run remediation** — fixed 15 instruction defects (SK1–SK15) caught running the audit against a real Go CLI repo. All doc-only.
- **semgrep** (go.md) — offline rulesets (`p/security-audit`, `p/secrets`, `p/golang`) are now the primary invocation; `--config=auto` demoted to an online-only option with a network note; added `skip_if: no_tool(semgrep)` + no-network fallback. Was silently producing zero SAST offline.
- **Serena preflight** (README.md) — health check now calls `activate_project` + a `get_symbols_overview` liveness probe instead of only `initial_instructions` (which reported a false-green while symbol nav was dead). MCP example calls use a `{prefix}` placeholder instead of a hardcoded bare prefix.
- **gitleaks** (go.md) — post-filter `--no-git` hits through `git check-ignore`/`git ls-files` (gitignored/untracked ⇒ INFO, not a committed-secret false positive); report path moved out-of-tree (no `.gitignore`-exists assumption).
- **universal.md git hygiene** — Windows large-file check now measures tracked git-OBJECT sizes (not working-tree `ls`, which false-positived on gitignored artifacts); added PowerShell twins + a `git check-ignore`/`status --ignored` assertion to the suspicious-files and `.gitignore`-completeness checks.
- **G104 `defer Close` whitelist** (universal.md + go.md) — narrowed to read-only handles; mutating/exec/commit handles must check or log; the two files are now consistent.
- **Misc** — `skip_if` guards for `go-licenses`/`betteralign`; fuzz block auto-derives target name + package (removed unrunnable `FuzzXxx`/`./path/to/package/` placeholders in both bash and PowerShell twins); deadcode-vs-staticcheck-U1000 divergence note; `-race` skip must be stated in the concurrency verdict; `SafeJoinPath`/`ValidateURLScheme` marked illustrative + CLI operator-path carve-out; solo-DEEP reviewer-role note.

## [1.9.0] — 2026-05-30

### Added
- **`versions.lock`** — single source of truth mirroring the ~62 tool pins in `tools.md` (maintainer-facing; not fetched at runtime). Carries the Trivy `security_hold` (no bump until `0.70.0`).
- **`scripts/check_versions.py`** — stdlib-only weekly version-drift + CVE checker (npm/pypi/go/cargo/nuget via registries + OSV.dev); respects `security_hold`; emits an advisory `version-report.md`.
- **`scripts/lint_docs.py`** — stdlib-only doc self-test: cross-ref resolution, code-fence balance, README↔CHANGELOG version match, table-column consistency, `versions.lock`↔docs pin-drift.
- **CI** — `.github/workflows/version-check.yml` (weekly cron → advisory PR) and `.github/workflows/lint.yml` (lint on push/PR). Maintainer-only; zero friction for skill users.

### Changed
- **Model tiers abstraction** — introduced `FAST` (haiku) / `RESEARCH` (sonnet) / `DEEP` (opus) tier vocabulary; replaced ~100 inline model literals across README/universal/stack files with tier tokens so model names can be swapped per environment without touching assignments.
- **Bootstrap fetch hardening** — README fetch step now resolves `releases/latest` → concrete release tag instead of dangling `{pinned_sha}`/`{release_tag}` placeholders (which silently fell back to mutable `main`).
- **Dedup** — merged two near-duplicate Playwright UI-testing sections in `universal.md`; collapsed the repeated Trivy supply-chain warning to a one-liner + `tools.md` pointer across stack files (pin and security signal preserved); deduped a duplicated MCP prefix-legend in README.

## [1.8.0] — 2026-05-30

### Changed
- **Fixer root-cause TRACE step** — fix at the origin, not the symptom; **defense-in-depth layering** for CRITICAL/HIGH data-flow findings; **self-review before handoff**; **architecture-escalation branch** added to the 3-strike STOP rule.
- **Orchestrator poll-until-condition** (`waitFor`) — condition-based waiting replaces wall-clock timers; **compressed subagent output discipline** (~60% less orchestrator context).
- **Review agent-report format** — one-line `path:line: <emoji> <sev>: problem. fix.`; **`❓ q:` question outlet**; **no-praise / no-scope-creep rule** (auto-clarity exception for security/architecture).
- **Commits/tasks** — subject ≤50 chars; body mandatory for security/migration/breaking changes; **no-placeholder banned-list** in fix tasks.

### Added
- **'Defense-in-Depth Validation' L3 check** (universal.md).

## [1.7.0] — 2026-05-30

### Security
- **Removed `curl … | sh` installers** — replaced with pinned release binaries + SHA256 verification (or the researched better alternative).
- **Pinned all tool versions** — every install/`npx`/download pinned to an exact version; no `@latest`.
- **`gitleaks --redact`** — added `--redact`, findings written to a gitignored report path, dropped `-v` from agent-captured (`2>&1`) output.
- **Pinned instruction-fetch to an immutable ref** — fetch playbook instructions by immutable commit ref, not a mutable branch/tag.
- **Explicit install consent** — tools install only with explicit user consent on level selection.

### Fixed
- **Command corrections** — golangci-lint v2 flags; `dotnet format` built-in SDK command (dropped deprecated `dotnet-format` tool); i18n-unused `display-unused` keys; `py_compile` → `compileall`; gocyclo cyclomatic-complexity threshold.
- **Windows `skip_if` guards** — bash-only commands (`which`, `command -v`, `for…do`, `find`, `grep`, `/dev/null`, `seq`) guarded with `skip_if: windows` or given PowerShell equivalents.
- **Stack parity** — secrets check skips when Trivy is the engine (skip-if-Trivy); added Python concurrency note.

### Added
- **'Documentation Concision' L3 check** — bullet-style, drop filler words, keep every value/name/path/command/URL exact.

### Docs
- **MCP prefix note**, **step-1.5 reference**, **license deliverable**, **unenforceable-timer reframe**, and **version-stale framework notes** (JDK 24, `GeneratedRegex`, React hooks).

## [1.6.0] — 2026-05-28

### Added
- **Pre-audit tool integrity protocol** (tools.md) — mandatory supply chain verification before ANY audit: npm version check, maintainer identity validation, publish date verification, checksum validation, Go sumdb verification. Red flags list for compromised packages. Runs BEFORE Wave 1.
- **Automated CLI waste detection** (frontend.md, README.md) — `waste-scanner` agent now runs `knip@latest`, `purgecss@latest`, `i18n-unused@latest`, `dotenv-check@latest` CLI tools instead of manual greps. Manual reasoning checks (CSS framework utilization, dead UI features, missing i18n keys) remain as Opus-only tasks in `impact-reviewer`.
- **`waste-scanner` agent** (README.md, Wave 1, L2+) — new haiku agent that runs automated cross-reference checks CLI tools like knip miss: dependency utilization (depcheck/cargo udeps/pip-extra-reqs), CSS framework utilization, dead CSS classes, dead i18n keys, tsconfig/eslint strictness verification, env var coherence. 1 per project, runs in parallel with cli-scanners.
- **`impact-reviewer` expanded responsibilities** (README.md, Wave 2) — three new cross-file checks: serialization tag audit (fields with `json:"-"`/`@JsonIgnore`/`[NonSerialized]` that have active consumers), progress/counter data flow tracing (source to display, silent reset detection), dead UI features (state variables without reachable triggers).
- **Dead Asset Detection** (frontend.md, L2) — 6 cross-reference checks that CLI tools miss: CSS framework utilization, dead CSS classes, dead i18n/localization keys, dependency utilization audit beyond knip/depcheck, dead imports enforcement, dead UI features (state without triggers). All checks are framework-agnostic — work for React, Vue, Svelte, Angular, Solid, or vanilla JS.
- **Cross-Stack Waste Detection** (universal.md, L2) — 4 universal waste detection checks for any tech stack: config-dependency coherence (with per-stack tooling: depcheck, go mod tidy, cargo udeps, pip-extra-reqs), declared-vs-used asset audit (CSS classes, i18n keys, env vars, API routes, DB columns, feature flags, config keys), progress/counter/metric data flow verification (source-to-sink tracing, zero-value default detection), serialization tag audit (fields excluded from serialization but expected by consumers).

## [1.5.0] — 2026-05-27

### Added
- **Interactive depth selection** — user picks audit depth (Level 1/2/3) interactively at start.
- **MCP preflight** — verify required MCP servers are available before spawning agents.
- **Functional UI testing (Playwright)** — automated browser-driven UI checks via Playwright MCP.
- **CLI tools install on level selection** — required CLI tools installed when the audit level is chosen.

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
