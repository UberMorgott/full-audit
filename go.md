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
grep -r "func Fuzz" --include="*_test.go" -l .
go test -fuzz=FuzzXxx -fuzztime=30s ./path/to/package/ 2>&1
```
```bash
# Coverage
go test -coverprofile=coverage.out -covermode=atomic -timeout 60s ./... 2>&1
go tool cover -func=coverage.out | tail -1
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

### Security review (OWASP)

What scanners miss — check manually:
- SQL injection (string concat near SQL, not parameterized)
- Command injection (`exec.Command` with user input)
- Path traversal (`filepath.Join` with user input without validation)
- SSRF (HTTP request with user-supplied URL without scheme check)
- TLS bypass (`InsecureSkipVerify: true`)
- Error leakage (internal errors in HTTP responses — should be generic)
- Hardcoded secrets (`password`/`token`/`api_key` in code, not tests)
- CORS (`Access-Control-Allow-Origin: *`)
- WebSocket origin bypass (`CheckOrigin: func(...) bool { return true }`)

### Concurrency safety

> Race detector (CLI) catches runtime races. Here — pattern audit:
- Global `var` (map/slice/struct) without mutex
- `go func` without WaitGroup or channel (goroutine leak)
- `select{}`/`for{}` without `case <-ctx.Done()` (no shutdown path)
- `sync.Mutex` with defer in loop (lock held too long)
- Unbuffered chan in hot path (blocking)
- Map writes from multiple goroutines

### Resource leaks & timeouts

- `http.Client` without `Timeout`
- DB connection without pool limits (`SetMaxOpenConns`, `SetMaxIdleConns`)
- `resp.Body` without `defer resp.Body.Close()`
- File open without `defer f.Close()`
- `context.Background()` in HTTP handler (should use `r.Context()`)
- `time.After` in select loop (timer leak — use `time.NewTimer` + `Reset`)
- HTTP server without `ReadTimeout`/`WriteTimeout` (Slowloris vulnerability)
- Background goroutine without `recover()`

---

## Level 3: Deep (includes Level 2)

### Error handling

- `recover()` in all long-lived goroutines (workers, WS handlers, background jobs)
- `json.NewEncoder().Encode()` errors handled
- No `log.Fatal`/`os.Exit` outside `main()`
- Errors from `defer` (Close, Flush, Commit) logged
- HTTP handlers return generic errors to client, details to logs

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

**Any DB:** no SQL via string concat, no `SELECT *` in prod, migrations have rollback, indexes on FK/WHERE, pool limits set, no hardcoded DB password, graceful close on shutdown.

### Complexity & architecture

- Functions with cognitive complexity >50
- Files >500 lines
- Circular package dependencies
- Test coverage assessment (target: >60% for business logic)

### Performance patterns

- `clone` / copy where pointer/reference would work in hot path
- `string` concatenation in loop (use `strings.Builder`)
- `fmt.Sprintf` in hot path (use `strconv` or builder)
- Missing `sync.Pool` for frequently allocated objects
- Value receiver on large struct (copies on every call)
- `append()` without pre-allocated capacity for known sizes
- Unbounded `[]byte` growth without reset

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
