# Changelog

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
