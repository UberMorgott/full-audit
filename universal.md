# Universal Audit Checks

Language-agnostic checks. Apply to ANY project regardless of stack.
These are code review tasks for Opus agents.

> **Note:** Stack-specific files (`go.md`, `python.md`, etc.) extend but do not repeat these checks. If a check here overlaps with a stack file, the stack file provides language-specific details.

---

## Level 2: Git Hygiene (CLI, haiku)

> Requires Unix shell (Git Bash / WSL on Windows). These commands may not work in Windows cmd/PowerShell natively.

```bash
# Large files >1MB
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | sed -n '/^blob/{s/blob //;p}' | awk '{if ($2 > 1048576) print $2, $3}' | sort -rn 2>&1

# Suspicious files (adjust exclusions per project)
git ls-files | grep -iE '\.(env|key|pem|p12|pfx|jks|sqlite|db)$' 2>&1
git ls-files '*.dll' '*.pdb' '*.exe' | grep -v 'tools/' 2>&1

# .gitignore completeness (add OS/stack-specific entries as needed)
for f in node_modules .env dist build .DS_Store Thumbs.db desktop.ini __pycache__ .venv venv target bin obj; do
  git ls-files --error-unmatch "$f" 2>/dev/null && echo "WARNING: $f tracked"
done
```

---

## Level 2: HTTP Security Headers (Opus)

Verify responses include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY` or `SAMEORIGIN`
- `Referrer-Policy: strict-origin-when-cross-origin` (or stricter)
- `Content-Security-Policy` (at least `default-src 'self'`)
- `Strict-Transport-Security` (if HTTPS, `max-age>=31536000`)
- `Permissions-Policy` (restrict camera, microphone, geolocation)
- No `Server` header leaking version info
- No `X-Powered-By` header

---

## Level 2: CSRF Protection (Opus)

- State-changing endpoints (POST/PUT/DELETE) protected against CSRF
- If using cookies for auth: CSRF token or SameSite=Strict/Lax cookie flag
- Double-submit cookie pattern or synchronizer token pattern implemented
- Origin/Referer header validated on server side
- GET requests do not cause side effects (safe methods)
- AJAX requests include CSRF header if required by framework

---

## Level 2: Rate Limiting (Opus)

- Rate limiting on all public-facing API endpoints (not just login)
- Per-user, per-IP, or per-API-key throttling
- 429 Too Many Requests response with `Retry-After` header
- Login/auth endpoints have stricter limits (prevent brute force)
- Rate limits documented for API consumers
- No rate limit bypass via header manipulation (X-Forwarded-For spoofing)

---

## Level 3: XSS Prevention (Opus)

- All user input escaped before rendering in HTML context
- No raw HTML rendering with user data (e.g., `v-html`, `dangerouslySetInnerHTML`, `innerHTML`, `Html.Raw()`, `|safe` Jinja filter, `@Html.Raw()`)
- Content-Security-Policy header blocks inline scripts (`script-src` without `unsafe-inline`)
- URL parameters not reflected in page without sanitization
- Rich text editors sanitize output (DOMPurify or equivalent)
- SVG uploads sanitized (can contain embedded scripts)
- JSON responses use `Content-Type: application/json` (not `text/html`)

---

## Level 3: SSRF Prevention (Opus)

- User-supplied URLs validated: only `http://` and `https://` schemes allowed
- Private/internal IP ranges blocked (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16, ::1)
- DNS rebinding protection (resolve hostname, check IP before request)
- Redirect following limited or disabled for user-supplied URLs
- Cloud metadata endpoints blocked (169.254.169.254, metadata.google.internal)
- URL validation applied before saving to config/DB, not just before use

---

## Level 3: IDOR / Access Control (Opus)

- Every endpoint validates that the authenticated user has access to the requested resource
- Object IDs in URLs/params checked against user's ownership/permissions (not just existence)
- No sequential/predictable IDs exposed without access check (use UUIDs or verify ownership)
- Bulk endpoints validate access for each item in the list
- Admin endpoints have explicit role/permission checks
- Privilege escalation paths checked: can a regular user access admin resources by changing IDs?
- Horizontal access checked: can user A access user B's resources?

---

## Level 3: Session Management (Opus)

- Session ID regenerated after login (prevent session fixation)
- Session timeout: idle timeout (e.g., 30 min) + absolute timeout (e.g., 24h)
- Concurrent session limits (if applicable)
- Session invalidated on logout (server-side, not just client-side token deletion)
- Secure cookie flags: `Secure`, `HttpOnly`, `SameSite=Strict` or `Lax`
- Session binding: consider IP/User-Agent binding for sensitive apps
- Session storage: server-side or encrypted JWT (not plain data in cookie)

---

## Level 3: JWT / Auth Audit (Opus)

- Algorithm validation (no `alg: none` acceptance, no RS256/HS256 confusion)
- Token expiry: access <=24h, refresh <=30d
- Refresh token rotation (old token invalidated on use)
- Rate limit on login endpoint (prevent brute force)
- Secret/key not hardcoded or predictable
- Logout invalidates token (blacklist or short-lived + refresh revocation)
- Token stored securely (httpOnly cookie, not localStorage for sensitive apps)
- CSRF protection if using cookies for auth
- Password hashing: bcrypt/Argon2/scrypt (not MD5/SHA)

---

## Level 3: API Contract Consistency (Opus)

- Backend model JSON field names match frontend interface/type definitions
- Nullable fields (backend: language-appropriate nullable type) match frontend optional (`field?: type`)
- Enums: backend values match frontend constants
- HTTP status codes: frontend handles 4xx/5xx appropriately
- No dead endpoints (backend route without any frontend caller, or vice versa)
- Request/response shapes documented (OpenAPI/Swagger or at least typed interfaces)
- Pagination: backend supports it, frontend uses it
- Error response format consistent across all endpoints

---

## Level 3: Logging & Observability (Opus)

- Errors logged with context (not bare `log(err)` — include what operation, what input)
- No PII in logs (emails, passwords, tokens, IP addresses)
- Structured logging (JSON or key-value, not free-form strings)
- Health check endpoint exists
- Key operations logged: login/logout, CRUD on important entities, config changes, permission changes
- Correct log levels (ERROR for errors, WARN for degradation, INFO for operations, DEBUG for dev)
- Log rotation configured (not growing unbounded)
- Request ID / correlation ID for tracing across services
- Debug endpoints disabled in production (`/debug/pprof`, `/actuator`, `/__debug__`, `/swagger` if not public API)

---

## Level 3: Error Information Disclosure (Opus)

- Stack traces not returned in production API responses
- Internal paths, hostnames, database names not leaked in errors
- Generic error messages to clients ("Internal server error"), details to logs
- Framework default error pages disabled in production
- Database error details not exposed (SQL syntax, table names)
- Verbose error modes disabled (`DEBUG=False`, `ASPNETCORE_ENVIRONMENT=Production`, etc.)

---

## Level 3: Overengineering & Wheel Reinvention (Opus)

**Reinventing wheels:** check `shared/`, `utils/`, `helpers/`, `common/`:
- Is there a stdlib or dependency equivalent?
- Manual implementations of: retry, debounce, throttle, cron, UUID, HTTP router, connection pool, rate limiter, LRU cache, event emitter

**Overengineering:**
- Interface/trait/protocol with exactly 1 implementation (not for testing)
- Factory for exactly 1 type
- Generics/templates called with exactly 1 type
- Event bus / pub-sub for <=2 subscribers
- Abstraction layer that just delegates to another layer
- Config for behavior that never changes

**Workarounds & tech debt markers:**
- `TODO` / `HACK` / `FIXME` / `XXX` markers (count and assess)
- Lint suppression without explanation (examples per language: `//nolint`, `@ts-ignore`, `# noqa`, `#pragma warning disable`, `@SuppressWarnings`)
- Copy-paste >10 lines (should be extracted)
- Type system bypass (examples per language: `any`, `object`, `dynamic`, `interface{}`, `unsafe`)
- Magic numbers (unexplained constants)

---

## Level 3: Documentation Freshness (Opus)

- README matches actual launch/build/deploy instructions
- API endpoints documented and up-to-date
- Environment variables documented
- Architecture docs match reality
- CLAUDE.md / contributing guide rules match actual code patterns
- Changelog maintained (if project uses one)
- Deprecated features marked

---

## Level 3: Input Validation Completeness (Opus)

- Endpoint x validation matrix (every endpoint validates its inputs)
- File upload: MIME check by magic bytes (not just extension/Content-Type header)
- Numeric inputs: boundary checks (min, max, NaN, Infinity)
- String inputs: length limits, format validation
- Server-side validation present (not just frontend)
- Query/path params not passed raw to SQL, filesystem, or shell
- JSON deserialized into explicit structs/classes (not raw dict/map)
- Array/list inputs: size limits (prevent memory exhaustion)
- Path traversal: user input in file paths validated (canonical path check, prefix validation)

---

## Level 3: Resilience Patterns (Opus)

- Retry with exponential backoff + jitter (not fixed interval)
- Idempotency on retry (same request doesn't cause duplicate side effects)
- Circuit breaker for unstable external dependencies
- Retry storm protection (not all instances retry at the same time)
- Fallback behavior defined (what happens when dependency is down?)
- Timeout cascade: external call timeout < handler timeout < server timeout
- Bulkhead: failure in one subsystem doesn't cascade to others

---

## Level 3: Configuration Management (Opus)

- No magic numbers (timeouts, limits, thresholds in config, not code)
- Dev defaults not in production (debug flags, verbose logging, permissive CORS)
- Config validated on startup (fail fast if misconfigured)
- Hot reload without race conditions (if supported)
- Secrets in env vars / secret manager (not in config files committed to git)
- Config files have comments/documentation for non-obvious values
- Debug endpoints disabled in production

---

## Level 3: State Management & Offline Resilience (Opus)

> Especially relevant for desktop, mobile, and SPA applications.

- Connection loss shows UI status indicator
- Reconnect without data duplication
- Reconnect syncs state (no stale data displayed)
- Crash recovery (app state persisted, restorable)
- Loading / error / empty states in all data-fetching components
- Optimistic updates rolled back on server error
- Concurrent edits handled (last-write-wins or conflict resolution)

---

## Level 3: Privacy / PII (Opus)

- No PII in logs (emails, names, addresses, phone numbers)
- No PII in URL params (visible in server logs, browser history)
- Passwords hashed with modern algorithm (bcrypt, Argon2, scrypt — not MD5, SHA)
- Data minimization (don't collect what you don't need)
- Data deletion mechanism exists (user can request data removal)
- PII encrypted at rest (if stored)
- GDPR/privacy policy considerations (if applicable)

---

## Level 3: Supply Chain (Opus)

- Lock files committed (e.g., `package-lock.json`, `go.sum`, `Cargo.lock`, `poetry.lock`, `packages.lock.json`)
- No `latest` / `*` / unbounded versions in manifests
- Binaries in repo have provenance documentation
- CI actions pinned by SHA, not by mutable tag (see Trivy v0.69.4 incident)
- Dependencies from trusted registries (not random git URLs)
- Minimal dependency count (each dependency justified)
- Sub-dependency audit: transitive deps checked for known vulns
- Dependency confusion: private package names don't conflict with public registries

> `skip_if` no CI/CD: check `.github/workflows/`, `Jenkinsfile`, `.gitlab-ci.yml`, `azure-pipelines.yml` first.

---

## Level 3: Stack Currency (Web search, Sonnet)

Read manifest files -> extract runtime/framework/library versions -> web search latest for each.

Rate each as:

| Status | Definition |
|--------|-----------|
| **Current** | Latest or latest-1 minor |
| **Behind** | 2+ minor versions behind |
| **EOL** | End of life / no security patches |
| **Vulnerability** | Known unpatched CVE |
