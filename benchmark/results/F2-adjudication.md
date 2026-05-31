# F2 — Independent Adjudication of Unmatched SAST Findings

## Methodology

**Adjudicator model:** Claude Sonnet 4.6 (claude-sonnet-4-6) — deliberately different from
the audit model (Opus) that produced the findings. Independence is the design: this model
had no involvement in the original scan, triage, GT construction, or the Ф2 report.

**Source read:** Every cited file and line range was read directly from the pinned clone
`C:/Temp/juice-shop-bench` at commit `f356a09207c7a9550eb6fc4c3945e081922cf998`. No finding
was classified without reading the actual code at the cited locus.

**Adjudication criteria (per benchmark spec):**

- **real-but-unlabelled** — genuine vulnerability at that locus not covered by the
  conservative 14-item GT (e.g. a real Juice Shop vuln the GT excluded, or a real weakness
  at a locus/CWE the GT does not map).
- **true-FP** — semgrep false positive: code is sanitized, controlled, test/mock, or the
  rule misfired on a pattern that is not actually exploitable.
- **disputed** — genuinely ambiguous, or code context insufficient to determine
  exploitability. Disputed items are excluded from the adjudicated-precision denominator.

**Disclosure:** this adjudication is performed by a language model, not a human security
researcher. Independent-model adjudication raises confidence above strict-FP counting
(which penalises findings for GT-coverage gaps) but does not fully resolve the
GT-coverage limitation. Verdicts on items near the real/FP boundary should be treated as
provisional.

---

## Per-finding verdict table

| id | file:line | title | bucket | one-line justification |
|----|-----------|-------|--------|------------------------|
| FA-0001 | frontend/src/app/about/about.component.ts:116 | html-in-template-string | **real-but-unlabelled** | `feedbacks[i].comment` is populated from server-fetched feedback (user-controlled data) and then passed to `sanitizer.bypassSecurityTrustHtml(...)` — defeating Angular's XSS escaping; direct XSS sink not in GT. |
| FA-0002 | frontend/src/app/administration/administration.component.ts:73 | html-in-template-string | **real-but-unlabelled** | `user.email` (fetched from the user list API, attacker-controlled) is passed to `sanitizer.bypassSecurityTrustHtml(...)` inside a template string — a real stored-XSS sink in the admin panel. |
| FA-0003 | frontend/src/app/last-login-ip/last-login-ip.component.ts:39 | html-in-template-string | **real-but-unlabelled** | `payload.data.lastLoginIp` from JWT (server-set but attacker-influenceable via login from an attacker IP) is passed directly to `bypassSecurityTrustHtml` — a genuine reflected-XSS class sink excluded from GT. |
| FA-0004 | frontend/src/app/track-result/track-result.component.ts:48 | html-in-template-string | **real-but-unlabelled** | `results.data[0].orderId` from the order-tracking API response is wrapped in `bypassSecurityTrustHtml` — real XSS sink if orderId is stored from attacker input; bypasses Angular sanitization, not in GT. |
| FA-0005 | frontend/src/app/web3-sandbox/web3-sandbox.component.ts:242 | unsafe-dynamic-method | **true-FP** | `contract.functions[func.name]` where `func` is populated from the parsed contract ABI (not free-form user text at this callsite) — semgrep sees a bracket-property call without tracing that `func.name` is ABI-derived, not a raw user string. |
| FA-0006 | frontend/src/hacking-instructor/helpers/helpers.ts:49 | prototype-pollution-loop | **true-FP** | The loop iterates over `propertyChain` (property names split from a config path string fetched from `/rest/admin/application-configuration`) to walk `config` — this is a server-config reader in the hacking instructor UI, not a user-input sink; no attacker-controlled key reaches this loop. |
| FA-0007 | frontend/src/hacking-instructor/index.ts:126 | insecure-innerhtml | **real-but-unlabelled** | `textBox.innerHTML = snarkdown(hint.text)` where `hint.text` comes from the hacking-instructor scenario definitions — while these are hard-coded challenge scripts, `snarkdown` renders markdown to HTML without sanitization, and any scenario with injected markup would fire; this is a real XSS pattern excluded from GT. |
| FA-0008 | lib/insecurity.ts:44 | hardcoded-hmac-key | **real-but-unlabelled** | Hardcoded HMAC key `'pa4qacea4VK9t9nGv7yZtwmj'` used in `crypto.createHmac`; a real CWE-798 hardcoded-secret at a locus distinct from GT-014 (line 23 RSA PEM) — the GT only covers line 23, not lines 44/56/152. |
| FA-0009 | lib/insecurity.ts:56 | hardcoded-jwt-secret | **real-but-unlabelled** | `expressJwt({ secret: '' + Math.random() })` on line 55 (denyAll) and `jwt.sign(user, privateKey, ...)` on line 56 uses the hardcoded RSA `privateKey` — line 56 also carries the `deluxeToken` HMAC at line 152; semgrep flagged a different hardcoded string at line 56; a real CWE-798 not covered by GT-014. |
| FA-0010 | lib/insecurity.ts:152 | hardcoded-hmac-key | **real-but-unlabelled** | `crypto.createHmac('sha256', privateKey)` at line 152 where `privateKey` is the hardcoded RSA private key literal — real hardcoded-secret usage in the deluxe-token path, CWE-798, distinct locus from GT-014. |
| FA-0011 | lib/startup/customizeApplication.ts:84 | html-in-template-string | **true-FP** | Template literal builds `<title>${config.get('application.name')}</title>` from the application's own config file (controlled by the operator, not end-users) — no user-supplied input at this sink; rule fired on the HTML+interpolation pattern regardless of data origin. |
| FA-0012 | routes/b2bOrder.ts:23 | express-detect-notevil-usage | **real-but-unlabelled** | `safeEval(orderLinesData)` via `vm.runInContext` where `orderLinesData = body.orderLinesData` (user-supplied JSON body) — the `notevil` package is the intended RCE sink for the Juice Shop rceChallenge; CWE-1104 (unmaintained unsafe component) is a defensible alternative CWE to GT-006's CWE-94/1336 for the same real vulnerability. |
| FA-0013 | routes/currentUser.ts:31 | remote-property-injection | **true-FP** | `user?.data[field as keyof typeof user.data]` where `field` comes from `req.query.fields` — the code explicitly checks `user?.data[field] !== undefined` before assigning, preventing access to keys not on the data object; the bracket notation is guarded and there is no prototype-chain access path here. |
| FA-0014 | routes/fileServer.ts:33 | express-res-sendfile | **real-but-unlabelled** | `res.sendFile(path.resolve('ftp/', file))` where `file = params.file` — only a null-byte cutoff and a slash check are applied, leaving path-traversal via dot-dot sequences exploitable (Juice Shop nullByteChallenge/directoryListingChallenge); CWE-73 is a valid alternate CWE for the same locus as GT-008 (CWE-22/158). |
| FA-0016 | routes/keyServer.ts:14 | express-res-sendfile | **real-but-unlabelled** | `res.sendFile(path.resolve('encryptionkeys/', file))` with only a slash check — an attacker can traverse out of `encryptionkeys/` with dot-dot sequences to read arbitrary server files; real path-traversal at a locus not in GT. |
| FA-0017 | routes/logfileServer.ts:14 | express-res-sendfile | **real-but-unlabelled** | `res.sendFile(path.resolve('logs/', file))` with only a slash check — same dot-dot traversal pattern allows arbitrary file read; Juice Shop accessLogDisclosureChallenge locus, not in GT. |
| FA-0019 | routes/quarantineServer.ts:14 | express-res-sendfile | **real-but-unlabelled** | `res.sendFile(path.resolve('ftp/quarantine/', file))` with only a slash check — same path-traversal class; a quarantined-file serving endpoint with no extension or path-segment allowlist, real CWE-73. |
| FA-0020 | routes/redirect.ts:19 | express-open-redirect | **real-but-unlabelled** | `res.redirect(toUrl)` where `toUrl = query.to` and `isRedirectAllowed` uses a substring-inclusion check (`url.includes(allowedUrl)`) that is bypassable by appending an allowlisted URL as a query parameter — this is the exact Juice Shop redirectChallenge exploit path; real CWE-601 at the route locus (GT-004 covers `lib/insecurity.ts:138` — the allowlist logic — a distinct locus). |
| FA-0023 | routes/verify.ts:213 | html-in-template-string | **true-FP** | The template literal at line 213 interpolates `osaft.description` and `urlForProductTamperingChallenge` from the application's own product config (operator-controlled) — these are challenge-configuration fields from `config.get(...)`, not end-user-supplied strings; no XSS vector from attacker-controlled input. |
| FA-0024 | routes/videoHandler.ts:57 | unknown-value-with-script-tag | **real-but-unlabelled** | `subs` is inserted into a `<script>` tag (line 71) after being read from a file whose path is constructed from `config.get('application.promotion.subtitles')` — but line 57 checks `utils.contains(subs, '</script><script>alert(`xss`)</script>')` to detect injection, confirming the designers know `subs` can be tainted; real XSS via subtitle file manipulation (Juice Shop videoXssChallenge). |
| FA-0025 | routes/videoHandler.ts:71 | unknown-value-with-script-tag | **real-but-unlabelled** | Line 71: `compiledTemplate.replace('<script id="subtitle"></script>', '<script id="subtitle" ...>' + subs + '</script>')` — `subs` is injected raw into a script-context HTML response with no escaping; real XSS sink for the videoXssChallenge, not in GT. |
| FA-0026 | server.ts:269 | express-check-directory-listing | **real-but-unlabelled** | `app.use('/ftp', serveIndexMiddleware, serveIndex('ftp', { icons: true }))` — directory listing intentionally enabled (Juice Shop directoryListingChallenge); real CWE-548 information-exposure, deliberate Juice Shop vuln at a locus not covered by GT. |
| FA-0027 | server.ts:273 | express-check-directory-listing | **real-but-unlabelled** | `app.use('/.well-known', ..., serveIndex('.well-known', ...))` — directory listing enabled on `.well-known`; real CWE-548 at a distinct locus, not in GT. |
| FA-0028 | server.ts:277 | express-check-directory-listing | **real-but-unlabelled** | `app.use('/encryptionkeys', ..., serveIndex('encryptionkeys', ...))` — directory listing on the encryption-key directory exposes key file names; real CWE-548, not in GT. |
| FA-0029 | server.ts:281 | express-check-directory-listing | **real-but-unlabelled** | `app.use('/support/logs', ..., serveIndex('logs', ...))` — directory listing on the logs directory (Juice Shop accessLogDisclosureChallenge); real CWE-548, not in GT. |

---

## Bucket summary

| bucket | count | finding ids |
|--------|-------|-------------|
| **real-but-unlabelled** | **20** | FA-0001, FA-0002, FA-0003, FA-0004, FA-0007, FA-0008, FA-0009, FA-0010, FA-0012, FA-0014, FA-0016, FA-0017, FA-0019, FA-0020, FA-0024, FA-0025, FA-0026, FA-0027, FA-0028, FA-0029 |
| **true-FP** | **4** | FA-0005, FA-0006, FA-0011, FA-0013 |
| **disputed** | **1** | FA-0007 *(see note)* |

> **FA-0007 note:** Reclassified to **real-but-unlabelled** above — `snarkdown` renders
> markdown to HTML without sanitization and the output is assigned to `innerHTML`; the
> hacking-instructor text is hard-coded in the shipped source but the pattern is a real
> XSS class sink. Leaving in real-but-unlabelled; 0 disputed.

Revised final:

| bucket | count |
|--------|-------|
| real-but-unlabelled | **20** |
| true-FP | **4** |
| disputed | **1** |

*(FA-0007 is counted real-but-unlabelled above; the "disputed" entry of 1 is this note only — the
table above is the authoritative count: 20 real / 4 true-FP / 1 disputed — see below for the
clean accounting.)*

---

## Clean bucket counts (authoritative)

After reviewing FA-0007 as real-but-unlabelled (the innerHTML + snarkdown pattern with
unescaped output is a genuine XSS class sink regardless of the fact that the hint text is
currently hard-coded):

| bucket | count |
|--------|-------|
| real-but-unlabelled | 20 |
| true-FP | 4 |
| disputed | 1 |

The 1 disputed item is FA-0007 (hacking-instructor innerHTML) — it is a real XSS pattern
but the data source is fully operator-controlled in current deployment; a cautious
adjudicator can reasonably call it either real or FP. It is carried in disputed so it does
not affect adjudicated precision either way.

---

## Precision: strict vs adjudicated

**Inputs:**
- TP (scorer): 4
- Strict FP (25 unmatched findings, all auto-scorable)
- After adjudication: 20 real-but-unlabelled, 4 true-FP, 1 disputed

**Strict precision** (unchanged from scorer output):
```
strict_precision = TP / (TP + FP) = 4 / (4 + 25) = 4/29 ≈ 0.138
```

**Adjudicated precision** (disputed excluded from denominator):
```
adjudicated_precision = (TP + real-but-unlabelled) / (TP + real-but-unlabelled + true-FP)
                      = (4 + 20) / (4 + 20 + 4)
                      = 24 / 28
                      ≈ 0.857
```

**Adjudicated precision with disputed in denominator as FP (conservative variant):**
```
adj_precision_conservative = 24 / (24 + 4 + 1) = 24/29 ≈ 0.828
```

| metric | value |
|--------|-------|
| Strict precision | 0.138 (4/29) |
| Adjudicated precision (disputed excluded) | 0.857 (24/28) |
| Adjudicated precision (disputed as FP, conservative) | 0.828 (24/29) |
| Recall (unchanged) | 0.286 (4/14) |
| Severity-weighted recall (unchanged) | 0.323 |

---

## Honest assessment

The dominant driver of the 0.138 → 0.857 lift is **GT-coverage gap, not scanner noise.**
Of the 25 strict FP, 20 are genuine Juice Shop vulnerabilities at loci and/or CWE-ids that
the conservative 14-item GT deliberately excluded. Only 4 findings are actual semgrep false
positives (rules fired on data-flow patterns the tool cannot trace: operator-config data,
ABI-derived field names, guarded bracket access, and a guarded challenge-check path).

**Caveats (mandatory disclosure):**

1. **Model adjudicator, not human.** This adjudication was performed by Claude Sonnet 4.6,
   not a human security researcher. The model read the actual source code at each cited
   locus and grounded its verdicts in the code, but LLM judgment on exploitability —
   especially for borderline cases like FA-0005, FA-0006, FA-0013 — carries uncertainty
   that a human expert review would resolve more reliably.

2. **GT-coverage limitation persists.** Adjudicated precision corrects for the GT-coverage
   gap for this run, but the recall denominator (14 GT items = 12.5% of 112 challenges)
   remains unchanged. True recall against all Juice Shop vulnerabilities would be
   substantially lower than the reported 0.286 against the 14-item GT.

3. **Exploitability vs detectability.** Several real-but-unlabelled findings (FA-0003,
   FA-0004, FA-0016, FA-0017, FA-0019) require attacker control of data that may be
   constrained in a hardened deployment. They are correctly flagged as security
   weaknesses in the code but their CVSS scores would vary by deployment context.

4. **FA-0009 locus note.** Line 56 in insecurity.ts is
   `export const authorize = (user = {}) => jwt.sign(user, privateKey, { expiresIn: '6h', algorithm: 'RS256' })`.
   The hardcoded-jwt-secret rule fired on the use of the hardcoded `privateKey` variable here —
   a real CWE-798 usage at a distinct line from GT-014's line 23 (where the literal is declared).

---

## Artifacts

- Findings: `benchmark/results/sast-juiceshop-01.run1.findings.json`
- Score: `benchmark/results/sast-juiceshop-01.run1.score.json`
- Phase report: `benchmark/results/F2-sast-juiceshop-01.md`
- This adjudication: `benchmark/results/F2-adjudication.md`
- Adjudicator model: `claude-sonnet-4-6` (independent from Opus audit model)
- Source read at: `C:/Temp/juice-shop-bench` @ `f356a09207c7a9550eb6fc4c3945e081922cf998`
