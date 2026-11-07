"""Read-only Phase 2 readiness contract tests."""
import json
import unittest
from app.phase2_coverage import report_field_coverage


class CoverageTests(unittest.TestCase):
    def test_latest_promoted_report_wins(self):
        rows = [
            {"id": 1, "company": "NG", "report_type": "AE", "columns": json.dumps(["Shipment No", "Customer Code"])},
            {"id": 2, "company": "NG", "report_type": "AE", "columns": json.dumps(["Shipment No", "Sales Person"])},
        ]
        x = report_field_coverage(rows)[0]
        self.assertTrue(x["fields"]["sales_person"])
        self.assertFalse(x["fields"]["customer_code"])

    def test_missing_company_lob_is_not_silent(self):
        x = report_field_coverage([])
        self.assertEqual(len(x), 8)
        self.assertTrue(all(r["status"] == "no_promoted_import" for r in x))

    def test_bad_metadata_is_explicit(self):
        x = report_field_coverage([{"id": 1, "company": "NCS", "report_type": "OI", "columns": "bad"}])
        self.assertEqual(x[-1]["status"], "invalid_column_metadata")

    def test_no_customer_or_financial_rows_exposed(self):
        x = report_field_coverage([{"id": 1, "company": "NG", "report_type": "AE",
                                    "columns": '["Customer Code"]', "secret": "sensitive"}])
        self.assertNotIn("secret", repr(x))


if __name__ == "__main__":
    unittest.main()
