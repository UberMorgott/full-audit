#!/usr/bin/env python3
"""score.py — benchmark scoring harness: confusion matrix vs ground truth.

WHAT THIS IS
  The Ф0 pipeline core of the full-audit benchmark (see BENCHMARK-PLAN.md). It joins
  a machine-readable audit emit (`audit-bugs.json`, schema v1.1) to a hand-labelled
  ground-truth YAML by the PRE-REGISTERED matching rule, and emits a per-category
  confusion matrix + recall/precision. It is DECOUPLED from any live audit run: it
  reads two files and computes joins. It runs no audit and costs no model tokens.

  The matching rule, metric definitions, and CVSS<->band crosswalk are documented
  VERBATIM in benchmark/ground-truth.schema.md. That file + the GT YAMLs must be
  git-tagged BEFORE any benchmark run (pre-registration).

MATCHING RULE (summary; schema doc is authoritative)
  - SCA   : GT(type=sca) matches a finding iff their CVE id sets intersect.
            File/line ignored (dependency-level).
  - SAST  : GT(type=sast) matches iff same file AND CWE sets intersect AND the
            finding line span overlaps [gt.line_start - N, gt.line_end + N], N=window.
  - logical: EXCLUDED from auto-matching; reported for manual adjudication only.

BUCKETS (per category sca/sast, never aggregated)
  TP = matched pair; FN = unmatched GT item; FP = auto-scorable finding (has cwe/cve)
  with no GT match. A finding with no cwe/cve that matches nothing -> "needs
  adjudication" (NOT a strict FP). Logical-class findings -> "manual review".

HOW TO RUN
  python benchmark/score.py --findings <audit-bugs.json> --truth <gt.yaml> [--window N]
  Prints a per-category report and writes score-result.json. Exit 0 on success.

DEPENDENCIES
  Python 3 standard library only. The GT YAML is parsed by a tiny self-contained
  reader (see ground-truth.schema.md sec.5); no PyYAML / pip install needed.
"""

import argparse
import json
import os
import re
import sys

# CVSS<->band weight crosswalk (documented in ground-truth.schema.md sec.3).
BAND_WEIGHT = {"CRITICAL": 10.0, "HIGH": 7.0, "MEDIUM": 4.0, "LOW": 1.0}

DEFAULT_WINDOW = 5


# --------------------------------------------------------------------------- #
# Tiny self-contained YAML reader for the flat GT subset (schema doc sec.5).
# Supports: top-level key: value mappings, an `items:` list of `- key: value`
# mappings, scalars (int/float/str), quoted strings, and inline [a, b] lists.
# NOT a general YAML parser.
# --------------------------------------------------------------------------- #
def _strip_comment(s):
    """Drop a trailing '# ...' comment not inside quotes."""
    out = []
    quote = None
    for ch in s:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out)


def _strip_quotes(s):
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def _scalar(val):
    """Coerce a YAML scalar string to int/float/bool/None/str."""
    v = val.strip()
    if v == "":
        return ""
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_scalar(p.strip()) for p in inner.split(",") if p.strip()]
    low = v.lower()
    if low in ("null", "~"):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+\.\d+", v):
        return float(v)
    return _strip_quotes(v)


def load_yaml(path):
    """Parse the flat GT subset. Returns a dict (top-level mapping)."""
    with open(path, "r", encoding="utf-8") as fh:
        raw_lines = fh.read().split("\n")

    root = {}
    items = None          # the list under `items:` once we enter it
    current = None        # the mapping for the current `- ...` item
    cur_indent = None     # indentation of the current item's keys

    for raw in raw_lines:
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        # Top-level `items:` opens the list.
        if indent == 0 and stripped == "items:":
            items = []
            root["items"] = items
            current = None
            continue

        # Other top-level `key: value` (e.g. meta:) — we only care about scalars;
        # nested mappings like meta: are skipped gracefully (their children are
        # indented and fall through to the item/key handling below only inside items).
        if indent == 0:
            key, _, val = stripped.partition(":")
            val = val.strip()
            if val == "":
                # A nested block we don't model (e.g. meta:). Skip its children by
                # remembering we're outside `items`.
                items = None
                current = None
                root.setdefault(key.strip(), {})
                root["_skip_block"] = key.strip()
            else:
                root[key.strip()] = _scalar(val)
            continue

        # Inside the `items:` list?
        if items is not None:
            m = re.match(r"^(-\s+)(.*)$", stripped)
            if m:
                # New list item begins.
                current = {}
                items.append(current)
                cur_indent = indent
                rest = m.group(2).strip()
                if rest:
                    k, _, v = rest.partition(":")
                    current[k.strip()] = _scalar(v.strip())
                continue
            if current is not None and indent > cur_indent - 1:
                k, _, v = stripped.partition(":")
                current[k.strip()] = _scalar(v.strip())
                continue
        # Anything else (children of a skipped top-level block) is ignored.

    root.pop("_skip_block", None)
    return root


# --------------------------------------------------------------------------- #
# Normalization helpers
# --------------------------------------------------------------------------- #
def as_set(val, normalizer=None):
    """Normalize a scalar-or-list taxonomy field to an uppercased set of strings.

    If `normalizer` is given it is applied to each already-stringified token
    (the normalizer is responsible for its own strip()/upper()); a normalizer
    that returns an empty string drops the token (-> adjudication, not FP)."""
    if val is None or val == "":
        return set()
    if isinstance(val, (list, tuple)):
        raw = [v for v in val if str(v).strip()]
    else:
        # Mirror the list-branch filtering: a whitespace-only / empty scalar
        # carries NO taxonomy, so it must yield an empty set.
        raw = [val] if str(val).strip() else []
    if normalizer is None:
        return {str(v).strip().upper() for v in raw if str(v).strip()}
    out = set()
    for v in raw:
        tok = normalizer(v)
        if tok:
            out.add(tok)
    return out


_CWE_RE = re.compile(r"^(?:CWE-?)?(\d+)$")
_CVE_RE = re.compile(r"^CVE-(\d{4})-(\d+)$")


def normalize_cwe(v):
    """Canonicalize a CWE id to `CWE-<int>` (no leading zeros).

    Accepts `CWE-89`, `cwe-89`, bare `89`, `CWE-089`, or an int. Unknown
    formats are returned stripped+uppercased UNCHANGED (defensive — never drop
    an id we don't recognize, so genuinely different ids cannot silently merge).
    Empty/whitespace -> "" (the caller drops it -> adjudication, not FP)."""
    s = str(v).strip().upper()
    if not s:
        return ""
    m = _CWE_RE.match(s)
    if m:
        return "CWE-%d" % int(m.group(1))
    return s


def normalize_cve(v):
    """Canonicalize a CVE id to uppercase `CVE-YYYY-NNNN` (case-insensitive).

    Unknown formats are returned stripped+uppercased UNCHANGED (defensive).
    Empty/whitespace -> "" (dropped by the caller)."""
    s = str(v).strip().upper()
    if not s:
        return ""
    m = _CVE_RE.match(s)
    if m:
        return "CVE-%s-%s" % (m.group(1), m.group(2))
    return s


def id_set(raw, kind):
    """Build a normalized id set for a cwe/cve field. `kind` is 'cwe' or 'cve'.

    Used on BOTH the finding and GT sides so canonical forms intersect."""
    if kind == "cwe":
        return as_set(raw, normalize_cwe)
    if kind == "cve":
        return as_set(raw, normalize_cve)
    return as_set(raw)


def weight_of(severity, cvss):
    """CVSS if present (a positive number), else band fallback."""
    if isinstance(cvss, (int, float)) and cvss > 0:
        return float(cvss)
    return BAND_WEIGHT.get(str(severity).strip().upper(), 0.0)


def spans_overlap(a, b, c, d):
    """Closed intervals [a,b] and [c,d] overlap iff a <= d and c <= b."""
    return a <= d and c <= b


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #
def finding_is_auto_scorable(finding):
    """True iff the finding carries a cve or cwe (so a no-match is a strict FP)."""
    return bool(id_set(finding.get("cwe"), "cwe") or id_set(finding.get("cve"), "cve"))


def finding_is_logical_class(finding):
    """Logical-class = carries neither cwe nor cve."""
    return not finding_is_auto_scorable(finding)


def match_sca(gt_items, findings):
    """Match SCA: CVE set intersection. Returns (tps, fns, matched_finding_idx)."""
    tps = []
    fns = []
    matched_idx = set()
    for gt in gt_items:
        gt_cves = id_set(gt.get("cve"), "cve")
        hit = None
        for i, f in enumerate(findings):
            if i in matched_idx:
                continue
            if gt_cves & id_set(f.get("cve"), "cve"):
                hit = i
                break
        if hit is not None:
            matched_idx.add(hit)
            tps.append((gt, findings[hit]))
        else:
            fns.append(gt)
    return tps, fns, matched_idx


def match_sast(gt_items, findings, window):
    """Match SAST: file + CWE intersection + line-window overlap."""
    tps = []
    fns = []
    matched_idx = set()
    for gt in gt_items:
        gt_cwes = id_set(gt.get("cwe"), "cwe")
        gt_file = str(gt.get("file", ""))
        ls = int(gt.get("line_start", 0))
        # Source lines are 1-indexed, so a line_end <= 0 (or missing) is not a
        # valid line span end -> fall back to line_start. (Note: `int(x) or ls`
        # alone only catches 0, not negatives; check <= 0 explicitly.)
        le = int(gt.get("line_end", ls))
        if le <= 0:
            le = ls
        lo, hi = ls - window, le + window
        hit = None
        for i, f in enumerate(findings):
            if i in matched_idx:
                continue
            if str(f.get("file", "")) != gt_file:
                continue
            if not (gt_cwes & id_set(f.get("cwe"), "cwe")):
                continue
            f_line = int(f.get("line", 0))
            f_end = int(f.get("end_line", f_line) or f_line)
            if spans_overlap(f_line, f_end, lo, hi):
                hit = i
                break
        if hit is not None:
            matched_idx.add(hit)
            tps.append((gt, findings[hit]))
        else:
            fns.append(gt)
    return tps, fns, matched_idx


def fn_record(gt):
    return {
        "id": gt.get("id"),
        "type": gt.get("type"),
        "severity": gt.get("severity"),
        "cwe": gt.get("cwe"),
        "cve": gt.get("cve"),
        "file": gt.get("file"),
        "line_start": gt.get("line_start"),
        "root_cause": "",  # to fill: tool-not-run / skip_if-fired / dismissed / below-threshold
    }


def finding_record(f):
    return {
        "id": f.get("id"),
        "severity": f.get("severity"),
        "file": f.get("file"),
        "line": f.get("line"),
        "cwe": f.get("cwe"),
        "cve": f.get("cve"),
        "detection": f.get("detection"),
        "title": f.get("title"),
    }


def category_metrics(tps, fns):
    """recall, strict precision (precision needs FP, filled by caller), weighted recall."""
    tp = len(tps)
    fn = len(fns)
    recall = tp / (tp + fn) if (tp + fn) else None

    w_tp = sum(weight_of(gt.get("severity"), gt.get("cvss")) for gt, _ in tps)
    w_all = w_tp + sum(weight_of(gt.get("severity"), gt.get("cvss")) for gt in fns)
    wrecall = w_tp / w_all if w_all else None
    return recall, wrecall


def score(findings, gt_root, window):
    items = gt_root.get("items", []) or []
    sca_gt = [g for g in items if str(g.get("type")).lower() == "sca"]
    sast_gt = [g for g in items if str(g.get("type")).lower() == "sast"]
    logical_gt = [g for g in items if str(g.get("type")).lower() == "logical"]

    sca_tps, sca_fns, sca_matched = match_sca(sca_gt, findings)
    sast_tps, sast_fns, sast_matched = match_sast(sast_gt, findings, window)

    all_matched = sca_matched | sast_matched

    # Classify every UNMATCHED finding into FP / adjudication / logical-review.
    sca_fp, sast_fp = [], []
    adjudication = []
    logical_findings = []
    for i, f in enumerate(findings):
        if i in all_matched:
            continue
        cves = id_set(f.get("cve"), "cve")
        cwes = id_set(f.get("cwe"), "cwe")
        if finding_is_logical_class(f):
            # No taxonomy -> manual review listing + adjudication bucket
            logical_findings.append(finding_record(f))
            adjudication.append(finding_record(f))
        elif cves:
            sca_fp.append(finding_record(f))   # auto-scorable SCA finding, no GT match
        elif cwes:
            sast_fp.append(finding_record(f))  # auto-scorable SAST finding, no GT match

    sca_recall, sca_wrecall = category_metrics(sca_tps, sca_fns)
    sast_recall, sast_wrecall = category_metrics(sast_tps, sast_fns)

    def precision(tp, fp):
        return tp / (tp + fp) if (tp + fp) else None

    result = {
        "window": window,
        "weight_crosswalk": BAND_WEIGHT,
        "categories": {
            "sca": {
                "tp": len(sca_tps),
                "fn": len(sca_fns),
                "fp": len(sca_fp),
                "recall": sca_recall,
                "strict_precision": precision(len(sca_tps), len(sca_fp)),
                "severity_weighted_recall": sca_wrecall,
                "tp_pairs": [{"gt": g.get("id"), "finding": f.get("id")}
                             for g, f in sca_tps],
                "fn_items": [fn_record(g) for g in sca_fns],
                "fp_findings": sca_fp,
            },
            "sast": {
                "tp": len(sast_tps),
                "fn": len(sast_fns),
                "fp": len(sast_fp),
                "recall": sast_recall,
                "strict_precision": precision(len(sast_tps), len(sast_fp)),
                "severity_weighted_recall": sast_wrecall,
                "tp_pairs": [{"gt": g.get("id"), "finding": f.get("id")}
                             for g, f in sast_tps],
                "fn_items": [fn_record(g) for g in sast_fns],
                "fp_findings": sast_fp,
            },
        },
        "unmatched_needs_adjudication": adjudication,
        "logical": {
            "gt_items": [fn_record(g) for g in logical_gt],
            "findings_for_manual_review": logical_findings,
        },
    }
    return result


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def _fmt_ratio(x):
    return "n/a" if x is None else "%.3f" % x


def print_report(result):
    print("benchmark score — per-category confusion matrix (window N=%d)"
          % result["window"])
    print("  (SCA and SAST are scored SEPARATELY and never aggregated)")
    print()
    for cat in ("sca", "sast"):
        c = result["categories"][cat]
        print("[%s]" % cat.upper())
        print("  TP=%d  FN=%d  FP=%d" % (c["tp"], c["fn"], c["fp"]))
        print("  recall           = %s" % _fmt_ratio(c["recall"]))
        print("  strict precision = %s" % _fmt_ratio(c["strict_precision"]))
        print("  sev-weighted recall = %s" % _fmt_ratio(c["severity_weighted_recall"]))
        if c["fn_items"]:
            print("  FN (missed GT, root_cause to fill):")
            for fn in c["fn_items"]:
                print("    - %s %s %s (root_cause: '')"
                      % (fn["id"], fn.get("cwe") or fn.get("cve") or "", fn["severity"]))
        if c["fp_findings"]:
            print("  FP (auto-scorable findings, no GT match):")
            for fp in c["fp_findings"]:
                print("    - %s [%s] %s" % (fp["id"], fp.get("detection"), fp.get("title")))
        print()

    adj = result["unmatched_needs_adjudication"]
    print("[UNMATCHED — needs adjudication]  (NOT counted as FP)  count=%d" % len(adj))
    for f in adj:
        print("    - %s [%s] %s" % (f["id"], f.get("detection"), f.get("title")))
    print()

    log = result["logical"]
    print("[LOGICAL — manual review only]  gt_items=%d  findings=%d"
          % (len(log["gt_items"]), len(log["findings_for_manual_review"])))
    for g in log["gt_items"]:
        print("    - GT %s %s %s" % (g["id"], g["severity"], g.get("file") or ""))
    for f in log["findings_for_manual_review"]:
        print("    - finding %s [%s] %s" % (f["id"], f.get("detection"), f.get("title")))
    print()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Benchmark scorer: join audit-bugs.json to a ground-truth YAML "
                    "by the pre-registered matching rule; per-category confusion matrix.")
    parser.add_argument("--findings", required=True, help="path to audit-bugs.json (schema v1.1)")
    parser.add_argument("--truth", required=True, help="path to ground-truth YAML")
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW,
                        help="SAST line-window N (default %d)" % DEFAULT_WINDOW)
    parser.add_argument("--out", default=None,
                        help="path for machine-readable result "
                             "(default: score-result.json next to --findings)")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.findings):
        print("ERROR: findings file not found: %s" % args.findings)
        return 2
    if not os.path.isfile(args.truth):
        print("ERROR: truth file not found: %s" % args.truth)
        return 2

    with open(args.findings, "r", encoding="utf-8") as fh:
        bugs = json.load(fh)
    findings = bugs.get("findings", []) if isinstance(bugs, dict) else []

    gt_root = load_yaml(args.truth)

    result = score(findings, gt_root, args.window)
    print_report(result)

    out_path = args.out or os.path.join(os.path.dirname(os.path.abspath(args.findings)),
                                        "score-result.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
    print("wrote machine-readable result -> %s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
