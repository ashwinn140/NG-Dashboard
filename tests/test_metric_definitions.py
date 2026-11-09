"""Standalone regression tests: python -m unittest discover -s tests -p 'test_metric_definitions.py'"""
import unittest
from app.metric_definitions import DEFINITIONS, get_metric


class MetricDefinitionTests(unittest.TestCase):
    def test_every_definition_has_source_and_formula(self):
        for metric in DEFINITIONS.values():
            with self.subTest(metric=metric.id):
                self.assertTrue(metric.source_columns)
                self.assertTrue(metric.date_column)
                self.assertTrue(metric.formula)
                self.assertIn("Exact source columns:", metric.explain())
                self.assertIn("Calculation:", metric.explain())

    def test_billing_proxy_is_not_claimed_to_be_invoice_status(self):
        metric = get_metric("profit.billing_pending_proxy")
        self.assertEqual(metric.readiness, "business_validation_required")
        self.assertIn("does NOT prove", metric.explain())

    def test_profit_exact_headers(self):
        m = get_metric("profit.gp")
        self.assertIn("Income (INR)", m.source_columns)
        self.assertIn("Expense (INR)", m.source_columns)
        self.assertIn("Profit (INR)", m.source_columns)

    def test_unknown_metric(self):
        self.assertIsNone(get_metric("unknown"))


if __name__ == "__main__":
    unittest.main()
