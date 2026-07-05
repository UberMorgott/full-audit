# Go Audit Checks

> **Cross-references:** [README.md](README.md) (orchestration), [universal.md](universal.md) (language-agnostic).
>
> **Required reading:**
> - **Confidence Scoring** (README.md) — 0-100 per finding. L1≥75, L2≥60, L3≥40.
> - **False Positive Detection** (universal.md) — stack-specific auto-discard patterns.
> - **CLI Finding Verification** (universal.md) — 5-step protocol per CLI finding.
> - **YAGNI Check** (universal.md) — verify need before suggesting "add X".
> - **Anti-Rationalization Rules** (universal.md) — no skipping/softening.

Applies when `go.mod` detected. Commands assume `cd {go_module_root}`.

> **Exit-code caution (piped commands):** the CLI-scanner trust policy keys on the tool's real exit code. Piping a command into `| head`/`| grep`/`| tail` makes `$?` reflect the LAST pipe stage (e.g. `head`), masking a tool failure. Capture the exit BEFORE any pipe — bash: `cmd 2>err; ec=$?` (or `set -o pipefail`); PowerShell: read `$LASTEXITCODE` immediately after the native call, before piping. (`2>&1` alone is fine — it only merges stderr; the clobber comes from the `|`.)

---

## Level 1: Quick

### Build + vet + lint
```bash
go build ./... 2>&1
```
```bash
go vet ./... 2>&1
```
```bash
staticcheck ./... 2>&1  # requires: go install honnef.co/go/tools/cmd/staticcheck@v0.7.0
```

### Dependency vulnerabilities
```bash
govulncheck ./... 2>&1  # requires: go install golang.org/x/vuln/cmd/govulncheck@v1.3.0
```

### Go toolchain currency
```bash
go version 2>&1
```
> If `govulncheck` reports stdlib vulns (e.g., `Found in: net@go1.25.8, Fixed in: net@go1.25.10`), update toolchain: `go mod edit -go=<fixed_version>`, `go mod tidy`, rebuild, re-check.

### Unit tests
```bash
go test -timeout 60s -count=1 ./... 2>&1
```

**Pass criteria:** 0 errors in all commands.

---

## Level 2: Full (includes Level 1)

### Static analysis — golangci-lint v2

> v2 (golangci-lint v2.12.2): `-E` removed. `--enable` takes ONE linter per flag (repeat the flag); comma lists no longer parse. `enable-all`/`disable-all` replaced by `linters.default`. Prefer the config file below over a long CLI.
> Install: `go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.12.2`
> **Config precedence:** if the repo already has `.golangci.yml`/`.golangci.yaml`, run `golangci-lint run ./...` with NO `--enable` flags (it honors the project config) and report which linters are active. The explicit `--enable` list below is ONLY for repos with no config file — running it against a configured repo fights the project's own linter selection.
> **CRLF/LF false positive (Windows):** a `gofmt`/`gofumpt`/format failure that is purely CRLF-vs-LF line endings (git `core.autocrlf` on a Windows checkout) is a FALSE POSITIVE, not a real style defect — verify with a line-ending diff before reporting it.

```bash
golangci-lint run ./... \
  --enable bodyclose --enable sqlclosecheck --enable nilerr --enable nilnil \
  --enable errcheck --enable errchkjson --enable ineffassign --enable gocognit \
  --enable gocyclo --enable funlen --enable nestif --enable goconst --enable dupl \
  --enable unconvert --enable unparam --enable prealloc --enable rowserrcheck \
  --enable forcetypeassert --enable wrapcheck --enable contextcheck --enable noctx \
  --timeout 5m 2>&1
```

<details><summary>Recommended .golangci.yml</summary>

```yaml
# golangci-lint v2 schema (v2.12.2)
version: "2"
run:
  timeout: 5m
linters:
  enable:
    - bodyclose
    - sqlclosecheck
    - nilerr
    - nilnil
    - errcheck
    - errchkjson
    - ineffassign
    - gocognit
    - gocyclo
    - funlen
    - nestif
    - goconst
    - dupl
    - unconvert
    - unparam
    - prealloc
    - rowserrcheck
    - forcetypeassert
    - wrapcheck
    - contextcheck
    - noctx
  settings:
    gocognit:
      min-complexity: 30
    gocyclo:
      min-complexity: 20
    funlen:
      lines: 60
```
</details>

**Critical linters:** `forcetypeassert` (panic), `nilerr`/`nilnil` (hidden bugs), `bodyclose`/`sqlclosecheck` (leaks), `errcheck`/`errchkjson` (unhandled errors), `noctx` (no cancellation).

### Security scan

> **Skip decision:** Use **either** Trivy (universal) **or** gosec+govulncheck. Not both.

**Option A — Trivy (vuln + secrets + licenses):**
```bash
# ⚠️ Trivy: pin `0.69.3` — v0.69.4–0.69.6 are compromised (supply-chain); do NOT bump until 0.70.0. Detail: tools.md.
#   choco install trivy --version=0.69.3 --require-checksums -y
trivy version 2>&1 | head -1
trivy fs --scanners vuln,secret,license --severity HIGH,CRITICAL . 2>&1
```

**Option B — Go-specific:**
```bash
# requires: go install github.com/securego/gosec/v2/cmd/gosec@v2.26.1
gosec ./... 2>&1
# requires: go install golang.org/x/vuln/cmd/govulncheck@v1.3.0
govulncheck ./... 2>&1
```
> **Post-filter `//nolint:gosec` (FP suppression):** gosec does NOT honor inline `//nolint:gosec` directives by default — a mechanical run reports phantom HIGHs for findings the author already suppressed. Before scoring, drop any gosec finding whose `file:line` carries a `//nolint:gosec` directive (same line or the line above). (Matches the README False-Positive Whitelist `// nolint: reason` rule.) A gosec finding adjudicated as a false positive can also be remembered across runs by its `fingerprint` in `.audit/ledger.json` suppressions (README Conventions -> Cross-audit memory), so it stays scored 0 without re-triage.

### Race detector + fuzz + coverage
```bash
# DEFAULT (bash). On Windows do NOT skip the race check — run the PowerShell twin below instead (it is the Windows equivalent, not an optional extra).
# Race detector (requires gcc for CGO)
which gcc > /dev/null 2>&1 || { echo "SKIP: gcc not found (required for -race). Install MinGW-w64."; exit 0; }
CGO_ENABLED=1 go test -race -timeout 60s -count=1 ./... 2>&1
```
```powershell
# Windows equivalent. gcc via: choco install mingw --version=15.2.0 -y
if (-not (Get-Command gcc -ErrorAction SilentlyContinue)) { Write-Output "SKIP: gcc not found (required for -race). choco install mingw --version=15.2.0 -y"; return }
$env:CGO_ENABLED=1; go test -race -timeout 60s -count=1 ./... 2>&1
```
```bash
# DEFAULT (bash). On Windows do NOT skip fuzzing — run the PowerShell twin below instead (Windows equivalent, not an optional extra).
# Fuzz: find tests, run each 30s
FUZZ_FILES=$(grep -r "func Fuzz" --include="*_test.go" -l . 2>/dev/null)
if [ -z "$FUZZ_FILES" ]; then echo "SKIP: no fuzz tests found"; else
  echo "$FUZZ_FILES"
  # Derive the first fuzz target name + its package dir from discovery (no hardcoded placeholder):
  FUZZ_FILE=$(echo "$FUZZ_FILES" | head -1)
  FUZZ_NAME=$(grep -oE "func (Fuzz[A-Za-z0-9_]+)" "$FUZZ_FILE" | head -1 | sed 's/func //')
  FUZZ_PKG=$(dirname "$FUZZ_FILE")
  echo "Running fuzz target $FUZZ_NAME in ./$FUZZ_PKG"
  go test -fuzz="^${FUZZ_NAME}$" -fuzztime=30s "./$FUZZ_PKG/" 2>&1
fi
```
```powershell
# Windows equivalent
# Guard the zero-match case: with no *_test.go files Get-ChildItem returns nothing and
# Select-String -Path $null throws — collect files first, skip cleanly if none.
$testFiles = Get-ChildItem -Recurse -Filter *_test.go -ErrorAction SilentlyContinue
$hits = if ($testFiles) { Select-String -Path $testFiles.FullName -Pattern 'func (Fuzz[A-Za-z0-9_]+)' -List } else { $null }
if (-not $hits) { Write-Output "SKIP: no fuzz tests found" } else {
  $hits | Select-Object -ExpandProperty Path
  # Derive the first fuzz target name + its package dir from discovery (no hardcoded placeholder):
  $first = $hits | Select-Object -First 1
  $fuzzName = $first.Matches[0].Groups[1].Value
  $fuzzPkg = (Resolve-Path -Relative (Split-Path $first.Path)) -replace '\\','/'
  Write-Output "Running fuzz target $fuzzName in $fuzzPkg"
  go test -fuzz="^$fuzzName$" -fuzztime=30s "$fuzzPkg/" 2>&1
}
```
```bash
# Coverage
go test -coverprofile=coverage.out -covermode=atomic -timeout 60s ./... 2>&1
go tool cover -func=coverage.out | tail -1
```

### Goroutine leak detection
```bash
# Add goleak to TestMain in critical packages:
# func TestMain(m *testing.M) { goleak.VerifyTestMain(m) }
go test -count=1 ./... 2>&1
```

### Dead code + modules
> **deadcode vs staticcheck U1000 (SK10):** they diverge on methods satisfying an interface (e.g. a `String()` satisfying `fmt.Stringer`). U1000 treats an interface-satisfying method as used (reachable), so it can MISS a method that is dead whole-program; `deadcode` does whole-program reachability analysis and is authoritative here. Reconcile both — don't treat a clean U1000 as complete dead-code coverage.
> **Test-only-helper false positives:** `deadcode ./...` analyzes the non-test build, so helpers called ONLY from `_test.go` (or behind build tags) — e.g. `testutil` packages, `Setup*`/`Seed*` fixtures — are commonly reported unreachable. Cross-check each reported symbol for `_test.go` callers before reporting it as dead.
```bash
deadcode ./... 2>&1  # requires: go install golang.org/x/tools/cmd/deadcode@v0.45.0
go mod verify 2>&1
```
```bash
go mod tidy -diff 2>&1
```

### Secrets scan
> skip_if: no_tool(gitleaks). Skip if Trivy used above.
> Install: `go install github.com/gitleaks/gitleaks/v8@v8.30.1`. `--redact` masks secret values; drop `-v` from agent-captured output to avoid leaking matches.
> **Report path (SK4):** write the report OUT OF TREE — never into the repo (a secret-bearing report must not become a commit candidate; don't assume a `.gitignore` exists). Use an OS temp path:
> - PowerShell: `--report-path "$env:TEMP\gitleaks-report.json"`
> - bash: `--report-path "${TMPDIR:-/tmp}/gitleaks-report.json"`
```bash
# Quick (working-tree, files only): use ${TMPDIR:-/tmp} (PowerShell: $env:TEMP) for the report path.
gitleaks detect --source . --no-git --redact --report-path "${TMPDIR:-/tmp}/gitleaks-report.json" 2>&1
# Full (+ git history) — AUTHORITATIVE for the committed-secrets verdict:
gitleaks detect --source . --redact --report-path "${TMPDIR:-/tmp}/gitleaks-report.json" 2>&1
```
> **Post-filter `--no-git` hits (SK3):** the working-tree scan flags files regardless of git status — a gitignored/untracked runtime artifact (e.g. a generated `id_ed25519_*` key) is NOT a committed secret. For each hit, classify by git status with this precedence (check tracked FIRST — it wins regardless of `check-ignore`):
> 1. **tracked** — `git ls-files --error-unmatch <path>` exit 0 ⇒ REAL committed-secret finding (regardless of `check-ignore`).
> 2. else **ignored** — `git check-ignore <path>` exit 0 ⇒ INFO (ignored, not committed).
> 3. else (**untracked AND not ignored**) ⇒ INFO-pending (new uncommitted file — re-evaluate once committed).
> - PowerShell: `git ls-files --error-unmatch $path; if ($LASTEXITCODE -eq 0) { 'REAL' } else { git check-ignore -q $path; if ($LASTEXITCODE -eq 0) { 'INFO: ignored' } else { 'INFO-pending: untracked' } }`
> Only tracked paths (or hits confirmed by the git-history form above) count as committed-secret findings.

### Semgrep SAST
> skip_if: no_tool(semgrep)
> **Primary (offline-capable):** pin explicit registry rulesets so the scan works without a live network fetch from semgrep.dev. `p/security-audit`, `p/secrets`, `p/golang` are real registry IDs; multiple `--config` flags combine. Rules are downloaded once and cached under `~/.semgrep`; an air-gapped host needs them pre-cached (or local YAML via `--config <file>`).
```bash
semgrep --config=p/security-audit --config=p/secrets --config=p/golang . 2>&1
```
> **Online option only:** `--config=auto` auto-selects rulesets but REQUIRES network (it fetches from semgrep.dev); on timeout/air-gap it yields nothing. Use only when network is available.
> ```bash
> semgrep --config=auto . 2>&1   # needs network
> ```
> **No-network fallback:** if rulesets are not cached and the host is offline, SAST cannot run via semgrep — record `SKIP: semgrep rulesets uncached + offline` and rely on `gosec`/`golangci-lint` for SAST coverage. (tools.md installs semgrep; the network requirement for first-run ruleset download is noted there.)

---

## Level 2: Code Review (DEEP agents)

> **Reviewer mapping:** Security → diff-scanner + impact-reviewer. Concurrency → diff-scanner + history-reviewer. Resource leaks → diff-scanner. Conventions → convention-checker. Stale comments/TODOs → comment-checker.
> **Solo DEEP review:** a single reviewer assumes all mapped roles; the mapping then only orders the checklist, not agents.

Manual review tasks for DEEP agents using Serena/Grep.

### Security review (OWASP + STRIDE)

> Threat model: **STRIDE** (Spoofing, Tampering, Repudiation, Information Disclosure, DoS, Elevation of Privilege).
> Severity: **DREAD** — Damage(0-10) + Reproducibility + Exploitability + Affected users + Discoverability. Critical: 8-10, High: 6-7.9, Medium: 4-5.9, Low: 1-3.9.

What scanners miss — check manually:

**Injection & Input:**
- SQL injection (string concat near SQL, not parameterized)
- Command injection (`exec.Command` with user input)
- Path traversal (`filepath.Join` with user input — `SafeJoinPath`/`ValidateURLScheme` are illustrative helper names — implement, or use stdlib `filepath.Clean` + a prefix/base-dir check; not provided. Also `filepath.EvalSymlinks`). CLI carve-out: operator-supplied local paths to the operator's own files are not a traversal vuln (trust boundary = the operator).
- SSRF (HTTP request with user-supplied URL without scheme check — see the illustrative-helper note above)
- CSV injection (user data in CSV with `=`, `+`, `-`, `@` prefixes — prepend `'` or validate)
- XXE in `encoding/xml` — safe by default (no external entity resolution). Risk: third-party libs with libxml2. `d.Strict = true` controls syntax only, not XXE

**Crypto & Secrets:**
- `math/rand` for security values (tokens, secrets, IDs) — must use `crypto/rand`
- Hardcoded secrets (`password`/`token`/`api_key` in code, not tests)
- Weak hash for security (MD5/SHA1 for passwords, tokens, integrity)
- Static/predictable IV or nonce
- `subtle.ConstantTimeCompare` not used for secret comparison (timing attack)

**Transport & Headers:**
- TLS bypass (`InsecureSkipVerify: true`)
- Error leakage (internal errors in HTTP responses — should be generic)
- CORS (`Access-Control-Allow-Origin: *`)
- WebSocket origin bypass (`CheckOrigin: func(...) bool { return true }`)
- Missing security headers (see `universal.md`)

**Deserialization:**
- `encoding/gob` with untrusted input (arbitrary type instantiation)
- `yaml.v2`/`yaml.v3` `Unmarshal` into `interface{}` (type confusion — use typed structs, `KnownFields(true)` in v3)
- `encoding/json` into `interface{}` without depth limit (hash collision DoS)
- Unbounded `json.Decoder` — use `d.DisallowUnknownFields()`, limit `MaxBytes`

### Concurrency safety

> Race detector catches runtime races. Here — pattern audit:
> **If `-race` was SKIPPED (SK13):** when the race-detector block above self-skipped (no gcc / Windows without MinGW), the report MUST state it explicitly — this manual pattern audit is then the SOLE concurrency coverage. Do not report "Concurrency: PASS" in a way that implies a runtime race verification that never ran.

**Goroutine lifecycle:**
- `go func` without WaitGroup or channel (leak)
- `select{}`/`for{}` without `case <-ctx.Done()` (no shutdown)
- Goroutine ownership unclear — who stops it?
- `wg.Add()` called inside goroutine (race with `wg.Wait()`) — must call before `go func`
- `log.Fatal` / `os.Exit` in goroutine — kills process without defer cleanup

**Shared state:**
- Global `var` (map/slice/struct) without mutex
- Map writes from multiple goroutines
- `sync.Map` for write-heavy workload (use `map+RWMutex` — `sync.Map` optimal for read-heavy/disjoint-key writes)

**Locking:**
- `sync.Mutex` with defer in loop (lock held too long)
- Missing `defer mu.Unlock()` (unlock on early return/panic)
- Nested locks without consistent ordering (deadlock)

**Channels:**
- Unbuffered chan in hot path (blocking)
- Channel direction not specified in signatures (use `chan<-`/`<-chan`)
- `time.After` in `select` loop — new timer each iteration (memory leak). Use `time.NewTimer` + `Reset()`
- Missing `default` in non-blocking select
- Sending on closed channel (panic)

### Resource leaks & timeouts

- `http.Client` without `Timeout`
- `http.DefaultTransport` modified globally — affects entire process. Create custom `Transport` per client
- DB connection without pool limits (`SetMaxOpenConns`, `SetMaxIdleConns`, `SetConnMaxLifetime`)
- `resp.Body` without `defer resp.Body.Close()` — also close on error paths
- File open without `defer f.Close()`
- `context.Background()` in HTTP handler (use `r.Context()`)
- `context.WithTimeout`/`context.WithCancel` without `defer cancel()` (context leak)
- Context not propagated through layers: HTTP handler → service → DB → external call
- HTTP server without `ReadTimeout`/`WriteTimeout` (Slowloris) — consider `http.TimeoutHandler` per-handler
- Background goroutine without `recover()`
- `io.ReadAll` without body size limit (DoS)

---

### Quick reference: vulnerability grep patterns

| Vuln | Grep pattern | Fix |
|------|-------------|-----|
| SQL Injection | `fmt.Sprintf.*SELECT`, `"SELECT.*" +` | Parameterized queries `db.Query("... WHERE id = ?", id)` |
| Command Injection | `exec.Command.*` + user input | Whitelist commands, no shell interpolation |
| Path Traversal | `filepath.Join.*` + HTTP param | `filepath.Clean` + prefix/base-dir check (`SafeJoinPath` illustrative, not provided) + `filepath.EvalSymlinks()`; operator-own local paths not a vuln |
| SSRF | `http.Get(userURL)`, `client.Do` + user URL | scheme check + block private IPs (`ValidateURLScheme` illustrative, not provided) |
| Timing Attack | `==` on secrets/tokens/HMAC | `subtle.ConstantTimeCompare()` |
| Weak RNG | `math/rand` for tokens/secrets | `crypto/rand.Read()` |
| Crypto | `md5.New()`, `sha1.New()` for auth | `sha256`, `bcrypt`, `argon2` |
| Race | global `var m map` without `sync.Mutex` | `sync.RWMutex` or `sync.Map` |
| Goroutine Leak | `go func` without cancel/WaitGroup | Context cancellation, `goleak` in tests |
| XXE | third-party XML libs with libxml2 | `encoding/xml` safe by default; audit CGO XML bindings |

---

## Level 3: Deep (includes Level 2)

> CRITICAL/HIGH findings trigger Variant Analysis (universal.md) — search similar patterns across codebase.

> Consider recommending log/slog (structured logging, standard since Go 1.21) for projects not using it.

### Type safety & language traps

> Source: `golang-safety` patterns. Go footguns that compile but break at runtime.

- **Nil interface trap:** `var err *MyError = nil; var i error = err; i != nil` — TRUE because interface holds typed nil. Compare to `error(nil)` or check `reflect.ValueOf(i).IsNil()`
- **Slice append aliasing:** `a := []int{1,2,3}; b := a[:2]; b = append(b, 4)` — mutates `a[2]`. Use `copy` or `append(a[:2:2], ...)` (3-index slice)
- **Numeric truncation:** `int64` → `int32`, `int` → `uint` — silent overflow. Validate bounds before conversion
- **Integer overflow:** arithmetic without bounds check, especially allocation sizes: `make([]byte, userInput*multiplier)` — can overflow to small value
- **Defer in loop:** `for rows.Next() { defer rows.Close() }` — defers accumulate until function exits. Use closure or explicit close
- **Zero-value traps:** `sync.Mutex`, `sync.WaitGroup`, `sync.Once` must not be copied after use (pointer or embed). `go vet` catches some
- **`init()` functions:** global side effects, hard to test, non-deterministic order. Audit and minimize
- **`unsafe` package:** search all usages. Each must have justification. Check: pointer arithmetic, `uintptr` casts, `reflect.SliceHeader`/`reflect.StringHeader` (deprecated Go 1.17)
- **`reflect` misuse:** `reflect.Value.Pointer()` creates dangling pointers, `reflect.DeepEqual` in production hot paths (slow)

### Error handling

- `recover()` in all long-lived goroutines (workers, WS handlers, background jobs)
- `json.NewEncoder().Encode()` errors handled
- No `log.Fatal`/`os.Exit` outside `main()`
- Errors from `defer` (Close, Flush, Commit) logged (supersedes universal.md's read-only `defer Close` allowance for mutating/exec/commit handles — those must be checked/logged, not auto-discarded)
- HTTP handlers return generic errors to client, details to logs
- Errors wrapped with context: `fmt.Errorf("operation X: %w", err)` — not bare return
- `errors.Is()`/`errors.As()` for comparison (not `==` — breaks with wrapped errors)
- Single-handling: either log OR return error, never both (prevents duplicate logs)

### Graceful shutdown

- HTTP server shutdown handler (`srv.Shutdown(ctx)`)
- Background goroutines stop via context/channel
- DB connections closed
- Temp files cleaned
- Child processes terminated
- WebSocket connections closed with deadline

### Database audit (SQLite)

```bash
sqlite3 path/to/db.sqlite "PRAGMA integrity_check; PRAGMA journal_mode; PRAGMA foreign_keys; PRAGMA busy_timeout; PRAGMA auto_vacuum;" 2>&1
```

Check: WAL mode, foreign_keys ON, busy_timeout >0, auto_vacuum, secure_delete (if PII), backup strategy.

<details><summary>PostgreSQL / MySQL</summary>

**PostgreSQL:** connection pooling, SSL mode (not `disable`), indexes on WHERE/JOIN, VACUUM, no superuser app role, statement_timeout.
**MySQL:** SSL enabled, `utf8mb4`, slow query log, pool configured.
</details>

**Any DB:** no SQL via string concat, no `SELECT *` in prod, migrations have rollback, indexes on FK/WHERE, pool limits set, no hardcoded DB password, graceful close on shutdown. N+1 queries: loop with query inside — use JOIN or batch query.

### Complexity & architecture

- Functions with cognitive complexity >50
- Files >500 lines
- Circular package dependencies
- Test coverage >60% for business logic

### Performance patterns

> Source: `golang-performance` profiling-first methodology.
> Rule: **never optimize without profiling.** Use `pprof` to identify actual bottlenecks first.

**Diagnostic table:**
| Symptom | Tool | Likely cause |
|---------|------|-------------|
| High alloc rate | `pprof -alloc_space` | Memory optimization needed |
| CPU bottleneck | `pprof -cpu` | Algorithm/hot path optimization |
| I/O blocking | `pprof -block` | Networking/concurrency optimization |
| Goroutine stalls | `pprof -goroutine` | Lock contention, channel blocking |

**Common anti-patterns:**
- `clone`/copy where pointer would work in hot path
- `string` concat in loop (use `strings.Builder`)
- `fmt.Sprintf` in hot path (use `strconv` or builder)
- Missing `sync.Pool` for frequently allocated objects
- Value receiver on large struct (copies every call)
- `append()` without pre-allocated capacity for known sizes
- Unbounded `[]byte` growth without reset
- `http.Client{}` per request (pool not reused) — use singleton with configured `Transport`
- Logging in hot loops (I/O per iteration)
- `reflect.DeepEqual` in production (use typed comparison)
- `json.Marshal`/`json.Unmarshal` in hot path — consider `jsoniter`, `sonic`, or code-gen
- Struct field alignment waste (optional tool: `betteralign` — `go install github.com/dkorunic/betteralign/cmd/betteralign@v0.11.0`). Optional, missing ⇒ skip (not BLOCKER).
> skip_if: no_tool(betteralign)

### Overengineering

- Interface with exactly 1 implementation (not for testing)
- `context.Value` for passing function arguments (use explicit params)
- Channel where mutex suffices
- Goroutine for synchronous operation

<details><summary>Web framework checks (Gin, Echo, Fiber, chi)</summary>

- Middleware order correct (logging -> recovery -> auth -> CORS -> routes)
- Request binding validated (`ShouldBind` not `Bind` in Gin)
- Rate limiting configured
- CORS scoped (not blanket `AllowAll`)
- Graceful shutdown with `signal.NotifyContext`
- Custom error handler returns generic errors to client
- Route groups for versioning (`/api/v1/`)

</details>

### License compliance

> skip_if: no_tool(go-licenses) — if `go-licenses` is missing, do NOT treat as BLOCKER; fall back to the `trivy fs --scanners license` line below.
```bash
go-licenses report ./... 2>&1  # requires: go install github.com/google/go-licenses/v2@v2.0.1
# Fallback (if go-licenses unavailable): trivy fs --scanners license . 2>&1
```

### Dependency freshness

```bash
# skip_if: windows  (uses grep; on Windows use the PowerShell line below)
go list -m -u all 2>&1 | grep '\['
```
```powershell
# Windows equivalent (Select-String for the [available-upgrade] marker)
go list -m -u all 2>&1 | Select-String -Pattern '\['
```
