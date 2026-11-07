"""Regression tests for the Phase 2 Sales Person field wiring."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class IntelligenceFieldTests(unittest.TestCase):
    def test_business_intelligence_removed(self):
        ui = (ROOT / "app" / "web" / "dashboard.html").read_text()
        source = (ROOT / "app" / "server.py").read_text()
        self.assertNotIn('href="/phase2/intelligence"', ui)
        self.assertNotIn('Business Intelligence <span', ui)
        self.assertIn('raise HTTPException(410, "Business Intelligence has been removed.', source)

    def test_production_dashboard_has_no_demo_toggle_or_demo_mask(self):
        ui = (ROOT / "app" / "web" / "dashboard.html").read_text()
        self.assertNotIn("Show demo history", ui)
        self.assertNotIn("opt.demo && S.demo", ui)
        self.assertNotIn("opt.demo && S.pdemo", ui)

    def test_yoy_uses_actual_imported_baseline(self):
        ui = (ROOT / "app" / "web" / "dashboard.html").read_text()
        self.assertNotIn("previous-year source completeness not verified", ui)
        self.assertIn("Current: ' + value + ' · Previous: ' + previousValue", ui)
        self.assertIn("No percentage (zero or unavailable baseline)", ui)

if __name__ == "__main__":
    unittest.main()

