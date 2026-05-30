# Infrastructure & CI Audit (infra.md)

> Fetch when any of these are present: `Dockerfile`, `docker-compose.y*ml`,
> `*.tf` / `*.tfvars`, `k8s/*.y*ml` / Kubernetes manifests, `.github/workflows/*.y*ml`.
> Language-agnostic. Pairs with `universal.md` for secrets/supply-chain checks.

## Tools (pin via tools.md integrity protocol; record in versions.lock)

| Target            | Tool          | Pin            | Purpose                                          |
|-------------------|---------------|----------------|--------------------------------------------------|
| Dockerfile        | hadolint      | `2.14.0`       | Dockerfile lint + best practices                 |
| IaC / config      | trivy config  | `0.69.3`       | Misconfig scan (Docker/K8s/TF)                   |
| IaC / config      | checkov       | `3.2.530`      | Policy-as-code misconfig                         |
| Terraform         | tfsec         | `1.28.14`      | Terraform-specific security (deprecated → Trivy) |
| Kubernetes        | kube-linter   | `0.8.3`        | K8s manifest correctness/security                |
| GitHub Actions    | actionlint    | `1.7.12`       | Workflow syntax + shell lint                     |
| GitHub Actions    | zizmor        | `1.25.2`       | Actions supply-chain/security                    |

> `skip_if: no_tool(name)` per tool. `skip_if: windows` only where a tool ships
> Unix-only; prefer container/cross-platform builds otherwise.

## Level 1 — quick (lint + obvious)

- `hadolint Dockerfile` — fail on DL3008/DL3018 (unpinned apt/apk), DL3002 (USER root),
  missing `USER` directive, `ADD` of remote URLs.
  > skip_if: no_tool(hadolint)
- `actionlint` — workflow syntax, shellcheck inside `run:` steps.
  > skip_if: no_tool(actionlint)
- Base image freshness: flag `:latest` and digest-less image refs in Dockerfiles
  and compose files.
- Action pinning: flag `uses:` referencing a mutable tag/branch instead of a
  full commit SHA (supply-chain risk).

## Level 2 — full (misconfig + image SCA)

- `trivy config .` — Docker/K8s/Terraform misconfig across the tree.
  > skip_if: no_tool(trivy)
- `checkov -d .` — policy violations; cross-check against trivy (dedupe overlaps).
  > skip_if: no_tool(checkov)
- `tfsec .` if Terraform present — OPTIONAL deprecated second opinion (tfsec is in
  maintenance, consolidated into Trivy; `trivy config` / `checkov` above are the
  primary Terraform scanners). Surfaces open security groups, public buckets,
  unencrypted storage, plaintext secrets in `*.tfvars` not already flagged above.
  > skip_if: no_tool(tfsec)
- `kube-linter lint <manifests>` if K8s present — missing resource limits,
  `privileged: true`, host network/PID, missing readiness/liveness probes.
  > skip_if: no_tool(kube-linter)
- Image SCA: `trivy image <built-image>` if an image is built in this repo, OR
  `trivy fs .` for filesystem-level dependency CVEs (no build needed). Universal
  lockfile SCA is `osv-scanner` (README waste-scanner step 0); if it is missing,
  these `trivy` scans + per-stack vuln tools cover their own scope — note any
  remaining cross-ecosystem gap under Audit Limitations.
- Secrets in infra files: defer to `universal.md` gitleaks pass; here, manually
  flag inline credentials in compose `environment:`, Dockerfile `ENV`, `*.tfvars`.

## Level 3 — deep (privilege, network, supply chain)

- `zizmor .github/workflows/` — template injection, excessive `GITHUB_TOKEN`
  permissions, dangerous `pull_request_target`, unpinned third-party actions.
  > skip_if: no_tool(zizmor)
- Least-privilege review: every workflow sets explicit `permissions:` (deny by
  default); no `permissions: write-all`.
- Container hardening: non-root `USER`, read-only root FS where viable, dropped
  Linux capabilities, no `--privileged`, multi-stage builds (no build secrets in
  final layer), `.dockerignore` excludes `.git`/secrets.
- Network exposure: compose/K8s — no unnecessary published ports, no `0.0.0.0`
  binds for internal services, no `hostNetwork`.
- Terraform state & drift: remote state with locking, no secrets in state,
  `terraform validate` clean.
- Supply chain: pinned base image digests, pinned action SHAs, renovate/dependabot
  present for both.

## Finding format

Use the repo's standard one-line finding format. Examples:

`Dockerfile:12: 🔴 CRITICAL: runs as root (no USER). add non-root USER before CMD.`
`.github/workflows/ci.yml:8: 🟡 HIGH: actions/checkout@v4 mutable tag. pin to full commit SHA.`
`k8s/deploy.yaml:23: 🟡 HIGH: no resource limits. set requests/limits to prevent noisy-neighbor.`

## Stack command mapping (for the README table)

| Detected                       | Lint/Scan (L1)        | Misconfig (L2)        |
|--------------------------------|-----------------------|-----------------------|
| `Dockerfile`                   | `hadolint Dockerfile` | `trivy config .`      |
| `.github/workflows/*`          | `actionlint`          | `zizmor` (L3)         |
| `*.tf`                         | —                     | `tfsec .` / `checkov` |
| K8s manifests                  | —                     | `kube-linter lint`    |
