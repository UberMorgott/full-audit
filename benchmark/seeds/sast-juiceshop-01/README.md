# Seed `sast-juiceshop-01` — SAST ground truth for OWASP Juice Shop

> First benchmark data point that exercises the **LLM code-review (SAST) path**
> (Ф2). SCA phases (Ф0/Ф1) were deterministic-tool-only and ≈0 model cost; this
> seed measures recall/precision of the JS/TS SAST path (semgrep offline rulesets
> + LLM review) against a vulnerable-by-design app.

## Target

- **Repo:** `juice-shop/juice-shop`
- **Release tag:** `v20.0.0` (published 2026-05-12, latest stable at run time)
- **Commit:** `f356a09207c7a9550eb6fc4c3945e081922cf998`
- **Clone:** scratch dir `C:/Temp/juice-shop-bench` (NOT in this repo tree); app NOT run.
- **App source size:** ≈ 23.1 KLOC TS (backend `routes/`+`lib/`+`models/` ≈ 7.8 KLOC,
  `app.ts`+`server.ts` ≈ 0.8 KLOC, `frontend/src` ≈ 14.5 KLOC), excluding
  `node_modules/`, `*.spec.ts`, build output, and `data/static` YAML fixtures.

## Ground-truth source

GT items come ONLY from real shipped Juice Shop vulnerability metadata + the actual
vulnerable code located by reading the source:

1. **`data/static/challenges.yml`** — the shipped catalogue of 112 intended
   vulnerabilities (challenge name, category, key).
2. **`vuln-code-snippet vuln-line <challengeKey>` source annotations** — the repo's
   own in-source markers (consumed by its "coding challenges" feature) that pin a
   challenge key to the exact vulnerable line. Harvested from `routes/`, `lib/`,
   `models/`, `server.ts`, and `frontend/src`.
3. **Manual code read** — every GT item's sink was opened and confirmed to be a real,
   user-reachable static sink before inclusion; CWE assigned from the sink semantics.

No item is a guess: each has a concrete `file:line`, a defensible CWE, and a named
shipped challenge.

## Coverage

- **Challenges total:** 112 (per `challenges.yml`).
- **Mapped to file+line+CWE (GT items):** **14** code-level static sinks across 9 files.
- These 14 cover the statically-locatable injection / XSS / XXE / RCE / SSRF / path-
  traversal / open-redirect / weak-crypto / hardcoded-secret sinks.

### GT items

| id | file:line | CWE | challenge |
|----|-----------|-----|-----------|
| GT-001 | routes/login.ts:34 | CWE-89 | loginAdmin/Bender/Jim (SQLi) |
| GT-002 | routes/search.ts:23 | CWE-89 | unionSqlInjection/dbSchema |
| GT-003 | routes/updateProductReviews.ts:18 | CWE-943/89 | noSqlReviews/forgedReview |
| GT-004 | lib/insecurity.ts:138 | CWE-601 | redirect (open redirect) |
| GT-005 | routes/fileUpload.ts:83 | CWE-611 | xxeFileDisclosure |
| GT-006 | routes/b2bOrder.ts:23 | CWE-94/1336 | rce/rceOccupy (eval RCE) |
| GT-007 | routes/userProfile.ts:61 | CWE-94/95 | usernameXss (SSTI eval) |
| GT-008 | routes/fileServer.ts:33 | CWE-22/158 | directoryListing/nullByte |
| GT-009 | routes/dataErasure.ts:104 | CWE-22 | lfr (local file read) |
| GT-010 | routes/profileImageUrlUpload.ts:24 | CWE-918 | ssrf |
| GT-011 | frontend/src/.../search-result.component.ts:110 | CWE-79 | restfulXss |
| GT-012 | frontend/src/.../search-result.component.ts:143 | CWE-79 | localXss/xssBonus |
| GT-013 | lib/insecurity.ts:43 | CWE-327/916 | weakPassword (MD5) |
| GT-014 | lib/insecurity.ts:23 | CWE-798/321 | hardcoded JWT RSA key |

## Exclusions (documented coverage limitation, NOT findings)

The remaining ~98 challenges are **deliberately NOT in GT** because they are not a
single statically-locatable code sink with a defensible CWE. Excluding them is an
honest GT-coverage limitation, not a capability claim. Excluded categories:

- **Broken Access Control / Improper Input Validation (24)** — behavioral
  authorization/mass-assignment bugs (e.g. view another basket, admin registration);
  the "vuln" is a missing/incorrect check across a request flow, not a sink line.
- **Sensitive Data Exposure (16)** — data reachable via API/endpoints/files
  (confidential docs, password hash leak); exposure is behavioral, no single sink.
- **Broken Authentication (9)** — weak/guessable creds, password-reset flows, 2FA
  bypass — protocol/logic, not a static sink.
- **Cryptographic Issues (5)** — most are protocol/usage challenges (forge JWT,
  encryption key recovery, Nested Easter Egg) — behavioral. (The two that DO have a
  static sink — MD5 hashing, hardcoded private key — ARE included as GT-013/GT-014.)
- **Security Misconfiguration / Observability / Misc / Anti-Automation / Security-
  through-Obscurity / Vulnerable Components (≈37)** — config, exposed metrics, log
  access, captcha bypass, deprecated/known-vuln dependency components (SCA-class, not
  SAST), and obscurity challenges — no statically-locatable application-code sink.
- A handful of XSS/redirect challenges are **variants reachable through the same sink**
  already in GT (e.g. several XSS challenges all flow through the two
  `bypassSecurityTrustHtml` sinks); they are not double-counted.

## Matching rule (frozen, pre-registered)

Per `benchmark/ground-truth.schema.md` §2: a SAST GT item matches a finding iff
`finding.file == gt.file` (verbatim) AND CWE sets intersect (normalized) AND the
finding line span overlaps `[line_start-N, line_end+N]`, default `N=5`. Finding
`file` MUST be the same repo-relative path string used here (forward slashes,
relative to the Juice Shop repo root).

## Pre-registration

Committed + annotated-tagged **before** semgrep was run on the target:
- Tag: `bench-prereg-sast-juiceshop-01`
- See `benchmark/results/F2-sast-juiceshop-01.md` for the run, scoring, and cost.
