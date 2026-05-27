# Universal Audit Checks

Language-agnostic checks. Apply to ANY project regardless of stack.
These are code review tasks for Opus agents.

> **Note:** universal.md applies from Level 2 onwards. Level 1 (Quick) uses only stack-specific files for fast CLI scans.

> **Note:** Stack-specific files (`go.md`, `python.md`, etc.) extend but do not repeat these checks. If a check here overlaps with a stack file, the stack file provides language-specific details.

---

## Level 2: Git Hygiene (CLI, haiku)

> Requires Unix shell with `sed` and `awk`. Works in Git Bash on Windows for most commands.
> `skip_if: windows` for the "Large files" command below — `awk` piping from `git cat-file` may fail in Git Bash due to line ending issues. On Windows, use `git lfs ls-files` or `git ls-files | xargs ls -la | sort -k5 -rn | head -20` as a simpler alternative.

```bash
# Large files >1MB (skip_if: windows — see note above)
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

> See also: YAGNI Check — verify CSRF protection is needed before including findings (e.g., token-based auth doesn't need CSRF).

---

## Level 2: Rate Limiting (Opus)

- Rate limiting on all public-facing API endpoints (not just login)
- Per-user, per-IP, or per-API-key throttling
- 429 Too Many Requests response with `Retry-After` header
- Login/auth endpoints have stricter limits (prevent brute force)
- Rate limits documented for API consumers
- No rate limit bypass via header manipulation (X-Forwarded-For spoofing)

> See also: YAGNI Check — verify rate limiting is needed before including findings (e.g., internal service behind API gateway).

---

## Level 2: Insecure Defaults & Dangerous Configuration (Opus)

> Source: Trail of Bits `insecure-defaults` methodology. Only check prod-reachable code paths.

**Hardcoded secrets & fallback patterns — grep for these regex:**
- `getenv\(.*(SECRET|PASSWORD|TOKEN|KEY|PRIVATE|CREDENTIAL).*\)\s*(or|OR|\|\|)\s*["']` — fallback secret after env var lookup (only for security-sensitive vars; non-secret fallbacks like PORT, HOST are OK)
- `DEFAULT_SECRET|default_password|changeme|password123|s3cr3t|hunter2` — well-known placeholder secrets
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
  - Java: `MessageDigest.isEqual(byte[], byte[])` — constant-time for equal-length arrays only; length difference leaks timing info
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

## Level 2: False Positive Detection (All agents)

> **When to apply:** AFTER running checks and collecting raw findings. These filters reduce noise in the final report — they do NOT mean "skip the check entirely."

Before including any finding in the report, apply these filters:

### Auto-discard (Score = 0)

| Pattern | Why it's a false positive |
|---------|--------------------------|
| Issue on non-modified line (Diff Mode) | Pre-existing, not introduced by recent changes |
| Pattern explicitly allowed in CLAUDE.md | Project convention, not a bug |
| `// nolint`, `# noqa`, `@SuppressWarnings` with explanation | Intentional suppression with documented reason |
| Code in `vendor/`, `node_modules/`, `third_party/` | Not project's responsibility |
| Generated code (protobuf `.pb.go`, swagger, ORM migrations) | Will be overwritten on regeneration |
| Test code intentionally using anti-patterns | Testing error handling, edge cases |
| TODO/FIXME in test files | Test improvement notes, not production issues |

### Requires verification before including (Score = 25-50)

| Pattern | Verify by |
|---------|----------|
| "Potential SQL injection" from SAST | Trace data flow — is input actually user-controlled? |
| "Unused variable/function" | Check if used via reflection, templates, or dynamic dispatch |
| "Hardcoded credential" | Is it a test fixture, example, or actual secret? Check git history |
| "Insecure random" | Is it used for security (tokens, keys) or non-security (IDs, shuffling)? |
| "Missing error handling" | Does the caller handle it? Is it a fatal-on-error context? |
| "Deprecated function" | Is there a migration path? Is the replacement available in project's min version? |

### Stack-specific false positives

**Go:**
- `shadow: declaration of "err"` in nested scopes — often intentional
- `G104: Errors unhandled` on `defer file.Close()` — acceptable in read-only contexts
- `SA1019: deprecated` on stdlib functions still supported for 2+ versions

**Python:**
- `B101: assert` in test files — assert IS the test mechanism
- `S101: hardcoded password` on test fixtures — intentional
- `C901: complexity` on CLI argument parsing — often unavoidable

**JavaScript/TypeScript:**
- `no-explicit-any` in type assertion bridges — sometimes necessary
- `@ts-ignore` with comment explaining why — documented workaround
- `console.log` in CLI tools — that IS the output mechanism

**Rust:**
- `clippy::too_many_arguments` on FFI bindings — must match C API
- `unsafe` in well-tested low-level code with safety comments — acceptable if justified
- `unwrap()` in tests and examples — standard practice

**Java:**
- `SpotBugs: NP_NULL_ON_SOME_PATH` from Optional.get() after isPresent() check — false positive
- `Error Prone: MissingSummary` on private methods — style, not bug
- `PMD: LooseCoupling` on internal implementation classes — coupling is intentional for non-public APIs
- `EI_EXPOSE_REP` (SpotBugs) on DTOs/records — these ARE data carriers by design

**C#:**
- `CA1062: null check` on parameters with `[NotNull]` attribute — already validated
- `IDE0060: unused parameter` in interface implementations — must match signature
- `CS8618: Non-nullable field` in EF Core entities — set by ORM, not constructor
- `CA1822: Mark members as static` on methods that need to be virtual for testing/mocking

---

## Level 2: CLI Finding Verification Protocol (All agents)

Every finding from CLI tools (gosec, bandit, semgrep, trivy, etc.) must pass 5 verification steps before inclusion:

| Step | Question | Action if NO |
|------|----------|-------------|
| 1. **Technically correct?** | Is this a real issue in THIS code, not a generic warning? | Discard (score=0) |
| 2. **Not pre-existing?** | Is this a pre-existing issue? (`git blame` check) | Full Audit: note age but keep at original severity. Diff Mode: downgrade to LOW or discard |
| 3. **No justification?** | Is there a documented reason for the current implementation? (comment, ADR, CLAUDE.md) | Discard if justified |
| 4. **Platform-relevant?** | Does this apply to the project's target platform/runtime? | Discard if platform mismatch |
| 5. **Full context?** | Does the tool understand cross-file dependencies? (e.g., validation in middleware, not endpoint) | Verify manually before including |

### Verification examples

**Tool says: "SQL injection in `query.go:45`"**
1. ✅ Uses string concatenation with user input → technically correct
2. ✅ `git blame` shows recent commit → not pre-existing
3. ✅ No comment explaining why → no justification
4. ✅ Web server, not CLI tool → platform relevant
5. ❌ Input is validated in middleware `auth.go:20` → **FALSE POSITIVE** — discard

**Tool says: "Hardcoded password in `config_test.go:12`"**
1. ❌ Test file with fixture data → **FALSE POSITIVE** — discard immediately

> **Important:** If a CLI tool is not installed, report as BLOCKER per Anti-Rationalization Rules — do not silently skip.

---

## Level 2: YAGNI Check for Recommendations (All agents)

Before recommending "add X" or "implement Y", verify it's actually needed:

### Mandatory checks

| Recommendation | Verify before suggesting |
|---------------|------------------------|
| "Add rate limiting" | Does the app have public endpoints? Is it behind an API gateway that already rate-limits? |
| "Add CSRF protection" | Does the app use cookies for auth? (Token-based auth doesn't need CSRF) |
| "Add input validation" | Is it already validated upstream? (middleware, framework, database constraints) |
| "Add error handling" | Is the caller handling it? Is this a crash-is-correct context? |
| "Add logging" | Is there structured logging elsewhere? Don't add inconsistent logging |
| "Add tests" | Is this code already tested via integration tests? Don't suggest unit tests for trivially tested code |
| "Use X library instead" | Is the current approach working, maintained, and understood by the team? |
| "Add authentication" | Is this an internal service behind a service mesh? |

### The YAGNI test

For each recommendation, grep the codebase:
1. Is the recommended feature actually used/needed anywhere?
2. Are there existing patterns that already solve this?
3. Would implementing this require changes to other parts of the codebase?
4. Is the risk being mitigated actually reachable in this project's context?

If any answer suggests the recommendation is unnecessary, **do not include it** or downgrade to LOW with a note: "Consider if applicable to your deployment context."

---

## Audit Discipline: Anti-Rationalization Rules (All agents)

> These rules prevent agents from skipping checks or softening findings.

### Red Flags — if you think this, STOP and reconsider

| Agent thought | Reality | Correct action |
|--------------|---------|---------------|
| "This file is too simple to audit" | Simple files often contain hardcoded secrets, default configs | Audit it — simple ≠ safe |
| "Tool not installed, skip this check" | Missing tool = missing coverage = risk | Report as **BLOCKER**, not SKIP |
| "This is legacy code, no point checking" | Legacy = highest vulnerability density | Prioritize it — legacy ≠ exempt |
| "The framework handles this" | Frameworks have defaults, configs, and escape hatches | Verify the framework IS handling it |
| "This is just a style issue" | Style issues can mask bugs (shadowed variables, confusing names) | Evaluate impact, don't dismiss |
| "Only 1 user hits this path" | 1 user with admin access = max impact | Assess by impact, not frequency |
| "They probably know about this" | Audit exists because they want fresh eyes | Report it — assumption ≠ knowledge |
| "This would be hard to exploit" | Attackers are creative, chained exploits exist | Report with realistic severity |
| "I already checked something similar" | Each instance can have unique context | Check each instance individually |
| "This is covered by other checks" | Overlapping checks catch different aspects | Don't skip — verify coverage |
| "The deadline is tight, skip deep checks" | Skipping checks = shipping vulnerabilities | Report time constraint, don't skip silently |
| "This is an internal tool, security doesn't matter" | Internal tools get compromised too (supply chain, lateral movement) | Apply same standards |

### Enforcement

- Orchestrator reviews agent outputs for signs of rationalization (unusual SKIP counts, LOW-only findings, empty sections)
- If an agent produces 0 findings for a complex codebase → flag for re-review by different agent
- SKIP count >30% of total checks → investigate why

### Proactive Self-Check (Before Claiming Completion)

Every agent MUST run this checklist before marking any task as completed:

- [ ] Every finding has file:line reference
- [ ] Every finding has evidence (tool output, code snippet, or manual trace)
- [ ] Every PASS/SKIP has justification (command output or documented reason)
- [ ] No hedging language: "should", "probably", "seems to", "appears to", "likely"
- [ ] No performative claims: "Great!", "Perfect!", "All clear!", "Looks good!"
- [ ] Confidence score assigned to every finding
- [ ] SKIP count is reasonable (<30% of total checks for this section)
- [ ] If 0 findings for a section with >10 checks — re-review or flag to orchestrator

This is proactive (agent self-checks) not just reactive (orchestrator reviews).

---

## Level 2: Cross-Stack Waste Detection (Opus)

These checks apply to ANY project regardless of language or framework.

#### 1. Config-Dependency Coherence

**Automated (per-stack CLI):**
- Node.js: `npx knip@latest` (primary) + `npx depcheck` (second opinion)
- Go: `go mod tidy -diff`
- Rust: `cargo udeps` (requires nightly)
- Python: `pip-extra-reqs .` + `pip-missing-reqs .`
- Ruby: `bundle-audit`

**Manual verification** (for tool false negatives):
For each dependency NOT flagged by tools but suspicious:
- CSS frameworks: check #1 in Dead Asset Detection (template grep)
- Runtime helpers (tslib, core-js): verify tsconfig/babel actually requires them
- Type-only packages (@types/*): verify corresponding runtime package exists

For every installed dependency/package/module:
- Is it referenced in source code, config files, OR build scripts?
- If only in lock file (transitive) — fine
- If in manifest (package.json, go.mod, Cargo.toml, requirements.txt, Gemfile) but not in source or config — **HIGH: unused dependency. Verify and remove.**

#### 2. Declared-vs-Used Asset Audit
Applies to ANY asset type with declarations that should have consumers:
- **CSS classes** defined in global stylesheets → must be used in templates
- **i18n/l10n keys** defined in locale files → must be used in source
- **Environment variables** declared in .env.example/.env.template → must be read in code
- **API routes** defined in router config → must have a handler AND a client caller
- **Database migrations** columns added → must be referenced in models/queries
- **Feature flags** defined in config → must be checked in code
- **Config keys** defined in schema/defaults → must be read somewhere

For each: zero consumers = dead declaration. Flag as HIGH.

#### 3. Progress/Counter/Metric Data Flow Verification
For every user-visible progress indicator, counter, or metric display:
- Trace the value from SOURCE (where incremented/calculated) to SINK (where displayed)
- Verify the data flows through the same variable/channel/event without silent resets
- Check edge cases: what happens on completion event? Does the final value survive or get overwritten by defaults?
- **Counter always shows 0/default despite activity = CRITICAL: broken data flow**
- Common patterns to check:
  - Event-driven: event payload has field with zero-value default → overwrites correct state
  - Async: counter updated in wrong scope/closure
  - Serialization: field excluded from JSON/serialization (e.g., `json:"-"`, `@JsonIgnore`, `[NonSerialized]`)

#### 4. Serialization Tag Audit
For structs/classes that cross system boundaries (API, IPC, WebSocket, file I/O):
- Check for fields excluded from serialization (`json:"-"`, `@Transient`, `[JsonIgnore]`, `transient`, `@Expose(false)`)
- For each excluded field: is there UI or consumer code that expects this field?
- **Excluded field + active consumer = CRITICAL: data silently lost in transit**

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
| Go | `encoding/gob` with untrusted input, `yaml.v2/v3` with `interface{}` target, `encoding/json` into `interface{}` without depth limit | Typed structs with `KnownFields(true)` in `yaml.v3`, limit JSON depth |
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
- Go: `encoding/xml` is safe by default — does not resolve external entities or process DTDs. `d.Strict = true` enforces syntax correctness only (not a security control). The real risk is third-party XML libraries (`libxml2` bindings, `etree`). Always verify against your Go version.
- Java: `DocumentBuilderFactory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)`
- Python: `defusedxml` library instead of `xml.etree`, `lxml` with `resolve_entities=False`
- C#: `XmlReaderSettings.DtdProcessing = DtdProcessing.Prohibit`
- PHP 7.x: `libxml_disable_entity_loader(true)`; PHP 8.0+: safe by default (function deprecated), use `LIBXML_NOENT` flag avoidance or `libxml_set_external_entity_loader(null)` if needed
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
- Token expiry: access <=15min (sensitive) to <=1h (low-risk), refresh <=30d
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

## Level 3: Container & Image Security (Opus)

> If the project uses Docker, Podman, or container orchestration.

**Dockerfile audit:**
- Base image pinned by digest, not just tag (`FROM node:20@sha256:abc...` not `FROM node:latest`)
- Multi-stage builds: final image has no build tools, source code, or test fixtures
- No `RUN` as root in final stage — use `USER nonroot` or equivalent
- No secrets in build args or environment variables in Dockerfile
- `.dockerignore` exists and excludes: `.git`, `.env`, `node_modules`, `__pycache__`, test fixtures
- `COPY` uses specific paths, not `COPY . .` (which may include secrets)
- Health check defined (`HEALTHCHECK` instruction or orchestrator probe)

**Image scanning:**
- `trivy image <image>` or equivalent scanner in CI
- No CRITICAL/HIGH CVEs in base image
- Image size reasonable (not shipping full OS when distroless/alpine suffices)

**Runtime security:**
- Containers run as non-root user
- Read-only filesystem where possible (`--read-only`)
- No privileged mode (`--privileged`) without justification
- Network policies restrict container-to-container communication
- Secrets injected via secret manager, not environment variables in compose files
- Resource limits set (CPU, memory) to prevent DoS

**Orchestration (if K8s/Docker Compose):**
- No `hostPath` mounts to sensitive directories
- Pod security standards enforced (restricted profile)
- Service accounts have minimal permissions
- Ingress/egress network policies defined

---

## Level 3: CI/CD Pipeline Security (Opus)

> If the project has CI/CD configuration files.

**Secret management:**
- No hardcoded secrets in CI config files (`.github/workflows/`, `Jenkinsfile`, `.gitlab-ci.yml`)
- Secrets stored in CI platform's secret manager (GitHub Secrets, GitLab CI Variables)
- Secrets not logged in CI output (mask sensitive values)
- Secrets not passed as command-line arguments (visible in process list)

**Action/plugin security:**
- GitHub Actions pinned by full SHA, not mutable tag (`uses: actions/checkout@abc123` not `@v4`)
- Third-party actions reviewed for supply chain risk (see Trivy v0.69.4/v0.69.5/v0.69.6 incident)
- Self-hosted runners: isolated, not shared across untrusted repos
- Minimal permissions: `permissions:` block restricts token scope

**Branch protection:**
- Main/release branches require PR review before merge
- Status checks (build, test, lint) required to pass
- Force-push disabled on protected branches
- Signed commits required (if applicable)

**Build integrity:**
- Build artifacts have checksums or signatures
- Reproducible builds where possible
- No arbitrary code execution from PR content (e.g., `pull_request_target` with checkout of PR head)
- Cache poisoning: CI cache keys include dependency lock file hashes

---

## Level 3: Supply Chain (Opus)

- Lock files committed (e.g., `package-lock.json`, `go.sum`, `Cargo.lock`, `poetry.lock`, `packages.lock.json`)
- No `latest` / `*` / unbounded versions in manifests
- Binaries in repo have provenance documentation
- CI actions pinned by SHA, not by mutable tag (see Trivy v0.69.4/v0.69.5/v0.69.6 incident)
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

## Level 3: Cryptographic Key Management (Opus)

- **Key storage:** Keys in environment variables, secret manager, or HSM — never in source code or config files committed to git
- **Key rotation:** mechanism exists, documented schedule (at minimum: on compromise, on employee departure, annually)
- **Key derivation:** PBKDF2-HMAC-SHA256 (≥600,000 iterations) or PBKDF2-HMAC-SHA1 (≥1,300,000 iterations), bcrypt (cost ≥13 new systems; ≥12 minimum legacy), Argon2id for password-derived keys
- **Asymmetric keys:** RSA ≥2048 bits, ECDSA ≥P-256, Ed25519 preferred for new implementations
- **Symmetric keys:** AES-128 minimum, AES-256 preferred. Generated via crypto-secure RNG
- **TLS configuration:** TLS 1.2 minimum, TLS 1.3 preferred. No SSLv3, TLS 1.0, TLS 1.1
- **Certificate management:** automated renewal (Let's Encrypt / ACME), no expired certs in production
- **Key separation:** different keys for different purposes (signing vs encryption vs auth)
- **Backup keys:** encrypted backup exists, tested restoration procedure

---

## Level 3: Concurrency Safety (Opus)

> Language-agnostic concurrency patterns. Stack files provide language-specific details.

**Data races:**
- Shared mutable state protected by mutex/lock or made immutable
- No concurrent reads and writes to maps/dicts/collections without synchronization
- Atomic operations used for simple counters/flags instead of full mutex

**Deadlocks:**
- Lock ordering: when acquiring multiple locks, always in consistent order
- No lock held while calling external services or performing I/O (risk of indefinite blocking)
- Timeout on lock acquisition where possible

**Resource lifecycle:**
- Goroutines/threads/tasks have clear ownership and shutdown mechanism
- No fire-and-forget goroutines/threads that leak on error
- Context/cancellation propagated through async call chains
- Worker pools have bounded size (prevent thread/goroutine explosion under load)

**Concurrency patterns:**
- Producer-consumer: bounded channel/queue to prevent memory exhaustion
- Fan-out/fan-in: proper error propagation from workers to coordinator
- Singleton initialization: thread-safe (sync.Once, std::once_flag, Lazy<T>, etc.)
- Shutdown: graceful drain of in-flight requests before process exit

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

## Level 3: Root Cause Analysis (Opus)

> For CRITICAL and HIGH findings, go beyond "what's wrong" to "why it happened."

### 4-Phase Root Cause Protocol

**Phase 1: Investigation**
1. Read the error/vulnerability in full context (not just the line — 20+ lines around it)
2. Trace the data flow: where does the input come from? Where does it go?
3. Check git history: when was this introduced? By what change? Was it a regression?

**Phase 2: Pattern Analysis**
1. Find working examples of the same pattern elsewhere in the codebase
2. Compare broken vs working: what's different?
3. Identify the root cause category:
   - **Missing validation** — input not checked
   - **Wrong abstraction** — API makes incorrect usage easy
   - **Configuration drift** — dev/prod divergence
   - **Incomplete migration** — partially updated pattern
   - **Knowledge gap** — developer didn't know about the risk

**Phase 3: Impact Assessment**
1. Is this a one-off mistake or systemic pattern?
2. How many code paths are affected? (→ feeds into Variant Analysis)
3. What's the blast radius if exploited?

**Phase 4: Recommendation**
1. Fix for this specific instance
2. Prevention for future instances (linter rule, code review checklist, architectural change)
3. Detection for similar existing issues (→ Variant Analysis grep patterns)

### Root Cause STOP Rule

**After 3 failed root cause hypotheses — STOP and escalate.**

1. First hypothesis fails: refine based on new data
2. Second hypothesis fails: step back, question assumptions, try different layer
3. Third hypothesis fails: **STOP.** Report to orchestrator:
   - What was investigated
   - What was ruled out
   - Remaining hypotheses ranked by likelihood
   - Recommended next step (different agent, user input, external expertise)

Do NOT continue guessing. Systematic analysis that concludes "unknown" is more valuable than a wrong root cause.

### Output format

```
Root Cause: [category from Phase 2]
Introduced: [commit SHA or "original code"]
Pattern: [systemic / isolated]
Fix: [specific fix for this instance]
Prevention: [systemic fix to prevent recurrence]
Variants: [grep pattern for Variant Analysis]
```

---

## Level 3: Variant Analysis (Opus)

> Source: Trail of Bits `variant-analysis` methodology. Run AFTER code review — not standalone. When a vulnerability is found during review, search for similar patterns before closing the task.

After finding any CRITICAL or HIGH vulnerability:
1. **Understand** the root cause pattern, not just the instance (see Root Cause Analysis section above)
2. **Exact match** — `grep -rn` codebase for identical pattern
3. **Identify abstraction points** — what makes this pattern generalizable? (same API misuse, same developer mistake, same library)
4. **Generalize** — broaden grep pattern to catch near-misses
5. **Triage** — assess each variant for exploitability

Output: append variants to the same finding with `[VARIANT]` prefix.

---

## Level 3: Functional UI/UX Testing (Opus)

> Addresses #1 user complaint: "audits find code issues but miss ~70% of broken UI — dead links, inactive buttons, non-working features."
> This section applies to ANY project with a web UI. For frontend-specific details, see `frontend.md → Functional UI Testing (Playwright)`.
> **Static analysis by default.** Start dev server ONLY if user explicitly requested runtime testing or project CLAUDE.md requires it. Otherwise — static analysis of routes, links, and handler wiring.

### Static analysis (no server required)

**Dead routes & orphan pages:**
```bash
# Find route definitions
grep -rn 'path:.*/' --include='*.ts' --include='*.tsx' --include='*.js' --include='*.vue' --include='*.svelte' 2>&1
# Find all internal link targets
grep -rn 'href="/' --include='*.html' --include='*.vue' --include='*.tsx' --include='*.jsx' --include='*.svelte' 2>&1
# Cross-reference: every href target should match a defined route
```

Check:
- Every route in router config has a corresponding component file
- Every `<a href="/...">` points to a defined route
- No orphan pages (component exists but no route points to it)
- Route guards/middleware reference existing auth functions
- Dynamic route params (`:id`, `[slug]`) have fallback for invalid values

**Button & handler wiring:**
```bash
# Buttons without click handlers (potential dead buttons)
grep -rn '<button' --include='*.vue' --include='*.tsx' --include='*.jsx' --include='*.svelte' | grep -v '@click\|onClick\|on:click\|disabled\|type="submit"' 2>&1
# Links with href="#" or href="" (placeholder links)
grep -rn 'href=["'"'"']#\?["'"'"']' --include='*.vue' --include='*.tsx' --include='*.html' --include='*.svelte' 2>&1
```

Check:
- Every `<button>` has a click handler, is a submit button, or is explicitly `disabled` with reason
- No `href="#"` or `href=""` placeholder links
- Event handlers reference existing functions (not typos)
- Conditional rendering (`v-if`, `{condition &&}`) conditions are reachable
- `disabled` attributes have matching enable conditions

**Form validation completeness:**
- Every `<form>` has submit handler
- Required fields have validation (client-side at minimum)
- Error messages defined for each validation rule
- Form submit button is not permanently disabled

**API integration wiring:**
- Every API call function is actually invoked from UI
- Response handlers cover success, error, and loading states
- No orphan API functions (defined but never called)
- API base URL is configurable (not hardcoded localhost)

### Runtime checks — DOM mode (requires dev server — ask user permission first)

> Only run if: user requested runtime testing, project has dev server, and Playwright MCP is available.
>
> **IMPORTANT: DOM snapshots only — NO screenshots.** Use `browser_snapshot` (returns accessibility tree as text — fast, zero vision tokens) instead of `browser_take_screenshot` (returns image — slow, expensive). Screenshots only if user explicitly requests visual regression.

**Navigation audit:**
Per route from router config:
1. `browser_navigate(url)` → `browser_snapshot` → verify page has content (not blank/error)
2. `browser_console_messages` → collect JS errors
3. `browser_network_requests` → collect failed requests (4xx, 5xx)
4. For each internal link in snapshot → `browser_click` → `browser_snapshot` → verify navigation worked

**Interactive elements (DOM diff method):**
Per page: take `browser_snapshot` (= baseline), then for each interactive element:
1. `browser_click` element → `browser_snapshot` → compare with baseline
2. If DOM unchanged after click → **dead element**, report it
3. If DOM changed → element works, record what changed

Specific checks:
- Buttons: click → DOM must change (new content, modal, state change)
- Forms: `browser_fill_form` → submit → verify success/validation in DOM
- Modals: click trigger → verify modal appears in snapshot → close → verify gone
- Dropdowns: `browser_select_option` → verify selection in snapshot
- Tabs: click → verify content swap in snapshot

**Console health:**
- Zero `console.error` on page load per route (excluding known third-party)
- Zero failed network requests on page load
- No CORS errors
- No mixed content warnings

**Reporting format per broken element:**

| Page/Route | Element (snapshot ref) | Expected | Actual | Console errors |
|------------|----------------------|----------|--------|----------------|


---

## Level 3: Business Logic & Domain Correctness (Opus)

> Source: Deep pipeline/workflow review. Not detectable by static analysis or SAST tools.

**Scope:** Review ALL domain-specific logic, not just security. Focus on correctness.

**Pipeline/Workflow Logic:**
- State machine correctness: all transitions valid, no stuck states
- Cancellation/pause/resume semantics: clean shutdown, no orphaned goroutines
- Progress tracking accuracy: counters match actual work done
- File processing: correct handling of groups/batches vs individual items
- Error propagation: errors from sub-operations surface correctly to user

**Heuristic & Classification Logic:**
- Detection heuristics: false positive rate, false negative rate
- Feature extraction: are all relevant signals actually used? (dead parameters = dead detection)
- Fallback behavior: when primary detection fails, is fallback reasonable?
- Priority/ordering: when multiple matches, is the right one selected?

**Edge Cases:**
- Empty input (zero files, empty directories, zero-byte files)
- Malformed input (corrupted files, wrong extensions, unexpected formats)
- Large input (memory-bounded? streaming? or load-all-at-once?)
- Permission errors (read-only dirs, locked files, Windows ACLs)
- Path edge cases (spaces, unicode, very long paths, dotfiles, symlinks)
- Concurrent operations (parallel requests, race conditions, TOCTOU)

**Tool Invocation Safety:**
- External process construction: no shell interpolation, proper quoting
- Timeout enforcement: subprocesses bounded by context/timeout
- Output capture: bounded memory (streaming vs ReadAll)
- Cleanup: temp files, child processes terminated on cancel
- Partial results: what happens when tool fails mid-operation?

**Config Consistency:**
- Config fields that exist but are never read (dead config = misleading)
- Config fields that are read but never set (missing defaults)
- Config validated on startup? (fail-fast vs silent bad config)

**Report format:** File:line, Category (logic bug / edge case / robustness / heuristic), Severity, Evidence, Root Cause, Fix.

---

## Level 3: UI/UX Functional Audit — Playwright DOM Mode (Opus)

> Requires: running dev server. If project has no dev server, skip with note.
> **IMPORTANT: DOM mode only — NO screenshots.** Use `browser_snapshot` (accessibility tree, text) instead of `browser_take_screenshot` (image, expensive).

Extends the existing Functional UI Testing section with structured methodology.

**Pre-flight:**
1. Start dev server (detect from package.json scripts or project CLAUDE.md)
2. Wait for server readiness (curl loop, max 30s)
3. Navigate to root URL, take initial snapshot

**Per-page audit protocol:**
1. `browser_navigate` → `browser_snapshot` → verify content renders (not blank/error)
2. `browser_console_messages` → collect JS errors (fail on any console.error on load)
3. `browser_network_requests` → collect failed requests (4xx, 5xx)

**Interactive element testing:**
For each interactive element in DOM snapshot:
- Buttons: click → snapshot → verify DOM changed. Unchanged = dead button.
- Forms: fill → submit → verify success/validation feedback
- Navigation: click each nav item → verify page content changes
- Toggles/switches: click → verify aria-checked/state flipped
- Modals: trigger → verify appears → close → verify gone

**State verification:**
- Empty state: navigate with no data → verify user-friendly message (not blank)
- Loading state: snapshot during async operation → verify spinner/skeleton
- Error state: trigger error condition → verify user-friendly error (not raw exception)
- Version/status displays: verify show valid data (not raw HTML, not undefined)

**Responsive check:**
- `browser_resize` to 3 breakpoints: mobile (375px), tablet (768px), desktop (1920px)
- Per breakpoint: snapshot → verify no content cut off, no overlapping elements

**Keyboard accessibility:**
- Tab through all interactive elements → verify focus order makes sense
- Enter/Space on focused buttons → verify activation
- Escape on modals → verify dismissal

**i18n consistency (if multilingual):**
- Switch language → snapshot → verify ALL visible strings changed
- Report any hardcoded strings that don't change with locale

**Poll/timer behavior:**
- Check for console error flooding (repeated errors without backoff)
- Verify cleanup on page navigation (no orphaned timers/intervals)

**Report format:**
| Page/Route | Element | Expected | Actual | Severity | Console errors |
|------------|---------|----------|--------|----------|----------------|

---

## Level 3: Architecture Decision Review (Opus)

Evaluate design decisions, not just code quality. Focus on trade-offs and alternatives.

**Communication Patterns:**
- How do components communicate? (HTTP, RPC, events, polling, WebSocket)
- Is the chosen pattern appropriate for the use case?
- Silent failures: messages dropped without feedback? Queue overflow handling?
- Event delivery guarantees: at-least-once? at-most-once? exactly-once?
- Latency: is polling acceptable or should push be used?

**Data Flow:**
- State ownership: who owns each piece of state? Clear boundaries?
- Event shape stability: are event payloads typed/versioned?
- Parsing: structured fields or regex/string parsing of messages?
- State object size: flat vs nested? Maintainable at current field count?

**External Dependencies:**
- Download integrity: checksums/signatures verified?
- API rate limits: handled? Cached? Graceful degradation?
- Version checking: sequential or parallel? Blocking or background?
- Retry logic: exists in config? Actually implemented?

**Configuration:**
- Dead config fields: defined but never read?
- Missing implementations: config promises features that don't work?
- Validation: fail-fast on invalid config or silent defaults?
- Migration: what happens when schema changes?

**Scalability:**
- Memory: bounded or load-all-at-once?
- CPU: O(n²) patterns? Unnecessary re-scans?
- Concurrency: sequential where parallel would help? Config exists but unused?
- I/O: streaming or buffered? Appropriate for expected data sizes?

**Extensibility:**
- Plugin/extension interface: clean contract? Boilerplate duplication?
- Registration pattern: how to add new X? (X = recipe, tool, handler, etc.)
- Composition: can features be combined? Or monolithic?

**Report format per decision:**
| Decision | What was chosen | Alternatives | Trade-offs | Rating (Good/Acceptable/Needs Improvement) | Recommendation |
|----------|----------------|--------------|------------|---------------------------------------------|----------------|

**Rating criteria:**
- **Good:** Appropriate for the use case, well-implemented, minimal friction for changes
- **Acceptable:** Works but has known limitations or tech debt
- **Needs Improvement:** Causes real problems (bugs, UX issues, maintenance burden)
---

## Level 2+: Stack Currency (Web search, Sonnet)

Read manifest files -> extract runtime/framework/library versions -> web search latest for each.

Rate each as:

| Status | Definition |
|--------|-----------|
| **Current** | Latest or latest-1 minor |
| **Behind** | 2+ minor versions behind |
| **EOL** | End of life / no security patches |
| **Vulnerability** | Known unpatched CVE |

Output table:

| Dependency | Current | Latest | Status | CVEs | Notes |
|-----------|---------|--------|--------|------|-------|

Include runtime version (Go 1.x, Node.js x, Python 3.x, etc.) as first row.

**Action thresholds:**
- **Current:** no action needed
- **Behind:** create LOW finding, recommend update plan
- **EOL:** create HIGH finding, migration plan needed
- **Vulnerability:** create CRITICAL/HIGH finding based on CVE severity, immediate patch required
- `Go: check govulncheck stdlib findings — if stdlib vuln reported, update go directive in go.mod to fixed version`
- `Python: check python --version against python.org; if pip-audit reports CPython vuln, update runtime`
- `Node.js: check node --version against nodejs.org; if npm audit reports core vuln, update runtime`
- `Rust: check rustc --version; run rustup update if cargo audit reports stdlib vuln`
- `Java: check java --version against adoptium.net LTS releases`
- `.NET: check dotnet --version against dotnet.microsoft.com patch releases`
