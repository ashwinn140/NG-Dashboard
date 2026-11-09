"""Tests for latest distinct customer job history and owner semantics."""
import unittest
from datetime import date

from app.customer_history import build_recent_jobs


class CustomerHistoryTests(unittest.TestCase):
    def test_returns_five_distinct_jobs_sorted_by_job_date(self):
        rows = [
            {"company": "NG", "customer": "Acme", "job_no": f"J-{n}",
             "job_date": date(2026, 1, n), "lob": "FFWD AIR EXP",
             "extra": {"Job Owner": f"Owner {n}"}}
            for n in range(1, 8)
        ]
        result = build_recent_jobs(rows, lobs=["AE"])
        self.assertEqual(len(result), 5)
        self.assertEqual([row["job_no"] for row in result], ["J-7", "J-6", "J-5", "J-4", "J-3"])
        self.assertEqual(result[0]["job_owner"], "Owner 7")

    def test_same_job_number_in_different_lob_or_company_is_distinct(self):
        rows = [
            {"company": "NG", "customer": "Acme", "job_no": "REUSED",
             "job_date": date(2026, 1, 1), "lob": "FFWD AIR EXP",
             "extra": {"Job Owner": "Air Owner"}},
            {"company": "NG", "customer": "Acme", "job_no": "REUSED",
             "job_date": date(2026, 1, 1), "lob": "FFWD SEA EXP",
             "extra": {"Job Owner": "Sea Owner"}},
            {"company": "NCS", "customer": "Acme", "job_no": "REUSED",
             "job_date": date(2026, 1, 1), "lob": "FFWD AIR EXP",
             "extra": {"Job Owner": "NCS Owner"}},
        ]
        result = build_recent_jobs(rows)
        self.assertEqual(len(result), 3)
        self.assertEqual({row["company"] for row in result}, {"NG", "NCS"})

    def test_missing_owner_is_not_inferred(self):
        row = {"company": "NG", "customer": "Acme", "job_no": "J-1",
               "job_date": date(2026, 1, 1), "lob": "FFWD AIR EXP",
               "extra": {"Job Owner": ""}}
        result = build_recent_jobs([row])
        self.assertEqual(result[0]["job_owner"], "Owner unavailable")
        self.assertEqual(result[0]["owner_status"], "missing")

    def test_conflicting_duplicate_owner_is_not_arbitrarily_selected(self):
        base = {"company": "NG", "customer": "Acme", "job_no": "J-1",
                "job_date": date(2026, 1, 1), "lob": "FFWD AIR EXP"}
        result = build_recent_jobs([
            dict(base, extra={"Job Owner": "Owner A"}),
            dict(base, extra={"Job Owner": "Owner B"}),
        ])
        self.assertEqual(result[0]["job_owner"], "Owner unavailable")
        self.assertEqual(result[0]["owner_status"], "conflicting")

    def test_road_and_general_jobs_are_included_for_unrestricted_scope(self):
        rows = [
            {"company": "NG", "customer": "Acme", "job_no": "R-1",
             "job_date": date(2026, 1, 1), "lob": "FFWD ROAD DOM",
             "extra": {"Job Owner": "Road Owner"}},
            {"company": "NG", "customer": "Acme", "job_no": "G-1",
             "job_date": date(2026, 1, 2), "lob": "GEN",
             "extra": {"Job Owner": "General Owner"}},
        ]
        self.assertEqual(len(build_recent_jobs(rows)), 2)
        self.assertEqual(len(build_recent_jobs(rows, lobs=["AE"])), 0)

    def test_operations_user_can_read_owner_history_without_finance_values(self):
        import pandas as pd
        from app import auth
        from app.server import create_app
        from fastapi.testclient import TestClient
        from scripts.test_daily_replacement import ReplacementTests as Fixture

        fixture = Fixture()
        fixture.setUp()
        app = None
        try:
            fixture.load(fixture.register(customers=("Customer", "Other Customer")))
            report = fixture.profit()
            report.df = pd.DataFrame([
                {"Location": "Mumbai", "LOB": "FFWD AIR EXP", "Job No.": f"JOB-{n}",
                 "Job Date": pd.Timestamp(2026, 1, n), "Date": pd.Timestamp(2026, 1, n),
                 "Organization": "Customer", "Job Owner": f"Owner {n}",
                 "Income (INR)": 100., "Expense (INR)": 50., "Profit (INR)": 50.}
                for n in range(1, 8)
            ])
            report.range_from = date(2026, 1, 1)
            report.range_to = date(2026, 1, 7)
            fixture.load_profit(report)
            auth.create_user(fixture.engine, "ops-history@example.test", "operations",
                             "Ops User", companies=["NG"], lobs=["AE"],
                             finance=False, password="Synthetic-pass123")
            app = create_app(fixture.engine, fixture.tmp.name + "/uploads")
            client = TestClient(app)
            self.assertEqual(client.post("/auth/login", json={
                "login": "ops-history@example.test", "password": "Synthetic-pass123"
            }).status_code, 200)
            csrf = client.get("/api/me").json()["csrf"]
            response = client.post("/api/customers/recent-jobs",
                headers={"X-CSRF-Token": csrf},
                json={"customers": [{"customer": "Customer", "companies": ["NG"], "lobs": ["AE"]}]})
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()["histories"][0]["jobs"]
            self.assertEqual(len(payload), 5)
            self.assertEqual([row["job_no"] for row in payload],
                             ["JOB-7", "JOB-6", "JOB-5", "JOB-4", "JOB-3"])
            self.assertEqual(payload[0]["job_owner"], "Owner 7")
            self.assertNotIn("income", repr(payload).lower())
            denied_company = client.post("/api/customers/recent-jobs",
                headers={"X-CSRF-Token": csrf},
                json={"customers": [{"customer": "Customer", "companies": ["NCS"], "lobs": ["AE"]}]})
            self.assertEqual(denied_company.status_code, 403)
            denied_lob = client.post("/api/customers/recent-jobs",
                headers={"X-CSRF-Token": csrf},
                json={"customers": [{"customer": "Customer", "companies": ["NG"], "lobs": ["OE"]}]})
            self.assertEqual(denied_lob.status_code, 403)
        finally:
            if app is not None:
                app.state.store.stop = True
                app.state.store.wake.set()
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
