import unittest
from datetime import datetime
from tempfile import TemporaryDirectory
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, insert, select

from app.db import metadata, org_master
from app.master import load_master, read_master


class OrganizationMasterSafetyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_blank_organization_cells_are_not_imported_as_nan(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty-master.xlsx"
            pd.DataFrame({"Organization": [None, ""], "CountryName": ["India", "India"]}).to_excel(path, index=False)
            self.assertEqual(read_master(str(path)), [])

    def test_empty_master_upload_does_not_delete_existing_company_master(self):
        with self.engine.begin() as conn:
            conn.execute(insert(org_master).values(
                norm_key="acmelogistics",
                company="NG",
                name="Acme Logistics",
                country="India",
                sales="Sales",
                network="",
                conf="",
                contact="Contact",
                email="contact@example.test",
                updated_at=datetime(2026, 11, 11),
            ))
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty-master.xlsx"
            pd.DataFrame({"Organization": [None, ""], "CountryName": ["India", "India"]}).to_excel(path, index=False)
            with self.assertRaisesRegex(ValueError, "existing master was not changed"):
                load_master(self.engine, str(path), "NG")
        with self.engine.connect() as conn:
            rows = conn.execute(select(org_master).where(org_master.c.company == "NG")).mappings().all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Acme Logistics")


if __name__ == "__main__":
    unittest.main()
