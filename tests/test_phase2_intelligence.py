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

if __name__ == "__main__":
    unittest.main()
