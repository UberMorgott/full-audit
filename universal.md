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

## Level 2: Insecure Defaults & Dangerous Configuration (Opus)

> Source: Trail of Bits `insecure-defaults` methodology. Only check prod-reachable code paths.

**Hardcoded secrets & fallback patterns — grep for these regex:**
- `getenv\(.*\)\s*(or|OR|\|\|)\s*["']` — fallback secret after env var lookup
- `DEFAULT_SECRET|default_password|changeme|password123` — well-known placeholder secrets
- `DEBUG\s*[:=]\s*(true|1|yes|on)` — debug mode enabled
- `AUTH.*[:=]\s*(false|0|no|off|disabled)` — auth disabled
- `VERIFY.*[:=]\s*(false|0|no|off)` — verification disabled

**Weak crypto defaults:**
- MD5 / SHA1 / DES / RC4 / Blowfish in security contexts (auth, token generation, integrity)
- `math/rand` (Go) / `random` (Python) / `Math.random()` (JS) for security-sensitive values — must use crypto-secure RNG
- Static or predictable IV/nonce in encryption
- ECB mode in block ciphers
- Key sizes below current minimum (RSA <2048, AES <128, ECDSA <256)

**Permissive access controls:**
- `AllowAll` / `*` in CORS, firewall, permissions without justification
- Default admin accounts or well-known credentials
- Anonymous access to administrative functions
- Default open permissions on file/directory creation

**Silent security failures:**
- Auth check that logs but doesn't block on failure
- Validation that warns but continues processing
- Rate limiter that counts but doesn't reject
- Certificate validation disabled with TODO to re-enable

---

## Level 2: Timing Attacks (Opus)

- Secret comparison (HMAC, tokens, API keys, passwords) must use constant-time comparison:
  - Go: `subtle.ConstantTimeCompare()`
  - Python: `hmac.compare_digest()`
  - Node.js: `crypto.timingSafeEqual()`
  - Java: `MessageDigest.isEqual()`
  - C#: `CryptographicOperations.FixedTimeEquals()`
  - Rust: `constant_time_eq` crate
- Login/auth endpoints: response time should not reveal whether username exists (early return on "user not found" leaks info)
- Rate-limited endpoints: constant-time rejection (don't short-circuit)

---

## Level 2: Mass Assignment / Over-Posting (Opus)

- JSON/form deserialization into structs/objects: ensure user cannot set fields they shouldn't
  - Go: only exported JSON fields user can modify; sensitive fields (`IsAdmin`, `Role`, `CreatedAt`) excluded from request binding
  - Python/Django: `ModelForm.Meta.fields` whitelist (never `__all__`); DRF: `read_only_fields` for computed/admin fields
  - Java/Spring: `@JsonIgnoreProperties` or DTO pattern (don't bind directly to entity)
  - C#: `[Bind(Include="...")]` or separate ViewModel
  - JS/TS: validate/pick only allowed fields from request body
- Admin-only fields (role, permissions, internal IDs) never bindable from user input
- Separate DTOs for create/update vs internal representation

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
- Private/internal IP ranges blocked:
  - IPv4: `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`
  - IPv6: `::1`, `fc00::/7` (unique local), `fe80::/10` (link-local)
- DNS rebinding protection (resolve hostname, check IP before request)
- Redirect following limited or disabled for user-supplied URLs
- Cloud metadata endpoints blocked (169.254.169.254, metadata.google.internal)
- URL validation applied before saving to config/DB, not just before use

---

## Level 3: Deserialization Safety (Opus)

Unsafe deserialization = Remote Code Execution in many languages:

| Language | Dangerous | Safe alternative |
|----------|-----------|-----------------|
| Go | `encoding/gob` with untrusted input, `yaml.v2` with arbitrary types, `encoding/json` into `interface{}` without depth limit | Typed structs, `yaml.v3`, limit JSON depth |
| Python | `pickle.loads()`, `yaml.load()`, `marshal.loads()` | `json`, `yaml.safe_load()`, `msgpack` |
| Java | `ObjectInputStream.readObject()`, `XMLDecoder` | JSON/Protobuf, `ObjectInputFilter` whitelist |
| C# | `BinaryFormatter` (banned), `NetDataContractSerializer` | `System.Text.Json`, `[JsonSerializable]` source gen |
| Rust | `bincode`/`serde` with `#[serde(deny_unknown_fields)]` missing | Typed deserialization with strict schemas |
| JS/TS | `eval(JSON)`, custom deserializers without validation | `JSON.parse()` with schema validation (zod/joi) |

Check:
- No deserialization of untrusted data into arbitrary types
- Input size limits on deserialization (prevent memory exhaustion)
- Schema validation before or during deserialization
- No polymorphic deserialization without type whitelist

---

## Level 3: XXE (XML External Entity) Injection (Opus)

If project processes XML in any form:

- XML parser configured to disable external entities and DTD processing
- Go: `encoding/xml` — vulnerable by default; disable with `xml.NewDecoder` + `d.Strict = true`
- Java: `DocumentBuilderFactory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)`
- Python: `defusedxml` library instead of `xml.etree`, `lxml` with `resolve_entities=False`
- C#: `XmlReaderSettings.DtdProcessing = DtdProcessing.Prohibit`
- PHP: `libxml_disable_entity_loader(true)`
- Check for: SOAP endpoints, RSS/Atom feeds, SAML, SVG uploads, Office file processing (OOXML = XML inside ZIP)

---

## Level 3: ReDoS (Regular Expression DoS) (Opus)

- Regex patterns with nested quantifiers on overlapping groups: `(a+)+`, `(a|a)+`, `(.*a){10}`
- User input used as regex pattern without sanitization (use `regexp.QuoteMeta` in Go, `re.escape()` in Python)
- Regex applied to unbounded user input without length limit
- Use RE2-compatible engines where possible (Go's `regexp` is safe by default — linear time; Python/Java/JS are not)
- Tools: `vuln-regex-detector` (JS), `recheck` (Java), Semgrep has ReDoS rules

---

## Level 3: Log Injection (Opus)

- User input logged without sanitization of newlines (`\n`, `\r`) — attacker can forge log entries
- Structured logging (JSON) mitigates but still check for:
  - Control characters in log values
  - Log entries that could be interpreted as commands by log aggregators
  - HTML/JS in logs viewed via web-based log viewers (XSS in log dashboards)
- Prevention: strip/encode `\r\n` in user input before logging, use structured logging with separate fields

---

## Level 3: Business Logic Abuse (Opus)

> Not detectable by scanners — requires manual review.

- **Negative values:** can user submit negative prices, quantities, durations?
- **Boundary bypass:** can user skip required steps (verification, payment, approval)?
- **Race conditions in business logic:** double-spend, duplicate submission, TOCTOU (time-of-check-to-time-of-use)
- **Privilege escalation via parameters:** can user change their role/permissions by modifying request body?
- **Abuse of bulk operations:** can user enumerate resources via bulk endpoints?
- **Referral/discount abuse:** can same code be applied multiple times, self-referral?
- **Rate limiting bypass via business logic:** rotating accounts, parallel sessions

---

## Level 3: Webhook Security (Opus)

> If the application receives or sends webhooks.

**Incoming webhooks:**
- Signature validation (HMAC) on every incoming webhook
- Replay protection: timestamp check + nonce/idempotency key
- Webhook URL not user-controlled (or validated against SSRF)
- Payload size limit
- Async processing (don't block on webhook handler)

**Outgoing webhooks:**
- TLS verification on target URL
- Timeout on delivery attempts
- Retry with exponential backoff
- Dead letter queue for failed deliveries
- Secrets not included in webhook payloads

---

## Level 3: File Upload Hardening (Opus)

> Extends Input Validation section with upload-specific checks.

- File size limit enforced **before** reading into memory (streaming validation)
- MIME type validated by magic bytes, not Content-Type header or extension
- Archive bombs: limit decompression ratio and total size for ZIP/GZIP uploads
- Path traversal via filename: sanitize filename from ZIP entries, strip `../`
- Polyglot files: file that is valid as multiple types (e.g., GIFAR = GIF + JAR)
- Image processing: use library with CVE track record check (ImageMagick policy.xml, libvips preferred)
- Virus scanning on uploaded files (ClamAV or cloud service)
- Store uploads outside webroot, serve via handler with auth check
- Generated filenames (UUID) — never use user-supplied filename for storage

---

## Level 3: IDOR / Access Control (Opus)

**BOLA (Broken Object Level Authorization):**
- Every endpoint validates that the authenticated user has access to the requested resource
- Object IDs in URLs/params checked against user's ownership/permissions (not just existence)
- No sequential/predictable IDs exposed without access check (use UUIDs or verify ownership)
- Bulk endpoints validate access for each item in the list

**BFLA (Broken Function Level Authorization):**
- Admin endpoints have explicit role/permission checks (not just authentication)
- Privilege escalation paths checked: can a regular user access admin resources by changing IDs?
- Horizontal access checked: can user A access user B's resources?
- HTTP method override: does `X-HTTP-Method-Override` bypass method-based access control?
- GraphQL/API: are mutations and sensitive queries restricted by role?

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
- Account enumeration prevention: login/register/reset responses don't reveal if account exists
- MFA bypass: if MFA enabled, ensure no fallback path that skips it
- Credential stuffing protection: CAPTCHA, device fingerprint, progressive delays

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
- **Log injection prevention:** user input sanitized before logging (strip `\r\n`, encode control characters). See also "Log Injection" section above
- **Audit log integrity:** audit logs protected from modification by the application itself (append-only, separate permissions)
- **Sensitive data in error context:** stack traces, request bodies, query parameters not logged if they may contain secrets

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
- Symlink resolution: `filepath.EvalSymlinks` (Go), `os.path.realpath` (Python) before prefix check
- Regex with user input: escape or validate (ReDoS risk — see ReDoS section)

---

## Level 3: Resilience Patterns (Opus)

- Retry with exponential backoff + jitter (not fixed interval)
- Idempotency on retry (same request doesn't cause duplicate side effects)
- Circuit breaker for unstable external dependencies
- Retry storm protection (not all instances retry at the same time)
- Fallback behavior defined (what happens when dependency is down?)
- Timeout cascade: external call timeout < handler timeout < server timeout
- Bulkhead: failure in one subsystem doesn't cascade to others
- Singleflight / dedup: concurrent identical requests coalesced (Go: `singleflight`, JS: `p-limit` / `p-queue`)
- Thundering herd prevention: cache stampede protection (lock + populate, or probabilistic early expiration)

---

## Level 3: Configuration Management (Opus)

- No magic numbers (timeouts, limits, thresholds in config, not code)
- Dev defaults not in production (debug flags, verbose logging, permissive CORS)
- Config validated on startup (fail fast if misconfigured)
- Hot reload without race conditions (if supported)
- Secrets in env vars / secret manager (not in config files committed to git)
- Config files have comments/documentation for non-obvious values
- Debug endpoints disabled in production
- **Config cliffs:** small config change causes catastrophic behavior shift (e.g., pool size 10→0 = unlimited, timeout 0 = no timeout vs infinite)
- **Feature flags:** cannot be manipulated via request parameters by end users

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
- **Single-maintainer risk:** critical dependencies with 1 maintainer and no org backing
- **Unmaintained dependencies:** no commits >2 years, no response to issues
- **High-risk features in deps:** FFI, deserialization, network access, native code — justify each
- **SBOM:** generated for releases (see SBOM section below)
- **Binary provenance:** release binaries have reproducible builds or signed checksums

> `skip_if` no CI/CD: check `.github/workflows/`, `Jenkinsfile`, `.gitlab-ci.yml`, `azure-pipelines.yml` first.

---

## Level 3: SBOM & Software Composition (Opus)

> Software Bill of Materials — increasingly required for enterprise and regulated industries.

- SBOM generated for release artifacts:
  - Go: `cyclonedx-gomod` or `syft`
  - Node.js: `syft` or `@cyclonedx/cyclonedx-npm`
  - Python: `cyclonedx-py` or `syft`
  - Rust: `cargo-cyclonedx`
  - Java: `cyclonedx-maven-plugin` / `cyclonedx-gradle-plugin`
  - C#: `CycloneDX` NuGet package
- Format: CycloneDX or SPDX (machine-readable)
- SBOM includes transitive dependencies
- SBOM stored alongside release artifacts
- CI pipeline generates SBOM automatically on release

---

## Level 3: Sharp Edges & Footgun Design (Opus)

> Source: Trail of Bits `sharp-edges` methodology. Review API design for footgun potential.

**How to execute:** For each public API/function/config in the codebase, ask: "What happens if a developer uses this wrong?" Grep for the patterns below and assess each match.

Evaluate against 3 developer archetypes: **malicious** (actively exploiting), **lazy** (skipping docs, using defaults), **confused** (misunderstanding semantics).

**Categories — grep for and assess:**
1. **Algorithm selection pitfalls** — API offers multiple algorithms/modes, wrong choice = vulnerability. Grep: `ECB`, `MD5`, `SHA1`, `DES`, `RC4` in non-test code
2. **Dangerous defaults** — default configuration is insecure, security requires opt-in. Grep: `default`, `Default`, constructor calls without security params
3. **Primitive vs semantic types** — accepting `string` where typed value needed. Grep: function signatures taking `string` for URLs, SQL, emails, file paths
4. **Config cliffs** — small config change causes catastrophic behavior shift. Review: config files, constructor defaults, zero-value behavior
5. **Silent failures** — operation appears to succeed but security property not enforced. Grep: `log` + `continue`/`return nil` in auth/validation code
6. **Stringly-typed security** — security decisions based on string matching. Grep: role/permission checks using string literals (`"admin"`, `"user"`)

---

## Level 3: Variant Analysis (Opus)

> Source: Trail of Bits `variant-analysis` methodology. Run AFTER code review — not standalone. When a vulnerability is found during review, search for similar patterns before closing the task.

After finding any CRITICAL or HIGH vulnerability:
1. **Understand** the root cause pattern (not just the instance)
2. **Exact match** — `grep -rn` codebase for identical pattern
3. **Identify abstraction points** — what makes this pattern generalizable? (same API misuse, same developer mistake, same library)
4. **Generalize** — broaden grep pattern to catch near-misses
5. **Triage** — assess each variant for exploitability

Output: append variants to the same finding with `[VARIANT]` prefix.

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
