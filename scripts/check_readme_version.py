#!/usr/bin/env python3
r"""check_readme_version.py — README/CHANGELOG version-string consistency gate.

WHAT THIS IS
  A fast "step 0" CI gate that catches a FORGOTTEN version bump: when a release
  touches some version mentions but misses others. The full-audit skill ships as
  markdown prompt playbooks; the README repeats the release version in several
  human-readable spots and the CHANGELOG carries it as its top entry. Those must
  all agree, or a consumer pins / fetches the wrong tag.

  SOURCE OF TRUTH = the CHANGELOG's top `## [X.Y.Z]` entry. We prefer this over the
  git tag because, at release time, the version-bump commit lands BEFORE the tag is
  pushed; gating on the in-repo CHANGELOG avoids that push-ordering race on normal
  main-push CI runs.

WHAT IT CHECKS (all must equal the CHANGELOG top version)
  1. README header           : `> **Version X.Y.Z**`
  2. README "currently" tag   : ...redirects to the newest tag (currently `vX.Y.Z`)
  3. README "e.g." example tag(s): ...resolved tag (e.g. `vX.Y.Z`) ...
     (only the `e.g. \`vX.Y.Z\`` form — a bare "e.g." in prose is ignored; the
      literal `<release-tag>` placeholder is never a version and is never flagged)

  TAG MODE (opt-in): when GITHUB_REF_TYPE=tag (set by GitHub Actions on a tag push)
  or `--tag <tag>` is passed, ALSO assert the resolved version equals the git tag
  (leading `v` stripped). Normal main-push runs only do internal consistency.

HOW TO RUN
  python scripts/check_readme_version.py            # internal consistency only
  python scripts/check_readme_version.py --tag v1.10.4   # also assert == tag
  GITHUB_REF_TYPE=tag GITHUB_REF_NAME=v1.10.4 python scripts/check_readme_version.py

  Exit 1 on any mismatch (with a clear message naming the values + locations),
  exit 0 when everything agrees.

  MAINTAINER-ONLY infra. Read-only — it never edits the docs.

DEPENDENCIES
  Python 3 standard library only. Runs on Windows and on ubuntu CI (no pip installs).
"""

import argparse
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(REPO_ROOT, "README.md")
CHANGELOG_PATH = os.path.join(REPO_ROOT, "CHANGELOG.md")

_VER = r"\d+\.\d+\.\d+"

# Source of truth: the CHANGELOG's first `## [X.Y.Z]` heading.
_CHANGELOG_TOP = re.compile(r"^\#{1,3}\s*\[v?(" + _VER + r")\]")

# README header: `> **Version X.Y.Z**`
_README_HEADER = re.compile(r"\*\*Version\s+(" + _VER + r")\*\*")

# README "currently `vX.Y.Z`" — anchored on the surrounding prose, not a line number.
_CURRENTLY_TAG = re.compile(r"currently\s+`v(" + _VER + r")`")

# README "e.g. `vX.Y.Z`" example tag — only the backticked vX.Y.Z form is a version.
# A bare "e.g." in prose (no backticked vX.Y.Z) and the `<release-tag>` placeholder
# are not matched, so they are never flagged.
_EG_TAG = re.compile(r"e\.g\.\s+`v(" + _VER + r")`")


def read_lines(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read().split("\n")


def _first_match(lines, pattern):
    """Return (version, lineno) for the first line matching pattern, else (None, None)."""
    for lineno, raw in enumerate(lines, 1):
        m = pattern.search(raw)
        if m:
            return m.group(1), lineno
    return None, None


def _all_matches(lines, pattern):
    """Return a list of (version, lineno) for every line matching pattern."""
    out = []
    for lineno, raw in enumerate(lines, 1):
        for m in pattern.finditer(raw):
            out.append((m.group(1), lineno))
    return out


def collect(errors):
    """Gather every version mention as (label, version, 'file:line'). Records a
    hard error for any required mention that is missing entirely."""
    found = []  # (label, version, location)

    changelog = read_lines(CHANGELOG_PATH)
    cv, cl = _first_match(changelog, _CHANGELOG_TOP)
    if cv is None:
        errors.append("CHANGELOG.md: no top '## [X.Y.Z]' version entry found "
                      "(this is the source of truth)")
    else:
        found.append(("CHANGELOG top entry", cv, "CHANGELOG.md:%d" % cl))

    readme = read_lines(README_PATH)

    hv, hl = _first_match(readme, _README_HEADER)
    if hv is None:
        errors.append("README.md: no '> **Version X.Y.Z**' header found")
    else:
        found.append(("README header", hv, "README.md:%d" % hl))

    curv, curl = _first_match(readme, _CURRENTLY_TAG)
    if curv is None:
        errors.append("README.md: no \"currently `vX.Y.Z`\" tag mention found")
    else:
        found.append(("README \"currently\" tag", curv, "README.md:%d" % curl))

    eg = _all_matches(readme, _EG_TAG)
    if not eg:
        errors.append("README.md: no \"e.g. `vX.Y.Z`\" example tag found")
    else:
        for i, (ev, el) in enumerate(eg, 1):
            label = "README \"e.g.\" example tag" + ("" if len(eg) == 1 else " #%d" % i)
            found.append((label, ev, "README.md:%d" % el))

    return found


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="README/CHANGELOG version-string consistency gate.")
    parser.add_argument(
        "--tag", metavar="TAG",
        help="Also assert the resolved version equals this git tag (leading 'v' "
             "stripped). On GitHub Actions this is taken from GITHUB_REF_NAME when "
             "GITHUB_REF_TYPE=tag.")
    args = parser.parse_args(argv)

    # Tag mode is opt-in: explicit --tag, or a tag-triggered Actions run.
    tag = args.tag
    if tag is None and os.environ.get("GITHUB_REF_TYPE") == "tag":
        tag = os.environ.get("GITHUB_REF_NAME")

    errors = []
    found = collect(errors)

    if errors:
        print("check_readme_version: FAIL")
        for msg in errors:
            print("  [missing] %s" % msg)
        return 1

    # All mentions present — verify they agree with the CHANGELOG source of truth.
    truth_label, truth_ver, truth_loc = found[0]  # CHANGELOG top is first
    mismatches = [(lbl, ver, loc) for (lbl, ver, loc) in found
                  if ver != truth_ver]

    if mismatches:
        print("check_readme_version: FAIL")
        print("  version mismatch — source of truth is %s = %s (%s)"
              % (truth_label, truth_ver, truth_loc))
        for lbl, ver, loc in mismatches:
            print("    [mismatch] %s = %s (%s) != %s"
                  % (lbl, ver, loc, truth_ver))
        return 1

    # Optional tag assertion (release / tag-triggered runs only).
    if tag:
        tag_ver = tag[1:] if tag[:1] in ("v", "V") else tag
        if tag_ver != truth_ver:
            print("check_readme_version: FAIL")
            print("  git tag %s (= %s) does not match the resolved repo version %s (%s)"
                  % (tag, tag_ver, truth_ver, truth_loc))
            return 1

    detail = ", ".join("%s=%s" % (lbl, ver) for (lbl, ver, _loc) in found)
    tag_note = " ; tag %s OK" % tag if tag else ""
    print("check_readme_version: PASS — all version mentions agree on %s%s"
          % (truth_ver, tag_note))
    print("  checked: %s" % detail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
