# Tool Installation

> **Version pinning:** When installing tools, pin to specific versions in CI to ensure reproducible results. The versions below are recommendations as of 2026-04.

First-time only. Install per detected stack. Check if tool exists before installing.

---

## Go

```bash
go install honnef.co/go/tools/cmd/staticcheck@latest
go install golang.org/x/vuln/cmd/govulncheck@latest
go install github.com/securego/gosec/v2/cmd/gosec@latest
go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@latest   # v2!
go install golang.org/x/tools/cmd/deadcode@latest
go install github.com/google/go-licenses/v2@latest
go install github.com/gitleaks/gitleaks/v8@latest
go install github.com/kisielk/errcheck@latest

# Goroutine leak detector (for tests)
go install go.uber.org/goleak/cmd/goleak@latest

# Struct alignment optimizer
go install github.com/dkorunic/betteralign/cmd/betteralign@latest

# Dependency vulnerability (alternative to govulncheck)
go install github.com/sonatype-nexus-community/nancy@latest
```

> Windows: Go race detector requires MinGW-w64 (`gcc` in PATH).
> Verify: `gcc --version`. Install: `choco install mingw` or download from https://winlibs.com/

---

## Node.js / Frontend

Tools run via `npx` — no global install needed:
- `knip` — dead code/exports
- `vue-tsc` — Vue TypeScript check
- `license-checker` — license compliance

Optional global:
```bash
npm install -g npm-check-updates   # ncu — interactive dependency update
npm install -g snyk                # Alternative vuln scanner with fix suggestions
```

Additional `npx` tools (no install needed):
- `npx depcheck` — find unused dependencies
- `npx audit-ci` — CI-friendly npm audit wrapper with configurable severity thresholds

---

## Python

```bash
pip install ruff           # Linter + formatter (replaces flake8, isort, black)
pip install pip-audit      # Vulnerability scanner
pip install bandit         # Security linter (SAST)
pip install mypy           # Type checker
pip install vulture        # Dead code finder
pip install radon          # Complexity metrics
pip install safety         # Dependency vulnerability check (alternative to pip-audit)
```

- **uv** (Python package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh` — faster alternative to pip, handles dependency resolution

---

## Rust

```bash
# Most tools ship with rustup
rustup component add clippy        # Linter
rustup component add rustfmt       # Formatter
cargo install cargo-audit          # Vulnerability scanner
cargo install cargo-deny           # License + vulnerability + ban checker
cargo install cargo-outdated       # Dependency freshness
cargo install cargo-geiger         # Unsafe code counter
cargo install cargo-tarpaulin      # Code coverage (Linux only)
cargo install cargo-bloat          # Binary size analysis
cargo install cargo-udeps          # Unused dependencies (nightly)
cargo install cargo-supply-chain   # Shows who maintains each dependency
cargo install cargo-vet            # Mozilla's code review tracking for deps
```

---

## Java / Kotlin (JVM)

Tools managed via build system (Gradle/Maven plugins). No separate install for most.

```bash
# SpotBugs — bug finder (Gradle: spotbugs plugin)
# PMD — static analysis (Gradle: pmd plugin)
# Checkstyle — style checker (Gradle: checkstyle plugin)

# Standalone:
# OWASP dependency-check
# https://github.com/jeremylong/DependencyCheck
```

---

## C# / .NET

```bash
dotnet tool install -g dotnet-format           # Formatter
dotnet tool install -g security-scan           # Vulnerability scanner
dotnet tool install -g dotnet-outdated-tool     # Dependency freshness (note: package name is dotnet-outdated-tool)
# Roslyn analyzers — via NuGet in .csproj
```

---

## Universal (all stacks)

```bash
# Trivy — CVE + secrets + licenses (all package managers)
# WARNING: v0.69.4 compromised (TeamPCP, 2026-03-19). Pin to safe version!
choco install trivy --version=0.69.3    # Windows
# brew install trivy                     # macOS
# apt install trivy                      # Linux

# Semgrep — SAST (30+ languages). Native Windows support since Fall 2025.
pip install --upgrade semgrep
# On Windows: ensure Python in PATH
# Set UTF-8: [System.Environment]::SetEnvironmentVariable('PYTHONUTF8','1','User')
# Docker fallback: docker run --rm -v "$(pwd):/src" semgrep/semgrep semgrep --config=auto /src

# Gitleaks — secrets scanner
# Already in Go tools above, or:
choco install gitleaks    # Windows
# brew install gitleaks   # macOS

# TruffleHog v3 — deep secrets scanner (verifies live credentials via API)
# More thorough than gitleaks for git history scanning
# WARNING: `pip install trufflehog` installs abandoned v2 (2021). Use Go binary:
# Install script (recommended):
curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b /usr/local/bin
# Or via Go:
go install github.com/trufflesecurity/trufflehog/v3@latest
# Or via Homebrew:
# brew install trufflehog
# Or Docker:
# docker run --rm -v "$(pwd):/src" trufflesecurity/trufflehog filesystem /src

# OSV-Scanner (Google) — vulnerability scanner using OSV database
# Natively supports go.sum, package-lock.json, requirements.txt, Cargo.lock
go install github.com/google/osv-scanner/cmd/osv-scanner@latest
# Or: npm install -g osv-scanner

# Detect-Secrets (Yelp) — pre-commit secrets scanner with baseline
pip install detect-secrets

# Checkov — IaC security scanner (Terraform, Dockerfile, K8s, GitHub Actions)
pip install checkov

# Syft — SBOM generator (CycloneDX/SPDX)
# Supports: Go, Node, Python, Rust, Java, C#, containers
choco install syft       # Windows
# brew install syft      # macOS
```

### Trivy Security Notice

> **CRITICAL: Trivy v0.69.4, v0.69.5, and v0.69.6 are ALL compromised.**
>
> On 2026-03-19, TeamPCP (aka DeadCatx3/ShellForce) used compromised `aqua-bot` credentials to publish
> malicious Trivy binaries containing an infostealer that exfiltrates Runner secrets (SSH, cloud, K8s).
>
> **Timeline:**
> - v0.69.4: 2026-03-19 18:22–21:42 UTC (initial compromise)
> - v0.69.5, v0.69.6: 2026-03-22 (secondary attack, also Docker Hub `latest` tag)
> - `trivy-action`: 75/76 tags force-pushed (safe: v0.35.0)
> - `setup-trivy`: all 7 tags force-pushed (safe: v0.2.6)
>
> **Safe version: v0.69.3** (protected by GitHub immutable releases since 2026-03-03).
>
> **In CI:** pin GitHub Actions by immutable commit SHA, never by mutable version tag.
> **Locally:** verify binary checksum before use. Run `trivy version` to confirm.
>
> References: [GHSA-69fq-xp46-6x23](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23)
