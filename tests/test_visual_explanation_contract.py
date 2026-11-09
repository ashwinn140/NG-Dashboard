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

    def test_manual_finance_margin_has_explanation(self):
        self.assertIn("businessMeaning('Margin', 'Profit divided by income", APP)

    def test_profit_job_metrics_have_explicit_formulas(self):
        self.assertIn("Profit = income minus booked expense", APP)
        self.assertIn("Total profit divided by the number of selected jobs", APP)

    def test_all_known_manual_kpis_have_explanations(self):
        for label in ('Top customer concentration', 'Customers only in current period',
                      'Customers only in comparison period', 'Negative income rows',
                      'Company-name matched jobs'):
            with self.subTest(label=label):
                self.assertIn("businessMeaning('" + label + "'", APP)

    def test_custom_variance_kpi_builders_have_explanations(self):
        self.assertIn("businessMeaning(label, note)); };", APP)
        self.assertIn("businessMeaning(label, 'Current versus previous reporting period')); };", APP)

    def test_shipment_formula_does_not_capture_invoice_metric(self):
        self.assertIn('/^(shipments|air export shipments|sea export shipments|air import shipments|sea import shipments)$/', APP)
        self.assertNotIn('/shipments|shipment count/.test(lower)', APP)

    def test_weight_explanation_mentions_display_unit(self):
        self.assertIn('converted to the displayed weight unit', APP)

    def test_no_demo_rows_generated(self):
        self.assertIn("const DEMO_KEEP = [0, 0.86, 0.72], demoSrc = [], demoK = []", APP)

if __name__ == "__main__":
    unittest.main()
