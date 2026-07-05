# Universal Audit Checks

Language-agnostic checks. Apply to ANY project regardless of stack.
Code review tasks for DEEP agents.

> Model tiers: FAST=haiku, RESEARCH=sonnet, DEEP=opus (current defaults; see README "Model tiers" legend). Section tags below name the tier, not a fixed model.

> **Note:** universal.md applies from Level 2 onwards. Level 1 (Quick) uses only stack-specific files.

> **Note:** Stack-specific files (`go.md`, `python.md`, etc.) extend but don't repeat these. If overlap, stack file has language-specific details.

---

## Level 2: Git Hygiene (CLI, FAST)

> Requires Unix shell with `sed`/`awk`. Works in Git Bash on Windows for most commands.
> `skip_if: windows` for "Large files" — `awk` piping from `git cat-file` may fail in Git Bash. On Windows use the PowerShell twin below; it measures **tracked git-object** sizes (not the working tree), so gitignored local artifacts (a 10MB `.exe`, `dist/`) never false-positive.

```bash
# Large files >1MB (skip_if: windows — use PowerShell twin)
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | sed -n '/^blob/{s/blob //;p}' | awk '{if ($2 > 1048576) print $2, $3}' | sort -rn 2>&1

# Suspicious files (adjust exclusions per project)
git ls-files | grep -iE '\.(env|key|pem|p12|pfx|jks|sqlite|db)$' 2>&1
git ls-files '*.dll' '*.pdb' '*.exe' | grep -v 'tools/' 2>&1

# .gitignore completeness — confirm artifacts are *ignored*, not merely *not-yet-added*
for f in node_modules .env dist build .DS_Store Thumbs.db desktop.ini __pycache__ .venv venv target bin obj; do
  git ls-files --error-unmatch "$f" 2>/dev/null && echo "WARNING: $f tracked"
  git check-ignore -q "$f" || echo "NOTE: $f not ignored (add to .gitignore if it can appear locally)"
done
git status --porcelain --ignored 2>&1 | grep '^!!' || echo "no ignored artifacts present"
```

```powershell
# PowerShell twins (Windows / PowerShell-only agent — no Git Bash needed)
# Large files >1MB — TRACKED git-OBJECT sizes only (git ls-files -s + git cat-file -s); ignores working-tree/gitignored artifacts
$big = git ls-files -s | ForEach-Object {
  $f = $_ -split "`t", 2                  # "<mode> <oid> <stage>`t<path>"
  $oid = ($f[0] -split '\s+')[1]
  [PSCustomObject]@{ Size = [int](git cat-file -s $oid); Path = $f[1] }
} | Where-Object { $_.Size -gt 1048576 } | Sort-Object Size -Descending | Select-Object -First 20
if ($big) { $big | Format-Table -AutoSize } else { "no tracked blob >1MB" }

# Suspicious files (adjust exclusions per project)
git ls-files | Where-Object { $_ -match '\.(env|key|pem|p12|pfx|jks|sqlite|db)$' }
git ls-files '*.dll' '*.pdb' '*.exe' | Where-Object { $_ -notmatch '^tools/' }

# .gitignore completeness — confirm artifacts are *ignored*, not merely *not-yet-added*
foreach ($f in 'node_modules','.env','dist','build','.DS_Store','Thumbs.db','desktop.ini','__pycache__','.venv','venv','target','bin','obj') {
  git ls-files --error-unmatch $f 2>$null; if ($LASTEXITCODE -eq 0) { "WARNING: $f tracked" }
  git check-ignore -q $f; if ($LASTEXITCODE -ne 0) { "NOTE: $f not ignored (add to .gitignore if it can appear locally)" }
}
$ign = git status --porcelain --ignored | Where-Object { $_ -like '!!*' }
if ($ign) { $ign } else { "no ignored artifacts present" }
```

---

## Level 2: HTTP Security Headers (DEEP)

Verify responses include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY` or `SAMEORIGIN`
- `Referrer-Policy: strict-origin-when-cross-origin` (or stricter)
- `Content-Security-Policy` (at least `default-src 'self'`)
- `Strict-Transport-Security` (if HTTPS, `max-age>=31536000`)
- `Permissions-Policy` (restrict camera, microphone, geolocation)
- No `Server` header leaking version
- No `X-Powered-By` header

---

## Level 2: CSRF Protection (DEEP)

- State-changing endpoints (POST/PUT/DELETE) protected against CSRF
- If cookies for auth: CSRF token or SameSite=Strict/Lax cookie flag
- Double-submit cookie or synchronizer token pattern implemented
- Origin/Referer header validated server-side
- GET requests cause no side effects
- AJAX requests include CSRF header if required by framework

> See also: YAGNI Check — verify CSRF needed before including (e.g., token-based auth doesn't need CSRF).

---

## Level 2: Rate Limiting (DEEP)

- Rate limiting on all public-facing API endpoints (not just login)
- Per-user, per-IP, or per-API-key throttling
- 429 Too Many Requests with `Retry-After` header
- Login/auth endpoints have stricter limits (prevent brute force)
- Rate limits documented for API consumers
- No bypass via header manipulation (X-Forwarded-For spoofing)

> See also: YAGNI Check — verify rate limiting needed (e.g., internal service behind API gateway).

---

## Level 2: Insecure Defaults & Dangerous Configuration (DEEP)

> Source: Trail of Bits `insecure-defaults`. Only check prod-reachable code paths.

**Hardcoded secrets & fallback patterns — grep:**
- `getenv\(.*(SECRET|PASSWORD|TOKEN|KEY|PRIVATE|CREDENTIAL).*\)\s*(or|OR|\|\|)\s*["']` — fallback secret after env var lookup (only security-sensitive vars; PORT, HOST OK)
- `DEFAULT_SECRET|default_password|changeme|password123|s3cr3t|hunter2` — placeholder secrets
- `DEBUG\s*[:=]\s*(true|1|yes|on)` — debug mode enabled
- `AUTH.*[:=]\s*(false|0|no|off|disabled)` — auth disabled
- `VERIFY.*[:=]\s*(false|0|no|off)` — verification disabled

**Weak crypto defaults:**
- MD5/SHA1/DES/RC4/Blowfish in security contexts (auth, tokens, integrity)
- `math/rand` (Go) / `random` (Python) / `Math.random()` (JS) for security values — must use crypto-secure RNG
- Static/predictable IV/nonce in encryption
- ECB mode in block ciphers
- Key sizes below minimum (RSA <2048, AES <128, ECDSA <256)

**Permissive access controls:**
- `AllowAll` / `*` in CORS, firewall, permissions without justification
- Default admin accounts or well-known credentials
- Anonymous access to admin functions
- Default open permissions on file/directory creation

**Silent security failures:**
- Auth check that logs but doesn't block on failure
- Validation that warns but continues
- Rate limiter that counts but doesn't reject
- Certificate validation disabled with TODO to re-enable

---

## Level 2: Timing Attacks (DEEP)

- Secret comparison (HMAC, tokens, API keys, passwords) must use constant-time:
  - Go: `subtle.ConstantTimeCompare()`
  - Python: `hmac.compare_digest()`
  - Node.js: `crypto.timingSafeEqual()`
  - Java: `MessageDigest.isEqual(byte[], byte[])` — constant-time for equal-length only; length difference leaks timing
  - C#: `CryptographicOperations.FixedTimeEquals()`
  - Rust: `constant_time_eq` crate
- Login/auth: response time should not reveal whether username exists
- Rate-limited endpoints: constant-time rejection (don't short-circuit)

---

## Level 2: Mass Assignment / Over-Posting (DEEP)

- JSON/form deserialization: ensure user cannot set unauthorized fields
  - Go: only exported JSON fields user can modify; sensitive fields (`IsAdmin`, `Role`, `CreatedAt`) excluded from binding
  - Python/Django: `ModelForm.Meta.fields` whitelist (never `__all__`); DRF: `read_only_fields` for computed/admin
  - Java/Spring: `@JsonIgnoreProperties` or DTO pattern (don't bind to entity)
  - C#: `[Bind(Include="...")]` or separate ViewModel
  - JS/TS: validate/pick only allowed fields from request body
- Admin-only fields never bindable from user input
- Separate DTOs for create/update vs internal representation

---

## Level 2: False Positive Detection (All agents)

> **When to apply:** AFTER collecting raw findings. Filters reduce noise — do NOT skip checks.

### Auto-discard (Score = 0)

| Pattern | Why false positive |
|---------|--------------------------|
| Issue on non-modified line (Diff Mode) | Pre-existing, not introduced by recent changes |
| Pattern allowed in CLAUDE.md | Project convention, not bug |
| `// nolint`, `# noqa`, `@SuppressWarnings` with explanation | Intentional suppression with documented reason |
| Code in `vendor/`, `node_modules/`, `third_party/` | Not project's responsibility |
| Generated code (protobuf `.pb.go`, swagger, ORM migrations) | Overwritten on regeneration |
| Test code using anti-patterns intentionally | Testing error handling, edge cases |
| TODO/FIXME in test files | Test improvement notes, not production |

### Requires verification (Score = 25-50)

| Pattern | Verify by |
|---------|----------|
| "Potential SQL injection" from SAST | Trace data flow — input actually user-controlled? |
| "Unused variable/function" | Used via reflection, templates, dynamic dispatch? |
| "Hardcoded credential" | Test fixture, example, or actual secret? Check git history |
| "Insecure random" | Used for security (tokens) or non-security (IDs, shuffling)? |
| "Missing error handling" | Caller handles it? Fatal-on-error context? |
| "Deprecated function" | Migration path exists? Replacement in min version? |

### Stack-specific false positives

**Go:**
- `shadow: declaration of "err"` in nested scopes — often intentional
- `G104: Errors unhandled` on `defer file.Close()` — acceptable ONLY on read-only handles; on mutating/committing handles (writes, exec/`sudo` sessions, DB Commit/Flush) a Close error MUST be checked or logged (see go.md "Errors from defer Close/Flush/Commit logged")
- `SA1019: deprecated` on stdlib still supported 2+ versions

**Python:**
- `B101: assert` in test files — assert IS test mechanism
- `S101: hardcoded password` on test fixtures — intentional
- `C901: complexity` on CLI parsing — often unavoidable
- `vulture` unused-variable/param on framework callback signatures (aiogram/aiogram-dialog handlers `button`/`widget`/`start_data`, Django views, pydantic `@field_validator cls`) — required by the framework's dispatch contract, not dead — ignore

**JavaScript/TypeScript:**
- `no-explicit-any` in type assertion bridges — sometimes necessary
- `@ts-ignore` with explaining comment — documented workaround
- `console.log` in CLI tools — IS output mechanism
- `purgecss` reporting an entire stylesheet as dead on Tailwind 4 (`@tailwindcss/vite`)/CSS-in-JS/build-time-CSS plugins — utilities are generated at build, not present in source CSS, so purgecss can't see them — ignore; use the manual template-usage grep instead

**Rust:**
- `clippy::too_many_arguments` on FFI — must match C API
- `unsafe` in well-tested low-level code with safety comments — acceptable if justified
- `unwrap()` in tests/examples — standard practice

**Java:**
- `SpotBugs: NP_NULL_ON_SOME_PATH` from Optional.get() after isPresent() — false positive
- `Error Prone: MissingSummary` on private methods — style, not bug
- `PMD: LooseCoupling` on internal classes — intentional for non-public APIs
- `EI_EXPOSE_REP` on DTOs/records — ARE data carriers by design

**C#:**
- `CA1062: null check` on `[NotNull]` parameters — already validated
- `IDE0060: unused parameter` in interface implementations — must match signature
- `CS8618: Non-nullable field` in EF Core entities — set by ORM
- `CA1822: Mark as static` on methods needing virtual for testing/mocking

---

## Level 2: CLI Finding Verification Protocol (All agents)

Every CLI tool finding must pass 5 steps:

| Step | Question | Action if NO |
|------|----------|-------------|
| 1. **Technically correct?** | Real issue in THIS code, not generic warning? | Discard (score=0) |
| 2. **Not pre-existing?** | (`git blame`) | Full Audit: note age, keep severity. Diff: downgrade/discard |
| 3. **No justification?** | Documented reason? (comment, ADR, CLAUDE.md) | Discard if justified |
| 4. **Platform-relevant?** | Applies to project's target? | Discard if mismatch |
| 5. **Full context?** | Tool understands cross-file deps? (validation in middleware) | Verify manually |

### Verification examples

**"SQL injection in `query.go:45`"**
1. ✅ String concatenation with user input → correct
2. ✅ `git blame` recent → not pre-existing
3. ✅ No explaining comment → no justification
4. ✅ Web server → platform relevant
5. ❌ Input validated in `auth.go:20` → **FALSE POSITIVE** — discard

**"Hardcoded password in `config_test.go:12`"**
1. ❌ Test fixture → **FALSE POSITIVE** — discard

> **Important:** CLI tool not installed → report as BLOCKER per Anti-Rationalization Rules.

---

## Level 2: YAGNI Check for Recommendations (All agents)

Before recommending "add X", verify actually needed:

### Mandatory checks

| Recommendation | Verify first |
|---------------|------------------------|
| "Add rate limiting" | Has public endpoints? Behind API gateway? |
| "Add CSRF protection" | Uses cookies for auth? (Token-based doesn't need CSRF) |
| "Add input validation" | Already validated upstream? (middleware, framework, DB) |
| "Add error handling" | Caller handling it? Crash-is-correct? |
| "Add logging" | Structured logging elsewhere? |
| "Add tests" | Already tested via integration? |
| "Use X library instead" | Current approach working, maintained, understood? |
| "Add authentication" | Internal service behind service mesh? |

### YAGNI test

For each recommendation, grep codebase:
1. Feature actually needed anywhere?
2. Existing patterns solve this?
3. Would implementing require other changes?
4. Risk actually reachable in this project's context?

If unnecessary, **do not include** or downgrade to LOW: "Consider if applicable to your deployment."

---

## Audit Discipline: Anti-Rationalization Rules (All agents)

> Prevent agents from skipping checks or softening findings.

### Red Flags — think this? STOP and reconsider

| Agent thought | Reality | Correct action |
|--------------|---------|---------------|
| "File too simple to audit" | Simple files often contain secrets, default configs | Audit — simple ≠ safe |
| "Tool not installed, skip" | Missing tool = missing coverage | Report as **BLOCKER** |
| "Legacy code, no point" | Legacy = highest vuln density | Prioritize — legacy ≠ exempt |
| "Framework handles this" | Frameworks have defaults, escape hatches | Verify framework IS handling it |
| "Just style issue" | Can mask bugs (shadowed vars, confusing names) | Evaluate impact |
| "Only 1 user hits this" | 1 admin user = max impact | Assess by impact, not frequency |
| "They probably know" | Audit = fresh eyes | Report — assumption ≠ knowledge |
| "Hard to exploit" | Chained exploits exist | Report with realistic severity |
| "Already checked similar" | Each instance has unique context | Check individually |
| "Covered by other checks" | Overlapping checks catch different aspects | Verify coverage |
| "Deadline tight, skip deep" | Skipping = shipping vulns | Report constraint, don't skip |
| "Internal tool, security meh" | Internal tools get compromised too | Apply same standards |

### Enforcement

- Orchestrator reviews for rationalization signs (unusual SKIP counts, LOW-only, empty sections)
- 0 findings for complex codebase → re-review by different agent
- SKIP >30% → investigate why

### Proactive Self-Check (Before Completion)

Every agent MUST run:
- [ ] Every finding has file:line reference
- [ ] Every finding has evidence (tool output, code snippet, manual trace)
- [ ] Every PASS/SKIP justified (command output or documented reason)
- [ ] No hedging: "should", "probably", "seems to", "appears to", "likely"
- [ ] No performative: "Great!", "Perfect!", "All clear!", "Looks good!"
- [ ] Confidence score on every finding
- [ ] SKIP <30% of total checks
- [ ] 0 findings for >10-check section → re-review or flag

---

## Level 2: Cross-Stack Waste Detection (DEEP)

#### 1. Config-Dependency Coherence

**Automated (per-stack CLI):**
- Node.js: `npx --yes knip@6.14.2` (dead deps/imports/exports/files) + `npx --yes knip@6.14.2 --dependencies` (dep second opinion; depcheck archived)
- Go: `go mod tidy -diff`
- Rust: `cargo udeps` (nightly)
- Python: `pip-extra-reqs .` + `pip-missing-reqs .`
- Ruby: `bundle-audit`

**Manual verification** (tool false negatives):
- CSS frameworks: check Dead Asset Detection (template grep)
- Runtime helpers (tslib, core-js): verify tsconfig/babel requires them
- Type-only packages (@types/*): verify corresponding runtime package exists

For every manifest dependency:
- Referenced in source, config, OR build scripts? If only in lock file (transitive) — fine
- In manifest but not source/config → **HIGH: unused. Verify and remove.**

#### 2. Declared-vs-Used Asset Audit
Any asset type with declarations needing consumers:
- **CSS classes** in global stylesheets → used in templates
- **i18n keys** in locale files → used in source
- **Env vars** in .env.example → read in code
- **API routes** in router config → have handler AND client caller
- **DB migration columns** → referenced in models/queries
- **Feature flags** in config → checked in code
- **Config keys** in schema/defaults → read somewhere

Zero consumers = dead declaration = HIGH.

#### 3. Progress/Counter/Metric Data Flow
For every user-visible progress/counter/metric:
- Trace SOURCE (incremented) → SINK (displayed)
- Verify same variable/channel/event without silent resets
- Edge: does final value survive completion or get overwritten by defaults?
- **Always 0/default despite activity = CRITICAL: broken data flow**
- Patterns: event payload zero-default overwrites state; async wrong scope; field excluded from serialization

#### 4. Serialization Tag Audit
For structs/classes crossing boundaries (API, IPC, WebSocket, file I/O):
- Fields excluded from serialization (`json:"-"`, `@Transient`, `[JsonIgnore]`, etc.)
- Each excluded field: UI/consumer expecting it?
- **Excluded + active consumer = CRITICAL: data silently lost**

---

## Level 3: XSS Prevention (DEEP)

- All user input escaped before HTML rendering
- No raw HTML with user data (`v-html`, `dangerouslySetInnerHTML`, `innerHTML`, `Html.Raw()`, `|safe`, `@Html.Raw()`)
- CSP blocks inline scripts (`script-src` without `unsafe-inline`)
- URL params not reflected without sanitization
- Rich text editors sanitize output (DOMPurify or equivalent)
- SVG uploads sanitized (can contain scripts)
- JSON responses use `Content-Type: application/json`

---

## Level 3: SSRF Prevention (DEEP)

- User-supplied URLs: only `http://`/`https://` schemes
- Private IP ranges blocked:
  - IPv4: `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`
  - IPv6: `::1`, `fc00::/7`, `fe80::/10`
- DNS rebinding protection (resolve hostname, check IP before request)
- Redirect following limited/disabled for user URLs
- Cloud metadata blocked (169.254.169.254, metadata.google.internal)
- URL validation before saving to config/DB, not just before use

---

## Level 3: Deserialization Safety (DEEP)

Unsafe deserialization = RCE in many languages:

| Language | Dangerous | Safe alternative |
|----------|-----------|-----------------|
| Go | `encoding/gob` untrusted, `yaml.v2/v3` with `interface{}`, `encoding/json` into `interface{}` no depth limit | Typed structs, `KnownFields(true)` yaml.v3, limit JSON depth |
| Python | `pickle.loads()`, `yaml.load()`, `marshal.loads()` | `json`, `yaml.safe_load()`, `msgpack` |
| Java | `ObjectInputStream.readObject()`, `XMLDecoder` | JSON/Protobuf, `ObjectInputFilter` whitelist |
| C# | `BinaryFormatter` (banned), `NetDataContractSerializer` | `System.Text.Json`, `[JsonSerializable]` source gen |
| Rust | `bincode`/`serde` missing `#[serde(deny_unknown_fields)]` | Typed deserialization, strict schemas |
| JS/TS | `eval(JSON)`, custom deserializers unvalidated | `JSON.parse()` + schema (zod/joi) |

- No untrusted data deserialized into arbitrary types
- Input size limits (prevent memory exhaustion)
- Schema validation before/during deserialization
- No polymorphic deserialization without type whitelist

---

## Level 3: XXE Injection (DEEP)

If project processes XML:

- Parser disables external entities and DTD
- Go: `encoding/xml` safe by default. Real risk: third-party XML libs (`libxml2`, `etree`)
- Java: `DocumentBuilderFactory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)`
- Python: `defusedxml` instead of `xml.etree`, `lxml` with `resolve_entities=False`
- C#: `XmlReaderSettings.DtdProcessing = DtdProcessing.Prohibit`
- PHP 7.x: `libxml_disable_entity_loader(true)`; PHP 8.0+: safe by default
- Check: SOAP, RSS/Atom, SAML, SVG uploads, Office files (OOXML = XML in ZIP)

---

## Level 3: ReDoS (DEEP)

- Nested quantifiers on overlapping groups: `(a+)+`, `(a|a)+`, `(.*a){10}`
- User input as regex without sanitization (`regexp.QuoteMeta` Go, `re.escape()` Python)
- Regex on unbounded input without length limit
- Use RE2-compatible engines (Go `regexp` safe by default; Python/Java/JS not)
- Tools: `vuln-regex-detector` (JS), `recheck` (Java), Semgrep ReDoS rules

---

## Level 3: Log Injection (DEEP)

- User input logged without sanitizing `\n`/`\r` — attacker can forge log entries
- Structured logging (JSON) mitigates but check:
  - Control characters in log values
  - Entries interpretable as commands by aggregators
  - HTML/JS in logs via web viewers (XSS in dashboards)
- Prevention: strip/encode `\r\n` before logging, structured logging with separate fields

---

## Level 3: Business Logic Abuse (DEEP)

> Not scanner-detectable — manual review required.

- **Negative values:** negative prices, quantities, durations?
- **Boundary bypass:** skip required steps (verification, payment, approval)?
- **Race conditions:** double-spend, duplicate submission, TOCTOU
- **Privilege escalation via params:** change role/permissions in request body?
- **Bulk abuse:** enumerate resources via bulk endpoints?
- **Referral/discount abuse:** same code multiple times, self-referral?
- **Rate limit bypass:** rotating accounts, parallel sessions

---

## Level 3: Webhook Security (DEEP)

> If app receives/sends webhooks.

**Incoming:**
- HMAC signature validation on every webhook
- Replay protection: timestamp + nonce/idempotency key
- URL not user-controlled (or SSRF-validated)
- Payload size limit
- Async processing

**Outgoing:**
- TLS verification on target
- Delivery timeout
- Retry with exponential backoff
- Dead letter queue for failures
- No secrets in payloads

---

## Level 3: File Upload Hardening (DEEP)

- Size limit **before** reading into memory (streaming)
- MIME by magic bytes, not Content-Type/extension
- Archive bombs: limit decompression ratio and total size
- Path traversal: sanitize ZIP entry filenames, strip `../`
- Polyglot files (e.g., GIFAR = GIF + JAR)
- Image processing: CVE-aware library (ImageMagick policy.xml, libvips preferred)
- Virus scanning (ClamAV or cloud)
- Store outside webroot, serve via auth handler
- UUID filenames — never user-supplied for storage

---

## Level 3: IDOR / Access Control (DEEP)

**BOLA:**
- Every endpoint validates user access to requested resource
- Object IDs checked against ownership/permissions (not just existence)
- No sequential/predictable IDs without access check
- Bulk endpoints validate per item

**BFLA:**
- Admin endpoints have explicit role/permission checks (not just auth)
- Can regular user access admin resources by changing IDs?
- Can user A access user B's resources?
- `X-HTTP-Method-Override` bypass method-based access control?
- GraphQL: mutations/sensitive queries restricted by role?

---

## Level 3: Session Management (DEEP)

- Session ID regenerated after login (prevent fixation)
- Timeout: idle (30 min) + absolute (24h)
- Concurrent session limits (if applicable)
- Invalidated on logout (server-side)
- Cookie flags: `Secure`, `HttpOnly`, `SameSite=Strict`/`Lax`
- Session binding: IP/User-Agent for sensitive apps
- Storage: server-side or encrypted JWT

---

## Level 3: JWT / Auth Audit (DEEP)

- No `alg: none`, no RS256/HS256 confusion
- Access token <=15min (sensitive) to <=1h, refresh <=30d
- Refresh token rotation (old invalidated)
- Rate limit on login (prevent brute force)
- Secret/key not hardcoded/predictable
- Logout invalidates token (blacklist or short-lived + revocation)
- Token in httpOnly cookie (not localStorage for sensitive apps)
- CSRF protection if cookies for auth
- Password hashing: bcrypt/Argon2/scrypt (not MD5/SHA)
- Account enumeration prevention: responses don't reveal account existence
- MFA: no fallback path skipping it
- Credential stuffing: CAPTCHA, device fingerprint, progressive delays

---

## Level 3: API Contract Consistency (DEEP)

- Backend JSON field names match frontend types
- Nullable fields match frontend optional (`field?: type`)
- Enum values match frontend constants
- Frontend handles 4xx/5xx appropriately
- No dead endpoints (backend without frontend caller or vice versa)
- Request/response documented (OpenAPI or typed interfaces)
- Pagination: backend supports, frontend uses
- Error format consistent across endpoints

---

## Level 3: Logging & Observability (DEEP)

- Errors logged with context (operation, input — not bare `log(err)`)
- No PII in logs
- Structured logging (JSON/key-value)
- Health check endpoint exists
- Key ops logged: login/logout, CRUD, config/permission changes
- Correct log levels (ERROR/WARN/INFO/DEBUG)
- Log rotation configured
- Request/correlation ID for tracing
- Debug endpoints disabled in prod (`/debug/pprof`, `/actuator`, `/__debug__`)
- **Log injection:** sanitize user input (strip `\r\n`). See Log Injection section
- **Audit log integrity:** append-only, separate permissions
- **Sensitive error context:** stack traces/request bodies not logged if may contain secrets

---

## Level 3: Error Information Disclosure (DEEP)

- No stack traces in production responses
- No internal paths, hostnames, DB names in errors
- Generic messages to clients, details to logs
- Framework error pages disabled in production
- DB error details not exposed
- Verbose modes disabled (`DEBUG=False`, `ASPNETCORE_ENVIRONMENT=Production`)

---

## Level 3: Overengineering & Wheel Reinvention (DEEP)

**Reinventing wheels:** check `shared/`, `utils/`, `helpers/`, `common/`:
- Stdlib/dependency equivalent exists?
- Manual: retry, debounce, throttle, cron, UUID, HTTP router, pool, rate limiter, LRU cache, event emitter

**Overengineering:**
- Interface with 1 implementation (not for testing)
- Factory for 1 type
- Generics called with 1 type
- Pub-sub for <=2 subscribers
- Abstraction that just delegates
- Config for never-changing behavior

**Tech debt markers:**
- `TODO`/`HACK`/`FIXME`/`XXX` (count, assess)
- Lint suppression without explanation
- Copy-paste >10 lines (extract)
- Type bypass (`any`, `object`, `dynamic`, `interface{}`, `unsafe`)
- Magic numbers

---

## Level 3: Purpose-Fit & Scope-Coherence (DEEP)

> Requires the project's stated PURPOSE (from `args.scope.product_purpose`, else README / CLAUDE.md / package description). If purpose is unknown, SKIP check (1) and record an Audit Limitation; still run (2)-(3). HIGH false-positive class: cap severity at MEDIUM, default LOW, **NEVER CRITICAL**; route any "might be intentional" call to `suspected_unconfirmed` (needs human). Opinion is not a defect.

**1. Feature relevance** (anti-pattern: feature/scope creep, boat anchor). In scope here = working, REACHABLE code — NOT dead code (that is the waste-scanner's job).
- Every non-trivial feature / module / endpoint / screen traces to a stated product goal?
- A capability present that the product's purpose does not call for? (unrelated function bolted on)
- A capability kept after its reason disappeared (boat anchor)?
- Evidence: name the feature + why it does not map to purpose. LOW unless it carries security/maintenance cost.

**2. Tech/pattern adoption consistency** (anti-pattern: parallel implementations, no single source of truth).
- Each declared framework / library / styling system / state pattern used consistently across the codebase, or not at all?
- Two ways to do the same thing? (Tailwind on half the UI + hand-written CSS on the rest; two HTTP clients; two date libs; two state stores)
- Partially-adopted tooling: installed + configured but applied to a fraction of the surface it should cover.
- Evidence: cite the inconsistent sites (file:line for each side). LOW-MEDIUM.

**3. Redundant defenses & log noise** (anti-pattern: defensive overkill, lava flow).
- Error handling / guards for states the type system or earlier validation already makes impossible.
- Logging on unreachable error paths, or debug logging left after stabilization (noise, not signal).
- Dead defensive branches kept "just in case" with no reachable trigger.
- Exclude legitimate defense-in-depth (untrusted input, concurrency, external I/O) — those are NOT findings.
- Evidence: show the guarded condition is unreachable. LOW.

Report: File:line, Anti-pattern, Severity, Evidence, Why-not-needed, Fix. Default LOW; never inflate. When unsure whether intentional, emit to `suspected_unconfirmed`.

---

## Level 3: Documentation Freshness (DEEP)

- README matches actual build/deploy instructions
- API endpoints documented, up-to-date
- Env vars documented
- Architecture docs match reality
- CLAUDE.md rules match code patterns
- Changelog maintained (if used)
- Deprecated features marked

---

## Level 3: Documentation Concision (DEEP)

> Applies to all prose docs/notes/rules: README, CLAUDE.md, ADRs, `/docs`, design notes, AND this audit's own report output.

- Bullet-first: facts as bullets, not paragraphs. Prose only where flow is load-bearing.
- Compressed without loss: drop filler (articles, hedging, "in order to", "it should be noted"). Keep every value, name, path, command, URL exact.
- One fact per bullet — no run-on bullets bundling 3 ideas.
- No redundancy: each rule stated once; cross-reference instead of repeating across files.
- Tables/lists over narrative for enumerable data (configs, flags, severities).
- Findings: paragraph that could be N bullets -> flag "verbose: compress to bullets". Detail lost on compression -> flag "over-compressed: restore {value}".
- The audit report itself MUST obey this: bullet-style, compressed, values exact.

---

## Level 3: Input Validation Completeness (DEEP)

- Endpoint x validation matrix
- File upload: MIME by magic bytes
- Numeric: boundary checks (min, max, NaN, Infinity)
- String: length limits, format validation
- Server-side validation (not just frontend)
- Query/path params not raw to SQL/filesystem/shell
- JSON into explicit structs (not raw dict/map)
- Array inputs: size limits
- Path traversal: canonical path + prefix validation — `SafeJoinPath`/`ValidateURLScheme` are illustrative helper names — implement, or use stdlib `filepath.Clean` + a prefix/base-dir check; not provided. Note: operator-supplied local paths to the operator's own files are not a traversal vuln (trust boundary = the operator).
- Symlink: `filepath.EvalSymlinks` (Go), `os.path.realpath` (Python) before prefix check
- Regex with user input: escape/validate (see ReDoS)

---

## Level 3: Defense-in-Depth Validation (DEEP)

> Consumed by code-reviewer-security; applied by fixers on CRITICAL/HIGH data-flow fixes.

- Map every checkpoint a value crosses: entry (deserialize/parse), business logic, env/config guard, debug/log.
- Validate at EACH layer, not just entry — one check fixes the bug, every layer makes it structurally impossible.
- Fail closed: reject on missing/invalid at first layer; deeper layers assert invariants, not re-parse.
- Trust boundary explicit: mark where untrusted data becomes trusted; no downstream layer re-trusts raw input.

---

## Level 3: Resilience Patterns (DEEP)

- Retry: exponential backoff + jitter
- Idempotency on retry
- Circuit breaker for unstable deps
- Retry storm protection
- Fallback defined (dependency down?)
- Timeout cascade: external < handler < server
- Bulkhead: failure isolation
- Singleflight/dedup (Go: `singleflight`, JS: `p-limit`/`p-queue`)
- Thundering herd: cache stampede protection

---

## Level 3: Configuration Management (DEEP)

- No magic numbers (timeouts/limits in config)
- Dev defaults not in production
- Config validated on startup (fail fast)
- Hot reload without races
- Secrets in env vars/secret manager
- Config comments for non-obvious values
- Debug endpoints disabled in prod
- **Config cliffs:** small change causes catastrophe (pool 10→0 = unlimited)
- **Feature flags:** not manipulable via request params

---

## Level 3: State Management & Offline Resilience (DEEP)

> Especially for desktop, mobile, SPA.

- Connection loss → UI indicator
- Reconnect without duplication
- Reconnect syncs state
- Crash recovery (state persisted)
- Loading/error/empty states everywhere
- Optimistic updates rolled back on error
- Concurrent edits handled

---

## Level 3: Privacy / PII (DEEP)

- No PII in logs
- No PII in URL params
- Passwords: bcrypt/Argon2/scrypt (not MD5/SHA)
- Data minimization
- Deletion mechanism exists
- PII encrypted at rest
- GDPR considerations (if applicable)

---

## Level 3: Container & Image Security (DEEP)

> If Docker/Podman/container orchestration used.

**Dockerfile:**
- Base image pinned by digest (`FROM node:20@sha256:abc...`)
- Multi-stage: final image clean (no build tools, source, tests)
- No root in final stage — `USER nonroot`
- No secrets in build args/env
- `.dockerignore` excludes `.git`, `.env`, `node_modules`, `__pycache__`, tests
- `COPY` specific paths (not `COPY . .`)
- Health check defined

**Image scanning:**
- `trivy image` or equivalent in CI
- No CRITICAL/HIGH CVEs in base
- Reasonable image size

**Runtime:**
- Non-root user
- Read-only filesystem where possible
- No `--privileged` without justification
- Network policies restrict container communication
- Secrets via secret manager, not compose env vars
- Resource limits (CPU, memory)

**Orchestration (K8s/Compose):**
- No `hostPath` to sensitive dirs
- Pod security standards enforced
- Minimal service account permissions
- Network policies defined

---

## Level 3: CI/CD Pipeline Security (DEEP)

> If CI/CD config exists.

**Secrets:**
- None hardcoded in CI config
- Stored in platform secret manager
- Not logged in output
- Not in CLI arguments

**Actions/plugins:**
- GitHub Actions pinned by SHA (not `@v4`)
- Third-party actions reviewed (Trivy v0.69 incident)
- Self-hosted runners isolated
- Minimal `permissions:` scope

**Branch protection:**
- PR review required for main/release
- Status checks must pass
- Force-push disabled
- Signed commits (if applicable)

**Build integrity:**
- Artifacts have checksums/signatures
- Reproducible builds where possible
- No code execution from PR content (`pull_request_target` + PR checkout)
- Cache keys include lock file hashes

---

## Level 3: Supply Chain (DEEP)

- Lock files committed
- No `latest`/`*`/unbounded versions
- Repo binaries have provenance docs
- CI actions pinned by SHA
- Deps from trusted registries
- Minimal dep count (each justified)
- Transitive deps checked for vulns
- No dependency confusion with public registries
- **Single-maintainer risk:** critical deps, 1 maintainer, no org
- **Unmaintained:** no commits >2y, no issue response
- **High-risk dep features:** FFI, deserialization, network, native — justify
- **SBOM:** generated for releases
- **Binary provenance:** reproducible builds or signed checksums
- **License compliance:** scan deps for incompatible/copyleft licenses (GPL/AGPL) — Node: `npx --yes license-checker-evergreen@6.3.1 --failOn "GPL-2.0;GPL-3.0;LGPL-2.1;LGPL-3.0;AGPL-3.0"`; Go: `go install github.com/google/go-licenses/v2@v2.0.1`

> `skip_if` no CI/CD: check `.github/workflows/`, `Jenkinsfile`, `.gitlab-ci.yml`, `azure-pipelines.yml` first.

---

## Level 3: SBOM & Software Composition (DEEP)

> Increasingly required for enterprise/regulated.

- SBOM for releases:
  - Go: `cyclonedx-gomod`/`syft`
  - Node.js: `syft`/`@cyclonedx/cyclonedx-npm`
  - Python: `cyclonedx-py`/`syft`
  - Rust: `cargo-cyclonedx`
  - Java: `cyclonedx-maven-plugin`/`cyclonedx-gradle-plugin`
  - C#: `CycloneDX` NuGet
- Format: CycloneDX or SPDX
- Includes transitive deps
- Stored alongside releases
- CI generates automatically

---

## Level 3: Cryptographic Key Management (DEEP)

- **Storage:** env vars, secret manager, HSM — never source/committed config
- **Rotation:** mechanism + schedule (compromise, departure, annually)
- **Derivation:** PBKDF2-HMAC-SHA256 ≥600k iter, PBKDF2-HMAC-SHA1 ≥1.3M, bcrypt cost ≥13 (new)/≥12 (legacy), Argon2id
- **Asymmetric:** RSA ≥2048, ECDSA ≥P-256, Ed25519 preferred
- **Symmetric:** AES-128 min, AES-256 preferred. Crypto-secure RNG
- **TLS:** 1.2 min, 1.3 preferred. No SSLv3/TLS 1.0/1.1
- **Certs:** automated renewal (ACME), no expired in prod
- **Separation:** different keys for signing/encryption/auth
- **Backup:** encrypted, tested restoration

---

## Level 3: Concurrency Safety (DEEP)

> Language-agnostic. Stack files have language-specific details.

**Data races:**
- Shared mutable state: mutex/lock or immutable
- No concurrent read/write to maps/collections without sync
- Atomics for simple counters/flags

**Deadlocks:**
- Consistent lock ordering
- No locks held during external calls/I/O
- Lock acquisition timeout where possible

**Resource lifecycle:**
- Clear ownership and shutdown for goroutines/threads/tasks
- No fire-and-forget that leaks on error
- Context/cancellation propagated
- Bounded worker pools

**Patterns:**
- Producer-consumer: bounded queue
- Fan-out/fan-in: error propagation to coordinator
- Singleton: thread-safe init (sync.Once, etc.)
- Shutdown: graceful drain before exit

---

## Level 3: Sharp Edges & Footgun Design (DEEP)

> Trail of Bits `sharp-edges`. Review API design for footgun potential.

For each public API/function/config: "What if developer uses this wrong?"

Evaluate against: **malicious**, **lazy** (skipping docs), **confused** (misunderstanding semantics).

**Categories — grep and assess:**
1. **Algorithm pitfalls** — wrong choice = vulnerability. Grep: `ECB`, `MD5`, `SHA1`, `DES`, `RC4` non-test
2. **Dangerous defaults** — insecure by default. Grep: constructors without security params
3. **Primitive vs semantic types** — `string` where typed value needed (URLs, SQL, emails, paths)
4. **Config cliffs** — small change → catastrophe. Review defaults, zero-values
5. **Silent failures** — appears to succeed, security not enforced. Grep: `log` + `continue`/`return nil` in auth
6. **Stringly-typed security** — string matching for roles (`"admin"`, `"user"`)

---

## Level 3: Root Cause Analysis (DEEP)

> For CRITICAL/HIGH: beyond "what's wrong" to "why."

### 4-Phase Protocol

**Phase 1: Investigation**
1. Read vulnerability in full context (20+ lines)
2. Trace data flow: input source → destination
3. Git history: when introduced? Regression?

**Phase 2: Pattern Analysis**
1. Find working examples of same pattern in codebase
2. Compare broken vs working
3. Root cause category:
   - **Missing validation**
   - **Wrong abstraction** — API makes misuse easy
   - **Config drift** — dev/prod divergence
   - **Incomplete migration**
   - **Knowledge gap**

**Phase 3: Impact**
1. One-off or systemic?
2. Code paths affected? (→ Variant Analysis)
3. Blast radius?

**Phase 4: Recommendation**
1. Fix this instance
2. Prevent future (linter, checklist, architecture)
3. Detect existing (→ Variant Analysis patterns)

### STOP Rule

**3 failed hypotheses → STOP, escalate.**
1. First fails: refine
2. Second fails: question assumptions, try different layer
3. Third fails: **STOP.** Report what investigated, ruled out, remaining hypotheses, next step

Systematic "unknown" > wrong root cause.

### Output format

```
Root Cause: [category]
Introduced: [SHA or "original"]
Pattern: [systemic / isolated]
Fix: [this instance]
Prevention: [recurrence prevention]
Variants: [grep pattern]
```

---

## Level 3: Variant Analysis (DEEP)

> Trail of Bits `variant-analysis`. Run AFTER review. When vulnerability found, search similar patterns.

After CRITICAL/HIGH:
1. **Understand** root cause pattern (see Root Cause Analysis)
2. **Exact match** — `grep -rn` for identical pattern
3. **Abstraction points** — what's generalizable? (API misuse, library)
4. **Generalize** — broaden grep for near-misses
5. **Triage** exploitability

Output: `[VARIANT]` prefix on same finding.

---

## Level 3: Functional UI/UX Testing (DEEP)

> #1 complaint: audits miss ~70% broken UI. Applies to any web UI project.
> See `frontend.md → Functional UI Testing (Playwright DOM mode)` for details.
> **Static analysis by default.** Dev server only if user explicitly requested.

### Static (no server)

**Dead routes & orphans:**
```bash
grep -rn 'path:.*/' --include='*.ts' --include='*.tsx' --include='*.js' --include='*.vue' --include='*.svelte' 2>&1
grep -rn 'href="/' --include='*.html' --include='*.vue' --include='*.tsx' --include='*.jsx' --include='*.svelte' 2>&1
```

- Every route has component file
- Every `<a href="/...">` matches defined route
- No orphan pages
- Route guards reference existing auth
- Dynamic params have invalid-value fallback

**Buttons & handlers:**
```bash
grep -rn '<button' --include='*.vue' --include='*.tsx' --include='*.jsx' --include='*.svelte' | grep -v '@click\|onClick\|on:click\|disabled\|type="submit"' 2>&1
grep -rn 'href=["'"'"']#\?["'"'"']' --include='*.vue' --include='*.tsx' --include='*.html' --include='*.svelte' 2>&1
```

- Every `<button>` has handler, is submit, or disabled with reason
- No `href="#"`/`href=""` placeholders
- Handlers reference existing functions
- Conditional rendering reachable
- `disabled` has enable conditions

**Forms:** submit handler, validation, error messages, button not permanently disabled

**API wiring:** every call invoked from UI, handlers cover success/error/loading, no orphan functions, base URL configurable

### Runtime — DOM mode (needs dev server + user permission)

> `browser_snapshot` only — NO screenshots unless user requests visual regression.

**Pre-flight:** start server, wait ready (30s), navigate root, snapshot

**Navigation:** per route → navigate → snapshot → verify content, console errors, failed requests, internal links work

**Interactive (DOM diff):** snapshot baseline → click each element → compare. Unchanged = dead.
- Buttons → DOM change; Forms → fill/submit/verify feedback; Nav items → page changes; Toggles → state flips; Modals → open/close (appear/disappear); Dropdowns → select; Tabs → swap

**States:** empty (friendly message), loading (spinner), error (friendly), version/status (valid data)

**Responsive:** 3 breakpoints (375/768/1920px) → no cutoff/overlap

**Keyboard:** Tab order, Enter/Space activation, Escape dismissal

**i18n:** language switch → ALL strings change, report hardcoded

**Timers:** no error flooding, cleanup on navigation

**Console:** zero `console.error` on load, zero failed requests, no CORS, no mixed content

| Page/Route | Element | Expected | Actual | Severity | Console errors |
|------------|---------|----------|--------|----------|----------------|

---

## Level 3: Business Logic & Domain Correctness (DEEP)

> Deep review. Not detectable by SAST.

**Pipeline/Workflow:**
- State machine: all transitions valid, no stuck states
- Cancel/pause/resume: clean shutdown, no orphans
- Progress accuracy: counters match work
- File processing: groups/batches vs individual correct
- Error propagation to user

**Heuristics:**
- False positive/negative rates
- Dead parameters = dead detection
- Reasonable fallback
- Correct priority/ordering on multiple matches

**Edge Cases:**
- Empty/malformed/large input
- Permission errors
- Path edge cases (spaces, unicode, long, symlinks)
- Concurrent operations

**Tool Safety:**
- No shell interpolation, proper quoting
- Timeout enforcement
- Bounded output capture
- Cleanup (temp files, child processes)
- Partial failure handling

**Config Consistency:**
- Fields never read (dead config)
- Fields read but never set
- Startup validation?

Report: File:line, Category, Severity, Evidence, Root Cause, Fix.

---

## Level 3: Architecture Decision Review (DEEP)

Evaluate design decisions. Focus on trade-offs.

**Communication:** patterns (HTTP/RPC/events/polling/WS), appropriateness, silent failures, delivery guarantees, latency

**Data Flow:** state ownership, event typing/versioning, parsing (structured vs string), state object size

**External Deps:** download integrity, rate limits/caching, version check strategy, retry implementation

**Config:** dead fields, missing implementations, validation, migration

**Scalability:** memory bounded?, O(n²)?, parallelism used?, I/O streaming?

**Extensibility:** plugin contract, registration pattern, composability

| Decision | Chosen | Alternatives | Trade-offs | Rating | Recommendation |
|----------|--------|--------------|------------|--------|----------------|

- **Good:** appropriate, minimal friction
- **Acceptable:** works, has limitations
- **Needs Improvement:** causes real problems

---

## Level 2+: Stack Currency (Web search, RESEARCH)

Read manifests → extract versions → web search latest.

| Status | Definition |
|--------|-----------|
| **Current** | Latest or latest-1 minor |
| **Behind** | 2+ minor behind |
| **EOL** | No security patches |
| **Vulnerability** | Unpatched CVE |

| Dependency | Current | Latest | Status | CVEs | Notes |
|-----------|---------|--------|--------|------|-------|

Runtime version as first row.

**Thresholds:**
- **Current:** no action
- **Behind:** LOW, recommend update
- **EOL:** HIGH, migration plan
- **Vulnerability:** CRITICAL/HIGH per CVE, immediate patch
- `Go: govulncheck → update go.mod directive`
- `Python: pip-audit → update runtime`
- `Node.js: npm audit → update runtime`
- `Rust: cargo audit → rustup update`
- `Java: check against adoptium.net LTS`
- `.NET: check against dotnet.microsoft.com patches`
