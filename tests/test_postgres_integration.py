"""PostgreSQL integration smoke tests for the production database dialect.

The normal unit suite uses SQLite for speed. CI supplies TEST_DATABASE_URL and
runs this module against a real PostgreSQL service so schema creation, JSON
round-trips, date types, indexes, and portable customer normalization are
exercised on the production database engine.
"""
import os
import unittest
from uuid import uuid4

from sqlalchemy import create_engine, select, text

from app.db import metadata, shipments, profit_lines
from app.customer_history import normalize_customer_sql


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "TEST_DATABASE_URL is not configured")
class PostgreSQLIntegrationTests(unittest.TestCase):
    def test_production_schema_and_operational_queries_on_postgresql(self):
        url = os.environ["TEST_DATABASE_URL"]
        admin_engine = create_engine(url, future=True)
        schema = "ng_audit_" + uuid4().hex
        scoped_engine = None
        try:
            with admin_engine.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            scoped_engine = create_engine(
                url, future=True,
                connect_args={"options": f"-csearch_path={schema}"},
            )

            # Build every application table/index in an isolated schema. This
            # catches PostgreSQL DDL incompatibilities without touching shared DB objects.
            metadata.create_all(scoped_engine)

            with scoped_engine.begin() as conn:
                conn.execute(shipments.insert().values(
                    company="NG", report_type="AE", key="shipment-1",
                    from_import=1, to_import=None, shipment_no="S-100",
                    shipment_date="2026-11-10", customer="  Acme\\t  Logistics ",
                    extra={"Job Owner": "Owner A", "source": "JPR"},
                ))
                conn.execute(profit_lines.insert().values(
                    company="NG", key="job-1", from_import=1, to_import=None,
                    lob="FFWD AIR EXP", job_no="S-100", job_date="2026-11-10",
                    customer="Acme Logistics",
                    extra={"Job Owner": "Owner A", "source_row": 7},
                ))

                normalized = conn.execute(select(
                    normalize_customer_sql(shipments.c.customer)
                )).scalar_one()
                self.assertEqual(normalized, "acme logistics")

                shipment = conn.execute(select(
                    shipments.c.shipment_no, shipments.c.extra
                )).mappings().one()
                self.assertEqual(shipment["shipment_no"], "S-100")
                self.assertEqual(shipment["extra"]["Job Owner"], "Owner A")

                job = conn.execute(select(
                    profit_lines.c.job_no, profit_lines.c.job_date,
                    profit_lines.c.extra,
                )).mappings().one()
                self.assertEqual(job["job_no"], "S-100")
                self.assertEqual(str(job["job_date"]), "2026-11-10")
                self.assertEqual(job["extra"]["source_row"], 7)
        finally:
            if scoped_engine is not None:
                scoped_engine.dispose()
            with admin_engine.begin() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            admin_engine.dispose()


if __name__ == "__main__":
    unittest.main()
