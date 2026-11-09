import unittest
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from app.report_scheduler import (
    ScheduleValidationError, next_run_at, period_bounds,
    validate_schedule, safe_excel_text, build_report_rows, build_report_workbook,
)


class SchedulerCoreTests(unittest.TestCase):
    def test_relative_periods_use_end_exclusive_bounds(self):
        as_of = date(2026, 11, 9)  # Monday
        self.assertEqual(period_bounds("yesterday", as_of), (date(2026, 11, 8), date(2026, 11, 9)))
        self.assertEqual(period_bounds("last_7_completed_days", as_of), (date(2026, 11, 2), date(2026, 11, 9)))
        self.assertEqual(period_bounds("prior_calendar_week", as_of), (date(2026, 11, 2), date(2026, 11, 9)))
        self.assertEqual(period_bounds("current_month_to_date", as_of), (date(2026, 11, 1), date(2026, 11, 10)))
        self.assertEqual(period_bounds("prior_calendar_month", as_of), (date(2026, 10, 1), date(2026, 11, 1)))

    def test_fiscal_periods_respect_april_start(self):
        as_of = date(2026, 2, 15)
        self.assertEqual(period_bounds("current_fy_to_date", as_of, 4), (date(2025, 4, 1), date(2026, 2, 16)))
        self.assertEqual(period_bounds("prior_fy", as_of, 4), (date(2024, 4, 1), date(2025, 4, 1)))

    def test_fixed_range_is_inclusive_at_both_user_selected_ends(self):
        self.assertEqual(period_bounds("fixed_range", date(2026, 11, 9), start_date="2026-10-01", end_date="2026-10-31"),
                         (date(2026, 10, 1), date(2026, 11, 1)))
        with self.assertRaises(ScheduleValidationError):
            period_bounds("fixed_range", date.today(), start_date="2026-11-02", end_date="2026-11-01")

    def test_daily_schedule_uses_local_time_and_strictly_future_instant(self):
        zone = ZoneInfo("Asia/Kolkata")
        now = datetime(2026, 11, 9, 1, 30, tzinfo=timezone.utc)  # 07:00 IST
        run = next_run_at(now, "daily", "Asia/Kolkata", "08:00")
        self.assertEqual(run.astimezone(zone).strftime("%Y-%m-%d %H:%M"), "2026-11-09 08:00")
        same = next_run_at(datetime(2026, 11, 9, 2, 30, tzinfo=timezone.utc), "daily", "Asia/Kolkata", "08:00")
        self.assertEqual(same.astimezone(zone).strftime("%Y-%m-%d %H:%M"), "2026-11-10 08:00")

    def test_weekly_schedule_advances_when_today_run_time_has_passed(self):
        now = datetime(2026, 11, 9, 4, 0, tzinfo=timezone.utc)  # 09:30 IST Monday
        run = next_run_at(now, "weekly", "Asia/Kolkata", "08:00", weekday=0)
        self.assertEqual(run.astimezone(ZoneInfo("Asia/Kolkata")).date(), date(2026, 11, 16))

    def test_monthly_day_31_clamps_to_month_end(self):
        now = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        run = next_run_at(now, "monthly", "Asia/Kolkata", "08:00", monthday=31)
        self.assertEqual(run.astimezone(ZoneInfo("Asia/Kolkata")).date(), date(2026, 4, 30))
        after = next_run_at(datetime(2026, 4, 30, 5, 0, tzinfo=timezone.utc), "monthly", "Asia/Kolkata", "08:00", monthday=31)
        self.assertEqual(after.astimezone(ZoneInfo("Asia/Kolkata")).date(), date(2026, 5, 31))

    def test_dst_gap_moves_to_next_valid_minute(self):
        now = datetime(2026, 3, 8, 5, 0, tzinfo=timezone.utc)
        run = next_run_at(now, "daily", "America/New_York", "02:30")
        local = run.astimezone(ZoneInfo("America/New_York"))
        self.assertEqual(local.strftime("%Y-%m-%d %H:%M"), "2026-03-08 03:00")

    def test_dst_fold_uses_first_occurrence(self):
        now = datetime(2026, 11, 1, 4, 0, tzinfo=timezone.utc)
        run = next_run_at(now, "daily", "America/New_York", "01:30")
        self.assertEqual(run, datetime(2026, 11, 1, 5, 30, tzinfo=timezone.utc))

    def test_invalid_timezone_and_schedule_parameters_rejected(self):
        with self.assertRaises(ScheduleValidationError):
            next_run_at(datetime.now(timezone.utc), "daily", "Not/AZone", "08:00")
        with self.assertRaises(ScheduleValidationError):
            next_run_at(datetime.now(timezone.utc), "weekly", "Asia/Kolkata", "08:00")
        with self.assertRaises(ScheduleValidationError):
            next_run_at(datetime.now(timezone.utc), "monthly", "Asia/Kolkata", "08:00", monthday=32)

    def test_user_scope_and_report_permissions_are_enforced(self):
        user = {"id": 7, "email": "ops@example.com", "companies": ["NG"], "lobs": ["AE"], "finance": False}
        definition = validate_schedule(user, {"report_id": "shipment_register", "frequency": "daily"})
        self.assertEqual(definition["companies"], ["NG"])
        self.assertEqual(definition["lobs"], ["AE"])
        self.assertEqual(definition["date_basis"], "Shipment Date")
        self.assertEqual(definition["recipients"], ["self"])
        with self.assertRaises(PermissionError):
            validate_schedule(user, {"report_id": "job_profitability"})
        with self.assertRaises(PermissionError):
            validate_schedule(user, {"report_id": "shipment_register", "companies": ["NCS"]})
        with self.assertRaises(PermissionError):
            validate_schedule(user, {"report_id": "shipment_register", "recipients": ["external@example.com"]})

    def test_job_profitability_is_job_date_based_and_finance_only(self):
        user = {"id": 1, "email": "finance@example.com", "companies": [], "lobs": [], "finance": True}
        definition = validate_schedule(user, {"report_id": "job_profitability", "frequency": "monthly", "monthday": 31})
        self.assertEqual(definition["date_basis"], "Job Date")
        self.assertEqual(definition["monthday"], 31)
        self.assertEqual(definition["status"], "paused")

    def test_allowlisted_columns_filters_and_sort(self):
        user = {"id": 1, "email": "ops@example.com", "companies": [], "lobs": [], "finance": False}
        definition = validate_schedule(user, {
            "report_id": "shipment_register", "columns": ["company", "shipment_no", "shipment_date"],
            "filters": {"customer": ["Alpha", "Beta"]},
            "sort": {"field": "shipment_date", "direction": "desc"},
            "summary_detail": "detail", "totals": True,
        })
        self.assertEqual(definition["columns"], ["company", "shipment_no", "shipment_date"])
        self.assertEqual(definition["filters"]["customer"], ["Alpha", "Beta"])
        with self.assertRaises(ScheduleValidationError):
            validate_schedule(user, {"report_id": "shipment_register", "columns": ["raw_sql"]})
        with self.assertRaises(ScheduleValidationError):
            validate_schedule(user, {"report_id": "shipment_register", "filters": {"table": ["users"]}})

    def fixture_dataset(self):
        from datetime import date
        day1 = (date(2026, 11, 7) - date(1970, 1, 1)).days
        day2 = (date(2026, 11, 8) - date(1970, 1, 1)).days
        cols = {
            "customer": {"d": ["=HYPERLINK(\\\"bad\\\")"], "c": [0, 0], "pc": [0]},
            "branch": {"d": ["Mumbai"], "c": [0, 0], "pc": [0]},
            "agent": {"d": ["Agent A"], "c": [0, 0]},
            "job_owner": {"d": ["Owner A"], "c": [0, 0]},
            "origin": {"d": ["BOM"], "c": [0, 0]},
            "destination": {"d": ["DXB"], "c": [0, 0]},
            "status": {"d": ["Open"], "c": [0, 0]},
            "p_job": {"d": ["J1"], "pc": [0]},
            "p_lob": {"d": ["Air Export"], "pc": [0]},
            "p_mode": {"d": ["Air"], "pc": [0]},
            "p_direction": {"d": ["Export"], "pc": [0]},
            "p_kind": {"d": ["Freight forwarding"], "pc": [0]},
            "jp_sales_person": {"d": ["Sales A"], "pc": [0]},
        }
        return {"rep": [0, 0], "reps": [["NG", "AE"]], "no": ["S1", "S2"],
                "date": [day1, day2], "ops": [-1, -1], "fin": [-1, -1],
                "gross": [1.0, 2.0], "chg": [1.5, 2.5], "teus": [0.0, 0.0],
                "cbm": [1.0, 2.0], "cols": cols,
                "p": {"co": [0], "jd": [day2], "income": [100.0], "expense": [40.0]}}

    def test_shipment_register_workbook_uses_shipment_date_and_escapes_text(self):
        from openpyxl import load_workbook
        from io import BytesIO
        from datetime import date
        user = {"id": 7, "email": "ops@example.com", "companies": ["NG"], "lobs": ["AE"], "finance": False}
        definition = validate_schedule(user, {"report_id": "shipment_register", "frequency": "daily",
            "columns": ["company", "lob", "shipment_no", "shipment_date", "customer", "chargeable_weight_t"]})
        rows = build_report_rows(self.fixture_dataset(), definition, date(2026, 11, 1), date(2026, 11, 9))
        self.assertEqual(len(rows), 2)
        result = build_report_workbook(self.fixture_dataset(), definition, date(2026, 11, 1), date(2026, 11, 9),
            {"status": "fresh", "max_age_hours": 48})
        wb = load_workbook(BytesIO(result["content"]), data_only=True)
        ws = wb["Report"]
        self.assertEqual(result["row_count"], 2)
        self.assertTrue(str(ws["E7"].value).startswith("'="), "untrusted source text is escaped for Excel")
        self.assertEqual(ws["D7"].number_format, "dd-mmm-yyyy")
        self.assertTrue(ws.auto_filter.ref.startswith("A6:"))

    def test_shipment_register_summary_and_customer_performance_aggregate(self):
        from datetime import date
        user = {"id": 7, "email": "ops@example.com", "companies": ["NG"], "lobs": ["AE"], "finance": False}
        d = self.fixture_dataset()
        shipment = validate_schedule(user, {"report_id": "shipment_register", "summary_detail": "summary"})
        rows = build_report_rows(d, shipment, date(2026, 11, 1), date(2026, 11, 9))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["shipments"], 2)
        self.assertEqual(rows[0]["air_chargeable_weight_t"], 4.0)
        customer = validate_schedule(user, {"report_id": "customer_performance"})
        rows2 = build_report_rows(d, customer, date(2026, 11, 1), date(2026, 11, 9))
        self.assertEqual(rows2[0]["shipments"], 2)
        with self.assertRaises(ScheduleValidationError):
            validate_schedule(user, {"report_id": "customer_performance", "summary_detail": "detail"})

    def test_job_profitability_workbook_uses_job_date_and_jpr_amounts(self):
        from datetime import date
        finance = {"id": 9, "email": "finance@example.com", "companies": ["NG"], "lobs": ["AE"], "finance": True}
        definition = validate_schedule(finance, {"report_id": "job_profitability", "frequency": "monthly",
            "columns": ["company", "lob", "job_no", "job_date", "customer", "income", "expense", "profit", "margin"]})
        rows = build_report_rows(self.fixture_dataset(), definition, date(2026, 11, 1), date(2026, 11, 9))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["profit"], 60.0)
        self.assertEqual(rows[0]["margin"], 0.6)

    def test_database_contains_durable_schedule_and_run_tables(self):
        from sqlalchemy import create_engine, inspect
        from app.db import metadata
        engine = create_engine("sqlite:///:memory:")
        metadata.create_all(engine)
        names = set(inspect(engine).get_table_names())
        self.assertIn("report_schedules", names)
        self.assertIn("report_runs", names)
        self.assertIn("uq_report_run_schedule_instant", {c["name"] for c in inspect(engine).get_unique_constraints("report_runs")})
        engine.dispose()

    def test_excel_formula_injection_is_escaped(self):
        for value in ("=1+1", "+cmd", "-1+1", "@SUM(A1:A2)", "\t=1", "\r=1"):
            self.assertTrue(safe_excel_text(value).startswith("'"))
        self.assertTrue(safe_excel_text("  =1+1").startswith("'"))
        self.assertEqual(safe_excel_text("Normal customer"), "Normal customer")
        self.assertEqual(safe_excel_text(None), "")


if __name__ == "__main__":
    unittest.main()
