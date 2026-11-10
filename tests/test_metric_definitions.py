"""Standalone regression tests: python -m unittest discover -s tests -p 'test_metric_definitions.py'"""
import unittest
from app.metric_definitions import DEFINITIONS, get_metric, all_metrics


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

    def test_explicit_database_fields_are_mapped_to_real_columns(self):
        metrics = {item["id"]: item for item in all_metrics()}
        expected = {
            "profit.customers": {"Organization": "profit_lines.customer; blank source values may use a unique current shipment-register customer match"},
            "ops.customer_concentration": {"Customer": "shipments.customer", "Chargeable Wt": "shipments.chargeable_wt", "TEUs": "shipments.teus"},
            "ops.volume": {"Volume": "shipments.volume"},
            "ops.old_open": {"Operations Locked On": "shipments.ops_locked_on", "Financials Locked On": "shipments.fin_locked_on"},
            "ops.invoice_lag": {"Invoice No. & Date": "shipments.extra['Invoice No. & Date']; parsed into invoice reference count and first invoice date", "Billing Details": "shipments.extra['Billing Details']; parsed with invoice references and dates"},
        }
        for metric_id, fields in expected.items():
            for column, mapping in fields.items():
                with self.subTest(metric=metric_id, column=column):
                    self.assertEqual(metrics[metric_id]["database_fields"][column], mapping)

    def test_customer_metrics_document_blank_bucket_exclusion(self):
        self.assertIn("nonblank", get_metric("profit.customers").formula)
        self.assertIn("blank-customer", get_metric("profit.biggest_customer").formula)
        self.assertIn("unassigned customer rows", get_metric("ops.customer_concentration").formula)


if __name__ == "__main__":
    unittest.main()
