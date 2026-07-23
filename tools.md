# Tool Installation

> **Version pinning:** Pin specific versions in CI for reproducibility. Versions below recommended as of 2026-05-30.

First-time only. Install per detected stack. Check tool exists before installing.

> **Windows/PowerShell host.** Bash `curl … | sha256sum` install recipes below are marked `skip_if: windows`; use the PowerShell twin (e.g. trufflehog below) or the `choco` line where present. Prefer a checksum-gated package manager (`choco --require-checksums`) over a raw download.
> **git-wrapping proxies corrupt counts.** A token-optimizing git wrapper/hook (e.g. `rtk`) can mangle `git` output and flags (wrong `rev-list`/`ls-files` counts; a rewritten `/p:`/`--property:` flag). For any census/count command whose number is load-bearing, run **raw `git`** (bypass the proxy) and verify.

---

## Pre-Audit Tool Integrity Protocol

Before ANY audit, orchestrator MUST ensure tools are:
1. **Pinned** — pin to a verified version (per-tool, see research); use `@latest` only after integrity check passes
2. **Integrity-verified** — check against supply chain compromise BEFORE install

### Step 1 — Verify integrity (run BEFORE install, BEFORE Wave 1)

npm-based tools. Run these FIRST; the red-flag gate below aborts install on any hit:

```bash
# > skip_if: windows  (uses tail; PowerShell equivalent below)
# Publish dates — compromised packages show sudden bumps
npm view knip time --json | tail -5
npm view purgecss time --json | tail -5
# Maintainers — must be unchanged from prior audit
npm view knip maintainers
npm view purgecss maintainers
# Dependencies — flag newly added
npm view knip dependencies
```

PowerShell equivalent:
```powershell
npm view knip time --json | ConvertFrom-Json
npm view knip maintainers
npm view purgecss maintainers
npm view knip dependencies
```

### Step 2 — BLOCKING red-flag gate (ABORT install if ANY are true)

- Maintainer/ownership changed in last 30 days → ABORT
- Recent advisory (npm advisories / Socket.dev / Snyk / OSV) → ABORT
- Version bump > 2 major since last audit → ABORT
- Package age < 6 months with sudden popularity spike → ABORT
- `postinstall`/`preinstall` script added recently → ABORT
- New unexpected dependencies → ABORT

### Step 3 — Install pinned (only if gate passes)

```bash
npm install -g knip@6.14.2 purgecss@8.0.0 i18n-unused@0.19.0 dotenv-check@1.0.4
# dotenv-check is unmaintained — prefer replacement dotenv-linter (see Node.js section)
```

### Step 4 — Post-install verification

```bash
npm audit --registry https://registry.npmjs.org   # vulns in installed tools
npm cache verify                                   # integrity of cached packages (replaces removed `npm cache ls`)
```

### Go tools (proxy + checksum DB give tamper-evident installs):
```bash
go install golang.org/x/tools/cmd/deadcode@v0.45.0
go install github.com/securego/gosec/v2/cmd/gosec@v2.26.1
go install honnef.co/go/tools/cmd/staticcheck@v0.7.0

# Enforce checksum verification (GONOSUMCHECK is obsolete/no-op):
#   GOFLAGS=-mod=readonly   GOSUMDB=sum.golang.org   (do NOT set GONOSUMDB/GOFLAGS=-insecure)
```

---

## Go

```bash
go install honnef.co/go/tools/cmd/staticcheck@v0.7.0
go install golang.org/x/vuln/cmd/govulncheck@v1.3.0
go install github.com/securego/gosec/v2/cmd/gosec@v2.26.1
go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.12.2   # v2!
go install golang.org/x/tools/cmd/deadcode@v0.45.0
go install github.com/google/go-licenses/v2@v2.0.1
go install github.com/gitleaks/gitleaks/v8@v8.30.1
go install github.com/kisielk/errcheck@v1.20.0   # or bundled in golangci-lint (enable errcheck linter)

# Goroutine leak detector (test dep, not CLI)
# Per-project: go get go.uber.org/goleak@v1.3.0
# Usage: goleak.VerifyTestMain(m) in TestMain — see go.md

# Struct alignment optimizer
go install github.com/dkorunic/betteralign/cmd/betteralign@v0.11.0

# Dep vulnerability (alt to govulncheck)
go install github.com/sonatype-nexus-community/nancy@v2.0.0   # checksums only, no signature: verify SHA-256 vs nancychecksums.txt if using release binaries
# Denser alt: govulncheck (above) is reachability/call-graph aware — complementary, prefer it
```

> Windows: Race detector needs MinGW-w64 (`gcc` in PATH).
> Verify: `gcc --version`. Install: `choco install mingw --version=15.2.0 -y` or https://winlibs.com/ (verify published SHA256)

---

## Node.js / Frontend

Via `npx` — no global install needed (pinned):
- `knip` — dead code, unused deps/exports/files. `npx --yes knip@6.14.2`
- `purgecss` — dead CSS. `npx --yes purgecss@8.0.0 --css src/app.css --content 'src/**/*.svelte' --rejected` (dry-run, shows unused selectors; `--output /dev/null` is Unix-only — omit on Windows or use a temp dir)
- `i18n-unused` — dead i18n keys. Config: `.i18n-unused.yml`. `npx --yes i18n-unused@0.19.0 display-unused` (i18next-only projects: prefer actively-maintained `i18next-cli@1.58.1`, not framework-agnostic)
- `dotenv-check` — dead env vars (unmaintained). Replace with `dotenv-linter@3.3.0` (Rust): `cargo install dotenv-linter --version 3.3.0`, or pinned GitHub release binary + `sha256sum -c`
- `vue-tsc` — Vue TypeScript check. Prefer the project's own `npm run build` / `vue-tsc --build`; else unpinned `npx --yes vue-tsc -b --noEmit` (fallback `npx --yes tsc --noEmit`). Do NOT hard-pin vue-tsc to one TS minor — it's tsc-coupled, so a stale pin silently drops type-check coverage on modern-TS (TS6) projects.
- `license-checker` — license compliance (unmaintained). Replace with drop-in fork: `npx --yes license-checker-evergreen@6.3.1 --failOn "GPL-2.0;GPL-3.0;LGPL-2.1;LGPL-3.0;AGPL-3.0"`

Optional global / dev (pinned, exact):
```bash
npm install --save-dev --save-exact knip@6.14.2          # dead code, unused deps/exports/files
npm install --save-dev --save-exact purgecss@8.0.0       # dead CSS
npm install --save-dev --save-exact i18n-unused@0.19.0   # dead i18n keys
# dotenv-check unmaintained — use dotenv-linter@3.3.0 (see above) instead of dotenv-check@1.0.4
npm install -g npm-check-updates@22.2.1                  # ncu — interactive dep update
npm install -g snyk@1.1305.0                             # vuln scanner with fix suggestions
```

ESLint plugin (project-level, pinned):
- `eslint-plugin-unused-imports` — per-file dead import autofix. `npm install --save-dev --save-exact eslint-plugin-unused-imports@4.4.1`

Additional `npx` tools (pinned):
- `npx --yes knip@6.14.2 --dependencies` — find unused deps (replaces abandoned/archived `depcheck`)
- `npx --yes audit-ci@7.1.0 --moderate` — CI-friendly npm audit wrapper, configurable severity thresholds

---

## Python

```bash
pip install ruff==0.15.15          # Linter + formatter (replaces flake8, isort, black)
pip install pip-audit==2.10.0      # Vulnerability scanner
pip install "bandit[toml]==1.9.4"  # Security linter (SAST)
pip install mypy==2.1.0            # Type checker
pip install vulture==2.16          # Dead code finder
pip install radon==6.0.1           # Complexity metrics
# safety: replaced by pip-audit (PyPA-maintained, no login required) — already installed above
pip install pip-licenses==5.5.5    # License compliance
pip install pipreqs==0.5.0         # Generate requirements.txt from imports
```

- **uv**: pinned installer (avoid unpinned `curl|sh` — no checksum gate). `pipx install uv==0.11.17`, or pinned standalone script `curl -LsSf https://astral.sh/uv/0.11.17/install.sh | sh` (still no checksum; prefer pipx or a release binary + SHA256 verify)

---

## Rust

Pin toolchain + components via checked-in `rust-toolchain.toml` (`channel = "1.96.0"`, `components = ["clippy", "rustfmt"]`):
```bash
rustup component add clippy --toolchain 1.96.0           # Linter (ships with toolchain)
rustup component add rustfmt --toolchain 1.96.0          # Formatter (ships with toolchain)
cargo install cargo-audit --version 0.22.1 --locked      # Vulnerability scanner
cargo install cargo-deny --version 0.19.8 --locked       # License + vuln + ban checker
cargo install cargo-outdated --version 0.19.0 --locked   # Dep freshness
cargo install cargo-geiger --version 0.13.0 --locked     # Unsafe code counter
cargo install cargo-tarpaulin --version 0.35.4 --locked  # Code coverage (Linux only; cross-platform alt: cargo-llvm-cov 0.8.7)
cargo install cargo-bloat --version 0.12.1 --locked      # Binary size analysis
cargo install cargo-udeps --version 0.1.61 --locked      # Unused deps (nightly)
cargo install cargo-supply-chain --version 0.3.7 --locked # Shows maintainers per dep
cargo install cargo-vet --version 0.10.2 --locked        # Mozilla dep review tracking
```

---

## Java / Kotlin (JVM)

Managed via build system (Gradle/Maven plugins). No separate install for most.

```bash
# SpotBugs — bug finder. Gradle: id("com.github.spotbugs") version "6.5.5"
#                        Maven plugin: com.github.spotbugs:spotbugs-maven-plugin:4.9.8.3 (core 4.9.8)
# PMD — static analysis. Gradle: pmd { toolVersion = "7.25.0" }
#                        Maven: maven-pmd-plugin 3.27.0 + net.sourceforge.pmd:pmd-java:7.25.0
#                        (verify GPG key 2EFA55D0785C31F956F2F87EA0B5CA1A4E086838, post-CVE-2025-23215)
# Checkstyle — style checker. Gradle: checkstyle { toolVersion = "13.4.2" }
#                        Maven: maven-checkstyle-plugin 3.6.0 + com.puppycrawl.tools:checkstyle:13.4.2

# Standalone: OWASP dependency-check 12.2.2 (set NVD_API_KEY to avoid 403/slow updates)
#   Maven:  mvn -B org.owasp:dependency-check-maven:12.2.2:check
#   Gradle: id 'org.owasp.dependencycheck' version '12.2.2' ; ./gradlew dependencyCheckAnalyze
#   New home: https://github.com/dependency-check/DependencyCheck (v12.2.2)
```

---

## C# / .NET

> **requires: `PackageReference`/`packages.config`.** `dotnet-outdated-tool`, `nuget-license`, and `NuGone` all read a NuGet manifest — on a **local-DLL-reference project** (deps are game-/vendor-shipped binaries, no package manager) they are inert. Detect that case up front and DOWNSHIFT: skip these tools with a one-line limitation + a manual DLL/assembly-version note, rather than installing tools that then no-op. Not a BLOCKER (the tool is N/A for the stack, not missing coverage). See csharp.md → local-DLL downshift.

```bash
# dotnet-format REMOVED (deprecated, retired into SDK). Use built-in `dotnet format` (SDK 6.0+);
#   pin SDK via global.json sdk.version (e.g. 8.0.414). Run: dotnet format --verify-no-changes
# security-scan REPLACED — prefer built-in Roslyn analyzers + SonarAnalyzer.CSharp:
#   <EnableNETAnalyzers>true</EnableNETAnalyzers> <AnalysisMode>All</AnalysisMode>
#   dotnet add package SonarAnalyzer.CSharp --version 10.18.0.124379
#   (interim only: dotnet tool install -g security-scan --version 5.6.7)
dotnet tool install -g dotnet-outdated-tool --version 4.7.2          # Dep freshness
dotnet tool install --global nuget-license --version 4.0.10          # License compliance (replaces abandoned dotnet-project-licenses)
# Unused-package finder: dotnet tool install --global NuGone --version 2.1.1
# Roslyn analyzers — via NuGet in .csproj
```

---

## Universal (all stacks)

```bash
# Trivy — CVE + secrets + licenses (all package managers)
# WARNING: v0.69.4-v0.69.6 ALL compromised (TeamPCP, 2026-03-19). Pin last clean v0.69.3!
choco install trivy --version=0.69.3 --require-checksums -y    # Windows (move to 0.70.0 once on community.chocolatey.org)
# brew install trivy                     # macOS
# apt install trivy                      # Linux

# Semgrep — SAST (30+ langs). Native Windows since Fall 2025.
pip install semgrep==1.164.0
# Windows: ensure Python in PATH
# UTF-8: [System.Environment]::SetEnvironmentVariable('PYTHONUTF8','1','User')
# Docker: docker run --rm -v "$(pwd):/src" semgrep/semgrep semgrep --config=auto /src

# Gitleaks — secrets scanner (also in Go section). Always run with --redact; write to gitignored report.
choco install gitleaks --version=8.30.1 -y    # Windows
# brew install gitleaks   # macOS
# e.g. gitleaks detect --redact --report-path .audit/gitleaks-report.json   (no -v in captured 2>&1 output)

# TruffleHog v3 — deep secrets scanner (verifies live creds via API)
# More thorough than gitleaks for git history. Dual-use credential harvester — restrict where it runs.
# WARNING: `pip install trufflehog` = abandoned v2 (2021). Use pinned Go release binary + SHA256 verify:
# > skip_if: windows  (bash/sha256sum; on Windows download the _windows_amd64.zip + verify hash via Get-FileHash)
VER=3.95.3
curl -sSfLO "https://github.com/trufflesecurity/trufflehog/releases/download/v${VER}/trufflehog_${VER}_linux_amd64.tar.gz"
curl -sSfLO "https://github.com/trufflesecurity/trufflehog/releases/download/v${VER}/trufflehog_${VER}_checksums.txt"
grep "trufflehog_${VER}_linux_amd64.tar.gz" "trufflehog_${VER}_checksums.txt" | sha256sum -c - && \
  tar -xzf "trufflehog_${VER}_linux_amd64.tar.gz" trufflehog && \
  install -m 0755 trufflehog /usr/local/bin/trufflehog
# (Optional, stronger) cosign verify-blob the checksums.txt against the trufflesecurity OIDC identity
# Or: go install github.com/trufflesecurity/trufflehog/v3@v3.95.3
# Or: docker run --rm -v "$(pwd):/src" trufflesecurity/trufflehog:3.95.3 filesystem /src
```

PowerShell twin (Windows — download the signed `_windows_amd64` archive + verify SHA256):
```powershell
$VER = '3.95.3'
$base = "https://github.com/trufflesecurity/trufflehog/releases/download/v$VER"
Invoke-WebRequest "$base/trufflehog_${VER}_windows_amd64.tar.gz" -OutFile trufflehog.tar.gz
Invoke-WebRequest "$base/trufflehog_${VER}_checksums.txt"       -OutFile checksums.txt
$want = ((Select-String -Path checksums.txt -Pattern 'windows_amd64.tar.gz').Line -split '\s+')[0]
if ((Get-FileHash trufflehog.tar.gz -Algorithm SHA256).Hash -ieq $want) { tar -xzf trufflehog.tar.gz trufflehog.exe } else { throw 'trufflehog checksum mismatch' }
```

```bash
# OSV-Scanner (Google) — vuln scanner, OSV database
# Supports go.sum, package-lock.json, requirements.txt, Cargo.lock
go install github.com/google/osv-scanner/v2/cmd/osv-scanner@v2.3.8
# Or: SLSA3 release binary from github.com/google/osv-scanner/releases/tag/v2.3.8 + verify checksum

# Detect-Secrets (Yelp) — pre-commit secrets scanner with baseline
pip install "detect-secrets==1.5.0"

# Checkov — IaC security (Terraform, Dockerfile, K8s, GitHub Actions)
pip install checkov==3.2.530

# Syft — SBOM generator (CycloneDX/SPDX)
# Supports: Go, Node, Python, Rust, Java, C#, containers
choco install syft --version=1.42.4 -y       # Windows (community pkg lags upstream 1.44.0; for highest assurance use Anchore's signed release binary)
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

---

## Infrastructure & CI

Pin per the integrity protocol. These are GitHub-released binaries (integrity = pinned
release binary + SHA256 checksum verification, mirroring trufflehog/syft) unless a
checksum-gated package manager is used. See `infra.md` for usage.

```bash
# hadolint — Dockerfile linter
choco install hadolint --version=2.14.0 --require-checksums -y   # Windows
# > skip_if: windows  (bash/sha256sum; on Windows use choco above or download the .exe + Get-FileHash)
VER=2.14.0
curl -sSfLO "https://github.com/hadolint/hadolint/releases/download/v${VER}/hadolint-Linux-x86_64"
curl -sSfLO "https://github.com/hadolint/hadolint/releases/download/v${VER}/hadolint-Linux-x86_64.sha256"
sha256sum -c "hadolint-Linux-x86_64.sha256" && \
  install -m 0755 hadolint-Linux-x86_64 /usr/local/bin/hadolint

# tfsec — Terraform security scanner
# DEPRECATED: superseded by `trivy config` (merged into Trivy). Pin kept for compatibility.
go install github.com/aquasecurity/tfsec/cmd/tfsec@v1.28.14   # proxy + checksum DB = tamper-evident
# Or: choco install tfsec --version=1.28.14 --require-checksums -y   # Windows

# kube-linter — Kubernetes manifest linter
go install golang.stackrox.io/kube-linter/cmd/kube-linter@v0.8.3   # proxy + checksum DB = tamper-evident
# Or: pinned GitHub release binary from github.com/stackrox/kube-linter/releases/tag/v0.8.3 + verify checksums.txt

# actionlint — GitHub Actions workflow linter
go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.12   # proxy + checksum DB = tamper-evident
# (bundles shellcheck integration if shellcheck is on PATH)

# zizmor — GitHub Actions supply-chain/security auditor
pipx install zizmor==1.25.2          # preferred (isolated)
# Or: cargo install zizmor --version 1.25.2 --locked   # builds from crates.io source
```
