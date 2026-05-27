# Tool Installation

> **Version pinning:** Pin specific versions in CI for reproducibility. Versions below recommended as of 2026-04.

First-time only. Install per detected stack. Check tool exists before installing.

---

## Pre-Audit Tool Integrity Protocol

Before ANY audit, orchestrator MUST ensure tools are:
1. **Latest version** — install with `@latest`, never pin in audit
2. **Integrity-verified** — check against supply chain compromise

### Version + Integrity Check (run BEFORE Wave 1)

npm-based tools:
```bash
# 1. Update to latest
npm install -g knip@latest purgecss@latest i18n-unused@latest dotenv-check@latest

# 2. Check publish date — compromised packages show sudden version bumps
npm view knip time --json | tail -5
npm view purgecss time --json | tail -5

# 3. Verify maintainer hasn't changed
npm view knip maintainers
npm view purgecss maintainers

# 4. Check vulnerabilities in audit tools
npm audit --registry https://registry.npmjs.org

# 5. Verify checksum (npm v9+)
npm cache ls knip 2>/dev/null | head -5

# 6. Check npm advisories and Socket.dev for alerts
```

### Red flags — STOP and investigate:
- Maintainer changed in last 30 days
- Version bump > 2 major since last audit
- Package age < 6 months with sudden popularity spike
- `postinstall` script added recently
- New dependencies added (check `npm view <pkg> dependencies`)

### Go tools:
```bash
go install golang.org/x/tools/cmd/deadcode@latest
go install github.com/securego/gosec/v2/cmd/gosec@latest
go install honnef.co/go/tools/cmd/staticcheck@latest

# Force sum verification
GONOSUMCHECK= go install ...
```

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

# Goroutine leak detector (test dep, not CLI)
# Per-project: go get go.uber.org/goleak
# Usage: goleak.VerifyTestMain(m) in TestMain — see go.md

# Struct alignment optimizer
go install github.com/dkorunic/betteralign/cmd/betteralign@latest

# Dep vulnerability (alt to govulncheck)
go install github.com/sonatype-nexus-community/nancy@latest
```

> Windows: Race detector needs MinGW-w64 (`gcc` in PATH).
> Verify: `gcc --version`. Install: `choco install mingw` or https://winlibs.com/

---

## Node.js / Frontend

Via `npx` — no global install needed:
- `knip` — dead code, unused deps/exports/files. `npx knip@latest`
- `purgecss` — dead CSS. `purgecss --css src/app.css --content 'src/**/*.svelte' --output /dev/null --rejected` (dry-run, shows unused selectors)
- `i18n-unused` — dead i18n keys. Config: `.i18n-unused.yml`. `npx i18n-unused display-unused-keys`
- `dotenv-check` — dead env vars. `npx dotenv-check@latest`
- `vue-tsc` — Vue TypeScript check
- `license-checker` — license compliance

Optional global:
```bash
npm install -g knip@latest             # dead code, unused deps/exports/files
npm install -g purgecss@latest         # dead CSS
npm install -g i18n-unused@latest      # dead i18n keys
npm install -g dotenv-check@latest     # dead env vars
npm install -g npm-check-updates       # ncu — interactive dep update
npm install -g snyk                    # vuln scanner with fix suggestions
```

ESLint plugin (project-level):
- `eslint-plugin-unused-imports` — per-file dead import autofix

Additional `npx` tools:
- `npx depcheck` — find unused deps
- `npx audit-ci` — CI-friendly npm audit wrapper, configurable severity thresholds

---

## Python

```bash
pip install ruff           # Linter + formatter (replaces flake8, isort, black)
pip install pip-audit      # Vulnerability scanner
pip install bandit         # Security linter (SAST)
pip install mypy           # Type checker
pip install vulture        # Dead code finder
pip install radon          # Complexity metrics
pip install safety         # Dep vuln check (alt to pip-audit)
pip install pip-licenses   # License compliance
pip install pipreqs        # Generate requirements.txt from imports
```

- **uv**: `curl -LsSf https://astral.sh/uv/install.sh | sh` — faster pip alt, handles dep resolution

---

## Rust

```bash
rustup component add clippy        # Linter
rustup component add rustfmt       # Formatter
cargo install cargo-audit          # Vulnerability scanner
cargo install cargo-deny           # License + vuln + ban checker
cargo install cargo-outdated       # Dep freshness
cargo install cargo-geiger         # Unsafe code counter
cargo install cargo-tarpaulin      # Code coverage (Linux only)
cargo install cargo-bloat          # Binary size analysis
cargo install cargo-udeps          # Unused deps (nightly)
cargo install cargo-supply-chain   # Shows maintainers per dep
cargo install cargo-vet            # Mozilla dep review tracking
```

---

## Java / Kotlin (JVM)

Managed via build system (Gradle/Maven plugins). No separate install for most.

```bash
# SpotBugs — bug finder (Gradle: spotbugs plugin)
# PMD — static analysis (Gradle: pmd plugin)
# Checkstyle — style checker (Gradle: checkstyle plugin)

# Standalone: OWASP dependency-check
# https://github.com/jeremylong/DependencyCheck
```

---

## C# / .NET

```bash
dotnet tool install -g dotnet-format           # Formatter
dotnet tool install -g security-scan           # Vuln scanner (archived ~2020; prefer Puma.Security.Rules or Roslyn analyzers for .NET 6+)
dotnet tool install -g dotnet-outdated-tool     # Dep freshness (pkg: dotnet-outdated-tool)
dotnet tool install -g dotnet-project-licenses  # License compliance
# Roslyn analyzers — via NuGet in .csproj
```

---

## Universal (all stacks)

```bash
# Trivy — CVE + secrets + licenses (all package managers)
# WARNING: v0.69.4-v0.69.6 ALL compromised (TeamPCP, 2026-03-19). Pin v0.69.3!
choco install trivy --version=0.69.3    # Windows
# brew install trivy                     # macOS
# apt install trivy                      # Linux

# Semgrep — SAST (30+ langs). Native Windows since Fall 2025.
pip install --upgrade semgrep
# Windows: ensure Python in PATH
# UTF-8: [System.Environment]::SetEnvironmentVariable('PYTHONUTF8','1','User')
# Docker: docker run --rm -v "$(pwd):/src" semgrep/semgrep semgrep --config=auto /src

# Gitleaks — secrets scanner (also in Go section)
choco install gitleaks    # Windows
# brew install gitleaks   # macOS

# TruffleHog v3 — deep secrets scanner (verifies live creds via API)
# More thorough than gitleaks for git history
# WARNING: `pip install trufflehog` = abandoned v2 (2021). Use Go binary:
curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b /usr/local/bin
# Or: go install github.com/trufflesecurity/trufflehog/v3@latest
# Or: brew install trufflehog
# Or: docker run --rm -v "$(pwd):/src" trufflesecurity/trufflehog filesystem /src

# OSV-Scanner (Google) — vuln scanner, OSV database
# Supports go.sum, package-lock.json, requirements.txt, Cargo.lock
go install github.com/google/osv-scanner/cmd/osv-scanner@latest
# Or: brew install osv-scanner | download from github.com/google/osv-scanner/releases

# Detect-Secrets (Yelp) — pre-commit secrets scanner with baseline
pip install detect-secrets

# Checkov — IaC security (Terraform, Dockerfile, K8s, GitHub Actions)
pip install checkov

# Syft — SBOM generator (CycloneDX/SPDX)
# Supports: Go, Node, Python, Rust, Java, C#, containers
choco install syft       # Windows
# brew install syft      # macOS
```

### Trivy Security Notice

> **CRITICAL: Trivy v0.69.4-v0.69.6 ALL compromised.**
>
> 2026-03-19: TeamPCP (DeadCatx3/ShellForce) used compromised `aqua-bot` creds to publish
> malicious binaries with infostealer exfiltrating Runner secrets (SSH, cloud, K8s).
>
> **Timeline:**
> - v0.69.4: 2026-03-19 18:22-21:42 UTC (initial)
> - v0.69.5, v0.69.6: 2026-03-22 (secondary, also Docker Hub `latest` tag)
> - `trivy-action`: 75/76 tags force-pushed (safe: v0.35.0)
> - `setup-trivy`: all 7 tags force-pushed (safe: v0.2.6)
>
> **Safe: v0.69.3** (GitHub immutable releases since 2026-03-03).
>
> **CI:** pin Actions by immutable commit SHA, never mutable tag.
> **Local:** verify checksum. `trivy version` to confirm.
>
> Ref: [GHSA-69fq-xp46-6x23](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23)
