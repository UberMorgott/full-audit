#!/usr/bin/env python3
"""lint_docs.py — maintainer-facing self-test / CI linter for the full-audit skill docs.

WHAT THIS IS
  The full-audit skill ships as a set of markdown "prompt playbooks" (README.md,
  universal.md, tools.md, the per-stack guides, CHANGELOG.md). There is NO executable
  app to test — the docs ARE the product. This linter catches the small set of bug
  classes that historically slipped through and had to be caught by hand:

    1. Broken cross-references to other *.md files.
    2. Unbalanced ``` code fences (an odd fence count = a runaway block).
    3. Version drift between README's headline version and the top CHANGELOG entry.
    4. Markdown tables whose body rows don't match the header column count.
    5. Tool-version-pin drift between versions.lock and the inline pins in the docs.

HOW TO RUN
  python scripts/lint_docs.py        # exit 1 if any ERROR, 0 otherwise (WARNINGs don't fail)

  MAINTAINER-ONLY infra. It is NOT fetched or run by the audit skill at runtime, and it
  NEVER edits the skill docs — it only reads them and reports findings.

DEPENDENCIES
  Python 3 standard library only. Runs on Windows and on ubuntu CI (no pip installs).
"""

import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK_PATH = os.path.join(REPO_ROOT, "versions.lock")

# The skill docs this linter is responsible for.
DOC_FILES = [
    "README.md", "universal.md", "tools.md", "api-audit.md", "go.md",
    "frontend.md", "python.md", "rust.md", "java.md", "csharp.md",
    "infra.md", "CHANGELOG.md",
]

# Ecosystems whose pin formatting is loose enough that a drift "miss" is only a WARNING.
LOOSE_ECOSYSTEMS = {"choco", "maven"}

# *.md names that the docs intentionally reference but that are NOT repo docs:
#   - CLAUDE.md       : the USER'S project rules file the audit skill reads at runtime.
#   - audit-filtered.md / audit-report.md : runtime audit OUTPUT artifacts (uncommitted).
# These are legitimate mentions, not broken cross-refs, so they are whitelisted.
EXTERNAL_MD_REFS = {"claude.md", "audit-filtered.md", "audit-report.md"}


# --------------------------------------------------------------------------- #
# Finding collection
# --------------------------------------------------------------------------- #
class Findings:
    def __init__(self):
        self.errors = []    # list of (check, message)
        self.warnings = []  # list of (check, message)

    def error(self, check, message):
        self.errors.append((check, message))

    def warning(self, check, message):
        self.warnings.append((check, message))


def read_lines(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read().split("\n")


# --------------------------------------------------------------------------- #
# Inline-code masking — blank out `...` backtick spans so their contents
# (pipes, ``` lookalikes, "foo.md") don't trip the table / link checks.
# We replace span interiors with spaces to preserve column positions.
# --------------------------------------------------------------------------- #
def mask_inline_code(line):
    out = []
    i = 0
    n = len(line)
    while i < n:
        if line[i] == "`":
            # Determine run length of backticks (delimiter length).
            j = i
            while j < n and line[j] == "`":
                j += 1
            delim = "`" * (j - i)  # the opening backtick run
            # Find a matching closing run of the same length.
            close = line.find(delim, j)
            if close == -1:
                # No closing delimiter on this line — leave the rest as-is.
                out.append(line[i:])
                i = n
                break
            # Keep the delimiters, blank the interior.
            out.append(delim)
            out.append(" " * (close - j))
            out.append(delim)
            i = close + len(delim)
        else:
            out.append(line[i])
            i += 1
    return "".join(out)


# --------------------------------------------------------------------------- #
# CHECK 1 — cross-reference links to other *.md files
# --------------------------------------------------------------------------- #
# Any token ending in `.md` is a candidate reference. We resolve it against the
# repo. Skip URLs (raw.githubusercontent / github.com paths) and anchors.
_MD_TOKEN = re.compile(r"([A-Za-z0-9_./-]+\.md)")


def check_cross_refs(doc_lines, findings):
    existing = {f for f in os.listdir(REPO_ROOT) if f.lower().endswith(".md")}
    # Also allow any *.md that physically exists (case-insensitive on Windows).
    existing_lower = {f.lower() for f in existing}

    for fname, lines in doc_lines.items():
        for lineno, raw in enumerate(lines, 1):
            line = mask_inline_code(raw)
            for m in _MD_TOKEN.finditer(line):
                ref = m.group(1)
                # Strip a markdown-link wrapper / anchor / query if present.
                ref = ref.split("#", 1)[0].split("?", 1)[0]
                if not ref.lower().endswith(".md"):
                    continue
                # Skip remote URLs — a ".md" inside an http(s) URL is not a local ref.
                ctx_start = max(0, m.start() - 8)
                if "http" in line[ctx_start:m.start()]:
                    continue
                if "://" in line[:m.start()] and "/" in ref and ref.count("/") > 0:
                    # heuristic: looks like a URL path segment
                    if "github" in line.lower() or "http" in line.lower():
                        continue
                base = os.path.basename(ref)
                if base.lower() in EXTERNAL_MD_REFS:
                    continue  # runtime/project file, not a repo doc cross-ref
                if base.lower() in existing_lower:
                    continue
                # Resolve relative to repo root too.
                if os.path.isfile(os.path.join(REPO_ROOT, ref)):
                    continue
                findings.error(
                    "cross-ref",
                    f"{fname}:{lineno}: broken doc reference -> '{ref}' "
                    f"(no such .md in repo)",
                )


# --------------------------------------------------------------------------- #
# CHECK 2 — code-fence balance
# A fence line is one whose stripped content STARTS with ``` (``` or ```lang).
# An odd count over the file means a block was left open.
# --------------------------------------------------------------------------- #
def check_fences(doc_lines, findings):
    for fname, lines in doc_lines.items():
        count = 0
        for raw in lines:
            if raw.strip().startswith("```"):
                count += 1
        if count % 2 != 0:
            findings.error(
                "code-fence",
                f"{fname}: unbalanced code fences — {count} ``` lines (odd = a block "
                f"is left open)",
            )


# --------------------------------------------------------------------------- #
# CHECK 3 — version consistency (README headline vs top CHANGELOG entry vs any
# "Version X.Y.Z" header carried by another doc)
# --------------------------------------------------------------------------- #
_README_VER = re.compile(r"\*\*Version\s+(\d+\.\d+\.\d+)\*\*")
_CHANGELOG_VER = re.compile(r"^\#{1,3}\s*\[?v?(\d+\.\d+\.\d+)\]?")
_HEADER_VER = re.compile(r"(?:^|[^.\d])Version\s+(\d+\.\d+\.\d+)")


def _first_match(lines, pattern):
    for lineno, raw in enumerate(lines, 1):
        m = pattern.search(raw)
        if m:
            return m.group(1), lineno
    return None, None


def check_version_consistency(doc_lines, findings):
    versions = {}  # label -> (version, "file:line")

    readme = doc_lines.get("README.md", [])
    rv, rl = _first_match(readme, _README_VER)
    if rv:
        versions["README.md headline"] = (rv, f"README.md:{rl}")
    else:
        findings.error("version", "README.md: no '**Version X.Y.Z**' headline found")

    changelog = doc_lines.get("CHANGELOG.md", [])
    cv, cl = _first_match(changelog, _CHANGELOG_VER)
    if cv:
        versions["CHANGELOG.md top entry"] = (cv, f"CHANGELOG.md:{cl}")
    else:
        findings.error("version", "CHANGELOG.md: no top '## [X.Y.Z]' version entry found")

    # Any other doc that carries an explicit "Version X.Y.Z" header line near the top.
    for fname, lines in doc_lines.items():
        if fname in ("README.md", "CHANGELOG.md"):
            continue
        for lineno, raw in enumerate(lines[:15], 1):  # only the header region
            m = _HEADER_VER.search(raw)
            if m:
                versions[f"{fname} header"] = (m.group(1), f"{fname}:{lineno}")
                break

    distinct = {v for (v, _loc) in versions.values()}
    if len(distinct) > 1:
        detail = "; ".join(
            f"{label}={ver} ({loc})" for label, (ver, loc) in sorted(versions.items())
        )
        findings.error("version", f"version mismatch across docs: {detail}")


# --------------------------------------------------------------------------- #
# CHECK 4 — table column consistency
# A table = a header row containing '|', followed by a separator row whose cells
# are all dashes (---). Body rows must match the header's column count.
# Inline code spans are masked first so a '|' inside `code` is ignored.
# --------------------------------------------------------------------------- #
def _split_cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return s.split("|")


def _is_separator(line):
    cells = _split_cells(line)
    if not cells:
        return False
    for c in cells:
        c = c.strip()
        if not c:
            return False
        if not re.fullmatch(r":?-{1,}:?", c):
            return False
    return True


def check_tables(doc_lines, findings):
    for fname, lines in doc_lines.items():
        in_fence = False
        i = 0
        n = len(lines)
        while i < n:
            raw = lines[i]
            if raw.strip().startswith("```"):
                in_fence = not in_fence
                i += 1
                continue
            if in_fence:
                i += 1
                continue

            masked = mask_inline_code(raw)
            # A header row: contains a pipe, and the NEXT line is a separator row.
            if "|" in masked and i + 1 < n and not lines[i + 1].strip().startswith("```"):
                sep_masked = mask_inline_code(lines[i + 1])
                if "|" in sep_masked and _is_separator(sep_masked):
                    header_cols = len(_split_cells(masked))
                    # Walk body rows until a non-table line.
                    j = i + 2
                    reported = False
                    while j < n:
                        body_raw = lines[j]
                        if body_raw.strip().startswith("```"):
                            break
                        body_masked = mask_inline_code(body_raw)
                        if "|" not in body_masked or not body_masked.strip():
                            break
                        body_cols = len(_split_cells(body_masked))
                        if body_cols != header_cols and not reported:
                            findings.error(
                                "table",
                                f"{fname}:{j + 1}: table row has {body_cols} columns, "
                                f"header has {header_cols}",
                            )
                            reported = True
                        j += 1
                    i = j
                    continue
            i += 1


# --------------------------------------------------------------------------- #
# CHECK 5 — versions.lock <-> docs pin drift
#
# Minimal stdlib YAML reader for the known flat schema, then for each tool/file:
#   - PASS  if the normalized pinned version appears in that file (pin present & correct).
#   - DRIFT if the file pins the SAME tool to a DIFFERENT version (the bug class we hunt):
#       ERROR for npm/pypi/go/cargo/nuget, WARNING for choco/maven (loose formatting).
#   - SKIP  if the file merely references the tool without pinning any version
#       (e.g. `semgrep --config=auto` in a stack guide) — that is not drift, so it is
#       reported only as low-severity INFO and never fails CI.
#
# WHY NOT "version must appear in every listed file": the lock's `files:` list every
# doc that MENTIONS a tool, not every doc that PINS it. Requiring the pin string in a
# file that legitimately references the tool version-lessly is a false positive — the
# historical bug was a STALE/DIVERGENT pin, which is exactly what the DRIFT branch
# catches. (See repo: semgrep is named in csharp.md/go.md without a version; only
# tools.md/python.md pin it.)
# --------------------------------------------------------------------------- #
def parse_lock(path):
    lines = read_lines(path)
    tools = []
    current = None
    in_tools = False
    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "tools:" and not line.startswith(" "):
            in_tools = True
            continue
        if not in_tools:
            continue
        m_item = re.match(r"^\s*-\s+(.*)$", line)
        if m_item:
            if current is not None:
                tools.append(current)
            current = {}
            _assign_kv(current, m_item.group(1).strip())
            continue
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


def _norm(v):
    """Strip a single leading 'v' for comparison (v0.45.0 == 0.45.0)."""
    return v[1:] if v and v[0] == "v" else v


# A version-looking token: digits with at least one dot (2.10.0, 10.18.0.124379, 0.45.0).
_VER_TOKEN = r"\d+(?:\.\d+){1,3}"
# Connectors that bind a version DIRECTLY to the preceding tool token in the docs:
#   name==2.10.0  name@6.14.2  name@v8.30.1  name --version=0.69.3  :1.2.3  name 0.45.0
# NOTE: --version may sit after whitespace ("choco install trivy --version=0.69.3"),
# so allow optional space before it — else the real pin is missed and a nearby
# "vX is compromised" prose note gets misread as the pin (false drift warning).
_PIN_CONNECTOR = r"(?:==|@v?|\s*--version[= ]v?|:v?|=v?|\s+v?)"

# Go-module install paths (golang.org/x/tools, honnef.co/go/tools) share generic
# basenames like "tools"/"cmd" that collide across tools. We never use a basename
# that is too generic to identify a single tool.
_GENERIC_BASENAMES = {"tools", "cmd", "go", "v2", "v3", "v8"}


def _name_tokens(tool):
    """Identifiers under which a tool may be referenced+pinned in the docs.

    Returns specific tokens only — the literal name and (for go modules) the last
    path segment, minus generic segments that would collide across tools.
    """
    toks = set()
    name = str(tool.get("name", "")).strip()
    inst = str(tool.get("install_id", "")).strip()
    if name:
        toks.add(name.lower())
    if inst:
        base = os.path.basename(inst).lower()
        if base and base not in _GENERIC_BASENAMES:
            toks.add(base)
        if "/" not in inst:  # plain install id (npm/pypi/cargo) is itself specific
            toks.add(inst.lower())
    return {t for t in toks if t}


def _is_prefix_version(a, b):
    """True if dotted version `a` is a prefix of `b` (or equal). 0.69 ~ 0.69.3."""
    pa, pb = a.split("."), b.split(".")
    if len(pa) > len(pb):
        pa, pb = pb, pa
    return pa == pb[: len(pa)]


def _find_bound_pin(line, toks, want_norm):
    """Find a version bound DIRECTLY to one of this tool's tokens on `line`.

    Returns (found_version_str, is_conflict) or None. A pin is only considered if
    a tool token is immediately followed by a connector+version, so a different
    tool's version elsewhere on the same line cannot be misattributed. A version
    that is a dotted-prefix of the lock version (e.g. prose "Trivy v0.69" vs pin
    "0.69.3") is NOT a conflict — only a fully-specified divergent pin is drift.
    """
    low = line.lower()
    for tok in toks:
        start = 0
        while True:
            idx = low.find(tok, start)
            if idx == -1:
                break
            tail = line[idx + len(tok):]
            m = re.match(_PIN_CONNECTOR + r"(" + _VER_TOKEN + r")", tail)
            if m:
                found = m.group(1)
                is_conflict = not _is_prefix_version(_norm(found), want_norm)
                return found, is_conflict
            start = idx + len(tok)
    return None


def check_lock_drift(doc_lines, findings):
    if not os.path.isfile(LOCK_PATH):
        findings.error("lock-drift", f"versions.lock not found at {LOCK_PATH}")
        return

    tools = parse_lock(LOCK_PATH)
    info = []  # low-severity coverage notes (printed, never fail CI)

    for tool in tools:
        name = tool.get("name", "?")
        version = str(tool.get("version", "")).strip()
        ecosystem = str(tool.get("ecosystem", "")).strip().lower()
        files = tool.get("files", []) or []
        if not version or not files:
            continue
        loose = ecosystem in LOOSE_ECOSYSTEMS or bool(tool.get("security_hold")) \
            or "manual" in str(tool.get("note", "")).lower()
        nv = _norm(version)
        toks = _name_tokens(tool)

        for fname in files:
            lines = doc_lines.get(fname)
            if lines is None:
                # File listed in lock but not among the docs we lint — note it.
                if not os.path.isfile(os.path.join(REPO_ROOT, fname)):
                    findings.warning(
                        "lock-drift",
                        f"{name}: versions.lock lists files:[{fname}] but that file "
                        f"does not exist",
                    )
                else:
                    findings.warning(
                        "lock-drift",
                        f"{name}: versions.lock lists files:[{fname}] which exists on "
                        f"disk but is NOT in DOC_FILES — pin drift there is unchecked",
                    )
                continue

            # Per-line scan bound to THIS tool's tokens (NOT a whole-file substring:
            # when two tools share a version in one doc, the other tool's matching
            # version must not satisfy this tool's pin and mask real drift). A pin is
            # only counted if the version is bound DIRECTLY to one of this tool's
            # identifying tokens (name@X / name==X / name:X / name X). A correct pin
            # anywhere -> PASS; else the first conflicting pin -> drift.
            correct_pin = False
            conflict = None
            conflict_line = None
            for lineno, raw in enumerate(lines, 1):
                hit = _find_bound_pin(raw, toks, nv)
                if not hit:
                    continue
                if hit[1]:  # bound version that differs from the lock
                    if conflict is None:
                        conflict, conflict_line = hit[0], lineno
                else:       # bound version matching the lock -> correct pin present
                    correct_pin = True
                    break

            if correct_pin:
                continue  # correct pin present, bound to this tool

            if conflict is not None:
                msg = (f"{name}: {fname}:{conflict_line} pins '{conflict}' but "
                       f"versions.lock says '{version}' (drift)")
                if loose:
                    findings.warning("lock-drift", msg)
                else:
                    findings.error("lock-drift", msg)
            else:
                # Tool referenced without (or not at all) a version here — not drift.
                info.append(
                    f"{name}: version '{version}' not pinned in {fname} "
                    f"(referenced version-lessly or not present) — informational")

    if info:
        print("INFO (coverage — not a failure):")
        for line in sorted(info):
            print(f"  - {line}")
        print()


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def main():
    missing = [f for f in DOC_FILES if not os.path.isfile(os.path.join(REPO_ROOT, f))]
    if missing:
        print(f"ERROR: expected doc file(s) missing from repo: {', '.join(missing)}")
        return 1

    doc_lines = {f: read_lines(os.path.join(REPO_ROOT, f)) for f in DOC_FILES}

    findings = Findings()
    check_cross_refs(doc_lines, findings)
    check_fences(doc_lines, findings)
    check_version_consistency(doc_lines, findings)
    check_tables(doc_lines, findings)
    check_lock_drift(doc_lines, findings)

    if findings.errors:
        print(f"ERRORS ({len(findings.errors)}):")
        for check, msg in findings.errors:
            print(f"  [{check}] {msg}")
        print()
    if findings.warnings:
        print(f"WARNINGS ({len(findings.warnings)}):")
        for check, msg in findings.warnings:
            print(f"  [{check}] {msg}")
        print()

    n_err = len(findings.errors)
    n_warn = len(findings.warnings)
    status = "FAIL" if n_err else "PASS"
    print(f"lint_docs: {status} — {n_err} error(s), {n_warn} warning(s) "
          f"across {len(DOC_FILES)} docs.")
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
