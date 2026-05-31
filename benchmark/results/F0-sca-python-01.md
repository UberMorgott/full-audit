# Ф0 report — SCA pipeline run on `sca-python-01`

> First end-to-end run of the full-audit benchmark machinery (GT schema → frozen
> matching rule → scorer) on a controlled SCA seed. Produces the first real
> recall/precision numbers and a measured cost for the SCA path.

## Target

Controlled seed `benchmark/seeds/sca-python-01/` — `requirements.txt` pinning six
popular PyPI packages at old, vulnerable-by-design versions:

| Package | Pinned version | requirements.txt line | distinct CVEs (osv.dev) |
|---------|----------------|-----------------------|-------------------------|
| Jinja2       | 2.10    | 1 | 6  |
| PyYAML       | 5.1     | 2 | 3  |
| requests     | 2.19.1  | 3 | 5  |
| urllib3      | 1.24    | 4 | 13 |
| Flask        | 0.12.2  | 5 | 4  |
| cryptography | 2.3     | 6 | 7  |
| **Total**    |         |   | **38** |

## Pre-registration (rule + GT frozen BEFORE the run)

- **Prereg commit:** `c802dedf6981cbaa01c3bdef0728e81a344a318b`
  (`bench(prereg): sca-python-01 seed + ground truth (osv.dev-sourced)`)
- **Annotated tag:** `bench-prereg-sca-python-01` → points at `c802ded`, pushed to origin.
- The tag fixes the ground truth + the frozen matching rule (`benchmark/ground-truth.schema.md`)
  before `pip-audit` was ever run, so the rule cannot have been tuned to the result.
- Scorer/rule untouched by this run (no edits to `score.py` or the schema doc).

## Ground truth (independent oracle)

- **Source:** osv.dev `POST /v1/query` per pinned `package@version`
  (`{"package":{"name":<pkg>,"ecosystem":"PyPI"},"version":<ver>}`).
- **N = 38** distinct `(package, CVE)` items. GHSA/PYSEC advisories sharing a CVE
  alias were deduplicated to that CVE (SCA matches on CVE id per the frozen rule).
- **CVSS / severity:** CVSS v3.x base score taken from the osv record when present;
  when the osv record carried only a CVSS v4 vector, the osv `database_specific`
  severity band is used (5 items: GT-006, GT-024, GT-025, GT-031, GT-037), weighted
  via the crosswalk in the schema.
- **CVE-less osv advisories (documented expected-FN, intentionally NOT GT items):**
  cryptography 2.3 `GHSA-5cpq-8wj7-hf2v` and `GHSA-jm77-qphf-c4w8` carry no CVE
  alias → not matchable by the CVE rule. (See per-package osv counts above; raw
  queries reproduced in "Grounding / raw queries" below.)

### osv.dev queries → CVE ids found (per package@version)

```
Jinja2 2.10        -> CVE-2019-10906, CVE-2020-28493, CVE-2024-22195, CVE-2024-34064,
                      CVE-2024-56326, CVE-2025-27516
PyYAML 5.1         -> CVE-2019-20477, CVE-2020-1747, CVE-2020-14343
requests 2.19.1    -> CVE-2018-18074, CVE-2023-32681, CVE-2024-35195, CVE-2024-47081,
                      CVE-2026-25645
urllib3 1.24       -> CVE-2018-25091, CVE-2019-11236, CVE-2019-11324, CVE-2020-26137,
                      CVE-2021-33503, CVE-2023-43804, CVE-2023-45803, CVE-2024-37891,
                      CVE-2025-50181, CVE-2025-66418, CVE-2025-66471, CVE-2026-21441,
                      CVE-2026-44431
Flask 0.12.2       -> CVE-2018-1000656, CVE-2019-1010083, CVE-2023-30861, CVE-2026-27205
cryptography 2.3   -> CVE-2020-25659, CVE-2023-0286, CVE-2023-23931, CVE-2023-50782,
                      CVE-2024-0727, CVE-2026-26007, CVE-2026-34073
                      (+ GHSA-5cpq-8wj7-hf2v, GHSA-jm77-qphf-c4w8: no CVE -> expected-FN)
```

## Scanner

- **Tool:** `pip-audit` **2.10.0** (`python -m pip install pip-audit`).
- **Invocation:** `python -m pip_audit -r benchmark/seeds/sca-python-01/requirements.txt
  --no-deps --disable-pip --format json`
- **Why `--no-deps --disable-pip`:** the default invocation (`-r` only) drives pip's
  resolver/dry-run, which tried to **build cryptography 2.3 from source** and failed
  on Python 3.13 (no compatible wheel; `pkg_resources`/build-backend errors). One
  corrective retry with `--no-deps` alone still invoked pip and failed identically.
  `--no-deps --disable-pip` audits the **exact pinned versions** with no resolution
  or build step — the documented offline-fallback path. This is a config change to
  make the run succeed, not a change to what is audited (the six pinned lines).
- **Raw output:** 46 advisory rows across all 6 packages ("Found 46 known
  vulnerabilities in 6 packages"); 44 rows carry ≥1 CVE, 2 are CVE-less
  (the two cryptography GHSA advisories above). Exit code 1 = pip-audit's convention
  for "vulnerabilities found".

## Transcription to schema v1.1

`benchmark/results/sca-python-01.findings.json` (schema_version `1.1`). One finding
per **distinct advisory group** (pip-audit rows sharing a CVE collapse into one
finding carrying the union of CVE aliases) → **38 findings**. Each:
`file="requirements.txt"`, `line=<package line>`, `cve=<id or list>`,
`detection="pip-audit"`, `confidence=90`, `reproduced="n/a"`, severity from the osv
CVSS/band already in GT, title/detail/recommendation from the advisory + fix version.
`summary` counts (CRITICAL 3 / HIGH 15 / MEDIUM 19 / LOW 1 = 38) equal the findings
array length.

> Note on CVE-2025-50460: pip-audit attaches it as a **second CVE alias on the same
> PyYAML advisory row** (PYSEC-2020-96) that already carries CVE-2020-1747 — it is
> the same full_load RCE vuln, not a distinct one. `osv.dev /v1/vulns/CVE-2025-50460`
> returns no standalone record, confirming it is alias-only. It is emitted as a
> co-alias on the CVE-2020-1747 finding (FA-0008), so it does not become a phantom FP.

## Result — per-category confusion matrix (window N=5, scorer default)

| Category | TP | FN | FP | recall | strict precision | sev-weighted recall |
|----------|----|----|----|--------|------------------|---------------------|
| **SCA**  | 38 | 0  | 0  | **1.000** | **1.000**     | **1.000**           |
| SAST     | 0  | 0  | 0  | n/a    | n/a              | n/a                 |

- Unmatched / needs-adjudication: **0**. Logical (manual review): **0**.
- Set diff confirms it: `GT \ pip-audit = ∅` (no SCA false negative);
  `pip-audit \ GT = {CVE-2025-50460}`, and that id is an alias of CVE-2020-1747 (a GT
  item) on a single advisory row → folded into FA-0008 → **0 FP**.

### FN list

**None.** Every osv.dev-known CVE for the six pinned versions was reported by
pip-audit and matched.

> Documented *non-FN by design* (never in GT): the two CVE-less cryptography
> advisories (`GHSA-5cpq-8wj7-hf2v`, `GHSA-jm77-qphf-c4w8`). root_cause:
> **CVE-less OSV advisory — not matchable by the CVE rule**. They are excluded from
> GT (so they cannot be FN); pip-audit also reported them as the 2 CVE-less rows, so
> there is no capability gap here — only a taxonomy gap that the frozen SCA rule
> (CVE-only) cannot express. If a future rule matched OSV ids, these would be TP.

### FP / adjudication list

**None.** The only candidate (CVE-2025-50460) is adjudicated as **same-vuln alias**
of an in-GT CVE (root_cause: *duplicate/re-assigned CVE alias on one advisory*),
handled at transcription time, not counted as FP.

## Measured cost

| Metric | Value |
|--------|-------|
| pip-audit wall-clock (successful `--no-deps --disable-pip` run) | **~1.3 s** (1261 ms) |
| Failed default-resolver attempts (build cryptography) | ~9.5 s + ~9.1 s (wasted) |
| osv.dev GT-build queries (6 × `/v1/query`) | a few seconds total, one-off |
| **Model / LLM token cost for the SCA path** | **≈ 0** — pip-audit is a deterministic CLI tool; no model inference in the SCA detection path. (Tokens were spent only on *this orchestration/report*, not on the audit's SCA detection itself.) |

The SCA path is essentially free in model terms and sub-second in wall-clock once the
scanner is installed and the correct invocation is known.

## Threats to validity

- **Circularity / shared lineage (the big one).** The ground truth is built from
  osv.dev, and `pip-audit`'s advisory database is sourced from the **same OSV / PyPA
  advisory ecosystem**. GT and scanner therefore share lineage. The 1.000/1.000 result
  is a **pipeline + coverage check** (does the harness wire up, parse, normalize, and
  score end-to-end; does pip-audit's DB cover the osv-known set), **NOT an independent
  measure of capability**. An independent oracle (e.g. NVD-only, or a scanner on a
  different DB such as govulncheck for Go) would be needed to claim independence.
- **Single controlled target.** One seed, one ecosystem (PyPI), six packages. No
  generalization claim. N=1 repo.
- **Known-easy seed.** Versions were deliberately chosen to be old and CVE-rich;
  this is the easiest possible SCA case, not a representative project lockfile (no
  transitive deps, no version-range edge cases, no private packages).
- **No transitive resolution.** `--no-deps --disable-pip` audits only the six pinned
  direct lines. A real project's transitive closure (and resolver behavior) is not
  exercised here; cryptography 2.3 could not even be built on Python 3.13.
- **Contamination is N/A for this path** — pip-audit is tool-deterministic, not an LLM
  recalling training data. (Contamination risk applies to the SAST/logical waves,
  measured in later phases.)
- **CVSS v4-only items.** 5 GT items had no CVSS v3 score; their weight comes from the
  osv `database_specific` band via the crosswalk, slightly coarser than a v3 base score.

## Calibrated Ф1 estimate (updated from measured Ф0 data)

Ф0 measured the **SCA detection path at ≈ 0 model tokens and ~1.3 s wall-clock** — it
is a deterministic tool invocation plus a thin parse/score. This confirms the plan's
assumption that SCA-only paths are cheap, and lets us re-anchor the budget:

- **SCA detection itself is effectively free** (model-token-wise). Per the plan's
  baseline definition (pinned tools, no LLM), an SCA-only baseline run is **near-zero
  model cost** — now measured, not assumed.
- **The expensive part of Ф1 is the SAST / LLM-review + reproduction waves**, not SCA.
  Ф0 contributes ~0 to that. The BENCHMARK-PLAN order-of-magnitude figure
  (~150k–400k output tokens per full L2+V framework audit) is driven by the SAST
  review-wave agents + reproduction wave + scoring/report agents — **none exercised
  here**.
- **Revised Ф1 framing:** for an SCA-only Ф1 (the cheap, objective fast-win the plan
  recommends as Ф1), per-repo model cost ≈ the orchestration/report overhead only
  (tens of k tokens at most), with detection at ~0. The big token spend remains
  deferred to Ф2 (SAST on vulnerable apps), where the LLM review waves dominate. The
  ~1.5M–3.5M-token "minimal Ф1" figure in the plan was for **framework runs that
  include LLM review**; an SCA-pure Ф1 across a handful of lockfiles is far cheaper —
  **budget it as low-hundreds-of-k tokens total**, dominated by report synthesis, not
  detection.
- **Action for Ф1:** add ≥1 SCA seed on a *different* advisory lineage (e.g. a Go
  `go.mod` scored against govulncheck/NVD, or a JS lockfile) to break the
  osv↔pip-audit circularity and turn the coverage check into a weak capability signal.

## Artifacts

- Seed: `benchmark/seeds/sca-python-01/` (requirements.txt, ground-truth.yaml, README.md)
- Findings: `benchmark/results/sca-python-01.findings.json`
- Score: `benchmark/results/sca-python-01.score.json`
- This report: `benchmark/results/F0-sca-python-01.md`
- Pre-registration: tag `bench-prereg-sca-python-01` @ `c802ded`
