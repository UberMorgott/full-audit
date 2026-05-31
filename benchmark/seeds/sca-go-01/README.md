# Seed: sca-go-01 (controlled SCA lineage-break benchmark)

This is a **controlled benchmark seed for the full-audit SCA path**, designed to break
the OSV-circularity of the Python seed (`sca-python-01`) and produce a **recall < 1.0**
data point on real tooling.

**Why this exists.** `sca-python-01` scored 1.000/1.000 because its ground truth
(osv.dev) and its scanner (pip-audit) share the same OSV/PyPA advisory lineage — the
result was a pipeline + coverage check, not an independent capability signal. This seed
uses a scanner on a **different signal**: `govulncheck`, which performs
**reachability analysis** — it lists a vulnerability as actionable only if the
vulnerable *symbol* is actually on a call path from the seed's code.

**The lineage break.** The ground truth (`ground-truth.yaml`) is the **full set of
CVEs osv.dev reports** for the three pinned modules, *regardless of reachability*. The
seed (`main.go`) is built so that:

- **Some** vulnerable symbols are genuinely **called** (reachable) → govulncheck
  reports them:
  - `github.com/dgrijalva/jwt-go` `MapClaims.VerifyAudience` (CVE-2020-26160)
  - `golang.org/x/text/language` `ParseAcceptLanguage` (CVE-2022-32149 **and**
    CVE-2021-38561 — both advisories list that symbol)
- **Some** pinned-vulnerable modules are **imported but their vulnerable symbol is
  NOT called** (unreachable) → govulncheck stays silent → **honest false negative**:
  - `golang.org/x/text` encoding/transform path (CVE-2020-14040) — only the
    `language` package is used.
  - `github.com/gogo/protobuf` `plugin/unmarshal` (CVE-2021-3121) — only the benign
    `proto` runtime helper is called.

So **recall < 1.0 is expected by design**, root-caused to govulncheck's reachability
filter — a genuine, non-contrived coverage gap, not a tool defect.

- **Scanner:** `govulncheck` (DB `vuln.go.dev`), reachability-filtered.
- **Ground truth:** osv.dev `/v1/query` (Go ecosystem) per pinned `module@version`,
  deduplicated to distinct CVE ids; CVSS from the GHSA record vector.
- **Scope:** only the three pinned **third-party** modules. Go stdlib/toolchain vulns
  that govulncheck also reports are a property of the local Go toolchain, not of these
  dependencies, and are out of scope for this seed's GT (see the F1 report).
- GT + the frozen matching rule were committed and git-tagged
  (`bench-prereg-sca-go-01`) **before** govulncheck was run, so the rule cannot have
  been tuned to the result.

`go build ./...` passes. This is not a real application — it exists only to exercise
the SCA pipeline and produce objective recall/precision numbers.
