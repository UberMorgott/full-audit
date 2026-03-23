# Python Audit Checks

Applies when `pyproject.toml`, `requirements.txt`, `setup.py`, or `Pipfile` detected.
All commands assume `cd {project_root}`.

---

## Level 1: Quick

### Syntax check + lint
```bash
ruff check . 2>&1
# Or if ruff not available:
# python -m py_compile $(find . -name "*.py" -not -path "./.venv/*") 2>&1
# flake8 . 2>&1
```

### Dependency vulnerabilities
```bash
pip-audit 2>&1
# Or: safety check 2>&1
# Or universal: trivy fs --scanners vuln --severity HIGH,CRITICAL . 2>&1
```

### Tests
```bash
# Detect test runner
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
# Check if mypy config exists or py.typed marker
if grep -q "mypy" pyproject.toml 2>/dev/null || [ -f "mypy.ini" ] || [ -f ".mypy.ini" ]; then
  mypy . 2>&1
fi
```

**Pass criteria:** 0 errors in all commands.

---

## Level 2: Full (includes Level 1)

### Security scan — Bandit
```bash
bandit -r . -x ./.venv,./tests -f json 2>&1
```

Key rules:
- `B101` — assert used for security (disabled in optimized mode)
- `B102` — exec() usage
- `B103` — set_bad_file_permissions
- `B104` — bind to 0.0.0.0
- `B105-B107` — hardcoded passwords/secrets
- `B108` — hardcoded tmp directory
- `B301-B303` — pickle/marshal/yaml deserialization
- `B501-B504` — SSL/TLS issues
- `B601-B610` — shell injection
- `B701` — Jinja2 autoescape

### Dead code
```bash
vulture . --min-confidence 80 2>&1
```

### Complexity metrics
```bash
radon cc . -a -nc 2>&1     # Cyclomatic complexity (show only C+ grade)
radon mi . -nc 2>&1         # Maintainability index (show only problematic)
```

### Import sorting + formatting check
```bash
ruff check --select I . 2>&1       # isort rules
ruff format --check . 2>&1         # formatting
```

### Code coverage
```bash
pytest --cov=. --cov-report=term-missing 2>&1
# Or:
coverage run -m pytest && coverage report --show-missing 2>&1
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

### Security review

- **SQL injection:** string formatting in SQL queries (`f"SELECT ... {user_input}"`, `%` formatting, `.format()`)
  - Must use parameterized queries: `cursor.execute("SELECT ... WHERE id = ?", (user_id,))`
- **Command injection:** `os.system()`, `subprocess.call(shell=True)`, `subprocess.Popen(shell=True)` with user input
- **Path traversal:** `os.path.join(base, user_input)` without `os.path.realpath` + prefix check
- **Deserialization:** `pickle.loads()`, `yaml.load()` (use `yaml.safe_load()`), `marshal.loads()` on untrusted data
- **SSRF:** `requests.get(user_url)` without URL scheme validation
- **Eval:** `eval()`, `exec()`, `compile()` with user data
- **Template injection:** Jinja2 without autoescape, `render_template_string(user_input)`
- **Hardcoded secrets:** API keys, passwords, tokens in source (not env vars)
- **Debug mode:** `DEBUG=True` in production config

### Concurrency (if async/threading used)

- `threading.Thread` without daemon flag or join (zombie threads)
- Shared mutable state without `threading.Lock`
- `asyncio.create_task()` without awaiting or storing reference (fire-and-forget)
- `async with` not used for async context managers
- Blocking calls in async functions (`time.sleep` instead of `asyncio.sleep`, sync I/O)
- No `asyncio.gather` error handling (`return_exceptions=True`)
- Thread pool without `max_workers` limit
- `global` keyword for mutable state in multi-threaded code

### Resource leaks

- File open without `with` statement (no guaranteed close)
- DB connection without context manager or explicit close
- HTTP session not reused (`requests.get()` per call instead of `Session`)
- Temp files without cleanup (`tempfile.NamedTemporaryFile(delete=False)` without cleanup)
- Socket/connection not closed in finally/context manager
- Generator not fully consumed or closed (resource held)

---

## Level 3: Deep (includes Level 2)

### Error handling

- Bare `except:` or `except Exception:` catching too broadly
- `pass` in except block (silently swallowing errors)
- No logging in except blocks
- `sys.exit()` outside `__main__`
- `raise` without `from` (lost exception chain): `raise NewError() from original_error`
- Return `None` on error instead of raising (hides failures)

### Type safety

```bash
mypy --strict . 2>&1
# Or: pyright . 2>&1
```

Check:
- `Any` type usage (should be specific)
- Missing return type annotations on public functions
- `# type: ignore` without specific error code
- `cast()` usage (potential type unsafety)
- `Optional` without None check before use

### Dependency management

```bash
# Freshness
pip list --outdated 2>&1

# Unused dependencies (if pipreqs available)
pipreqs . --print 2>&1
# Compare with requirements.txt / pyproject.toml
```

Check:
- `requirements.txt` has pinned versions (not `>=` or unpinned)
- `pyproject.toml` has version bounds
- No `pip install` in source code
- Virtual environment used (`.venv/`, `venv/` in .gitignore)
- Lock file committed (`poetry.lock`, `Pipfile.lock`, `uv.lock`)

### License compliance
```bash
pip-licenses --fail-on="GPL-2.0;GPL-3.0;AGPL-3.0" 2>&1
# Or: trivy fs --scanners license . 2>&1
```

### Architecture

- Circular imports (import at module level that creates cycle)
- God modules (>500 lines)
- Business logic in views/routes (should be in services/domain layer)
- No `__init__.py` structure (flat package, hard to navigate)
- Test files not mirroring source structure

### Task queue checks (Celery, RQ, Dramatiq)

<details><summary>Celery / task queue</summary>

- Tasks are idempotent (safe to retry)
- Retry with `max_retries` + exponential backoff (`retry_backoff=True`)
- Result backend configured and cleaned up (results expire)
- Dead letter queue / error handling for failed tasks
- Task serialization: JSON preferred over pickle (security)
- `task_acks_late=True` for at-least-once delivery
- Worker concurrency configured (not unlimited)
- Periodic tasks via `celery beat` with proper schedule (no drift)

</details>

### Django/Flask/FastAPI specific

<details><summary>Django</summary>

- `DEBUG = True` in production settings
- `SECRET_KEY` hardcoded (should be env var)
- `ALLOWED_HOSTS = ['*']`
- CSRF middleware disabled
- Raw SQL queries (`cursor.execute` with string formatting)
- `@csrf_exempt` on POST endpoints
- No rate limiting on auth endpoints
- `FileField`/`ImageField` without upload validation
- `JsonResponse` with internal error details

</details>

<details><summary>Flask</summary>

- `app.run(debug=True)` in production
- `SECRET_KEY` hardcoded
- No CSRF protection (use Flask-WTF)
- `send_file()` with user-controlled path
- No rate limiting (Flask-Limiter)
- `jsonify()` with internal error details

</details>

<details><summary>FastAPI</summary>

- No `Depends()` for auth on protected routes
- `allow_origins=["*"]` in CORS middleware
- No rate limiting
- Sync functions in async router (blocking event loop)
- No `response_model` on endpoints (leaking internal fields)
- Background tasks without error handling

</details>
