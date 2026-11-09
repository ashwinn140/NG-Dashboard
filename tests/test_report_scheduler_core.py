import unittest
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from app.report_scheduler import (
    ScheduleValidationError, next_run_at, period_bounds,
    validate_schedule, safe_excel_text,
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

    def test_excel_formula_injection_is_escaped(self):
        for value in ("=1+1", "+cmd", "-1+1", "@SUM(A1:A2)", "\t=1", "\r=1"):
            self.assertTrue(safe_excel_text(value).startswith("'"))
        self.assertEqual(safe_excel_text("Normal customer"), "Normal customer")
        self.assertEqual(safe_excel_text(None), "")


if __name__ == "__main__":
    unittest.main()
