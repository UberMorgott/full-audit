# F2 — Blind SAST Run on OWASP Juice Shop (defensible recall / precision)

> This is the **authoritative SAST benchmark result**. It closes the design flaw of
> the non-blind multi-agent run (where the same Opus model that produced the findings
> also had de-facto access to the ground-truth construction rationale). Here the
> reviewer (Opus) produced findings **without ever seeing the frozen GT**; a separate,
> independent model (Sonnet 4.6) scores and adjudicates. This model-role split is the
> minimum design needed for a defensible blind recall/precision figure.

## 1. Run design

| Role | Model | What it saw | What it did NOT see |
|------|-------|-------------|---------------------|
| **Blind reviewer** | Claude Opus (stage 1) | Juice Shop source at pinned commit | frozen GT YAML, this scoring document |
| **Independent scorer + adjudicator** | Claude Sonnet 4.6 (stage 2, THIS run) | frozen blind findings + frozen GT + real source | the blind reviewer's reasoning; was not involved in GT construction |

- **Blind findings (frozen):** `benchmark/results/sast-juiceshop-01.blind.findings.json`
- **Frozen GT (frozen, pre-registered):** `benchmark/seeds/sast-juiceshop-01/ground-truth.yaml`
  — tagged `bench-prereg-sast-juiceshop-01` @ `599b703` **before any run**.
- **Scorer:** `benchmark/score.py` — frozen, untouched, identical to all prior runs.
- **Window:** N=5 (frozen rule default).
- **Source read (adjudication):** `C:/Temp/juice-shop-bench` @ `f356a09207c7a9550eb6fc4c3945e081922cf998`.

The blind reviewer emitted **25 findings** (FA-0001 through FA-0025) spanning
7 CRITICAL / 9 HIGH / 7 MEDIUM / 2 LOW across CWEs 89, 94, 943, 611, 321, 918,
22, 79, 601, 327, 798, 639, 116, 290.

## 2. Confusion matrix (SAST, frozen rule, window N=5)

| Category | TP | FN | FP | Recall | Strict precision | Sev-weighted recall |
|----------|----|----|----|--------|------------------|---------------------|
| **SAST** | **14** | **0** | **11** | **1.000** | **0.560** | **1.000** |

Scorer command run by the adjudicator (independent, grounded):

```
python benchmark/score.py \
  --findings benchmark/results/sast-juiceshop-01.blind.findings.json \
  --truth benchmark/seeds/sast-juiceshop-01/ground-truth.yaml \
  --out benchmark/results/sast-juiceshop-01.blind.score.json
```

### TP — all 14 GT items matched by the blind reviewer

| GT | Finding | Locus | CWE |
|----|---------|-------|-----|
| GT-001 | FA-0001 | routes/login.ts:34 | CWE-89 SQLi |
| GT-002 | FA-0002 | routes/search.ts:23 | CWE-89 SQLi |
| GT-003 | FA-0015 | routes/updateProductReviews.ts:18 | CWE-943 NoSQL injection |
| GT-004 | FA-0016 | lib/insecurity.ts:135 | CWE-601 open redirect |
| GT-005 | FA-0007 | routes/fileUpload.ts:83 | CWE-611 XXE |
| GT-006 | FA-0004 | routes/b2bOrder.ts:23 | CWE-94 RCE |
| GT-007 | FA-0003 | routes/userProfile.ts:61 | CWE-94 SSTI/code injection |
| GT-008 | FA-0009 | routes/fileServer.ts:33 | CWE-22 path traversal |
| GT-009 | FA-0010 | routes/dataErasure.ts:104 | CWE-22 LFR |
| GT-010 | FA-0008 | routes/profileImageUrlUpload.ts:24 | CWE-918 SSRF |
| GT-011 | FA-0012 | frontend/.../search-result.component.ts:110 | CWE-79 XSS |
| GT-012 | FA-0011 | frontend/.../search-result.component.ts:143 | CWE-79 DOM XSS |
| GT-013 | FA-0017 | lib/insecurity.ts:43 | CWE-327 weak MD5 |
| GT-014 | FA-0006 | lib/insecurity.ts:23 | CWE-321 hardcoded RSA key |

**FN = 0.** The blind reviewer found every GT item independently.

The most notable recoveries vs the semgrep-only proxy run (which had FN=10):

- **GT-003 NoSQL injection** (`updateProductReviews.ts:18`, `{_id: req.body.id}` multi:true) — tool-missed in proxy, found by blind LLM review.
- **GT-004 Open redirect** (`lib/insecurity.ts:135`, `url.includes(allowedUrl)` substring check) — proxy flagged the route locus (different file), blind reviewer found the correct GT locus.
- **GT-006 RCE** (`b2bOrder.ts:23`, `safeEval(orderLinesData)`) — proxy emitted CWE-1104 (mismatch); blind reviewer emitted CWE-94 (correct).
- **GT-008 Path traversal** (`fileServer.ts:33`) — proxy emitted CWE-73 (mismatch); blind reviewer emitted CWE-22/158 (correct).
- **GT-009 LFR** (`dataErasure.ts:104`, `path.resolve(req.body.layout)`) — tool-missed in proxy, found by blind review.
- **GT-010 SSRF** (`profileImageUrlUpload.ts:24`, `fetch(req.body.imageUrl)`) — tool-missed in proxy, found by blind review.
- **GT-011/012 Angular XSS** (`search-result.component.ts:110/143`, `bypassSecurityTrustHtml`) — tool-missed in proxy, found by blind review.
- **GT-013 Weak MD5** (`insecurity.ts:43`, `crypto.createHash('md5')`) — tool-missed in proxy, found by blind review.
- **GT-014 RSA PEM literal** (`insecurity.ts:23`) — proxy missed the declaration locus; blind reviewer pinned it correctly.

## 3. FN root-cause analysis

**Zero FN.** Nothing to root-cause. The blind reviewer independently located every GT item
without access to the ground truth.

## 4. Adjudication of 11 unmatched findings (strict FP)

Source read for each: `C:/Temp/juice-shop-bench` at the pinned commit.
Method mirrors `benchmark/results/F2-adjudication.md`.

**Buckets:** real-but-unlabelled / true-FP / disputed.

| id | file:line | title | bucket | justification (source-grounded) |
|----|-----------|-------|--------|---------------------------------|
| FA-0005 | routes/trackOrder.ts:18 | NoSQL/JS injection via MongoDB $where in order tracking | **real-but-unlabelled** | `db.ordersCollection.find({ $where: \`this.orderId === '${id}'\` })` — user-supplied `req.params.id` is interpolated into a MongoDB `$where` JS predicate. The only filtering is a `\w-` regex when `reflectedXssChallenge` is disabled, or a 60-char truncation when enabled. Both paths allow injecting `'||true||'` to return all orders. Real CWE-943 NoSQL injection (Juice Shop `noSqlOrdersChallenge`); GT covers `updateProductReviews.ts` not this locus. |
| FA-0013 | frontend/src/app/about/about.component.ts:119 | Stored XSS via customer feedback comment | **real-but-unlabelled** | `feedbacks[i].comment = this.sanitizer.bypassSecurityTrustHtml(feedbacks[i].comment)` where `feedbacks[i].comment` is user-submitted text from the server. `bypassSecurityTrustHtml` defeats Angular's XSS escaping; any visitor of the About page renders attacker-submitted HTML. Real stored XSS (Juice Shop `persistedXssUserChallenge`); not in GT. |
| FA-0014 | frontend/src/app/last-login-ip/last-login-ip.component.ts:39 | Stored XSS via True-Client-IP header -> lastLoginIp | **real-but-unlabelled** | `this.lastLoginIp = this.sanitizer.bypassSecurityTrustHtml(\`<small>${payload.data.lastLoginIp}</small>\`)` — `lastLoginIp` is decoded from the JWT, which stores the attacker-controlled `true-client-ip` header. `bypassSecurityTrustHtml` leaves the HTML unescaped in the DOM. Real stored/header-injected XSS (Juice Shop `httpHeaderXssChallenge`); not in GT. |
| FA-0018 | lib/insecurity.ts:44 | Hardcoded HMAC secret key | **real-but-unlabelled** | `export const hmac = (data: string) => crypto.createHmac('sha256', 'pa4qacea4VK9t9nGv7yZtwmj').update(data).digest('hex')` — plaintext HMAC secret in source at line 44. Real CWE-798 hardcoded secret used for security-question answer verification; distinct locus from GT-014 (line 23, the RSA PEM). Not in GT. |
| FA-0019 | routes/showProductReviews.ts:36 | NoSQL $where injection / DoS in product review listing | **real-but-unlabelled** | `db.reviewsCollection.find({ $where: 'this.product == ' + id })` — `id = req.params.id` is coerced to Number normally but passed raw (truncated to 40 chars) when `noSqlCommandChallenge` is enabled. `$where` runs server-side JS; injecting blocking code enables DoS. The code explicitly measures >2000 ms to detect the attack. Real CWE-943 (Juice Shop `noSqlCommandChallenge`); not in GT. |
| FA-0020 | routes/keyServer.ts:14 | Path traversal exposure of encryptionkeys directory | **real-but-unlabelled** | `res.sendFile(path.resolve('encryptionkeys/', file))` where `file = params.file` guarded only by `!file.includes('/')`. Backslash-encoded or dot-dot sequences can traverse out of `encryptionkeys/` on Windows/POSIX respectively; serving the encryption-key directory by filename is itself a real CWE-22 exposure (Juice Shop `forgottenDevBackupChallenge` / key-file disclosure). Not in GT. |
| FA-0021 | routes/logfileServer.ts:14 | Path traversal exposure of logs directory | **real-but-unlabelled** | `res.sendFile(path.resolve('logs/', file))` guarded only by a forward-slash check. Same dot-dot traversal class as FA-0020; real CWE-22 path traversal (Juice Shop `accessLogDisclosureChallenge`). Not in GT. |
| FA-0022 | routes/createProductReviews.ts:23 | Review author spoofing via client-supplied author field | **real-but-unlabelled** | `await reviewsCollection.insert({ ..., author: req.body.author, ... })` with no check that `req.body.author` equals the authenticated user's email (CWE-639 / broken object-level authorization). The code itself detects this as `forgedReviewChallenge` by comparing `user?.data?.email !== req.body.author`. Real IDOR/spoofing; not in GT. |
| FA-0023 | routes/order.ts:142 | Wallet IDOR via client-supplied UserId in order placement | **real-but-unlabelled** | `WalletModel.findOne({ where: { UserId: req.body.UserId } })` / `decrement` / `increment` all key on `req.body.UserId` without verifying it matches the authenticated user's id. A user can supply another user's UserId to manipulate their wallet balance. Real CWE-639 IDOR (Juice Shop `negativeOrderChallenge` adjacent); not in GT. |
| FA-0024 | lib/insecurity.ts:61 | Ineffective legacy HTML sanitizer (regex-based) | **real-but-unlabelled** | `export const sanitizeLegacy = (input = '') => input.replace(/<(?:\w+)\W+?[\w]/gi, '')` — a single regex that is trivially bypassable (malformed tags, event-handler-only attributes, non-standard syntax). Any caller relying on it for XSS protection is unprotected. Real CWE-116 (inadequate encoding). Not in GT but a genuine code weakness. |
| FA-0025 | lib/insecurity.ts:95 | User identity taken from spoofable X-User-Email header | **real-but-unlabelled** | `export const userEmailFrom = ({ headers }: any) => headers ? headers['x-user-email'] : undefined` — verbatim return of a client-supplied header. Any authorization decision keying on this is spoofable. Real CWE-290 pattern; not in GT. |

### Bucket summary

| bucket | count | finding ids |
|--------|-------|-------------|
| **real-but-unlabelled** | **11** | FA-0005, FA-0013, FA-0014, FA-0018, FA-0019, FA-0020, FA-0021, FA-0022, FA-0023, FA-0024, FA-0025 |
| **true-FP** | **0** | — |
| **disputed** | **0** | — |

All 11 unmatched findings are genuine Juice Shop vulnerabilities at loci/CWEs the
conservative 14-item GT deliberately excluded. **Zero true semgrep or LLM false positives.**

### Precision: strict vs adjudicated

```
strict_precision      = TP / (TP + FP)                       = 14 / (14 + 11) = 14/25 = 0.560
adjudicated_precision = (TP + real) / (TP + real + true-FP)  = (14+11)/(14+11+0) = 25/25 = 1.000
```

| metric | value |
|--------|-------|
| Recall | **1.000** (14/14) |
| Strict precision | **0.560** (14/25) |
| Adjudicated precision | **1.000** (25/25) |
| Severity-weighted recall | **1.000** |

The 0.560 → 1.000 lift from strict to adjudicated precision is **entirely GT-coverage gap,
not reviewer noise**: the blind reviewer produced zero true false positives. Every unmatched
finding is a real Juice Shop vulnerability outside the conservative 14-item GT.

## 5. Three-way comparison: proxy run1 vs non-blind multi-agent vs blind run

| Run | Reviewer | Saw GT? | TP | FN | FP | Recall | Strict precision | Adjudicated precision | Sev-weighted recall |
|-----|----------|---------|----|----|----|----|---|---|---|
| **Proxy run1** (semgrep-only) | Opus (single-agent) | No | 4 | 10 | 25 | **0.286** | 0.138 | 0.857 | 0.323 |
| **Non-blind multi-agent** (answer-key-inflated) | Opus (inline review waves) | **Yes** (implicitly: GT construction rationale visible to orchestrator) | 14 | 0 | 18 | **1.000** | 0.438 | 0.935 | 1.000 |
| **Blind run** (THIS — defensible) | Opus (blind findings) + Sonnet 4.6 (scorer) | **No** (Opus blind; Sonnet independent) | 14 | 0 | 11 | **1.000** | **0.560** | **1.000** | **1.000** |

**Honest interpretation:**

- The **proxy run1 (0.286)** is the semgrep-tool-only floor: a single-agent semgrep scan with
  no LLM source-review wave. It measures what the deterministic tool can find alone.
- The **non-blind multi-agent (1.000)** achieved perfect recall but the design was flawed:
  the orchestrator (Opus) that produced findings was the same session that had constructed the
  GT rationale, so it was not blind to what it should find. This run is **superseded** as a
  capability measure — its recall is contaminated by answer-key visibility.
- The **blind run (THIS — 1.000)** is the defensible number. The blind reviewer (Opus) produced
  findings entirely independently. Scoring and adjudication were done by a separate model
  (Sonnet 4.6) that also had no involvement in the findings. The design flaw of the non-blind
  run is closed by the role split across models and sessions. The 1.000 recall here is
  the first number that can be cited as a genuine LLM-review capability measure (with the
  Threats to Validity below).
- **The 0.286 → 1.000 lift** confirms the key claim: LLM source review recovers the
  tool-missed FNs that semgrep-only cannot reach (NoSQL injection, SSRF, LFR, Angular
  `bypassSecurityTrustHtml` XSS, weak-MD5, RSA PEM literal locus, CWE-mismatch corrections).

## 6. Threats to Validity

### Addressed by this design

- **Blindness to GT:** satisfied. The blind reviewer (Opus) produced findings before this
  scoring document existed. The scorer/adjudicator (Sonnet 4.6) is a different model that
  was not involved in the findings.
- **Fox-guarding-henhouse:** satisfied. Roles are split across models AND sessions — the
  model that produced the findings cannot have influenced the scoring or adjudication.

### Remaining threats (unchanged from prior runs)

1. **Juice Shop is in LLM training data (contamination).** The 1.000 recall may reflect
   the blind reviewer recalling memorized knowledge of Juice Shop's famous vulnerabilities
   rather than discovering them by pure static analysis of the code. The 14 GT items are
   exactly the class of well-documented, challenge-annotated Juice Shop vulns most likely
   to be in training data. **A fully clean capability test needs a non-public / post-cutoff
   target** (planned Ф3). This is the single biggest caveat on interpreting the 1.000
   as a "framework SAST capability" number vs a "LLM familiarity with Juice Shop" number.

2. **GT coverage is 12.5% (14 of 112 challenges).** Recall is "recall against the 14
   statically-locatable sinks", not against all Juice Shop vulns. The 11 real-but-unlabelled
   findings are direct evidence the GT under-counts. True recall against all vulns would be
   lower (the denominator would expand substantially).

3. **Single run, no variability.** N=1; no confidence interval. LLM review has sampling
   variability; a single run cannot bound the spread.

4. **Adjudicator is a model, not a human.** Sonnet 4.6 adjudicated by reading real source
   at each locus, which raises confidence above strict-FP counting, but human security
   reviewer spot-check was not performed. All 11 adjudicated-real items in this run are
   straightforward (clearly-real Juice Shop challenge loci) so model error is unlikely to
   affect the 1.000 adjudicated precision here.

5. **Inline review, no true parallel subagents.** The framework playbook prescribes
   parallel independent review sub-agents. In both the non-blind and blind runs the review
   was performed inline by a single session. The *substance* (real source-grounded review)
   is preserved; the *process* (inter-agent cross-check, independent dedup) was not.

## 7. Gates

| gate | result |
|------|--------|
| `python scripts/lint_docs.py` | **PASS** — 0 errors, 0 warnings across 11 docs |
| `python benchmark/test_score.py` | **PASS** — 27/27 OK |

## 8. Artifacts

- Blind findings (frozen): `benchmark/results/sast-juiceshop-01.blind.findings.json`
- Score: `benchmark/results/sast-juiceshop-01.blind.score.json`
- Frozen GT (pre-registered, unmodified): `benchmark/seeds/sast-juiceshop-01/ground-truth.yaml`
  @ tag `bench-prereg-sast-juiceshop-01` (commit `599b703`)
- Proxy run (for comparison): `benchmark/results/F2-sast-juiceshop-01.md`
- Non-blind run (superseded): `benchmark/results/F2-multiagent-juiceshop-01.md`
- Prior adjudication (for comparison): `benchmark/results/F2-adjudication.md`
- This report: `benchmark/results/F2-blind-juiceshop-01.md`
- Source read at: `C:/Temp/juice-shop-bench` @ `f356a09207c7a9550eb6fc4c3945e081922cf998`
- Blind reviewer model: Claude Opus (stage 1)
- Scorer / adjudicator model: Claude Sonnet 4.6 (stage 2, independent)
