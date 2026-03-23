# Tool Installation

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
```

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
dotnet tool install -g dotnet-outdated         # Dependency freshness
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
```

### Trivy Security Notice

> **Trivy v0.69.4** was compromised on 2026-03-19 by TeamPCP group (infostealer malware).
> Compromised window: ~3 hours (18:22-21:42 UTC). Also affected: `trivy-action` (~12h), `setup-trivy` (~4h).
> **Safe version: v0.69.3** (released 2026-03-03, before incident).
> In CI: pin by immutable commit SHA, never by mutable tag.
> Verify binary SHA before use.
