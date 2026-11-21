import unittest
from datetime import date

from sqlalchemy import create_engine, insert, select, func

from app.db import metadata, shipments, profit_lines, admin_log
from app.processor import retention_preview, apply_retention


class RetentionProfitLineTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            conn.execute(insert(shipments), [
                {"company": "NG", "report_type": "AE", "key": "OLD", "shipment_date": date(2023, 12, 31)},
                {"company": "NG", "report_type": "AE", "key": "KEEP", "shipment_date": date(2024, 4, 1)},
            ])
            conn.execute(insert(profit_lines), [
                {"company": "NG", "key": "OLD-JOB", "job_no": "OLD-JOB", "job_date": date(2023, 12, 31)},
                {"company": "NG", "key": "KEEP-JOB", "job_no": "KEEP-JOB", "job_date": date(2024, 4, 1)},
            ])

    def tearDown(self):
        self.engine.dispose()

    def test_preview_counts_shipments_and_profit_rows(self):
        result = retention_preview(self.engine, date(2026, 11, 21), years=3, fy_start_month=4)
        self.assertEqual(result["window_start"], date(2024, 4, 1))
        self.assertEqual(result["shipment_rows_before_window"], 1)
        self.assertEqual(result["profit_rows_before_window"], 1)
        self.assertEqual(result["total_rows_before_window"], 2)

    def test_apply_removes_old_rows_and_preserves_retained_years(self):
        result = apply_retention(self.engine, "admin@example.test", "approved test retention",
                                 date(2026, 11, 21), years=3, fy_start_month=4)
        self.assertEqual(result["removed_shipments"], 1)
        self.assertEqual(result["removed_profit_lines"], 1)
        with self.engine.connect() as conn:
            shipments_left = conn.execute(select(func.count()).select_from(shipments)).scalar()
            profit_left = conn.execute(select(func.count()).select_from(profit_lines)).scalar()
            audit_count = conn.execute(select(func.count()).select_from(admin_log)).scalar()
        self.assertEqual(shipments_left, 1)
        self.assertEqual(profit_left, 1)
        self.assertEqual(audit_count, 1)


if __name__ == "__main__":
    unittest.main()
