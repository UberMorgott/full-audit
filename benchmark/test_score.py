#!/usr/bin/env python3
"""test_score.py — proof the scoring pipeline works against hand-built fixtures.

Runs benchmark/score.py's scorer over benchmark/fixtures/{audit-bugs.json,
ground-truth.yaml} and asserts the EXACT per-category TP/FN/FP plus the
adjudication / manual-review bucket contents match the documented expected values.

Stdlib unittest only. No network, no audit run, no model cost.
  python benchmark/test_score.py
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import score  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures")
BUGS = os.path.join(FIXTURES, "audit-bugs.json")
TRUTH = os.path.join(FIXTURES, "ground-truth.yaml")


def run_score(window=5):
    with open(BUGS, "r", encoding="utf-8") as fh:
        findings = json.load(fh)["findings"]
    gt = score.load_yaml(TRUTH)
    return score.score(findings, gt, window)


class TestYamlLoader(unittest.TestCase):
    def test_parses_items_and_scalars(self):
        gt = score.load_yaml(TRUTH)
        ids = [i["id"] for i in gt["items"]]
        self.assertEqual(
            ids, ["GT-SCA-TP", "GT-SCA-FN", "GT-SAST-TP", "GT-SAST-FN", "GT-LOG-1"])
        sca_tp = gt["items"][0]
        self.assertEqual(sca_tp["cve"], "CVE-2021-1111")
        self.assertEqual(sca_tp["cvss"], 7.5)         # float coercion
        self.assertEqual(sca_tp["line_start"], 10)    # int coercion
        sast_tp = gt["items"][2]
        self.assertEqual(sast_tp["line_end"], 52)


class TestSca(unittest.TestCase):
    def setUp(self):
        self.r = run_score()["categories"]["sca"]

    def test_counts(self):
        self.assertEqual((self.r["tp"], self.r["fn"], self.r["fp"]), (1, 1, 1))

    def test_pairs_and_items(self):
        self.assertEqual(self.r["tp_pairs"],
                         [{"gt": "GT-SCA-TP", "finding": "FA-0001"}])
        self.assertEqual([f["id"] for f in self.r["fn_items"]], ["GT-SCA-FN"])
        self.assertEqual([f["id"] for f in self.r["fp_findings"]], ["FA-0006"])

    def test_metrics(self):
        self.assertAlmostEqual(self.r["recall"], 0.5)            # 1/(1+1)
        self.assertAlmostEqual(self.r["strict_precision"], 0.5)  # 1/(1+1)
        # weighted recall = w(TP) / (w(TP)+w(FN)) = 7.5 / (7.5 + 9.8)
        self.assertAlmostEqual(self.r["severity_weighted_recall"], 7.5 / (7.5 + 9.8))

    def test_fn_has_empty_root_cause(self):
        self.assertEqual(self.r["fn_items"][0]["root_cause"], "")


class TestSast(unittest.TestCase):
    def setUp(self):
        self.r = run_score()["categories"]["sast"]

    def test_counts(self):
        self.assertEqual((self.r["tp"], self.r["fn"], self.r["fp"]), (1, 1, 1))

    def test_pairs_and_items(self):
        self.assertEqual(self.r["tp_pairs"],
                         [{"gt": "GT-SAST-TP", "finding": "FA-0002"}])
        self.assertEqual([f["id"] for f in self.r["fn_items"]], ["GT-SAST-FN"])
        self.assertEqual([f["id"] for f in self.r["fp_findings"]], ["FA-0003"])

    def test_metrics(self):
        self.assertAlmostEqual(self.r["recall"], 0.5)
        self.assertAlmostEqual(self.r["strict_precision"], 0.5)
        # weighted recall = 9.1 / (9.1 + band(HIGH)=7.0)
        self.assertAlmostEqual(self.r["severity_weighted_recall"], 9.1 / (9.1 + 7.0))

    def test_fn_root_cause(self):
        self.assertEqual(self.r["fn_items"][0]["root_cause"], "")


class TestBuckets(unittest.TestCase):
    def setUp(self):
        self.r = run_score()

    def test_adjudication_holds_both_no_taxonomy_findings_not_fp(self):
        adj_ids = sorted(f["id"] for f in self.r["unmatched_needs_adjudication"])
        self.assertEqual(adj_ids, ["FA-0004", "FA-0005"])
        # And neither is ever counted as a strict FP in any category.
        all_fp = ([f["id"] for f in self.r["categories"]["sca"]["fp_findings"]]
                  + [f["id"] for f in self.r["categories"]["sast"]["fp_findings"]])
        self.assertNotIn("FA-0004", all_fp)
        self.assertNotIn("FA-0005", all_fp)

    def test_logical_gt_listed_for_manual_review(self):
        gt_ids = [g["id"] for g in self.r["logical"]["gt_items"]]
        self.assertEqual(gt_ids, ["GT-LOG-1"])

    def test_logical_findings_for_manual_review(self):
        ids = sorted(f["id"] for f in self.r["logical"]["findings_for_manual_review"])
        self.assertEqual(ids, ["FA-0004", "FA-0005"])


class TestWindowSensitivity(unittest.TestCase):
    def test_zero_window_still_matches_overlapping_span(self):
        # finding FA-0002 span [47,50] is inside GT [45,52] even at N=0.
        r = run_score(window=0)["categories"]["sast"]
        self.assertEqual(r["tp"], 1)


class TestBlankTaxonomyNotFp(unittest.TestCase):
    """Regression: a finding whose only cwe/cve is blank/whitespace has NO
    taxonomy -> it must route to the adjudication bucket, NOT be counted as a
    strict FP (SAST/SCA). Reproduces BUG 1 (as_set scalar branch didn't filter
    empty/whitespace)."""

    def test_whitespace_cwe_is_no_taxonomy_not_sast_fp(self):
        findings = [{"id": "FA-WS-CWE", "file": "x.go", "line": 5,
                     "cwe": "   ", "detection": "manual", "title": "blank cwe"}]
        gt = {"items": []}
        r = score.score(findings, gt, window=5)
        sast_fp = [f["id"] for f in r["categories"]["sast"]["fp_findings"]]
        self.assertNotIn("FA-WS-CWE", sast_fp)
        adj_ids = [f["id"] for f in r["unmatched_needs_adjudication"]]
        self.assertIn("FA-WS-CWE", adj_ids)

    def test_empty_cve_is_no_taxonomy_not_sca_fp(self):
        findings = [{"id": "FA-EMPTY-CVE", "file": "y.json", "line": 1,
                     "cve": "", "detection": "osv-scanner", "title": "blank cve"}]
        gt = {"items": []}
        r = score.score(findings, gt, window=5)
        sca_fp = [f["id"] for f in r["categories"]["sca"]["fp_findings"]]
        self.assertNotIn("FA-EMPTY-CVE", sca_fp)
        adj_ids = [f["id"] for f in r["unmatched_needs_adjudication"]]
        self.assertIn("FA-EMPTY-CVE", adj_ids)

    def test_as_set_filters_blank_scalar(self):
        self.assertEqual(score.as_set("   "), set())
        self.assertEqual(score.as_set(""), set())
        self.assertEqual(score.as_set("CWE-89"), {"CWE-89"})


class TestCweCveNormalization(unittest.TestCase):
    """Schema §2 (refined pre-tag): CWE/CVE ids are normalized to a canonical
    form (CWE-<int>, CVE-YYYY-NNNN; case-insensitive, 'CWE-' prefix optional /
    bare integer accepted) BEFORE set intersection. Real scanners emit CWE-89 /
    89 / cwe-89 interchangeably; verbatim matching produced phantom FN/FP.
    Normalization must NOT collapse genuinely different ids."""

    def _sast_score(self, finding_cwe, gt_cwe):
        findings = [{"id": "FA-X", "file": "src/db/query.go", "line": 47,
                     "end_line": 50, "cwe": finding_cwe, "detection": "semgrep",
                     "title": "cwe normalization"}]
        gt = {"items": [{"id": "GT-SAST", "type": "sast", "cwe": gt_cwe,
                         "severity": "HIGH", "file": "src/db/query.go",
                         "line_start": 45, "line_end": 52}]}
        return score.score(findings, gt, window=5)["categories"]["sast"]

    def _sca_score(self, finding_cve, gt_cve):
        findings = [{"id": "FA-X", "file": "go.mod", "line": 10,
                     "cve": finding_cve, "detection": "osv-scanner",
                     "title": "cve normalization"}]
        gt = {"items": [{"id": "GT-SCA", "type": "sca", "cve": gt_cve,
                         "severity": "HIGH", "file": "go.mod",
                         "line_start": 10}]}
        return score.score(findings, gt, window=5)["categories"]["sca"]

    def test_bare_number_matches_prefixed_cwe(self):
        # FLIPPED (was TestCwePrefixNotNormalized): cwe='89' now matches 'CWE-89'.
        sast = self._sast_score("89", "CWE-89")
        self.assertEqual(sast["tp"], 1)
        self.assertEqual(sast["fn_items"], [])
        self.assertEqual(sast["fp_findings"], [])

    def test_lowercase_prefix_matches(self):
        sast = self._sast_score("cwe-89", "CWE-89")
        self.assertEqual(sast["tp"], 1)

    def test_leading_zero_matches(self):
        # CWE-089 canonicalizes to CWE-89 (no leading zeros) -> matches CWE-89.
        sast = self._sast_score("CWE-089", "CWE-89")
        self.assertEqual(sast["tp"], 1)

    def test_int_cwe_matches_prefixed(self):
        # Integer input (e.g. from a JSON number) normalizes too.
        sast = self._sast_score(89, "CWE-89")
        self.assertEqual(sast["tp"], 1)

    def test_different_cwe_still_does_not_match(self):
        # Guard against over-normalization: CWE-89 vs CWE-79 must NOT match.
        sast = self._sast_score("CWE-89", "CWE-79")
        self.assertEqual(sast["tp"], 0)
        self.assertEqual([f["id"] for f in sast["fn_items"]], ["GT-SAST"])
        self.assertEqual([f["id"] for f in sast["fp_findings"]], ["FA-X"])

    def test_cve_case_insensitive_matches(self):
        sca = self._sca_score("cve-2023-1234", "CVE-2023-1234")
        self.assertEqual(sca["tp"], 1)

    def test_different_cve_year_still_does_not_match(self):
        sca = self._sca_score("CVE-2022-1234", "CVE-2023-1234")
        self.assertEqual(sca["tp"], 0)
        self.assertEqual([f["id"] for f in sca["fn_items"]], ["GT-SCA"])
        self.assertEqual([f["id"] for f in sca["fp_findings"]], ["FA-X"])

    def test_normalize_cwe_unit(self):
        self.assertEqual(score.normalize_cwe("89"), "CWE-89")
        self.assertEqual(score.normalize_cwe("cwe-89"), "CWE-89")
        self.assertEqual(score.normalize_cwe("CWE-089"), "CWE-89")
        self.assertEqual(score.normalize_cwe(89), "CWE-89")
        self.assertEqual(score.normalize_cwe(" CWE-89 "), "CWE-89")
        # Unknown format: defensively kept (stripped+uppercased), not dropped.
        self.assertEqual(score.normalize_cwe("CWE-89A"), "CWE-89A")
        self.assertEqual(score.normalize_cwe("foo"), "FOO")
        # Empty/whitespace -> dropped (caller filters None/"").
        self.assertEqual(score.normalize_cwe("   "), "")
        self.assertEqual(score.normalize_cwe(""), "")

    def test_normalize_cve_unit(self):
        self.assertEqual(score.normalize_cve("cve-2023-1234"), "CVE-2023-1234")
        self.assertEqual(score.normalize_cve("CVE-2023-1234"), "CVE-2023-1234")
        self.assertEqual(score.normalize_cve(" cve-2023-1234 "), "CVE-2023-1234")
        # Unknown format kept defensively.
        self.assertEqual(score.normalize_cve("GHSA-xxxx"), "GHSA-XXXX")
        self.assertEqual(score.normalize_cve("   "), "")


class TestLineEndNonPositiveFallback(unittest.TestCase):
    """line_end <= 0 (or missing) falls back to line_start (lines are 1-indexed,
    so 0/negative is not a valid line). BUG 3: behavior kept, intent made
    explicit."""

    def test_line_end_zero_behaves_as_line_start(self):
        gt_item = {"id": "GT", "type": "sast", "cwe": "CWE-89", "severity": "HIGH",
                   "file": "a.go", "line_start": 30, "line_end": 0}
        # With line_end=0 -> span collapses to [30,30]; widened by N=0 -> [30,30].
        finding_in = [{"id": "F-IN", "file": "a.go", "line": 30, "cwe": "CWE-89"}]
        finding_out = [{"id": "F-OUT", "file": "a.go", "line": 36, "cwe": "CWE-89"}]
        r_in = score.score(finding_in, {"items": [gt_item]}, window=0)
        r_out = score.score(finding_out, {"items": [dict(gt_item)]}, window=0)
        self.assertEqual(r_in["categories"]["sast"]["tp"], 1)
        # If line_end=0 were honored literally as a line, span would be [0,30] and
        # the line-36 finding still wouldn't match; the point is it behaves as
        # [30,30]: a finding at line 36 (window 0) misses.
        self.assertEqual(r_out["categories"]["sast"]["tp"], 0)

    def test_negative_line_end_behaves_as_line_start(self):
        gt_item = {"id": "GT", "type": "sast", "cwe": "CWE-89", "severity": "HIGH",
                   "file": "a.go", "line_start": 30, "line_end": -7}
        finding = [{"id": "F", "file": "a.go", "line": 30, "cwe": "CWE-89"}]
        r = score.score(finding, {"items": [gt_item]}, window=0)
        self.assertEqual(r["categories"]["sast"]["tp"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
