"""Isolated Phase 2 metric contract tests; no database or network required."""
import unittest
from datetime import date, timedelta
from app.phase2_metrics import gp_bridge, customer_activity


class TestGPBridge(unittest.TestCase):
    def test_exact_bridge(self):
        r = gp_bridge(10, 1000.0, 12, 1080.0)
        self.assertEqual(r.status, "ok")
        self.assertAlmostEqual(r.volume_impact, 200)
        self.assertAlmostEqual(r.yield_impact, -120)
        self.assertAlmostEqual(r.volume_impact + r.yield_impact, r.change)

    def test_missing_gp_is_not_zero(self):
        r = gp_bridge(10, None, 12, 1200)
        self.assertEqual(r.status, "incomplete_gp")
        self.assertIsNone(r.volume_impact)

    def test_zero_denominator_is_not_comparable(self):
        r = gp_bridge(0, 0, 5, 100)
        self.assertEqual(r.status, "not_comparable")
        self.assertIsNone(r.yield_impact)

    def test_negative_shipment_count_rejected(self):
        with self.assertRaises(ValueError):
            gp_bridge(-1, 0, 5, 10)


class TestActivity(unittest.TestCase):
    def test_sparse_history_not_lost(self):
        r = customer_activity([date(2026, 1, 1)], date(2026, 11, 7))
        self.assertEqual(r["status"], "insufficient_history")

    def test_frequent_shipper_active(self):
        today = date(2026, 11, 7)
        r = customer_activity([today - timedelta(days=n) for n in (5, 10, 15, 20)], today)
        self.assertEqual(r["status"], "active")
        self.assertEqual(r["threshold_days"], 30)

    def test_frequent_shipper_inactive(self):
        today = date(2026, 11, 7)
        r = customer_activity([today - timedelta(days=n) for n in (70, 75, 80, 85)], today)
        self.assertEqual(r["status"], "inactive")

    def test_future_shipments_ignored(self):
        today = date(2026, 11, 7)
        r = customer_activity([today + timedelta(days=1)], today)
        self.assertEqual(r["status"], "insufficient_history")
        self.assertIsNone(r["days_since_last"])


if __name__ == "__main__":
    unittest.main()
