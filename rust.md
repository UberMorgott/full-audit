# Rust Audit Checks

> **Cross-references:** Works with [README.md](README.md) (orchestration), [universal.md](universal.md) (language-agnostic checks).
>
> **Required reading:**
> - **Confidence Scoring** (README.md) — assign 0-100 per finding. Thresholds: L1≥75, L2≥60, L3≥40.
> - **False Positive Detection** (universal.md) — check stack-specific auto-discard patterns first.
> - **CLI Finding Verification** (universal.md) — 5-step protocol per CLI tool finding.
> - **YAGNI Check** (universal.md) — verify need before suggesting additions.
> - **Anti-Rationalization Rules** (universal.md) — never skip checks or soften findings.

Applies when `Cargo.toml` detected. All commands assume `cd {project_root}`.

---

## Level 1: Quick

### Build + lint
```bash
cargo build 2>&1
cargo clippy -- -D warnings 2>&1
```

### Dependency vulnerabilities
```bash
# Pin: cargo install cargo-audit --version 0.22.1 --locked
cargo audit 2>&1
# Or universal (trivy 0.69.4-6 compromised — pin 0.69.3 / 0.70.0, see tools.md):
# trivy fs --scanners vuln --severity HIGH,CRITICAL . 2>&1
```

### Tests
```bash
cargo test 2>&1
```

### Format check
```bash
cargo fmt --check 2>&1
```

### Toolchain currency
```bash
rustc --version 2>&1
```
> `cargo audit` scans `Cargo.lock` crate advisories (RustSec DB) — NOT stdlib/compiler. For stdlib/toolchain CVEs, track Rust release notes + run `rustup update stable` (separate path). Check `rust-version` in Cargo.toml.

**Pass criteria:** 0 errors, 0 clippy warnings.

---

## Level 2: Full (includes L1)

### cargo-deny (vulns, licenses, bans, duplicates)

```bash
# Requires deny.toml (generate: cargo deny init)
cargo deny check 2>&1
```

Without `deny.toml`:
```bash
cargo deny check advisories 2>&1
cargo deny check licenses 2>&1
cargo deny check bans 2>&1
cargo deny check sources 2>&1
```

### Unsafe code audit
```bash
cargo geiger --all-features 2>&1
```

Check:
- `unsafe` blocks justified with `// SAFETY:` comment
- `unsafe` count minimized — isolated in wrapper functions
- No `unsafe` in public API without docs
- `transmute` usage (almost always wrong — use `from_*`/`TryFrom`)

### Unused dependencies
```bash
# skip_if: nightly_only
# Pin: cargo install cargo-udeps --version 0.1.61 --locked
rustup run nightly rustc --version >/dev/null 2>&1 || { echo "SKIP: nightly not installed"; exit 0; }
cargo +nightly udeps --all-targets 2>&1
```

### Dependency freshness
```bash
cargo outdated -R 2>&1
```

### Code coverage
```bash
# tarpaulin: now cross-platform (Linux/macOS/Windows); ptrace engine richest on Linux
# Pin: cargo install cargo-tarpaulin --version 0.35.4 --locked
cargo tarpaulin --out Html --skip-clean 2>&1

# Cross-platform via llvm-cov (region-level accuracy)
# Install if not present (preferred: pre-install via tools.md, pin 0.8.7):
# Windows: if (-not (Get-Command cargo-llvm-cov -EA SilentlyContinue)) { cargo +stable install cargo-llvm-cov --version 0.8.7 --locked }
# POSIX:   command -v cargo-llvm-cov >/dev/null 2>&1 || cargo +stable install cargo-llvm-cov --version 0.8.7 --locked
cargo llvm-cov --summary-only 2>&1
```

### Binary size analysis
```bash
cargo bloat --release --crates 2>&1
```

### Fuzz testing
```bash
# skip_if: nightly_only
cargo +nightly fuzz list 2>&1
cargo +nightly fuzz run {target} -- -max_total_time=30 2>&1
```

### Miri (UB detection)
```bash
# skip_if: nightly_only + no_tool(miri component)
cargo +nightly miri test 2>&1
```

### Semgrep SAST
```bash
semgrep --config=auto . 2>&1
```

### Secrets scan
> Skip if Trivy used. Pin: `go install github.com/gitleaks/gitleaks/v8@v8.30.1`
```bash
# --redact masks secret values; write findings to gitignored report (add gitleaks-report.json to .gitignore)
gitleaks detect --source . --no-git --redact --report-path gitleaks-report.json 2>&1
```

---

## Level 2: Code Review (Opus agents)

> **Reviewer mapping:** Security → diff-scanner + impact-reviewer. Concurrency → diff-scanner + history-reviewer. Resource leaks → diff-scanner. Conventions → convention-checker. Stale comments/TODOs → comment-checker.

### Memory safety (beyond borrow checker)

- `unsafe`: each block needs `// SAFETY:` comment with invariants
- `std::mem::transmute` — prefer safe alternatives
- `std::ptr::read`/`write` — ensure alignment + validity
- `Box::from_raw` without matching `Box::into_raw` (double-free/leak)
- `ManuallyDrop` without explicit drop path
- `Pin` misuse (moving pinned data)
- FFI: all `extern "C"` functions validate inputs
- Manual `Send`/`Sync` impls — require careful review

### Concurrency

- `Arc<Mutex<T>>` with long-held locks (deadlock risk)
- Inconsistent lock ordering (A→B vs B→A)
- `Mutex::lock().unwrap()` — panics on poison (use `.expect("reason")` or handle)
- `tokio::spawn` without `.await` on handle (fire-and-forget, lost errors)
- Blocking in async context (`std::thread::sleep`, sync I/O in async fn)
- `async_trait` overhead in hot paths
- Unbounded `mpsc` channel (unbounded memory growth)
- `RwLock` with write-heavy pattern (consider `Mutex`)

### Error handling

- `unwrap()`/`expect()` in library code (should return `Result`)
- `unwrap()` in production paths (OK only in tests/provably-safe)
- `.unwrap_or_default()` hiding real errors
- Error types missing `Display`/`Error` impl
- `?` losing context (use `anyhow::Context` or `map_err`)
- `panic!` in library code
- `todo!()`/`unimplemented!()` in non-prototype code

### Resource management

- File/socket without `drop` guarantee (use RAII)
- `forget()` on resource-owning values (leak)
- Connection pools without size limits
- `TempDir`/`TempFile` drop not guaranteed on panic
- HTTP client without timeout

### Performance

- `clone()` in hot paths where borrow works
- `String` where `&str` suffices
- `Vec` without `with_capacity` for known sizes
- `format!()` in hot loop (allocates each time)
- `HashMap` without `with_capacity` for known sizes
- `collect::<Vec<_>>()` immediately iterated (skip collect)
- Boxing where stack allocation works
- `to_string()`/`to_owned()` where reference lifetime sufficient

### Rust vulnerability patterns

| Vuln | Grep pattern | Fix |
|------|-------------|-----|
| Unsafe code | `unsafe\s*\{` | Minimize, wrap in safe API, add `// SAFETY:` |
| Transmute | `transmute` | Use `from_*`, `TryFrom`, or `as` casts |
| SQL Injection | `format!.*SELECT`, `&format!.*WHERE` | Parameterized queries (sqlx `query!`) |
| Command Injection | `Command::new.*` + user input | Whitelist commands, use `.arg()` not shell interpolation |
| Path Traversal | `Path::new.*` + user input | Canonicalize + prefix check |
| Unwrap in prod | `\.unwrap\(\)` (outside `_test.rs`) | Use `?`, `.expect("reason")`, or handle `Result` |
| Blocking in async | `std::thread::sleep`, `std::fs::` in async fn | Use `tokio::time::sleep`, `tokio::fs::` |
| Deadlock | `Mutex::lock.*Mutex::lock` (nested) | Consistent lock ordering, or `parking_lot` |
| Memory leak | `mem::forget`, `ManuallyDrop` without drop | Ensure explicit drop path |
| Fire-and-forget | `tokio::spawn` without `JoinHandle` | Store handle, await/abort on shutdown |

---

## Level 3: Deep (includes L2)

### Architecture

- Public API surface too large (should be `pub(crate)`)
- Flat module structure (everything in `lib.rs`/`main.rs`)
- Circular module dependencies
- God struct (>20 fields, >10 methods)
- Trait >10 methods (split it)
- Over-generic where concrete type works

### API safety

- Public fns accepting `String` where `&str` works (unnecessary caller allocation)
- Returning `Vec<T>` where `impl Iterator<Item=T>` works (lazy eval)
- `pub` fields on structs (should be private with getter/setter)
- Missing `#[must_use]` on `Result`-returning fns
- Missing `#[non_exhaustive]` on public enums (adding variant = breaking change)
- Builder pattern without compile-time guarantees (typestate for required fields)

### Dependency quality

> L3: consider cargo-vet for supply chain verification (see tools.md).
> Check Cargo.toml for `rust-version` (MSRV). Missing = potential compat issues.

```bash
cargo tree --depth 3 2>&1
cargo tree --duplicates 2>&1
```

Check:
- No unmaintained crates (>2yr without update)
- No yanked versions
- Minimal dep tree (each dep justified)
- `[patch]` section explained in comments
- Feature flags minimize compiled code

### Web framework checks (Actix-web, Axum, Rocket)

<details><summary>Actix-web / Axum / Rocket</summary>

- Middleware/layer order: tracing → auth → CORS → routes
- Extractors validate input (reject malformed early)
- Shared state via `Arc`/`Extension` — no global mutable
- Rate limiting configured
- CORS scoped (not blanket allow-all)
- Graceful shutdown via `tokio::signal`
- Custom error responses (no internals to client)
- Request body size limits set
- TLS configured or behind reverse proxy

</details>

### Async-specific (tokio/async-std)

> Async cancellation safety: verify `select!` branches handle cancellation. Drop + async interaction can leak resources.

- `tokio::main` with proper runtime config (multi-thread vs current-thread)
- `select!` branches all cancel-safe
- Graceful shutdown via `tokio::signal`
- Task `JoinHandle` errors handled (panic in spawned task)
- No sync primitives in async (`std::sync::Mutex` vs `tokio::sync::Mutex`)
- Backpressure on channels (bounded + handle full case)

### License compliance
```bash
cargo deny check licenses 2>&1
# Or: trivy fs --scanners license . 2>&1
```
