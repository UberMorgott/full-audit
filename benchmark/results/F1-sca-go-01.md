# Ф1 report — SCA pipeline run on `sca-go-01` (Go / govulncheck lineage-break)

> Second SCA data point for the full-audit benchmark, designed to **break the
> osv↔pip-audit circularity of Ф0** and prove the instrument discriminates on real
> data. The scanner here (`govulncheck`) applies **reachability analysis** — it lists
> a vuln as actionable only if the vulnerable symbol is on a call path — so the
> osv-known ground truth and the scanner output diverge by design, producing an honest
> **recall < 1.0** rooted in a genuine coverage gap (not a contrived fixture).

## Target

Controlled seed `benchmark/seeds/sca-go-01/` — a small, **buildable** Go module
(`go build ./...` passes) pinning three third-party modules at old,
vulnerable-by-design versions, with their vulnerable symbols deliberately split into
reachable vs unreachable call paths:

| Module | Pinned version | go.mod line | distinct CVEs (osv.dev, Go) | symbol called by seed? |
|--------|----------------|-------------|------------------------------|------------------------|
| github.com/dgrijalva/jwt-go | v3.2.0+incompatible | 6 | 1 | **YES** — `MapClaims.VerifyAudience` (reachable) |
| github.com/gogo/protobuf    | v1.3.1              | 7 | 1 | **NO** — only benign `proto.String`; vuln is in `plugin/unmarshal` (unreachable) |
| golang.org/x/text           | v0.3.0              | 8 | 3 | **PARTLY** — `language.ParseAcceptLanguage` called (reachable, covers 2 CVEs); `encoding/unicode`+`transform` never called (1 CVE unreachable) |
| **Total** | | | **5** | |

**Which symbols are called vs not** (this is the whole point of the seed):

- **Reachable (govulncheck reports):**
  - `jwt.MapClaims.VerifyAudience` ← `main.go:43` `sca.parseToken` (CVE-2020-26160)
  - `language.ParseAcceptLanguage` ← `main.go:51` `sca.matchLanguage`
    (CVE-2022-32149 **and** CVE-2021-38561 — both advisories list this symbol)
- **Present but unreachable (govulncheck silent → honest FN):**
  - `golang.org/x/text/encoding/unicode` + `transform.String` (CVE-2020-14040) — the
    seed uses only the `language` package, never the unicode/transform decode path.
  - `github.com/gogo/protobuf/plugin/unmarshal` (CVE-2021-3121) — a code-generator
    symbol; the seed calls only the `proto` runtime helper, so it is never on a call path.

## Pre-registration (rule + GT frozen BEFORE the run)

- **Prereg commit:** `4b1cbcb75397062997d1b631414aa0b821cf8945`
  (`bench(prereg): sca-go-01 Go lineage-break seed + GT`)
- **Annotated tag:** `bench-prereg-sca-go-01` → points at `4b1cbcb`, pushed to origin.
- The tag fixes the ground truth + the frozen matching rule
  (`benchmark/ground-truth.schema.md`) **before** `govulncheck` was ever run, so the
  rule cannot have been tuned to the result.
- Scorer/rule untouched by this run (no edits to `score.py` or the schema doc).

## Ground truth (independent oracle)

- **Source:** osv.dev `POST /v1/query` per pinned `module@version`
  (`{"package":{"name":<module>,"ecosystem":"Go"},"version":<ver>}`), then per-vuln
  detail via `GET /v1/vulns/<id>`.
- **N = 5** distinct `(module, CVE)` items. GO/GHSA advisories sharing a CVE alias were
  deduplicated to that CVE (the frozen SCA rule matches on CVE id).
- **Scope:** only the three pinned **third-party** modules. The GT is the **FULL
  osv-known set for those modules regardless of reachability** — that is what makes the
  reachability gap visible as honest FN.
- **CVSS / severity:** CVSS v3.1 base score **computed from the vector** in each GHSA
  record (the GO records carry no CVSS); all five are HIGH.

### osv.dev queries → CVE ids found (per module@version)

```
github.com/dgrijalva/jwt-go v3.2.0+incompatible
    -> CVE-2020-26160                     (GO-2020-0017 / GHSA-w73w-5m7g-f7qc)  CVSS 7.5
golang.org/x/text v0.3.0
    -> CVE-2022-32149                     (GO-2022-1059 / GHSA-69ch-w2m2-3vjp)  CVSS 7.5  [reachable]
    -> CVE-2021-38561                     (GO-2021-0113 / GHSA-ppp9-7jff-5vj2)  CVSS 7.5  [reachable]
    -> CVE-2020-14040                     (GO-2020-0015 / GHSA-5rcv-m4m3-hfh7)  CVSS 7.5  [UNREACHABLE]
github.com/gogo/protobuf v1.3.1
    -> CVE-2021-3121                      (GO-2021-0053 / GHSA-c3h9-896r-86jm)  CVSS 8.6  [UNREACHABLE]
```

CVSS base scores were recomputed from the v3.1 vectors (jwt `C:H/I:N/A:N`=7.5;
x/text three `…/A:H`=7.5 each; gogo `C:L/I:L/A:H`=8.6) and match the GHSA-record bands.

## Scanner

- **Tool:** `govulncheck` **v1.3.0** (`go install golang.org/x/vuln/cmd/govulncheck@latest`).
  - Go toolchain: `go1.26.2 windows/amd64`.
  - DB: `https://vuln.go.dev`, "DB updated: 2026-05-29".
- **Invocation:** from the seed dir, `govulncheck -json ./...` (JSON stream captured).
- **Reachability semantics:** `govulncheck -json` emits a stream of `osv` records plus
  `finding` messages; each finding is emitted at one or more **trace levels** (module →
  package → function). A finding with a **function-level trace frame** is *reachable*
  (the vulnerable symbol is actually called); module/package-only frames mean
  *imported/required but not called*. The tool's own text-mode summary states it plainly:

  > "Your code is affected by **3 vulnerabilities** from 2 modules. This scan also found
  > **2 vulnerabilities in packages you import** and **8 vulnerabilities in modules you
  > require**, but your code doesn't appear to call these vulnerabilities."

### Reachable vs imported (scoped to the 3 pinned third-party modules)

| OSV id | CVE | govulncheck classification | in seed GT? |
|--------|-----|----------------------------|-------------|
| GO-2020-0017 | CVE-2020-26160 | **reachable** (function `VerifyAudience`) | TP |
| GO-2022-1059 | CVE-2022-32149 | **reachable** (function `ParseAcceptLanguage`) | TP |
| GO-2021-0113 | CVE-2021-38561 | **reachable** (function `ParseAcceptLanguage`) | TP |
| GO-2020-0015 | CVE-2020-14040 | required, **not called** (module-level only) | **FN** |
| GO-2021-0053 | CVE-2021-3121  | required, **not called** (module-level only) | **FN** |

- **Reachable (third-party, in GT): 3.** **Present-but-unreachable (third-party, in
  GT): 2.**
- govulncheck also surfaced **~150 Go standard-library / toolchain** advisories (net/http,
  crypto/x509, math/big, …) tied to the local `go1.26.2` toolchain. These are a property
  of the toolchain, **not** of the seed's pinned dependencies, and are **out of scope**
  for this seed's GT (see Threats to validity). Only the five third-party
  module CVEs above are scored.

## Transcription to schema v1.1

`benchmark/results/sca-go-01.findings.json` (schema_version `1.1`). One finding per
**reachable** CVE govulncheck reported (GO-id → CVE alias) → **3 findings**. Each:
`file="go.mod"`, `line=<module line>`, `cve=<id>`, `detection="govulncheck"`,
`confidence=90`, `reproduced="n/a"`, severity/CVSS from the osv/GHSA record,
title/detail/recommendation from the osv summary + call trace + fix version. Only
reachable findings are transcribed — the unreachable ones are intentionally left out so
the scorer sees them as the honest FN they are.

## Result — per-category confusion matrix (window N=5, scorer default)

| Category | TP | FN | FP | recall | strict precision | sev-weighted recall |
|----------|----|----|----|--------|------------------|---------------------|
| **SCA**  | 3  | 2  | 0  | **0.600** | **1.000**     | **0.583**           |
| SAST     | 0  | 0  | 0  | n/a    | n/a              | n/a                 |

- Unmatched / needs-adjudication: **0**. Logical (manual review): **0**.
- **recall = 0.600 (< 1.0) by design** — the instrument discriminates on real data.
- sev-weighted recall = `(7.5+7.5+7.5) / (7.5+7.5+7.5+7.5+8.6)` = `22.5/38.6` = **0.583**
  (slightly below raw recall because the heaviest CVE, 8.6, is one of the misses).
- strict precision = 1.000 — every reported finding matched a GT CVE (govulncheck
  emitted no third-party false positive).

### FN list (each root-caused)

| GT | CVE | severity | root_cause |
|----|-----|----------|------------|
| GT-004 | CVE-2020-14040 | HIGH (7.5) | **vuln present but unreachable** — govulncheck reachability filter: the vulnerable `x/text/encoding/unicode`+`transform` symbol is never called (only the `language` package is used). |
| GT-005 | CVE-2021-3121  | HIGH (8.6) | **vuln present but unreachable** — govulncheck reachability filter: the vulnerable `gogo/protobuf/plugin/unmarshal` symbol (code-generator path) is never on a call path; only the benign `proto` runtime helper is called. |

Both are **honest, non-contrived false negatives**: the dependency *is* present and
*is* vulnerable per osv.dev, but govulncheck (correctly, by its own design) does not
flag it as actionable because the seed never exercises the vulnerable code. This is the
coverage gap the seed was built to expose.

### FP / adjudication list

**None.** All three reported findings matched in-GT CVEs (strict precision 1.000). The
~150 Go stdlib/toolchain advisories are not transcribed and are out of scope, so they
create no phantom FP.

## Measured cost

| Metric | Value |
|--------|-------|
| govulncheck wall-clock (`-json ./...`, successful) | **~1.1 s** (1110 ms) |
| osv.dev GT-build queries (3 × `/v1/query` + per-vuln `/v1/vulns`) | a few seconds total, one-off |
| **Model / LLM token cost for the SCA path** | **≈ 0** — govulncheck is a deterministic CLI tool; no model inference in the SCA detection path. (Tokens were spent only on *this orchestration/report*, not on the audit's SCA detection.) |

As with Ф0, the SCA detection path is essentially free in model terms and sub-second in
wall-clock once the scanner is installed.

## Threats to validity

- **Reachability is a DIFFERENT signal than raw listing.** The recall measured here
  (0.600) is **reachable-CVE detection recall against a raw-listing oracle**. The
  GT-vs-reachability gap is a deliberate **property of the tool's design**
  (govulncheck intentionally suppresses unreachable vulns to cut noise), **not a
  defect**. A different scanner that lists all present advisories (e.g. osv-scanner /
  trivy on the same `go.sum`) would likely score ~1.0 here — exactly the Ф0 coverage
  check. The value of this run is that it shows the **instrument is not pinned at 1.0**:
  it reports the honest miss when the scanner's model of "vulnerable" differs from the
  oracle's.
- **Lineage is only partially broken.** govulncheck's DB (`vuln.go.dev`) and osv.dev
  share advisory data upstream, so the *advisory identity* is still common lineage. What
  differs — and what produces the FN — is the **reachability filter govulncheck adds on
  top**. So this is a *reachability* independence, not a fully independent oracle.
- **Single controlled target, one ecosystem (Go).** Three modules, five CVEs. No
  generalization claim. N=1 repo.
- **Known-easy seed.** Versions deliberately old and CVE-rich; not a representative
  project module graph (no large transitive closure, no version-range edge cases).
- **Stdlib/toolchain scope decision.** govulncheck reports ~150 Go-stdlib advisories
  for the local `go1.26.2` toolchain. These were **excluded from GT** because they track
  the developer's Go install, not the seed's pinned dependencies; including them would
  make recall depend on the local toolchain version rather than on the seed. This is a
  defensible scoping choice, documented here and in the GT file, made before scoring.
- **Contamination is N/A** — govulncheck is tool-deterministic, not an LLM recalling
  training data.

## Comparison vs Ф0

Ф0 (`sca-python-01`, pip-audit) scored **1.000/1.000** because GT (osv.dev) and the
scanner (pip-audit, OSV/PyPA-sourced) shared lineage *and* pip-audit lists every present
advisory — so coverage and recall coincided. Ф1 can be **< 1.0** because govulncheck
adds a **reachability filter**: it reports only vulns whose symbols are actually called,
while the GT lists all present ones — so unreachable-but-present vulns become honest FN.
Ф0 was a pipeline + coverage check; Ф1 is a (weak) capability signal showing the scorer
correctly registers a real coverage gap.

## Artifacts

- Seed: `benchmark/seeds/sca-go-01/` (go.mod, go.sum, main.go, ground-truth.yaml, README.md)
- Findings: `benchmark/results/sca-go-01.findings.json`
- Score: `benchmark/results/sca-go-01.score.json`
- This report: `benchmark/results/F1-sca-go-01.md`
- Pre-registration: tag `bench-prereg-sca-go-01` @ `4b1cbcb`
