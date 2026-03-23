# Rust Audit Checks

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
cargo audit 2>&1
# Or universal: trivy fs --scanners vuln --severity HIGH,CRITICAL . 2>&1
```

### Tests
```bash
cargo test 2>&1
```

### Format check
```bash
cargo fmt --check 2>&1
```

**Pass criteria:** 0 errors, 0 warnings from clippy.

---

## Level 2: Full (includes Level 1)

### Comprehensive lint — cargo-deny

Covers: vulnerabilities, licenses, banned crates, duplicate deps.

```bash
# Requires deny.toml config (generate default: cargo deny init)
cargo deny check 2>&1
```

If no `deny.toml`:
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
- `unsafe` count minimized — wrapper functions isolate unsafe
- No `unsafe` in public API without documentation
- `transmute` usage (almost always wrong — use `from_*` or `TryFrom`)

### Unused dependencies
```bash
# Requires nightly
cargo +nightly udeps --all-targets 2>&1
```

### Dependency freshness
```bash
cargo outdated -R 2>&1
```

### Code coverage
```bash
# Linux only (tarpaulin)
cargo tarpaulin --out Html --skip-clean 2>&1

# Cross-platform alternative via llvm-cov
cargo install cargo-llvm-cov
cargo llvm-cov --summary-only 2>&1
```

### Binary size analysis (for binaries)
```bash
cargo bloat --release --crates 2>&1
```

### Fuzz testing
```bash
# Requires cargo-fuzz (nightly)
cargo +nightly fuzz list 2>&1
# Run each target for 30s:
cargo +nightly fuzz run {target} -- -max_total_time=30 2>&1
```

### Miri (undefined behavior detection)
```bash
cargo +nightly miri test 2>&1
```

### Semgrep SAST
```bash
semgrep --config=auto . 2>&1
```

### Secrets scan
> Skip if Trivy used.
```bash
gitleaks detect --source . --no-git -v 2>&1
```

---

## Level 2: Code Review (Opus agents)

### Memory safety (beyond borrow checker)

- `unsafe` blocks: each must have `// SAFETY:` comment explaining invariants
- `std::mem::transmute` — almost always wrong, prefer safe alternatives
- `std::ptr::read`/`write` — ensure alignment and validity
- `Box::from_raw` without matching `Box::into_raw` (double-free or leak)
- `ManuallyDrop` without explicit drop path
- `Pin` misuse (moving pinned data)
- FFI boundaries: all `extern "C"` functions validate inputs
- `Send`/`Sync` manual implementations — require careful review

### Concurrency

- `Arc<Mutex<T>>` with long-held locks (potential deadlock)
- Lock ordering inconsistency (A->B in one place, B->A in another)
- `Mutex::lock().unwrap()` — panics on poisoned mutex (use `lock().expect("reason")` or handle)
- `tokio::spawn` without `.await` on handle (fire-and-forget, lost errors)
- Blocking in async context (`std::thread::sleep`, sync I/O in async fn)
- `async_trait` overhead in hot paths
- Channel (`mpsc`) without bounded capacity (unbounded memory growth)
- `RwLock` with write-heavy pattern (consider `Mutex` instead)

### Error handling

- `unwrap()` / `expect()` in library code (should return `Result`)
- `unwrap()` in production paths (only OK in tests and provably-safe cases)
- `.unwrap_or_default()` hiding real errors
- Error types without `Display`/`Error` impl
- `?` operator losing context (use `anyhow::Context` or `map_err`)
- `panic!` in library code
- `todo!()` / `unimplemented!()` in non-prototype code

### Resource management

- File/socket without `drop` guarantee (use RAII patterns)
- `forget()` on values that own resources (memory/handle leak)
- Connection pools without size limits
- `TempDir` / `TempFile` drop not guaranteed on panic
- HTTP client without timeout configuration

### Performance

- `clone()` in hot paths where borrow would work
- `String` allocation where `&str` suffices
- `Vec` without `with_capacity` for known sizes
- `format!()` in hot loop (allocates each time)
- `HashMap` without `with_capacity` for known sizes
- `collect::<Vec<_>>()` immediately followed by iteration (skip collect)
- Boxing where stack allocation works
- `to_string()` / `to_owned()` where reference lifetime is sufficient

---

## Level 3: Deep (includes Level 2)

### Architecture

- Public API surface too large (items that should be `pub(crate)`)
- Module structure flat (everything in `lib.rs` / `main.rs`)
- Circular module dependencies
- God struct (>20 fields, >10 methods)
- Trait with >10 methods (should be split)
- Generics over-used where concrete type works

### API safety

- Public functions accepting `String` where `&str` works (unnecessary allocation on caller)
- Returning `Vec<T>` where `impl Iterator<Item=T>` works (lazy evaluation)
- `pub` fields on structs (should be private with getter/setter for invariants)
- Missing `#[must_use]` on functions returning `Result` or values that shouldn't be discarded
- Missing `#[non_exhaustive]` on public enums (breaking change to add variant)
- Builder pattern without compile-time guarantees (typestate pattern for required fields)

### Dependency quality

```bash
# Check dependency tree depth
cargo tree --depth 3 2>&1
# Check for duplicate versions
cargo tree --duplicates 2>&1
```

Check:
- No unmaintained crates (>2 years without update)
- No yanked versions
- Minimal dependency tree (each dep justified)
- `[patch]` section explained in comments
- Feature flags used to minimize compiled code

### Web framework checks (Actix-web, Axum, Rocket)

<details><summary>Actix-web / Axum / Rocket</summary>

- Middleware/layer order correct (tracing -> auth -> CORS -> routes)
- Extractors validate input (reject malformed requests early)
- Shared state via `Arc` / `Extension` — not global mutable
- Rate limiting middleware configured
- CORS policy scoped (not blanket allow-all)
- Graceful shutdown via `tokio::signal`
- Custom error responses (no internal details to client)
- Request body size limits configured
- TLS configured or behind reverse proxy

</details>

### Async-specific (if using tokio/async-std)

- `tokio::main` with proper runtime configuration (multi-thread vs current-thread)
- `select!` branches all cancel-safe
- Graceful shutdown via `tokio::signal`
- Task JoinHandle errors handled (panic in spawned task)
- No sync primitives in async code (`std::sync::Mutex` vs `tokio::sync::Mutex`)
- Backpressure on channels (bounded channels with handled full case)

### License compliance
```bash
cargo deny check licenses 2>&1
# Or: trivy fs --scanners license . 2>&1
```
