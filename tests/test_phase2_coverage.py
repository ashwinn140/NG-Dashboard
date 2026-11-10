"""Read-only Phase 2 readiness contract tests."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
from app.phase2_coverage import report_field_coverage, job_history_field_coverage, job_history_data_quality


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


    def test_admin_overview_surfaces_job_history_readiness_without_row_data(self):
        ui = (ROOT / "app" / "web" / "admin.html").read_text()
        self.assertIn("Job history source readiness", ui)
        self.assertIn("job_history_fields", ui)
        self.assertIn("Header presence does not prove job-to-register matching", ui)
        self.assertIn("Matched register fallback", ui)



class JobHistoryDataQualityTests(unittest.TestCase):
    def test_unique_composite_match_supplies_register_owner(self):
        from datetime import date
        result = job_history_data_quality(
            [{"company": "NG", "report_type": "AE", "shipment_no": "J-1",
              "shipment_date": date(2026, 11, 8), "job_owner": "Owner A"}],
            [{"company": "NG", "job_no": "J-1", "job_date": date(2026, 11, 8),
              "lob": "FFWD AIR EXP", "extra": {}}])
        row = result[0]
        self.assertEqual(row["matched_register_jobs"], 1)
        self.assertEqual(row["owner_from_register"], 1)
        self.assertEqual(row["job_owner_populated"], 1)
        self.assertEqual(row["job_owner_coverage_pct"], 100.0)
        self.assertEqual(row["status"], "ready")

    def test_jpr_owner_field_has_priority_even_when_explicitly_blank(self):
        from datetime import date
        register = [{"company": "NG", "report_type": "AE", "shipment_no": "J-1",
                     "shipment_date": date(2026, 11, 8), "job_owner": "Register Owner"}]
        jobs = [
            {"company": "NG", "job_no": "J-1", "job_date": date(2026, 11, 8),
             "lob": "FFWD AIR EXP", "extra": {"Job Owner": "JPR Owner"}},
            {"company": "NG", "job_no": "J-2", "job_date": date(2026, 11, 9),
             "lob": "FFWD AIR EXP", "extra": {"Job Owner": ""}},
        ]
        row = job_history_data_quality(register, jobs)[0]
        self.assertEqual(row["owner_from_jpr"], 1)
        self.assertEqual(row["owner_from_register"], 0)
        self.assertEqual(row["jpr_owner_explicitly_blank"], 1)
        self.assertEqual(row["job_owner_missing"], 1)

    def test_ambiguous_number_fallback_is_not_guessed(self):
        from datetime import date
        register = [
            {"company": "NG", "report_type": "AE", "shipment_no": "REUSED",
             "shipment_date": date(2026, 1, 1), "job_owner": "Owner A"},
            {"company": "NG", "report_type": "AE", "shipment_no": "REUSED",
             "shipment_date": date(2026, 1, 2), "job_owner": "Owner B"},
        ]
        jobs = [{"company": "NG", "job_no": "REUSED", "job_date": date(2026, 1, 3),
                 "lob": "FFWD AIR EXP", "extra": {}}]
        row = job_history_data_quality(register, jobs)[0]
        self.assertEqual(row["ambiguous_register_matches"], 1)
        self.assertEqual(row["job_owner_populated"], 0)
        self.assertEqual(row["job_owner_missing"], 1)

    def test_wrong_lob_register_is_not_used_as_owner_fallback(self):
        from datetime import date
        register = [{"company": "NG", "report_type": "AE", "shipment_no": "J-1",
                     "shipment_date": date(2026, 11, 8), "job_owner": "Air Owner"}]
        jobs = [{"company": "NG", "job_no": "J-1", "job_date": date(2026, 11, 8),
                 "lob": "FFWD SEA EXP", "extra": {}}]
        rows = job_history_data_quality(register, jobs)
        row = next(item for item in rows if item["lob"] == "Sea Export")
        self.assertEqual(row["matched_register_jobs"], 0)
        self.assertEqual(row["unmatched_register_jobs"], 1)
        self.assertEqual(row["job_owner_missing"], 1)


    def test_road_jobs_never_inherit_owner_from_colliding_air_register(self):
        from datetime import date
        register = [{
            "company": "NG", "report_type": "AE", "shipment_no": "ROAD-1",
            "shipment_date": date(2026, 11, 8), "job_owner": "Unrelated Air Owner"
        }]
        jobs = [{
            "company": "NG", "job_no": "ROAD-1", "job_date": date(2026, 11, 8),
            "lob": "FFWD ROAD EXPORT", "extra": {}
        }]
        rows = job_history_data_quality(register, jobs)
        row = next(item for item in rows if item["lob"] == "FFWD ROAD EXPORT")
        self.assertEqual(row["register_not_applicable"], 1)
        self.assertEqual(row["matched_register_jobs"], 0)
        self.assertEqual(row["owner_from_register"], 0)
        self.assertEqual(row["job_owner_missing"], 1)

    def test_expected_lob_fallback_survives_wrong_lob_exact_date_collision(self):
        from datetime import date
        register = [
            {"company": "NG", "report_type": "OE", "shipment_no": "SHARED-1",
             "shipment_date": date(2026, 11, 8), "job_owner": "Wrong Air Owner"},
            {"company": "NG", "report_type": "AE", "shipment_no": "SHARED-1",
             "shipment_date": date(2026, 11, 7), "job_owner": "Correct Sea Owner"},
        ]
        jobs = [{
            "company": "NG", "job_no": "SHARED-1", "job_date": date(2026, 11, 8),
            "lob": "FFWD AIR EXPORT", "extra": {}
        }]
        rows = job_history_data_quality(register, jobs)
        row = next(item for item in rows if item["lob"] == "Air Export")
        self.assertEqual(row["matched_register_jobs"], 1)
        self.assertEqual(row["owner_from_register"], 1)
        self.assertEqual(row["job_owner_populated"], 1)
        self.assertEqual(row["job_owner_missing"], 0)

    def test_duplicate_jpr_identity_is_flagged_and_output_contains_no_names(self):
        from datetime import date
        job = {"company": "NG", "job_no": "J-1", "job_date": date(2026, 11, 8),
               "lob": "FFWD AIR EXP", "customer": "Sensitive Customer",
               "extra": {"Job Owner": "Sensitive Owner"}}
        result = job_history_data_quality([], [job, dict(job)])
        row = result[0]
        self.assertEqual(row["job_count"], 1)
        self.assertEqual(row["duplicate_job_identities"], 1)
        self.assertEqual(row["job_owner_missing"], 1)
        self.assertNotIn("Sensitive Customer", repr(result))
        self.assertNotIn("Sensitive Owner", repr(result))

if __name__ == "__main__":
    unittest.main()
