"""Tests for latest distinct customer job history and owner semantics."""
import unittest
from datetime import date

from app.customer_history import build_recent_jobs, build_last_shipment_owners, visible_report_types_for_scopes, normalize_customer_sql
from sqlalchemy import create_engine, literal, select


class CustomerHistoryTests(unittest.TestCase):
    def test_customer_sql_normalization_matches_dashboard_whitespace_rules(self):
        engine = create_engine("sqlite://")
        try:
            with engine.connect() as conn:
                value = conn.execute(select(normalize_customer_sql(
                    literal("  Acme\t\u00a0  Logistics\u202f\nIndia   ")
                ))).scalar_one()
            self.assertEqual(value, "acme logistics india")
        finally:
            engine.dispose()

    def test_mixed_customer_history_lob_scopes_use_union_not_intersection(self):
        self.assertEqual(visible_report_types_for_scopes([{"AE"}, {"OE"}]), ["AE", "OE"])
        self.assertEqual(visible_report_types_for_scopes([{"AE"}, set()]), ["AE", "AI", "OE", "OI"])

    def test_returns_five_distinct_jobs_sorted_by_job_date(self):
        rows = [
            {"company": "NG", "customer": "Acme", "job_no": f"J-{n}",
             "job_date": date(2026, 1, n), "lob": "FFWD AIR EXP",
             "extra": {"Job Owner": "Repeat Owner"}}
            for n in range(1, 8)
        ]
        result = build_recent_jobs(rows, lobs=["AE"])
        self.assertEqual(len(result), 5)
        self.assertEqual([row["job_no"] for row in result], ["J-7", "J-6", "J-5", "J-4", "J-3"])
        self.assertEqual(result[0]["job_owner"], "Repeat Owner")
        self.assertEqual([row["job_owner"] for row in result], ["Repeat Owner"] * 5)

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

    def test_blank_and_populated_duplicate_owners_are_order_independent_conflicts(self):
        base = {"company": "NG", "customer": "Acme", "job_no": "J-1",
                "job_date": date(2026, 1, 1), "lob": "FFWD AIR EXP"}
        blank = dict(base, extra={"Job Owner": ""})
        populated = dict(base, extra={"Job Owner": "Owner A"})
        for rows in ([blank, populated], [populated, blank]):
            with self.subTest(rows=rows):
                result = build_recent_jobs(rows)
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


    def test_last_shipment_owner_matches_shipment_number_and_date_not_latest_jpr_job(self):
        shipments = [
            {"company": "NG", "report_type": "AE", "shipment_no": "SHIP-07",
             "shipment_date": date(2026, 11, 7), "customer": "Acme"},
            {"company": "NG", "report_type": "AE", "shipment_no": "SHIP-06",
             "shipment_date": date(2026, 11, 6), "customer": "Acme"},
        ]
        jpr = [
            {"company": "NG", "job_no": "SHIP-07", "job_date": date(2026, 11, 7),
             "lob": "FFWD AIR EXP", "extra": {"Job Owner": "Shipment Owner"}},
            {"company": "NG", "job_no": "OTHER-LATEST", "job_date": date(2026, 11, 9),
             "lob": "FFWD AIR EXP", "extra": {"Job Owner": "Newer JPR Owner"}},
            {"company": "NG", "job_no": "SHIP-06", "job_date": date(2026, 11, 6),
             "lob": "FFWD AIR EXP", "extra": {"Job Owner": "Older Shipment Owner"}},
        ]
        result = build_last_shipment_owners(shipments, jpr, lobs=["AE"])
        self.assertEqual(result["acme"]["last_shipment_job_owner"], "Shipment Owner")
        self.assertEqual(result["acme"]["last_shipment_date"], "2026-11-07")
        self.assertEqual(result["acme"]["last_shipment_numbers"], ["SHIP-07"])

    def test_last_shipment_owner_respects_date_displayed_by_customer_table(self):
        shipments = [
            {"company": "NG", "report_type": "AE", "shipment_no": "SHIP-OLD",
             "shipment_date": date(2026, 11, 6), "customer": "Acme"},
            {"company": "NG", "report_type": "AE", "shipment_no": "SHIP-CURRENT",
             "shipment_date": date(2026, 11, 7), "customer": "Acme"},
        ]
        jpr = [
            {"company": "NG", "job_no": "SHIP-OLD", "job_date": date(2026, 11, 6),
             "lob": "FFWD AIR EXP", "extra": {"Job Owner": "Old Owner"}},
            {"company": "NG", "job_no": "SHIP-CURRENT", "job_date": date(2026, 11, 7),
             "lob": "FFWD AIR EXP", "extra": {"Job Owner": "Displayed Date Owner"}},
        ]
        result = build_last_shipment_owners(
            shipments, jpr, lobs=["AE"], target_date="2026-11-07")
        self.assertEqual(result["acme"]["last_shipment_job_owner"], "Displayed Date Owner")
        self.assertEqual(result["acme"]["last_shipment_date"], "2026-11-07")

    def test_last_shipment_owner_uses_unique_job_number_fallback_when_dates_differ(self):
        shipments = [{"company": "NG", "report_type": "AE", "shipment_no": "SHIP-1",
                      "shipment_date": date(2026, 11, 7), "customer": "Acme"}]
        jpr = [{"company": "NG", "job_no": "SHIP-1", "job_date": date(2026, 11, 5),
                "lob": "FFWD AIR EXP", "extra": {"Job Owner": "Matched Owner"}}]
        result = build_last_shipment_owners(shipments, jpr, lobs=["AE"])
        self.assertEqual(result["acme"]["last_shipment_job_owner"], "Matched Owner")

    def test_last_shipment_owner_does_not_guess_when_fallback_job_number_is_ambiguous(self):
        shipments = [{"company": "NG", "report_type": "AE", "shipment_no": "REUSED",
                      "shipment_date": date(2026, 11, 7), "customer": "Acme"}]
        jpr = [
            {"company": "NG", "job_no": "REUSED", "job_date": date(2026, 11, 5),
             "lob": "FFWD AIR EXP", "extra": {"Job Owner": "Owner A"}},
            {"company": "NG", "job_no": "REUSED", "job_date": date(2026, 11, 6),
             "lob": "FFWD AIR EXP", "extra": {"Job Owner": "Owner B"}},
        ]
        result = build_last_shipment_owners(shipments, jpr, lobs=["AE"])
        self.assertEqual(result["acme"]["last_shipment_job_owner"], "Owner unavailable")

    def test_multiple_shipments_on_last_date_report_multiple_owners(self):
        shipments = [
            {"company": "NG", "report_type": "AE", "shipment_no": "SHIP-A",
             "shipment_date": date(2026, 11, 7), "customer": "Acme"},
            {"company": "NG", "report_type": "AE", "shipment_no": "SHIP-B",
             "shipment_date": date(2026, 11, 7), "customer": "Acme"},
        ]
        jpr = [
            {"company": "NG", "job_no": "SHIP-A", "job_date": date(2026, 11, 7),
             "lob": "FFWD AIR EXP", "extra": {"Job Owner": "Owner A"}},
            {"company": "NG", "job_no": "SHIP-B", "job_date": date(2026, 11, 7),
             "lob": "FFWD AIR EXP", "extra": {"Job Owner": "Owner B"}},
        ]
        result = build_last_shipment_owners(shipments, jpr, lobs=["AE"])
        self.assertEqual(result["acme"]["last_shipment_job_owner"], "Multiple owners")


if __name__ == "__main__":
    unittest.main()
