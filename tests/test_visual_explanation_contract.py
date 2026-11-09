"""Regression tests for source-level visual explanation wiring.

These checks deliberately do not assert ERP financial correctness: that needs
archived workbooks and a database reconciliation, not source-code matching.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "app_prod.js").read_text(encoding="utf-8")

class VisualExplanationContract(unittest.TestCase):
    def test_shared_cards_include_explanation(self):
        self.assertRegex(APP, r"function card\(title, note, body, cls\).*businessMeaning\(title, note\)")

    def test_shared_kpis_include_explanation(self):
        self.assertIn("businessMeaning(label, note)", APP)

    def test_explanation_is_collapsible(self):
        self.assertIn("h('details', {class: 'business-explanation'", APP)
        self.assertIn("What this means:", APP)
        self.assertIn("How it is calculated:", APP)

    def test_reporting_periods_shown(self):
        self.assertIn("Reporting dates:", APP)
        self.assertIn("reportingWindow.pfrom", APP)
        self.assertIn("reportingWindow.pto", APP)

    def test_gp_pattern_has_word_boundaries(self):
        self.assertIn(r"/gross profit|\bgp\b/", APP)
        self.assertNotIn(r"/gross profit|\\bgp\\b/", APP)

    def test_unverified_calculations_not_asserted(self):
        self.assertIn("Metric-specific formula not yet verified", APP)

    def test_no_demo_rows_generated(self):
        self.assertIn("const DEMO_KEEP = [0, 0.86, 0.72], demoSrc = [], demoK = []", APP)

if __name__ == "__main__":
    unittest.main()
