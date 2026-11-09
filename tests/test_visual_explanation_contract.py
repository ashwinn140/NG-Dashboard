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
        self.assertIn("Dashboard date selection:", APP)
        self.assertIn("reportingWindow.pfrom", APP)
        self.assertIn("reportingWindow.pto", APP)

    def test_exact_metric_registry_and_conservative_fallback(self):
        self.assertIn("VERIFIED_METRIC_EXPLANATIONS", APP)
        self.assertIn("Calculation not yet verified against this visual", APP)
        self.assertNotIn("/gross profit|", APP)

    def test_manual_finance_margin_has_explanation(self):
        self.assertIn("businessMeaning('Margin', 'Profit divided by income", APP)

    def test_profit_job_metrics_have_explicit_formulas(self):
        self.assertIn("Adds job profit, calculated as each job", APP)
        self.assertIn("Divides selected total job-summary Profit by the selected job count", APP)

    def test_all_known_manual_kpis_have_explanations(self):
        for label in ('Top customer concentration', 'Customers only in current period',
                      'Customers only in comparison period', 'Negative income rows',
                      'Company-name matched jobs'):
            with self.subTest(label=label):
                self.assertIn("businessMeaning('" + label + "'", APP)

    def test_custom_variance_kpi_builders_have_explanations(self):
        self.assertIn("businessMeaning(label, note)); };", APP)
        self.assertIn("businessMeaning(label, 'Current versus previous reporting period')); };", APP)

    def test_no_title_based_formula_guessing(self):
        self.assertNotIn("/shipments|shipment count/.test(lower)", APP)
        self.assertNotIn("/chargeable weight/.test(lower)", APP)

    def test_specific_kpi_formulas_not_title_guesses(self):
        for label in ("air chargeable weight (tonnes)", "sea teus",
                      "jobs with cost booked",
                      "profit after expected costs", "shipments invoiced",
                      "jobs matched to the register"):
            with self.subTest(label=label):
                self.assertIn("'" + label + "': [", APP)

    def test_customer_profit_and_air_rate_descriptions(self):
        for label in ("customers making 80% of profit", "loss-making customers",
                      "air: profit per tonne", "sea: profit per teu",
                      "days from shipment to first invoice",
                      "days from ops lock to first invoice",
                      "average sell rate", "average buy rate",
                      "freight margin per kg", "estimated freight margin",
                      "selling below buy"):
            with self.subTest(label=label):
                self.assertIn("'" + label + "': [", APP)

    def test_ambiguous_active_customer_label_not_assigned_one_formula(self):
        self.assertNotIn("'active customers': [", APP)

    def test_no_demo_rows_generated(self):
        self.assertIn("const DEMO_KEEP = [0, 0.86, 0.72], demoSrc = [], demoK = []", APP)

if __name__ == "__main__":
    unittest.main()
