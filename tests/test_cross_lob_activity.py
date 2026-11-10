"""Cross-LOB inactivity classification must respect scope and source coverage."""
import unittest
from datetime import date, timedelta
from app.phase2_metrics import cross_lob_customer_activity


class CrossLobActivityTests(unittest.TestCase):
    def setUp(self):
        self.as_of = date(2026, 11, 9)

    def dates(self, offsets):
        return [self.as_of - timedelta(days=n) for n in offsets]

    def test_inactive_air_export_but_active_sea_import_is_not_company_wide_lost(self):
        result = cross_lob_customer_activity(
            {"AE": self.dates([100, 110, 120, 130]), "OI": self.dates([5, 10, 15, 20])},
            self.as_of, ["AE"], ["AE", "AI", "OE", "OI"], True)
        self.assertEqual(result["classification"], "inactive_in_selected_lob_active_elsewhere")
        self.assertEqual(result["active_elsewhere_lobs"], ["OI"])
        self.assertFalse(result["company_wide_verified"])

    def test_restricted_scope_never_claims_company_wide_inactivity(self):
        result = cross_lob_customer_activity(
            {"AE": self.dates([100, 110, 120, 130])},
            self.as_of, ["AE"], ["AE"], False)
        self.assertEqual(result["classification"], "inactive_in_selected_lob_no_other_visible_activity")
        self.assertEqual(result["company_wide_status"], "not_verified_incomplete_scope_or_sources")
        self.assertFalse(result["company_wide_verified"])
        self.assertEqual(result["visible_lobs"], ["AE"])

    def test_missing_source_prevents_company_wide_inactive_claim(self):
        dates = self.dates([100, 110, 120, 130])
        result = cross_lob_customer_activity(
            {"AE": dates, "AI": dates, "OE": dates, "OI": dates},
            self.as_of, ["AE"], ["AE", "AI", "OE", "OI"], False)
        self.assertFalse(result["source_coverage_complete"])
        self.assertFalse(result["company_wide_verified"])

    def test_complete_company_scope_can_verify_inactivity(self):
        dates = self.dates([100, 110, 120, 130])
        result = cross_lob_customer_activity(
            {"AE": dates, "AI": dates, "OE": dates, "OI": dates},
            self.as_of, ["AE"], ["AE", "AI", "OE", "OI"], True)
        self.assertEqual(result["classification"], "verified_company_wide_inactivity")
        self.assertTrue(result["company_wide_verified"])

    def test_sparse_history_is_insufficient_not_lost(self):
        result = cross_lob_customer_activity(
            {"AE": self.dates([200, 210])},
            self.as_of, ["AE"], ["AE", "AI", "OE", "OI"], True)
        self.assertEqual(result["classification"], "insufficient_history")


if __name__ == "__main__":
    unittest.main()
