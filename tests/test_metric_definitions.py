"""Standalone regression tests: python -m unittest discover -s tests -p 'test_metric_definitions.py'"""
import unittest
from app.metric_definitions import DEFINITIONS, REGISTRY_VERSION, get_metric


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

    def test_metric_identity_and_source_mappings_match_the_actual_tables(self):
        self.assertEqual(REGISTRY_VERSION, "3")
        shipments = get_metric("ops.shipments").public_dict()
        self.assertIn("report_type", shipments["formula"])
        self.assertNotIn("department", shipments["formula"])
        rate = get_metric("ops.rate_sell").public_dict()
        self.assertEqual(
            rate["identity"],
            ["company", "report_type", "shipment_no", "shipment_date"],
        )
        self.assertEqual(
            rate["database_fields"]["Chargeable Wt"],
            "shipments.chargeable_wt",
        )
        customer = get_metric("profit.customers").public_dict()
        self.assertIn("no shipment-register fallback", customer["database_fields"]["Organization"])
        self.assertIn("(blank)", customer["formula"])
        self.assertIn("blank-customer GP remains", get_metric("profit.biggest_customer").formula)

    def test_cross_report_metrics_disclose_register_dependencies(self):
        air = get_metric("profit.air_yield")
        self.assertIn("Chargeable Wt", air.source_columns)
        self.assertIn("Shipment No", air.source_columns)
        self.assertIn("Shipment Date", air.source_columns)
        rate = get_metric("profit.rate_matched_estimate")
        self.assertIn("Buy Rate (UDF)", rate.source_columns)
        self.assertIn("Sell Rate (UDF)", rate.source_columns)
        self.assertIn("Shipment Date", rate.source_columns)
        concentration = get_metric("ops.customer_concentration")
        self.assertIn("including unassigned customer rows", concentration.formula)

    def test_unknown_metric(self):
        self.assertIsNone(get_metric("unknown"))


if __name__ == "__main__":
    unittest.main()
