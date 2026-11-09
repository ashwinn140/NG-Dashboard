"""Cross-LOB inactivity classification must respect scope and source coverage."""
import unittest
from datetime import date, timedelta

from app.phase2_metrics import cross_lob_customer_activity


class CrossLobActivityTests(unittest.TestCase):
    def setUp(self):
        self.as_of = date(2026, 11, 9)

    def dates(self, days):
        return [self.as_of - timedelta(days=n) for n in days]

    def test_air_export_inactive_but_sea_import_active_is_not_company_wide_lost(self):
        result = cross_lob_customer_activity(
            {"AE": self.dates([100, 110, 120, 130]),
             "OI": self.dates([5, 10, 15, 20])},
            self.as_of, ["AE"], ["AE", "AI", "OE", "OI"], True)
        self.assertEqual(result["classification"], "inactive_in_selected_lob_active_elsewhere")
        self.assertEqual(result["inactive_selected_lobs"], ["AE"])
        self.assertEqual(result["active_elsewhere_lobs"], ["OI"])
        self.assertFalse(result["company_wide_verified"])

    def test_restricted_scope_never_claims_company_wide_inactivity(self):
        result = cross_lob_customer_activity(
            {"AE": self.dates([100, 110, 120, 130])},
            self.as_of, ["AE"], ["AE"], False)
        self.assertEqual(result["classification"], "inactive_in_selected_lob_no_other_visible_activity")
        self.assertEqual(result["company_wide_status"], "not_verified_incomplete_scope_or_sources")
        self.assertFalse(result["company_wide_verified"])

    def test_missing_lob_source_prevents_company_wide_lost_claim(self):
        result = cross_lob_customer_activity(
            {"AE": self.dates([100, 110, 120, 130])},
            self.as_of, ["AE"], ["AE", "AI", "OE", "OI"], False)
        self.assertEqual(result["classification"], "inactive_in_selected_lob_no_other_visible_activity")
        self.assertFalse(result["source_coverage_complete"])

    def test_company_wide_inactivity_requires_all_lobs_and_inactive_combined_history(self):
        dates = self.dates([100, 110, 120, 130])
        result = cross_lob_customer_activity(
            {"AE": dates, "AI": dates[:2], "OE": dates[1:3], "OI": dates[2:]},
            self.as_of, ["AE"], ["AE", "AI", "OE", "OI"], True)
        self.assertEqual(result["classification"], "verified_company_wide_inactivity")
        self.assertEqual(result["company_wide_status"], "inactive")
        self.assertTrue(result["company_wide_verified"])

    def test_recent_activity_in_any_selected_lob_prevents_lost_classification(self):
        result = cross_lob_customer_activity(
            {"AE": self.dates([5, 10, 15, 20]),
             "OI": self.dates([100, 110, 120, 130])},
            self.as_of, ["AE", "OI"], ["AE", "AI", "OE", "OI"], True)
        self.assertEqual(result["classification"], "active_in_selected_scope")

    def test_sparse_history_is_insufficient_not_lost(self):
        result = cross_lob_customer_activity(
            {"AE": self.dates([200, 210])},
            self.as_of, ["AE"], ["AE", "AI", "OE", "OI"], True)
        self.assertEqual(result["classification"], "insufficient_history")
        self.assertEqual(result["company_wide_status"], "insufficient_history")


if __name__ == "__main__":
    unittest.main()
