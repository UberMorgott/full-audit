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

### Race detector + fuzz + coverage
```bash
# skip_if: windows  (uses `which`; on Windows use the PowerShell block below)
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
# skip_if: windows  (uses grep/[ -z ]; on Windows use the PowerShell block below)
# Fuzz: find tests, run each 30s
FUZZ_FILES=$(grep -r "func Fuzz" --include="*_test.go" -l . 2>/dev/null)
if [ -z "$FUZZ_FILES" ]; then echo "SKIP: no fuzz tests found"; else
  echo "$FUZZ_FILES"
  # List fuzz targets: grep -r "func Fuzz" --include="*_test.go" -l
  # Replace FuzzXxx and path with actual values from grep output:
  go test -fuzz=FuzzXxx -fuzztime=30s ./path/to/package/ 2>&1
fi
```
```powershell
# Windows equivalent
$fuzz = Select-String -Path (Get-ChildItem -Recurse -Filter *_test.go) -Pattern 'func Fuzz' -List | Select-Object -ExpandProperty Path
if (-not $fuzz) { Write-Output "SKIP: no fuzz tests found" } else {
  $fuzz
  # Replace FuzzXxx and path with actual values from the list above:
  go test -fuzz=FuzzXxx -fuzztime=30s ./path/to/package/ 2>&1
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
```bash
deadcode ./... 2>&1  # requires: go install golang.org/x/tools/cmd/deadcode@v0.45.0
go mod verify 2>&1
```
```bash
go mod tidy -diff 2>&1
```

### Secrets scan
> Skip if Trivy used above.
> Install: `go install github.com/gitleaks/gitleaks/v8@v8.30.1`. Write findings to a gitignored report path (add `gitleaks-report.json` to `.gitignore`); `--redact` masks secret values; drop `-v` from agent-captured output to avoid leaking matches.
```bash
gitleaks detect --source . --no-git --redact --report-path gitleaks-report.json 2>&1   # Quick: files only
gitleaks detect --source . --redact --report-path gitleaks-report.json 2>&1             # Full: + git history
```

### Semgrep SAST
```bash
semgrep --config=auto . 2>&1
```

---

## Level 2: Code Review (DEEP agents)

> **Reviewer mapping:** Security → diff-scanner + impact-reviewer. Concurrency → diff-scanner + history-reviewer. Resource leaks → diff-scanner. Conventions → convention-checker. Stale comments/TODOs → comment-checker.

Manual review tasks for DEEP agents using Serena/Grep.

### Security review (OWASP + STRIDE)

> Threat model: **STRIDE** (Spoofing, Tampering, Repudiation, Information Disclosure, DoS, Elevation of Privilege).
> Severity: **DREAD** — Damage(0-10) + Reproducibility + Exploitability + Affected users + Discoverability. Critical: 8-10, High: 6-7.9, Medium: 4-5.9, Low: 1-3.9.

What scanners miss — check manually:

**Injection & Input:**
- SQL injection (string concat near SQL, not parameterized)
- Command injection (`exec.Command` with user input)
- Path traversal (`filepath.Join` with user input — use `SafeJoinPath` + `filepath.EvalSymlinks`)
- SSRF (HTTP request with user-supplied URL without scheme check)
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
| Path Traversal | `filepath.Join.*` + HTTP param | `SafeJoinPath()` + `filepath.EvalSymlinks()` |
| SSRF | `http.Get(userURL)`, `client.Do` + user URL | `ValidateURLScheme()` + block private IPs |
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
- Errors from `defer` (Close, Flush, Commit) logged
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
- Struct field alignment waste (tool: `betteralign` — `go install github.com/dkorunic/betteralign/cmd/betteralign@v0.11.0`)

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

```bash
go-licenses report ./... 2>&1  # requires: go install github.com/google/go-licenses/v2@v2.0.1
# Or: trivy fs --scanners license . 2>&1
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
