# Go Audit Checks

Applies when `go.mod` detected. All commands assume `cd {go_module_root}` (e.g., `cd backend`).

---

## Level 1: Quick

### Build + vet + lint
```bash
go build ./... && go vet ./... && staticcheck ./... 2>&1
```

### Dependency vulnerabilities
```bash
govulncheck ./... 2>&1
```

### Unit tests
```bash
go test -timeout 60s -count=1 ./... 2>&1
```

**Pass criteria:** 0 errors in all commands.

---

## Level 2: Full (includes Level 1)

### Static analysis — golangci-lint v2

> v2: `--enable`/`-E` works. `enable-all`/`disable-all` removed (replaced by `linters.default`).

```bash
golangci-lint run ./... -E bodyclose,sqlclosecheck,nilerr,nilnil,errcheck,errchkjson,ineffassign,gocognit,gocyclo,funlen,nestif,goconst,dupl,unconvert,unparam,prealloc,rowserrcheck,forcetypeassert,wrapcheck,contextcheck,noctx --timeout 5m 2>&1
```

<details><summary>Recommended .golangci.yml</summary>

```yaml
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
linters-settings:
  gocognit:
    min-complexity: 30
  gocyclo:
    min-complexity: 10
  funlen:
    lines: 60
run:
  timeout: 5m
```
</details>

**Critical linters:** `forcetypeassert` (panic), `nilerr`/`nilnil` (hidden bugs), `bodyclose`/`sqlclosecheck` (leaks), `errcheck`/`errchkjson` (unhandled errors), `noctx` (no cancellation).

### Security scan

> **Skip decision:** Use **either** Trivy (universal) **or** gosec+govulncheck. Not both.

**Option A — Trivy (covers vuln + secrets + licenses):**
```bash
# IMPORTANT: verify Trivy version first — v0.69.4/v0.69.5/v0.69.6 are compromised (see tools.md)
trivy version 2>&1 | head -1
trivy fs --scanners vuln,secret,license --severity HIGH,CRITICAL . 2>&1
```

**Option B — Go-specific tools:**
```bash
gosec ./... 2>&1
govulncheck ./... 2>&1
```

### Race detector + fuzz + coverage
```bash
# Race detector (requires gcc for CGO)
which gcc > /dev/null 2>&1 || { echo "SKIP: gcc not found (required for -race). Install MinGW-w64."; exit 0; }
CGO_ENABLED=1 go test -race -timeout 60s -count=1 ./... 2>&1
```
```bash
# Fuzz: find tests, run each 30s
# skip_if: no fuzz tests found (grep returns empty)
FUZZ_FILES=$(grep -r "func Fuzz" --include="*_test.go" -l . 2>/dev/null)
if [ -z "$FUZZ_FILES" ]; then echo "SKIP: no fuzz tests found"; else
  echo "$FUZZ_FILES"
  # Replace FuzzXxx and path with actual values from grep output:
  go test -fuzz=FuzzXxx -fuzztime=30s ./path/to/package/ 2>&1
fi
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
# Then run tests — goleak will fail if goroutines leak
go test -count=1 ./... 2>&1
```

### Dead code + modules
```bash
deadcode ./... 2>&1
go mod verify && go mod tidy -diff 2>&1
```

### Secrets scan
> Skip if Trivy used in security scan.
```bash
gitleaks detect --source . --no-git -v 2>&1      # Quick: files only
gitleaks detect --source . -v 2>&1                 # Full: + git history
```

### Semgrep SAST
```bash
semgrep --config=auto . 2>&1
```

---

## Level 2: Code Review (Opus agents)

These are manual code review tasks for Opus agents using Serena/Grep.

### Security review (OWASP + STRIDE)

> Threat model reference: **STRIDE** (Spoofing, Tampering, Repudiation, Information Disclosure, DoS, Elevation of Privilege).
> Severity scoring: **DREAD** — Damage(0-10) + Reproducibility + Exploitability + Affected users + Discoverability. Critical: 8-10, High: 6-7.9, Medium: 4-5.9, Low: 1-3.9.

What scanners miss — check manually:

**Injection & Input:**
- SQL injection (string concat near SQL, not parameterized)
- Command injection (`exec.Command` with user input)
- Path traversal (`filepath.Join` with user input without validation — use `SafeJoinPath` + `filepath.EvalSymlinks`)
- SSRF (HTTP request with user-supplied URL without scheme check)
- CSV injection (user data in CSV export with `=`, `+`, `-`, `@` prefixes — prepend `'` or validate)
- XXE in `encoding/xml` — use `xml.NewDecoder` with `d.Strict = true`

**Crypto & Secrets:**
- `math/rand` used for security-sensitive values (tokens, secrets, IDs) — must use `crypto/rand`
- Hardcoded secrets (`password`/`token`/`api_key` in code, not tests)
- Weak hash for security (MD5/SHA1 for passwords, tokens, integrity)
- Static/predictable IV or nonce in encryption
- `subtle.ConstantTimeCompare` not used for secret comparison (timing attack)

**Transport & Headers:**
- TLS bypass (`InsecureSkipVerify: true`)
- Error leakage (internal errors in HTTP responses — should be generic)
- CORS (`Access-Control-Allow-Origin: *`)
- WebSocket origin bypass (`CheckOrigin: func(...) bool { return true }`)
- Missing security headers (see `universal.md`)

**Deserialization:**
- `encoding/gob` with untrusted input (arbitrary type instantiation)
- `gopkg.in/yaml.v2` with `yaml.Unmarshal` into `interface{}` (can instantiate arbitrary types — use `yaml.v3`)
- `encoding/json` into `interface{}` without depth limit (hash collision DoS)
- Unbounded `json.Decoder` — use `d.DisallowUnknownFields()`, limit `MaxBytes`

### Concurrency safety

> Race detector (CLI) catches runtime races. Here — pattern audit:

**Goroutine lifecycle:**
- `go func` without WaitGroup or channel (goroutine leak)
- `select{}`/`for{}` without `case <-ctx.Done()` (no shutdown path)
- Goroutine ownership unclear — who is responsible for stopping it?
- `wg.Add()` called inside goroutine (race with `wg.Wait()`) — must call before `go func`
- `log.Fatal` / `os.Exit` in goroutine — kills process without defer cleanup

**Shared state:**
- Global `var` (map/slice/struct) without mutex
- Map writes from multiple goroutines
- `sync.Map` used for write-heavy workload (use `map+RWMutex` instead — `sync.Map` optimal only for read-heavy, disjoint-key writes)

**Locking:**
- `sync.Mutex` with defer in loop (lock held too long)
- Missing `defer mu.Unlock()` (unlock on early return/panic)
- Nested locks without consistent ordering (deadlock)

**Channels:**
- Unbuffered chan in hot path (blocking)
- Channel direction not specified in function signatures (use `chan<-` / `<-chan`)
- `time.After` in `select` loop — creates new timer each iteration (memory leak). Use `time.NewTimer` + `Reset()`
- Missing `default` case in non-blocking select
- Sending on closed channel (panic)

### Resource leaks & timeouts

- `http.Client` without `Timeout`
- `http.DefaultTransport` modified globally — affects entire process. Create custom `Transport` per client
- DB connection without pool limits (`SetMaxOpenConns`, `SetMaxIdleConns`, `SetConnMaxLifetime`)
- `resp.Body` without `defer resp.Body.Close()` — also close on error paths
- File open without `defer f.Close()`
- `context.Background()` in HTTP handler (should use `r.Context()`)
- `context.WithTimeout` / `context.WithCancel` without `defer cancel()` (context leak)
- Context not propagated through layers: HTTP handler → service → DB → external call — all should pass `ctx`
- HTTP server without `ReadTimeout`/`WriteTimeout` (Slowloris) — also consider `http.TimeoutHandler` for per-handler timeouts
- Background goroutine without `recover()`
- `io.ReadAll` without body size limit (DoS via large response)

---

### Quick reference: Go vulnerability patterns

| Vuln | Grep pattern | Fix |
|------|-------------|-----|
| SQL Injection | `fmt.Sprintf.*SELECT`, `"SELECT.*" +` | Parameterized queries `db.Query("... WHERE id = ?", id)` |
| Command Injection | `exec.Command.*` + user input | Whitelist allowed commands, no shell interpolation |
| Path Traversal | `filepath.Join.*` + HTTP param | `SafeJoinPath()` + `filepath.EvalSymlinks()` |
| SSRF | `http.Get(userURL)`, `client.Do` + user URL | `ValidateURLScheme()` + block private IPs |
| Timing Attack | `==` on secrets/tokens/HMAC | `subtle.ConstantTimeCompare()` |
| Weak RNG | `math/rand` for tokens/secrets | `crypto/rand.Read()` |
| Crypto | `md5.New()`, `sha1.New()` for auth | `sha256`, `bcrypt`, `argon2` |
| Race | global `var m map` without `sync.Mutex` | `sync.RWMutex` or `sync.Map` |
| Goroutine Leak | `go func` without cancel/WaitGroup | Context cancellation, `goleak` in tests |
| XXE | `xml.NewDecoder` defaults | `d.Strict = true`, disable entities |

---

## Level 3: Deep (includes Level 2)

### Type safety & language traps

> Source: `golang-safety` patterns. Go-specific footguns that compile but break at runtime.

- **Nil interface trap:** `var err *MyError = nil; var i error = err; i != nil` — is TRUE because interface holds typed nil. Compare to `error(nil)` or check `reflect.ValueOf(i).IsNil()`
- **Slice append aliasing:** `a := []int{1,2,3}; b := a[:2]; b = append(b, 4)` — mutates `a[2]`. Use `copy` or `append(a[:2:2], ...)` (3-index slice)
- **Numeric truncation:** `int64` → `int32`, `int` → `uint` — silent overflow. Validate bounds before conversion
- **Integer overflow:** arithmetic without bounds check, especially in allocation size calculations: `make([]byte, userInput*multiplier)` — can overflow to small value
- **Defer in loop:** `for rows.Next() { defer rows.Close() }` — defers accumulate, not called until function exits. Use closure or explicit close
- **Zero-value traps:** `sync.Mutex`, `sync.WaitGroup`, `sync.Once` must not be copied after use (use pointer or embed). `go vet` catches some cases
- **`init()` functions:** global side effects, hard to test, non-deterministic order across packages. Audit and minimize
- **`unsafe` package:** `import "unsafe"` — search for all usages. Each must have justification. Check: pointer arithmetic, `uintptr` casts, `reflect.SliceHeader` / `reflect.StringHeader` (deprecated since Go 1.17)
- **`reflect` misuse:** `reflect.Value.Pointer()` creates dangling pointers, `reflect.DeepEqual` in production hot paths (slow)

### Error handling

- `recover()` in all long-lived goroutines (workers, WS handlers, background jobs)
- `json.NewEncoder().Encode()` errors handled
- No `log.Fatal`/`os.Exit` outside `main()`
- Errors from `defer` (Close, Flush, Commit) logged
- HTTP handlers return generic errors to client, details to logs
- Errors wrapped with context: `fmt.Errorf("operation X: %w", err)` — not bare return
- `errors.Is()` / `errors.As()` used for comparison (not `==` — breaks with wrapped errors)
- Single-handling rule: either log OR return error, never both (prevents duplicate log entries)

### Graceful shutdown

- HTTP server has shutdown handler (`srv.Shutdown(ctx)`)
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

**PostgreSQL:** connection pooling, SSL mode (not `disable`), indexes on WHERE/JOIN, VACUUM, no superuser app role, statement_timeout set.
**MySQL:** SSL enabled, `utf8mb4`, slow query log, pool configured.
</details>

**Any DB:** no SQL via string concat, no `SELECT *` in prod, migrations have rollback, indexes on FK/WHERE, pool limits set, no hardcoded DB password, graceful close on shutdown. N+1 queries: loop with query inside (fetch list, then query per item — use JOIN or batch query).

### Complexity & architecture

- Functions with cognitive complexity >50
- Files >500 lines
- Circular package dependencies
- Test coverage assessment (target: >60% for business logic)

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
- `clone` / copy where pointer/reference would work in hot path
- `string` concatenation in loop (use `strings.Builder`)
- `fmt.Sprintf` in hot path (use `strconv` or builder)
- Missing `sync.Pool` for frequently allocated objects
- Value receiver on large struct (copies on every call)
- `append()` without pre-allocated capacity for known sizes
- Unbounded `[]byte` growth without reset
- `http.Client{}` created per request (connection pool not reused) — use singleton with configured `Transport`
- Logging in hot loops (I/O per iteration)
- `reflect.DeepEqual` in production code (use typed comparison)
- `json.Marshal` / `json.Unmarshal` in hot path — consider `jsoniter`, `sonic`, or code-gen
- Struct field alignment wasting memory (tool: `betteralign`)

### Overengineering

- Interface with exactly 1 implementation (not for testing)
- `context.Value` for passing function arguments (should be explicit params)
- Channel where mutex suffices
- Goroutine for synchronous operation

<details><summary>Web framework checks (Gin, Echo, Fiber, chi)</summary>

- Middleware order correct (logging -> recovery -> auth -> CORS -> routes)
- Request binding validated (`ShouldBind` not `Bind` in Gin)
- Rate limiting middleware configured
- CORS policy scoped (not blanket `AllowAll`)
- Graceful shutdown with `signal.NotifyContext`
- Custom error handler returns generic errors to client
- Route groups for versioning (`/api/v1/`)

</details>

### License compliance

```bash
go-licenses report ./... 2>&1
# Or: trivy fs --scanners license . 2>&1
```

### Dependency freshness

```bash
go list -m -u all 2>&1 | grep '\['
```
