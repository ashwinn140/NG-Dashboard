"""Integration tests for permission-scoped cross-LOB relationship activity."""
import json
import unittest
from datetime import date, timedelta

from sqlalchemy import insert

from app import auth
from app.db import imports, shipments
from app.server import create_app
from scripts.test_daily_replacement import ReplacementTests as Fixture


class CrossLobActivityApiTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.fixture.setUp()
        self.app = None

    def tearDown(self):
        if self.app is not None:
            self.app.state.store.stop = True
            self.app.state.store.wake.set()
        self.fixture.tearDown()

    def seed(self):
        as_of = date(2026, 11, 9)
        report_ids = {}
        with self.fixture.engine.begin() as conn:
            for lob in ("AE", "AI", "OE", "OI"):
                result = conn.execute(insert(imports).values(
                    company="NG", report_type=lob, received_at=self.fixture.clock,
                    report_time=self.fixture.clock, file_name=f"{lob}.xlsx",
                    status="promoted", row_count=0, range_from=date(2026, 1, 1),
                    range_to=date(2026, 12, 31), columns=json.dumps(
                        ["Shipment No", "Shipment Date", "Customer", "Job Owner"]
                    ), source="manual",
                ))
                report_ids[lob] = result.inserted_primary_key[0]
            records = []
            for lob, offsets in {
                "AE": (100, 110, 120, 130),
                "OI": (5, 10, 15, 20),
            }.items():
                for n, offset in enumerate(offsets):
                    when = as_of - timedelta(days=offset)
                    shipment_no = f"{lob}-{n}"
                    records.append({
                        "company": "NG", "report_type": lob,
                        "key": f"{lob}:{shipment_no}", "from_import": report_ids[lob],
                        "to_import": None, "row_hash": f"{lob}-{n}",
                        "shipment_no": shipment_no, "shipment_date": when,
                        "branch": "Mumbai", "customer": "Acme Logistics",
                        "job_owner": f"Owner {lob} {n}",
                        "extra": {
                            "Shipment No": shipment_no,
                            "Shipment Date": when.isoformat(),
                            "Customer": "Acme Logistics",
                            "Job Owner": f"Owner {lob} {n}",
                            "Airline": "Test Carrier",
                            "Branch": "Mumbai",
                        },
                    })
            conn.execute(insert(shipments), records)

    def login(self, client, email, lobs):
        auth.create_user(
            self.fixture.engine, email, "operations", "Test User",
            companies=["NG"], lobs=lobs, finance=False,
            password="Synthetic-pass123",
        )
        response = client.post("/auth/login", json={
            "login": email, "password": "Synthetic-pass123",
        })
        self.assertEqual(response.status_code, 200, response.text)
        return client.get("/api/me").json()["csrf"]

    def activity(self, client, csrf):
        dataset_response = client.get("/api/dataset")
        self.assertEqual(dataset_response.status_code, 200)
        data = json.loads(dataset_response.content)
        indices = [
            i for i, rep in enumerate(data["rep"])
            if data["reps"][rep][1] == "AE"
        ]
        return client.post("/api/metrics/activity", headers={
            "X-CSRF-Token": csrf,
        }, json={
            "metric": "ops.shipments",
            "dataset_built_at": data["built_at"],
            "indices": indices,
            "context": {
                "as_of": "2026-11-09",
                "company": "NGL",
                "mode": "Air",
                "direction": "Export",
                "service": "Forwarding",
                "relationships": {},
            },
        })

    def test_full_scope_identifies_active_customer_in_another_lob(self):
        self.seed()
        self.app = create_app(self.fixture.engine, self.fixture.tmp.name + "/uploads")
        from fastapi.testclient import TestClient
        client = TestClient(self.app)
        csrf = self.login(client, "full-scope@example.test", ["AE", "AI", "OE", "OI"])
        response = self.activity(client, csrf)
        self.assertEqual(response.status_code, 200, response.text)
        customer = response.json()["customers"][0]
        signal = customer["selected_lob_activity"]
        self.assertEqual(signal["classification"], "inactive_in_selected_lob_active_elsewhere")
        self.assertEqual(signal["active_elsewhere_lobs"], ["OI"])
        self.assertFalse(signal["company_wide_verified"])
        self.assertEqual(customer["identity_basis"], "exact source customer name, case/whitespace normalized")

    def test_restricted_user_cannot_learn_other_lob_activity(self):
        self.seed()
        self.app = create_app(self.fixture.engine, self.fixture.tmp.name + "/uploads")
        from fastapi.testclient import TestClient
        client = TestClient(self.app)
        csrf = self.login(client, "air-only@example.test", ["AE"])
        response = self.activity(client, csrf)
        self.assertEqual(response.status_code, 200, response.text)
        customer = response.json()["customers"][0]
        signal = customer["selected_lob_activity"]
        self.assertEqual(signal["classification"], "inactive_in_selected_lob_no_other_visible_activity")
        self.assertEqual(signal["visible_lobs"], ["AE"])
        self.assertEqual(signal["active_elsewhere_lobs"], [])
        self.assertFalse(signal["company_wide_verified"])
        self.assertNotIn("OI", json.dumps(response.json()))

if __name__ == "__main__":
    unittest.main()
