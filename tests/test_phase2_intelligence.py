"""Regression tests for the Phase 2 Sales Person field wiring."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class IntelligenceFieldTests(unittest.TestCase):
    def test_salesperson_dataset_key_matches_ui(self):
        source = (ROOT / "app" / "dataset.py").read_text()
        ui = (ROOT / "app" / "web" / "intelligence.html").read_text()
        norm = lambda value: re.sub(r"[^a-z0-9]", "", value.lower())
        self.assertIn('"Sales Person"', source)
        self.assertIn('cats["x_" + norm(x)]', source)
        self.assertIn("name('x_" + norm("Sales Person") + "',i)", ui)
        self.assertNotIn("x_sales_person", ui)

    def test_finance_permission_guard(self):
        ui = (ROOT / "app" / "web" / "intelligence.html").read_text()
        self.assertIn("if(!D.user.finance)return null", ui)

    def test_intelligence_route_is_authenticated(self):
        source = (ROOT / "app" / "server.py").read_text()
        self.assertIn('def phase2_intelligence_page(user: dict = Depends(me)):', source)

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

    def test_intelligence_date_and_customer_filters(self):
        ui = (ROOT / "app" / "web" / "intelligence.html").read_text()
        self.assertIn("asOf=Math.min(today,d.date.reduce(", ui)
        self.assertIn("r.date<=asOf-period&&(!query||r.customer.toLowerCase().includes(query))", ui)

if __name__ == "__main__":
    unittest.main()
