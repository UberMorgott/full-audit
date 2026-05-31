# Seed `synthetic-vuln-01` — Contamination-Control SAST Benchmark App

> **Pre-registration artifact.** This seed and its ground-truth YAML are committed
> and git-tagged BEFORE any blind reviewer or scanner sees the code.

## Purpose

Prior benchmark runs used OWASP Juice Shop, which is heavily represented in LLM
training data. A model scoring high recall on Juice Shop may be **recalling**
memorised vulnerability locations rather than **analysing** the code. This seed
removes that confound:

- Code is **original**, authored 2026-05, post-LLM-knowledge-cutoff.
- Domain, variable names, route names, and logic are **NOT** derived from Juice
  Shop, DVWA, WebGoat, or any textbook example.
- A blind reviewer must **read and reason** about this specific code to find bugs.

## Domain

**HiveTrack** — a community beekeeping club web app for tracking hives,
honey harvests, inspection reports, member profiles, and queen-bee lineage.
Routes: registration/login, hive CRUD, harvest logging, file upload/download,
admin member management, admin CSV export, external weather lookup, open redirect
helper, snapshot import, queen registration.

## Authorship

- **Authored:** 2026-05 (post-cutoff; uncontaminated)
- **Language:** Python 3 / Flask (single-file, ~690 LOC)
- **Author stage:** Seed Author (Ф3 stage A) — plants bugs, writes GT.
- **Ground truth:** by-construction-exact. Each GT item was recorded by the
  author at the moment of planting; no inference or reverse-engineering needed.

## Vulnerability inventory

14 deliberate vulnerabilities across 10 distinct CWE classes, planted at known
exact loci. See `ground-truth.yaml` for file + line + CWE + rationale.

| GT id        | CWE(s)        | Severity | Short description |
|--------------|---------------|----------|-------------------|
| GT-S01-001   | CWE-798       | CRITICAL | Hardcoded Flask secret key |
| GT-S01-002   | CWE-328       | HIGH     | MD5 password hashing, no salt |
| GT-S01-003   | CWE-89        | CRITICAL | SQL injection — login username concat |
| GT-S01-004   | CWE-639       | HIGH     | IDOR — hive fetch, no ownership check |
| GT-S01-005   | CWE-89        | CRITICAL | SQL injection — search %-format |
| GT-S01-006   | CWE-184       | MEDIUM   | Incomplete allowlist (extension check bypass + path sep) |
| GT-S01-007   | CWE-22        | HIGH     | Path traversal — raw filename in os.path.join |
| GT-S01-008   | CWE-94        | CRITICAL | SSTI — bio concat into render_template_string |
| GT-S01-009   | CWE-78        | CRITICAL | Command injection — format param to os.system |
| GT-S01-010   | CWE-918       | HIGH     | SSRF — user URL to requests.get |
| GT-S01-011   | CWE-601       | MEDIUM   | Open redirect — startswith bypass |
| GT-S01-012   | CWE-502       | CRITICAL | Insecure deserialization — pickle.loads on request body |
| GT-S01-013   | CWE-79        | HIGH     | Stored XSS — notes via \|safe filter |
| GT-S01-014   | CWE-78        | HIGH     | 2-hop command injection — regex partial match + subprocess |

## Safe / decoy code paths (NOT in GT)

Intentional correct patterns included so the reviewer must discriminate
(tests precision, not just recall):

- Parameterized queries in `dashboard()`, `add_harvest()`, `add_note()`,
  `download_report()`, `register()` — correct `?` placeholders.
- Ownership check in `add_harvest()` (`WHERE id=? AND owner_id=?`) — correct.
- Ownership check in `add_note()` — correct (only the content is unsafe, not
  the authz logic).
- `download_report()` DB lookup verifies report ownership transitively — correct.
- `admin_members()` role check — correct (no IDOR at the admin level).

## Matching rule

Per `benchmark/ground-truth.schema.md` §2: a SAST finding matches a GT item iff
`finding.file == gt.file` (verbatim), CWE sets intersect (normalized), and the
finding's line span overlaps `[line_start - N, line_end + N]`, default `N=5`.

`finding.file` MUST be repo-relative from the `full-audit` repo root:
`benchmark/seeds/synthetic-vuln-01/app.py`

## Pre-registration

Committed and annotated-tagged **before** any scanner or blind reviewer runs:
- Tag: `bench-prereg-synthetic-01`
- Commit recorded in tag annotation.
