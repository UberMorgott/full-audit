#!/usr/bin/env python3
"""check_versions.py — maintainer-facing version-drift checker for the full-audit skill.

WHAT THIS IS
  The audit skill pins ~60 tool versions inline across the *.md prompt playbooks.
  `versions.lock` (repo root) mirrors `tools.md` (the canonical source of truth).
  This script reads that lock, queries each tool's LATEST stable version + known CVEs,
  and writes an advisory markdown report to `version-report.md` (repo root).

  It is MAINTAINER-ONLY infra. It does NOT run at audit time, is NOT fetched by the
  skill, and NEVER edits the .md docs. Bumping pins remains a manual human decision.

HOW TO RUN
  python scripts/check_versions.py            # always exits 0; writes version-report.md
  python scripts/check_versions.py --check     # exits 1 if any non-held tool is behind or has a CVE

DEPENDENCIES
  Python 3 standard library only (urllib, json, ...). No pip installs.
  Runs on ubuntu CI and on Windows.

ECOSYSTEMS
  npm, pypi, go, cargo query a real "latest" endpoint.
  nuget queries flat-container index (skips prerelease).
  choco and maven have no clean JSON API here -> reported as "manual: check upstream".
  CVEs come from OSV.dev for npm/pypi/cargo/go/nuget (choco/maven skipped).

SECURITY HOLDS
  A tool may carry `security_hold` in the lock (e.g. trivy: do not bump until 0.70.0).
  Such a tool is NEVER reported as "behind" while latest is inside the held range;
  it is only flagged once latest >= the stated safe-resume version.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK_PATH = os.path.join(REPO_ROOT, "versions.lock")
REPORT_PATH = os.path.join(REPO_ROOT, "version-report.md")

HTTP_TIMEOUT = 15  # seconds per request
USER_AGENT = "full-audit-version-check/1.0 (+maintainer infra; stdlib urllib)"

# ecosystem -> OSV.dev ecosystem name (None = no CVE lookup)
OSV_ECOSYSTEM = {
    "npm": "npm",
    "pypi": "PyPI",
    "cargo": "crates.io",
    "go": "Go",
    "nuget": "NuGet",
    "choco": None,
    "maven": None,
}


# --------------------------------------------------------------------------- #
# Minimal YAML reader for the known-flat versions.lock schema.
# Supports: a top-level `tools:` list of mappings; scalar `key: value` lines;
# inline flow lists `key: [a, b, c]`. No anchors, no nested mappings.
# --------------------------------------------------------------------------- #
def parse_lock(path):
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    tools = []
    current = None
    in_tools = False

    for raw in lines:
        # strip trailing newline; drop full-line comments and blanks
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped == "tools:" and not line.startswith(" "):
            in_tools = True
            continue
        if not in_tools:
            continue

        # A new tool entry begins with "- " (after indentation).
        m_item = re.match(r"^\s*-\s+(.*)$", line)
        if m_item:
            if current is not None:
                tools.append(current)
            current = {}
            rest = m_item.group(1).strip()
            _assign_kv(current, rest)
            continue

        # Continuation key under the current item.
        if current is not None:
            _assign_kv(current, stripped)

    if current is not None:
        tools.append(current)
    return tools


def _assign_kv(target, kv):
    if ":" not in kv:
        return
    key, _, val = kv.partition(":")
    key = key.strip()
    val = val.strip()
    if not key:
        return
    target[key] = _parse_scalar_or_list(val)


def _parse_scalar_or_list(val):
    if val == "":
        return ""
    # inline flow list: [a, b, c]
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [_strip_quotes(p.strip()) for p in inner.split(",") if p.strip()]
    return _strip_quotes(val)


def _strip_quotes(s):
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"User-Agent": USER_AGENT,
                 "Content-Type": "application/json",
                 "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --------------------------------------------------------------------------- #
# Version helpers
# --------------------------------------------------------------------------- #
def _version_tuple(v):
    """Return a tuple of the leading numeric components for a rough compare."""
    v = str(v).lstrip("vV").strip()
    parts = re.split(r"[.\-+]", v)
    nums = []
    for p in parts:
        if p.isdigit():
            nums.append(int(p))
        else:
            # stop at first non-numeric segment (e.g. 'rc1', 'beta')
            break
    return tuple(nums) if nums else (0,)


def _is_behind(pinned, latest):
    if not latest:
        return False
    return _version_tuple(latest) > _version_tuple(pinned)


def _is_prerelease(v):
    return bool(re.search(r"(?i)(a|b|rc|alpha|beta|dev|pre)\d*", str(v).split("+")[0].split("-", 1)[-1])) \
        and not str(v).replace(".", "").isdigit()


# --------------------------------------------------------------------------- #
# Latest-version lookups per ecosystem
# --------------------------------------------------------------------------- #
def latest_npm(tool):
    data = _get_json("https://registry.npmjs.org/%s/latest" % tool["install_id"])
    return data.get("version")


def latest_pypi(tool):
    data = _get_json("https://pypi.org/pypi/%s/json" % tool["install_id"])
    return data.get("info", {}).get("version")


def latest_go(tool):
    mod = tool["install_id"].lower()
    data = _get_json("https://proxy.golang.org/%s/@latest" % mod)
    ver = data.get("Version", "")
    return ver.lstrip("v") if ver else None


def latest_cargo(tool):
    data = _get_json("https://crates.io/api/v1/crates/%s" % tool["install_id"])
    crate = data.get("crate", {})
    return crate.get("max_stable_version") or crate.get("max_version")


def latest_nuget(tool):
    pkg = tool["install_id"].lower()
    data = _get_json("https://api.nuget.org/v3-flatcontainer/%s/index.json" % pkg)
    versions = [v for v in data.get("versions", []) if not _is_prerelease(v)]
    return versions[-1] if versions else None


LATEST_FUNCS = {
    "npm": latest_npm,
    "pypi": latest_pypi,
    "go": latest_go,
    "cargo": latest_cargo,
    "nuget": latest_nuget,
}


# --------------------------------------------------------------------------- #
# CVE lookup via OSV.dev
# --------------------------------------------------------------------------- #
def query_cves(tool):
    osv_eco = OSV_ECOSYSTEM.get(tool["ecosystem"])
    if not osv_eco:
        return []
    # For Go, OSV expects the module path as the package name.
    name = tool["install_id"]
    payload = {
        "package": {"ecosystem": osv_eco, "name": name},
        "version": str(tool["version"]),
    }
    data = _post_json("https://api.osv.dev/v1/query", payload)
    vulns = data.get("vulns", []) or []
    return [v.get("id", "?") for v in vulns]


# --------------------------------------------------------------------------- #
# Security-hold handling
# --------------------------------------------------------------------------- #
def _safe_resume_version(hold_text):
    """Extract the 'do NOT bump until X.Y.Z' resume version from a hold note."""
    if not hold_text:
        return None
    m = re.search(r"until\s+v?(\d+\.\d+(?:\.\d+)?)", str(hold_text))
    if m:
        return m.group(1)
    return None


# --------------------------------------------------------------------------- #
# Per-tool evaluation
# --------------------------------------------------------------------------- #
def evaluate(tool):
    result = {
        "name": tool.get("name", "?"),
        "ecosystem": tool.get("ecosystem", "?"),
        "pinned": str(tool.get("version", "?")),
        "latest": None,
        "behind": False,
        "cves": [],
        "security_hold": tool.get("security_hold"),
        "note": tool.get("note"),
        "status": "ok",        # ok | manual | check-failed
        "messages": [],
    }

    eco = tool.get("ecosystem")

    # 1) latest version
    if eco in LATEST_FUNCS:
        try:
            result["latest"] = LATEST_FUNCS[eco](tool)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                ValueError, KeyError, OSError) as exc:
            result["status"] = "check-failed"
            result["messages"].append("latest lookup failed: %s" % exc)
    else:
        result["status"] = "manual"
        result["messages"].append("manual: check upstream registry for %s" % eco)

    # 2) behind? (respect security hold)
    if result["latest"]:
        behind = _is_behind(result["pinned"], result["latest"])
        if behind and result["security_hold"]:
            resume = _safe_resume_version(result["security_hold"])
            if resume and _version_tuple(result["latest"]) < _version_tuple(resume):
                # latest is still inside the held range -> NOT behind
                behind = False
                result["messages"].append(
                    "held: latest %s < safe-resume %s -> not flagged"
                    % (result["latest"], resume))
            elif resume:
                result["messages"].append(
                    "HOLD CLEARED: latest %s >= safe-resume %s -> bump now allowed"
                    % (result["latest"], resume))
        result["behind"] = behind

    # 3) CVEs
    if eco in LATEST_FUNCS or OSV_ECOSYSTEM.get(eco):
        try:
            result["cves"] = query_cves(tool)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                ValueError, KeyError, OSError) as exc:
            # don't downgrade a successful latest lookup; just note CVE failure
            result["messages"].append("CVE lookup failed: %s" % exc)
            if result["status"] == "ok":
                result["status"] = "check-failed"

    return result


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report(results):
    behind = [r for r in results if r["behind"]]
    cve_hits = [r for r in results if r["cves"]]
    held = [r for r in results if r["security_hold"]]
    manual = [r for r in results if r["status"] == "manual"]
    failed = [r for r in results if r["status"] == "check-failed"]

    lines = []
    lines.append("# Version-drift report")
    lines.append("")
    lines.append("> Advisory only. Generated by `scripts/check_versions.py` from "
                 "`versions.lock` (which mirrors `tools.md`).")
    lines.append("> A human reviews this and bumps the inline `*.md` pins manually. "
                 "This report does NOT edit any skill docs.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("- Tools checked: **%d**" % len(results))
    lines.append("- Behind (non-held): **%d**" % len(behind))
    lines.append("- With CVE hits: **%d**" % len(cve_hits))
    lines.append("- Security holds: **%d**" % len(held))
    lines.append("- Manual ecosystems (choco/maven): **%d**" % len(manual))
    lines.append("- Check failed (network/lookup): **%d**" % len(failed))
    lines.append("")

    lines.append("## All tools")
    lines.append("")
    lines.append("| Tool | Eco | Pinned | Latest | Behind? | CVEs | Notes |")
    lines.append("|------|-----|--------|--------|---------|------|-------|")
    for r in sorted(results, key=lambda x: (x["ecosystem"], x["name"].lower())):
        latest = r["latest"] or ("manual" if r["status"] == "manual"
                                 else ("FAILED" if r["status"] == "check-failed" else "?"))
        behind_mark = "**YES**" if r["behind"] else "no"
        cves = ", ".join(r["cves"]) if r["cves"] else "-"
        notes = []
        if r["security_hold"]:
            notes.append("HOLD: %s" % r["security_hold"])
        if r["note"]:
            notes.append(r["note"])
        notes.extend(r["messages"])
        note_txt = " ; ".join(notes).replace("|", "\\|") if notes else ""
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            r["name"], r["ecosystem"], r["pinned"], latest, behind_mark, cves, note_txt))
    lines.append("")

    if behind:
        lines.append("## Behind (non-held) — review for bump")
        lines.append("")
        for r in sorted(behind, key=lambda x: x["name"].lower()):
            lines.append("- **%s** (%s): pinned `%s` -> latest `%s`"
                         % (r["name"], r["ecosystem"], r["pinned"], r["latest"]))
        lines.append("")

    if cve_hits:
        lines.append("## CVE hits — investigate")
        lines.append("")
        for r in sorted(cve_hits, key=lambda x: x["name"].lower()):
            lines.append("- **%s** (%s) pinned `%s`: %s"
                         % (r["name"], r["ecosystem"], r["pinned"], ", ".join(r["cves"])))
        lines.append("")

    if held:
        lines.append("## Security holds")
        lines.append("")
        for r in sorted(held, key=lambda x: x["name"].lower()):
            lines.append("- **%s** pinned `%s`: %s (latest seen: `%s`)"
                         % (r["name"], r["pinned"], r["security_hold"], r["latest"] or "n/a"))
        lines.append("")

    if manual:
        lines.append("## Manual-check ecosystems")
        lines.append("")
        for r in sorted(manual, key=lambda x: x["name"].lower()):
            hint = ("community.chocolatey.org" if r["ecosystem"] == "choco"
                    else "central.sonatype.com / mvnrepository.com")
            lines.append("- **%s** (%s) pinned `%s` — check %s"
                         % (r["name"], r["ecosystem"], r["pinned"], hint))
        lines.append("")

    if failed:
        lines.append("## Check failed")
        lines.append("")
        for r in sorted(failed, key=lambda x: x["name"].lower()):
            lines.append("- **%s** (%s): %s"
                         % (r["name"], r["ecosystem"], " ; ".join(r["messages"]) or "unknown error"))
        lines.append("")

    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv=None):
    parser = argparse.ArgumentParser(description="Maintainer version-drift checker (advisory).")
    parser.add_argument("--check", action="store_true",
                        help="Exit 1 if any non-held tool is behind or has a CVE (optional gating).")
    args = parser.parse_args(argv)

    if not os.path.exists(LOCK_PATH):
        sys.stderr.write("ERROR: versions.lock not found at %s\n" % LOCK_PATH)
        return 0  # report is the artifact; do not hard-fail CI on a missing lock here

    try:
        tools = parse_lock(LOCK_PATH)
    except Exception as exc:  # noqa: BLE001 - resilience over purity
        sys.stderr.write("ERROR: failed to parse versions.lock: %s\n" % exc)
        return 0

    results = []
    for tool in tools:
        if not tool.get("name"):
            continue
        try:
            results.append(evaluate(tool))
        except Exception as exc:  # noqa: BLE001 - never crash the whole run on one tool
            results.append({
                "name": tool.get("name", "?"),
                "ecosystem": tool.get("ecosystem", "?"),
                "pinned": str(tool.get("version", "?")),
                "latest": None, "behind": False, "cves": [],
                "security_hold": tool.get("security_hold"), "note": tool.get("note"),
                "status": "check-failed", "messages": ["unexpected error: %s" % exc],
            })

    report = render_report(results)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write(report)

    behind = sum(1 for r in results if r["behind"])
    cves = sum(1 for r in results if r["cves"])
    failed = sum(1 for r in results if r["status"] == "check-failed")
    print("version-check: %d tools | %d behind (non-held) | %d CVE | %d check-failed | report -> %s"
          % (len(results), behind, cves, failed, os.path.basename(REPORT_PATH)))

    if args.check and (behind > 0 or cves > 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
