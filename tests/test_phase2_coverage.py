"""Read-only Phase 2 readiness contract tests."""
import json
import unittest
from app.phase2_coverage import report_field_coverage, job_history_field_coverage


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


    def test_job_history_readiness_checks_jpr_and_register_headers(self):
        rows = [
            {"id": 1, "company": "NG", "report_type": "JP",
             "columns": json.dumps(["Job No.", "Job Date", "LOB", "Organization"])},
            {"id": 2, "company": "NG", "report_type": "AE",
             "columns": json.dumps(["Shipment No", "Shipment Date", "Job Owner"])},
        ]
        result = job_history_field_coverage(rows)
        jp = next(x for x in result if x["company"] == "NG" and x["report_type"] == "JP")
        ae = next(x for x in result if x["company"] == "NG" and x["report_type"] == "AE")
        self.assertEqual(jp["status"], "ok")
        self.assertTrue(jp["fields"]["job_number"])
        self.assertFalse(jp["fields"]["job_owner"])
        self.assertEqual(jp["job_owner_source"], "matched_register_fallback")
        self.assertEqual(ae["status"], "ok")
        self.assertTrue(ae["fields"]["job_owner"])

    def test_job_history_latest_promoted_import_wins_and_missing_is_explicit(self):
        rows = [
            {"id": 1, "company": "NG", "report_type": "AE",
             "columns": json.dumps(["Shipment No", "Shipment Date", "Job Owner"])},
            {"id": 2, "company": "NG", "report_type": "AE",
             "columns": json.dumps(["Shipment No", "Shipment Date"])},
        ]
        result = job_history_field_coverage(rows)
        ae = next(x for x in result if x["company"] == "NG" and x["report_type"] == "AE")
        ncs_jp = next(x for x in result if x["company"] == "NCS" and x["report_type"] == "JP")
        self.assertEqual(ae["status"], "missing_required_fields")
        self.assertFalse(ae["fields"]["job_owner"])
        self.assertEqual(ncs_jp["status"], "no_promoted_import")

    def test_job_history_bad_metadata_is_explicit_and_no_rows_leak(self):
        result = job_history_field_coverage([
            {"id": 1, "company": "NCS", "report_type": "JP",
             "columns": "invalid", "secret": "private job rows"}
        ])
        row = next(x for x in result if x["company"] == "NCS" and x["report_type"] == "JP")
        self.assertEqual(row["status"], "invalid_column_metadata")
        self.assertNotIn("private job rows", repr(result))


if __name__ == "__main__":
    unittest.main()
