# Python Audit Checks

> **Cross-references:** Works with [README.md](README.md) (orchestration), [universal.md](universal.md) (language-agnostic checks).
>
> **Required reading:**
> - **Confidence Scoring** (README.md) — 0-100 per finding. Thresholds: L1>=75, L2>=60, L3>=40.
> - **False Positive Detection** (universal.md) — check auto-discard patterns before including.
> - **CLI Finding Verification** (universal.md) — 5-step protocol per CLI finding.
> - **YAGNI Check** (universal.md) — verify need before suggesting additions.
> - **Anti-Rationalization** (universal.md) — don't skip checks or soften findings.

Applies when `pyproject.toml`, `requirements.txt`, `setup.py`, or `Pipfile` detected.
All commands assume `cd {project_root}`.

---

## Level 1: Quick

### Syntax + lint
```bash
ruff check . 2>&1   # install pinned: pip install ruff==0.15.15
# Or if ruff unavailable (cross-platform):
# python -m compileall . 2>&1
# python -m py_compile $(find . -name "*.py" -not -path "./.venv/*") 2>&1   # > skip_if: windows ($()/find bash-only)
# flake8 . 2>&1
```

### Dependency vulns
```bash
pip-audit 2>&1   # install pinned: pip install pip-audit==2.10.0
# Or (safety -> replaced by pip-audit; safety needs login/account): pip install pip-audit==2.10.0
# Or (verify version — v0.69.4-6 compromised, see tools.md):
# trivy fs --scanners vuln --severity HIGH,CRITICAL . 2>&1
```

> For `uv` projects, use uv-based dependency checking instead.

> Tip: Prefix with `uv tool run` if tools not globally installed.

### Tests
```bash
if [ -f "pyproject.toml" ] && grep -q "pytest" pyproject.toml; then
  python -m pytest --tb=short -q 2>&1
elif [ -d "tests" ]; then
  python -m pytest --tb=short -q 2>&1
else
  python -m unittest discover -s . -p "test_*.py" 2>&1
fi
```

### Type check (if typed)
```bash
if grep -q "mypy" pyproject.toml 2>/dev/null || [ -f "mypy.ini" ] || [ -f ".mypy.ini" ]; then
  mypy . 2>&1   # install pinned: pip install mypy==2.1.0
fi
```

### Runtime currency
```bash
python --version 2>&1
```
> If pip-audit/safety reports stdlib/CPython vulns, update runtime via python.org/downloads.

**Pass criteria:** 0 errors in all commands.

---

## Level 2: Full (includes L1)

### Security — Bandit
```bash
bandit -r . -x ./.venv,./tests -f json 2>&1   # install pinned: pip install "bandit[toml]==1.9.4"
```

Key rules:
- `B101` — assert for security (disabled in optimized mode)
- `B102` — exec()
- `B103` — bad file permissions
- `B104` — bind 0.0.0.0
- `B105-B107` — hardcoded passwords/secrets
- `B108` — hardcoded tmp dir
- `B301-B303` — pickle/marshal/yaml deserialization
- `B501-B504` — SSL/TLS issues
- `B601-B610` — shell injection
- `B701` — Jinja2 autoescape

### Dead code
```bash
vulture . --min-confidence 80 2>&1   # install pinned: pip install vulture==2.16
```

### Complexity
```bash
radon cc . -a -nc 2>&1     # Cyclomatic (C+ grade only); install pinned: pip install radon==6.0.1
radon mi . -nc 2>&1         # Maintainability (problematic only)
```

### Import sorting + formatting
```bash
ruff check --select I . 2>&1       # isort
ruff format --check . 2>&1         # formatting
```

### Coverage
```bash
pytest --cov=. --cov-report=term-missing 2>&1
# Or:
coverage run -m pytest; coverage report --show-missing 2>&1
```

### Semgrep SAST
```bash
semgrep --config=auto . 2>&1   # install pinned: pip install semgrep==1.164.0
```

### Secrets scan
> Skip if Trivy used.
```bash
# --redact (no raw secrets in output); findings to gitignored report; no -v in captured output
gitleaks detect --source . --no-git --redact --report-path .gitleaks-report.json 2>&1   # install pinned: go install github.com/gitleaks/gitleaks/v8@v8.30.1
# Add .gitleaks-report.json to .gitignore
```

---

## Level 2: Code Review (Opus agents)

> **Reviewer mapping:** Security -> diff-scanner + impact-reviewer. Concurrency -> diff-scanner + history-reviewer. Resource leaks -> diff-scanner. Convention -> convention-checker. Stale comments/TODOs -> comment-checker.

### Security

- **SQL injection:** string formatting in queries (`f"SELECT ... {user_input}"`, `%`, `.format()`) — use parameterized: `cursor.execute("... WHERE id = ?", (user_id,))`
- **Command injection:** `os.system()`, `subprocess.*(shell=True)` with user input
- **Path traversal:** `os.path.join(base, user_input)` without `realpath` + prefix check
- **Deserialization:** `pickle.loads()`, `yaml.load()` (use `safe_load`), `marshal.loads()` on untrusted data
- **SSRF:** `requests.get(user_url)` without scheme validation
- **Eval:** `eval()`, `exec()`, `compile()` with user data
- **Template injection:** Jinja2 without autoescape, `render_template_string(user_input)`
- **Hardcoded secrets:** API keys/passwords/tokens in source (not env vars)
- **Debug mode:** `DEBUG=True` in production

### Concurrency (if async/threading)

> 3.11+: Check TaskGroup. 3.12+: Check ExceptionGroup handling.
>
> **Dynamic-concurrency parity:** The GIL does NOT make multi-step ops race-free — check-then-act, read-modify-write, and `+=` on shared state still race (GIL only protects single bytecode ops, releases between them; gone entirely under free-threaded 3.13+ `--disable-gil`). Unlike Go (`-race`), Rust (Send/Sync), Java/C# (dynamic race detectors), Python has NO dynamic race-detection tier. Compensate with: pytest-asyncio for async test coverage + a threading/lock static lint pass (the static patterns below). Treat shared-state correctness as manually audited, not tool-guaranteed.

- `threading.Thread` without daemon/join (zombie threads)
- Shared mutable state without `threading.Lock`
- `asyncio.create_task()` without await/store (fire-and-forget)
- Missing `async with` for async context managers
- Blocking in async (`time.sleep` vs `asyncio.sleep`, sync I/O)
- `asyncio.gather` without `return_exceptions=True`
- Thread pool without `max_workers`
- `global` mutable state in multi-threaded code

### Resource leaks

- File open without `with` (no guaranteed close)
- DB connection without context manager/close
- HTTP session not reused (`requests.get()` per call vs `Session`)
- Temp files without cleanup (`NamedTemporaryFile(delete=False)`)
- Socket/connection not closed in finally/context manager
- Generator not consumed/closed (resource held)

### Vulnerability patterns quick reference

| Vuln | Grep pattern | Fix |
|------|-------------|-----|
| SQL Injection | `f"SELECT`, `"SELECT.*".format`, `%s.*execute` | Parameterized: `cursor.execute("...?", (id,))` |
| Cmd Injection | `os.system`, `subprocess.*shell=True` | `subprocess.run([...], shell=False)`, whitelist |
| Path Traversal | `os.path.join.*request`, `open(.*request` | `os.path.realpath()` + prefix check |
| Deserialization | `pickle.loads`, `yaml.load\(` | `json`, `yaml.safe_load()` |
| SSRF | `requests.get\(.*url`, `urllib.request.urlopen` | Validate scheme, block private IPs |
| Eval/exec | `eval\(`, `exec\(`, `compile\(` | Never with user input; AST or safe alt |
| Weak RNG | `random\.(random\|randint\|choice\|randrange\|getrandbits)\(` in security/token context (not bare `import random` — overbroad, see universal.md false-positive table) | `secrets.token_hex()`, `token_urlsafe()`, `secrets.choice()` |
| Debug prod | `DEBUG\s*=\s*True`, `app.run(debug=True)` | `DEBUG = os.getenv("DEBUG") == "true"` |
| Hardcoded secrets | `password\s*=\s*["']`, `api_key\s*=\s*["']` | Env vars, secret manager |
| Template injection | `render_template_string\(.*request` | Never pass user input to templates |

---

## Level 3: Deep (includes L2)

### Error handling

- Bare `except:`/`except Exception:` — too broad
- `pass` in except (silently swallowing)
- No logging in except blocks
- `sys.exit()` outside `__main__`
- `raise` without `from` (lost chain): use `raise X() from orig`
- Return `None` on error vs raising (hides failures)

### Type safety

```bash
mypy --strict . 2>&1
# Or: pyright . 2>&1
```

- `Any` usage (should be specific)
- Missing return annotations on public functions
- `# type: ignore` without error code
- `cast()` (potential unsafety)
- `Optional` without None check

### Dependency management

```bash
pip list --outdated 2>&1

# Unused deps (if pipreqs available)
pipreqs . --print 2>&1   # install pinned: pip install pipreqs==0.5.0
# Compare with requirements.txt / pyproject.toml
```

- `requirements.txt` pinned versions (not `>=` or unpinned)
- `pyproject.toml` version bounds
- No `pip install` in source
- Virtual env in .gitignore
- Lock file committed (`poetry.lock`, `Pipfile.lock`, `uv.lock`)

### License compliance
```bash
pip-licenses --fail-on="GPL-2.0;GPL-3.0;LGPL-2.1;LGPL-3.0;AGPL-3.0" 2>&1   # install pinned: pip install pip-licenses==5.5.5
# Or: trivy fs --scanners license . 2>&1
```

### Architecture

- Circular imports (module-level cycles)
- God modules (>500 lines)
- Business logic in views/routes (belongs in services/domain)
- No `__init__.py` structure (flat package)
- Tests not mirroring source structure

### Performance

- N+1 queries (`select_related`/`prefetch_related` missing in Django, eager loading in SQLAlchemy)
- Sync blocking in async (`time.sleep`, `requests.*` in `async def` — use `asyncio.sleep`, `httpx.AsyncClient`)
- GIL-bound CPU in hot paths — offload to `ProcessPoolExecutor`/C extension
- Repeated serialization in loops (`json.dumps/loads` — use `orjson`/`msgpack`)
- Unbounded collection growth (no eviction)
- Missing DB connection pooling (`pool_size`, `CONN_MAX_AGE`)
- Large queryset without `.iterator()` (loads all into memory)

### Task queue (Celery, RQ, Dramatiq)

<details><summary>Celery / task queue</summary>

- Tasks idempotent (safe to retry)
- `max_retries` + exponential backoff (`retry_backoff=True`)
- Result backend configured, results expire
- Dead letter queue for failed tasks
- JSON serialization over pickle (security)
- `task_acks_late=True` for at-least-once
- Worker concurrency configured
- `celery beat` periodic tasks with proper schedule

</details>

### Django/Flask/FastAPI

<details><summary>Django</summary>

- `DEBUG = True` in production
- `SECRET_KEY` hardcoded
- `ALLOWED_HOSTS = ['*']`
- CSRF disabled or `@csrf_exempt` on POST
- **Middleware order:** `SecurityMiddleware` -> `SessionMiddleware` -> `CommonMiddleware` -> `CsrfViewMiddleware` -> `AuthenticationMiddleware` -> custom -> `MessageMiddleware`. Auth before CSRF = broken. Wrong order = silent failures.
- Raw SQL with string formatting
- No rate limiting on auth
- `FileField`/`ImageField` without upload validation
- `JsonResponse` with internal error details

</details>

<details><summary>Flask</summary>

- `app.run(debug=True)` in production
- `SECRET_KEY` hardcoded
- No CSRF (use Flask-WTF)
- `send_file()` with user-controlled path
- No rate limiting (Flask-Limiter)
- `jsonify()` with internal errors
- **before_request order:** registration order matters. Auth before data-access. Rate limiting before routes.

</details>

<details><summary>FastAPI</summary>

- No `Depends()` for auth on protected routes
- `allow_origins=["*"]` in CORS
- No rate limiting
- Sync in async router (blocking loop)
- No `response_model` (leaking internals)
- Background tasks without error handling
- **Middleware order:** `add_middleware()` reverse order (last added = first run). Call order: routes -> auth -> CORS -> TrustedHost -> HTTPS redirect. CORS must wrap auth.

</details>
