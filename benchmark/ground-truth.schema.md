# Ground-truth schema + pre-registered matching rule

> Pre-registration artifact for the full-audit benchmark (Ф0 pipeline core).
> This file plus every `ground-truth.yaml` it governs **MUST be committed and
> git-tagged BEFORE any benchmark run** (e.g. `bench-prereg-v1`). The tag is what
> makes "we did not tune the matching rule to flatter the results" externally
> verifiable. See `BENCHMARK-PLAN.md` → "Pre-registration is an artifact, not a
> promise".

## 1. Ground-truth YAML format

A ground-truth (GT) file is the labelled oracle for one target repo at one pinned
commit. It is a YAML mapping with an optional `meta:` block and a required `items:`
list. Each item is one known vulnerability.

```yaml
meta:
  repo: example/target
  commit: 0000000000000000000000000000000000000000   # exact pinned commit
  notes: optional free text
items:
  - id: GT-001
    type: sca
    cve: CVE-2023-1234
    severity: HIGH
    cvss: 7.5
    file: go.mod          # advisory for sca (ignored by the matcher)
    line_start: 12
```

### Item fields

| Field        | Required for      | Type            | Meaning |
|--------------|-------------------|-----------------|---------|
| `id`         | all               | string          | Stable label, unique within the file (e.g. `GT-001`). |
| `type`       | all               | `sca`\|`sast`\|`logical` | Category. Drives which matching rule applies. |
| `file`       | sast (advisory sca)| string         | Repo-relative path. Compared verbatim for sast. |
| `line_start` | sast              | int             | First line of the vulnerable span. |
| `line_end`   | sast (optional)   | int             | Last line; defaults to `line_start` when absent. |
| `cwe`        | sast              | string\|list    | CWE id(s), e.g. `CWE-89` or `[CWE-89, CWE-564]`. |
| `cve`        | sca               | string\|list    | CVE id(s), e.g. `CVE-2023-1234`. |
| `severity`   | all               | `CRITICAL`\|`HIGH`\|`MEDIUM`\|`LOW` | Oracle severity band. |
| `cvss`       | all (optional)    | float           | Oracle CVSS base score (0.0–10.0). Preferred over band for weighting. |

Notes:
- `cwe`/`cve` accept a scalar **or** a list; the matcher treats both as a set and
  normalizes each id to canonical form before intersection (see §2).
- `logical` items carry no CWE/line precision requirement — they exist only so the
  oracle inventory is complete; they are **never** auto-matched (see §2).

## 2. Pre-registered matching rule (VERBATIM — do not edit post-tag)

Categories are scored **separately and never aggregated** (a finding/GT item in one
category can never match across categories).

**CWE/CVE id normalization (applied on BOTH sides before intersection).** CWE and
CVE ids are canonicalized before the set intersections below, because real scanners
(semgrep / gosec / osv-scanner / etc.) emit the same id in varied forms and verbatim
matching would produce phantom FN/FP that corrupt recall/precision:
  - **CWE** → `CWE-<int>` (uppercase, leading zeros stripped). The `CWE-` prefix is
    **optional** and a **bare integer** is accepted, all case-insensitive: `CWE-89`,
    `cwe-89`, `89`, `CWE-089`, and the integer `89` all canonicalize to `CWE-89`.
  - **CVE** → uppercase `CVE-YYYY-NNNN` (case-insensitive): `cve-2023-1234` →
    `CVE-2023-1234`.
  - An id that does **not** match the recognized shape is kept **unchanged**
    (stripped + uppercased), never dropped — so genuinely different ids
    (e.g. `CWE-89` vs `CWE-79`, or CVEs with different years) can never silently
    merge. A blank / whitespace-only id carries no token (→ adjudication, not FP).

  This normalization is **part of the frozen pre-registered rule** (a deliberate
  refinement made before the pre-registration tag). It changes only the *form* of
  comparison, never which distinct ids are considered equal.

- **SCA** — a GT item with `type: sca` matches a finding **iff their (normalized)
  CVE id sets intersect**: `norm(set(finding.cve)) ∩ norm(set(gt.cve)) ≠ ∅`. File and
  line are **ignored** (SCA is dependency-level, not location-level).

- **SAST** — a GT item with `type: sast` matches a finding **iff all** hold:
  1. `finding.file == gt.file` (verbatim string equality), AND
  2. normalized CWE id sets intersect: `norm(set(finding.cwe)) ∩ norm(set(gt.cwe)) ≠ ∅`, AND
  3. the finding's line span overlaps the GT span widened by window `N`:
     `[finding.line, finding.end_line or finding.line]` overlaps
     `[gt.line_start − N, (gt.line_end or gt.line_start) + N]`.
     Two closed intervals `[a,b]` and `[c,d]` overlap iff `a ≤ d AND c ≤ b`.
     `N` is configurable via `--window`, **default 5**.

- **logical** — **EXCLUDED from automated matching.** Logical/LLM findings lack
  CWE/line precision; auto-matching would either under-count or invite rule-tuning.
  Both logical GT items and logical-class findings are reported separately as
  *manual adjudication required* and are **never** scored as TP/FN/FP.

### Outcome buckets

- **TP** (true positive) — a matched GT↔finding pair (one match consumes one GT item
  and one finding; a finding may match at most one GT item per category).
- **FN** (false negative) — a GT item (`sca` or `sast` only) with no matching finding.
- **FP** (strict false positive) — a finding that is **auto-scorable** (its
  `detection` produced a `cve` or a `cwe`) and matches no GT item.
- **unmatched — needs adjudication** — a finding that is neither matched nor a
  strict FP: it carries no `cwe`/`cve` (not auto-scorable) and is not logical-class.
  Per the plan's *strict vs adjudicated precision* split, these go to an independent
  adjudication pass (out of scope for this harness) and are **NOT** counted as FP.
- **logical — manual review** — every logical-class finding and every `type: logical`
  GT item, listed for human/independent-model adjudication only.

A finding is **logical-class** when it has neither `cwe` nor `cve`. Such a finding,
when it cannot match a sast/sca GT item, is bucketed as *needs adjudication* (it is
indistinguishable from an unmatched no-taxonomy finding by the auto-rule). The
*logical — manual review* list is populated from the `type: logical` GT items plus,
informationally, the same no-taxonomy findings.

## 3. Metric definitions (per category: `sca`, `sast` — never blended)

- **recall** = `TP / (TP + FN)` — of the labelled bugs, how many the audit found.
- **strict precision** = `TP / (TP + FP)` — of the auto-scorable emitted findings,
  how many are real. Adjudicated precision (folding in the adjudication verdicts) is
  computed in a later phase, not here.
- **severity-weighted recall** = `Σ weight(TP) / Σ weight(TP ∪ FN)` — weights a
  missed CRITICAL far above a missed nitpick.

### CVSS ↔ band weight crosswalk

When a GT item carries a `cvss` float it is used directly as the weight; otherwise
the severity band maps to a representative weight:

| Band     | Weight (band fallback) | CVSS range it represents |
|----------|------------------------|--------------------------|
| CRITICAL | 10                     | 9.0–10.0 |
| HIGH     | 7                      | 7.0–8.9  |
| MEDIUM   | 4                      | 4.0–6.9  |
| LOW      | 1                      | 0.1–3.9  |

`weight(item) = item.cvss if present else band_weight[item.severity]`.

## 4. FN root-cause field

Every FN emitted by the scorer carries an empty `root_cause: ""` field, to be filled
during review with one of: `tool-not-run` / `skip_if-fired` / `dismissed` /
`below-threshold`. This turns the scoreboard into a remediation backlog (per plan §2,
"FN root-cause tag").

## 5. YAML dependency choice

This repo's tooling is **stdlib-only** (`scripts/lint_docs.py`,
`scripts/check_readme_version.py` both state "Python 3 standard library only"; PyYAML
is not installed). To keep that contract, `benchmark/score.py` ships a **tiny
self-contained YAML reader** for the flat subset used by these GT files (the same
approach as `parse_lock` in `lint_docs.py`). It supports: top-level mappings, a list
of mapping items under `items:`, scalar values, `[a, b]` inline lists, quoted
strings, ints, and floats. It does **not** aim to be a general YAML parser. No `pip
install` is required to run the harness.
