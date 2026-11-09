"""Core contracts for the durable, permission-aware Excel report scheduler.

No worker is started from this module. Scheduling is deliberately inert until
server-side queue, permissions, freshness and delivery controls are integrated.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc
COMPANIES = ("NG", "NCS")
LOBS = ("AE", "AI", "OE", "OI")
PERIODS = (
    "yesterday", "today_to_date", "last_7_completed_days",
    "last_30_completed_days", "prior_calendar_week",
    "current_month_to_date", "prior_calendar_month",
    "current_fy_to_date", "prior_fy", "fixed_range",
)
FREQUENCIES = ("daily", "weekly", "monthly")

REPORT_CATALOG = {
    "shipment_register": {
        "version": 1, "title": "Shipment Register", "permission": "operations",
        "date_basis": "Shipment Date", "date_array": "date",
        "columns": (
            "company", "lob", "shipment_no", "shipment_date", "customer",
            "branch", "agent", "salesperson", "job_owner", "origin",
            "destination", "status", "operations_locked_on",
            "financials_locked_on", "gross_weight_t", "chargeable_weight_t",
            "teus", "volume_cbm",
        ),
        "filters": ("customer", "branch", "agent", "salesperson", "job_owner", "status"),
    },
    "customer_performance": {
        "version": 1, "title": "Customer Shipment Performance", "permission": "operations",
        "date_basis": "Shipment Date", "date_array": "date",
        "columns": (
            "company", "customer", "shipments", "air_shipments",
            "ocean_shipments", "air_chargeable_weight_t", "ocean_teus",
            "lob_count", "last_shipment_date",
        ),
        "filters": ("customer", "branch", "agent", "salesperson", "job_owner"),
    },
    "job_profitability": {
        "version": 1, "title": "Job Profitability", "permission": "finance",
        "date_basis": "Job Date", "date_array": "p.jd",
        "columns": (
            "company", "lob", "job_no", "job_date", "customer", "branch",
            "mode", "direction", "service", "income", "expense", "profit",
            "margin",
        ),
        "filters": ("customer", "branch", "salesperson", "lob", "mode", "direction", "service"),
    },
}


class ScheduleValidationError(ValueError):
    pass


def _date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ScheduleValidationError(f"{label} must be an ISO date (YYYY-MM-DD).")


def _local_candidate(day: date, local_time: time, zone: ZoneInfo) -> datetime:
    """Attach zone; ambiguous times use fold=0, nonexistent times move forward to next valid minute."""
    naive = datetime.combine(day, local_time)
    candidate = naive.replace(tzinfo=zone, fold=0)
    if candidate.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == naive:
        return candidate
    for minute in range(1, 181):
        adjusted = naive + timedelta(minutes=minute)
        candidate = adjusted.replace(tzinfo=zone, fold=0)
        if candidate.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == adjusted:
            return candidate
    raise ScheduleValidationError("The selected local time cannot be resolved in this timezone.")


def next_run_at(now: datetime, frequency: str, timezone_name: str,
                run_at_local: str, weekday: int | None = None,
                monthday: int | None = None) -> datetime:
    """Return the next strictly-future UTC run instant for a local schedule."""
    if now.tzinfo is None:
        raise ScheduleValidationError("The scheduler clock must be timezone-aware.")
    if frequency not in FREQUENCIES:
        raise ScheduleValidationError("Frequency must be daily, weekly or monthly.")
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, TypeError):
        raise ScheduleValidationError("Choose a valid IANA timezone.")
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(run_at_local)):
        raise ScheduleValidationError("Run time must use HH:MM (24-hour local time).")
    hh, mm = map(int, run_at_local.split(":"))
    local_now = now.astimezone(zone)
    clock = time(hh, mm)

    if frequency == "daily":
        day = local_now.date()
        candidate = _local_candidate(day, clock, zone)
        if candidate.astimezone(UTC) <= now.astimezone(UTC):
            candidate = _local_candidate(day + timedelta(days=1), clock, zone)
    elif frequency == "weekly":
        if not isinstance(weekday, int) or not 0 <= weekday <= 6:
            raise ScheduleValidationError("Weekly schedules require weekday 0–6 (Monday=0).")
        offset = (weekday - local_now.weekday()) % 7
        day = local_now.date() + timedelta(days=offset)
        candidate = _local_candidate(day, clock, zone)
        if candidate.astimezone(UTC) <= now.astimezone(UTC):
            candidate = _local_candidate(day + timedelta(days=7), clock, zone)
    else:
        if not isinstance(monthday, int) or not 1 <= monthday <= 31:
            raise ScheduleValidationError("Monthly schedules require a day from 1 to 31.")
        day_num = min(monthday, calendar.monthrange(local_now.year, local_now.month)[1])
        day = date(local_now.year, local_now.month, day_num)
        candidate = _local_candidate(day, clock, zone)
        if candidate.astimezone(UTC) <= now.astimezone(UTC):
            year, month = local_now.year, local_now.month + 1
            if month == 13:
                year, month = year + 1, 1
            day_num = min(monthday, calendar.monthrange(year, month)[1])
            candidate = _local_candidate(date(year, month, day_num), clock, zone)
    return candidate.astimezone(UTC)


def period_bounds(period: str, as_of: date, fiscal_start_month: int = 4,
                  start_date: str | None = None, end_date: str | None = None) -> tuple[date, date]:
    """Return [start, end_exclusive); fixed_range inputs are inclusive calendar dates."""
    if period not in PERIODS:
        raise ScheduleValidationError("Unsupported relative period.")
    tomorrow = as_of + timedelta(days=1)
    if period == "yesterday":
        return as_of - timedelta(days=1), as_of
    if period == "today_to_date":
        return as_of, tomorrow
    if period == "last_7_completed_days":
        return as_of - timedelta(days=7), as_of
    if period == "last_30_completed_days":
        return as_of - timedelta(days=30), as_of
    if period == "prior_calendar_week":
        current_monday = as_of - timedelta(days=as_of.weekday())
        return current_monday - timedelta(days=7), current_monday
    if period == "current_month_to_date":
        return date(as_of.year, as_of.month, 1), tomorrow
    if period == "prior_calendar_month":
        current_month = date(as_of.year, as_of.month, 1)
        if as_of.month == 1:
            previous_month = date(as_of.year - 1, 12, 1)
        else:
            previous_month = date(as_of.year, as_of.month - 1, 1)
        return previous_month, current_month
    if not isinstance(fiscal_start_month, int) or not 1 <= fiscal_start_month <= 12:
        raise ScheduleValidationError("Fiscal start month must be 1–12.")
    fy_year = as_of.year if as_of.month >= fiscal_start_month else as_of.year - 1
    fy_start = date(fy_year, fiscal_start_month, 1)
    if period == "current_fy_to_date":
        return fy_start, tomorrow
    if period == "prior_fy":
        return date(fy_year - 1, fiscal_start_month, 1), fy_start
    if not start_date or not end_date:
        raise ScheduleValidationError("Fixed range requires both start_date and end_date.")
    start, end = _date(start_date, "start_date"), _date(end_date, "end_date")
    if start > end:
        raise ScheduleValidationError("start_date must be on or before end_date.")
    return start, end + timedelta(days=1)


def validate_schedule(user: dict, payload: dict) -> dict:
    """Validate and normalize a schedule. Recipient is self-only in the pilot."""
    if not isinstance(payload, dict):
        raise ScheduleValidationError("A schedule definition is required.")
    report_id = payload.get("report_id")
    report = REPORT_CATALOG.get(report_id)
    if not report:
        raise ScheduleValidationError("Choose a report from the enabled catalog.")
    if report["permission"] == "finance" and not user.get("finance"):
        raise PermissionError("Finance permission is required for Job Profitability.")

    allowed_companies = set(user.get("companies") or COMPANIES)
    allowed_lobs = set(user.get("lobs") or LOBS)
    companies = payload.get("companies") or sorted(allowed_companies)
    lobs = payload.get("lobs") or sorted(allowed_lobs)
    if not isinstance(companies, list) or not companies or not set(companies).issubset(set(COMPANIES)):
        raise ScheduleValidationError("Select at least one valid company.")
    if not set(companies).issubset(allowed_companies):
        raise PermissionError("The schedule includes a company outside your access scope.")
    if not isinstance(lobs, list) or not lobs or not set(lobs).issubset(set(LOBS)):
        raise ScheduleValidationError("Select at least one valid line of business.")
    if not set(lobs).issubset(allowed_lobs):
        raise PermissionError("The schedule includes a line of business outside your access scope.")

    frequency = payload.get("frequency", "weekly")
    if frequency not in FREQUENCIES:
        raise ScheduleValidationError("Frequency must be daily, weekly or monthly.")
    timezone_name = payload.get("timezone", "Asia/Kolkata")
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, TypeError):
        raise ScheduleValidationError("Choose a valid IANA timezone.")
    run_at_local = payload.get("run_at_local", "08:00")
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(run_at_local)):
        raise ScheduleValidationError("Run time must use HH:MM (24-hour local time).")
    weekday = payload.get("weekday")
    monthday = payload.get("monthday")
    if frequency == "weekly" and (not isinstance(weekday, int) or not 0 <= weekday <= 6):
        raise ScheduleValidationError("Weekly schedules require weekday 0–6 (Monday=0).")
    if frequency == "monthly" and (not isinstance(monthday, int) or not 1 <= monthday <= 31):
        raise ScheduleValidationError("Monthly schedules require a day from 1 to 31.")

    period = payload.get("period", "last_7_completed_days" if frequency == "weekly" else "yesterday")
    if period not in PERIODS:
        raise ScheduleValidationError("Choose a supported relative or fixed date period.")
    if period == "fixed_range":
        period_bounds(period, date.today(), start_date=payload.get("start_date"), end_date=payload.get("end_date"))

    columns = payload.get("columns") or list(report["columns"])
    if not isinstance(columns, list) or not columns or len(columns) != len(set(columns)):
        raise ScheduleValidationError("Select one or more unique report columns.")
    if not set(columns).issubset(set(report["columns"])):
        raise ScheduleValidationError("One or more selected columns are not available for this report.")
    sort = payload.get("sort") or {"field": columns[0], "direction": "asc"}
    if not isinstance(sort, dict) or sort.get("field") not in report["columns"] or sort.get("direction") not in ("asc", "desc"):
        raise ScheduleValidationError("Choose a valid sort field and direction.")

    filters = payload.get("filters") or {}
    if not isinstance(filters, dict) or not set(filters).issubset(set(report["filters"])):
        raise ScheduleValidationError("One or more filters are not supported by this report.")
    clean_filters = {}
    for key, values in filters.items():
        if not isinstance(values, list) or len(values) > 100 or any(not isinstance(v, str) or len(v) > 200 for v in values):
            raise ScheduleValidationError("Filter values must be lists of at most 100 text values.")
        clean_filters[key] = list(dict.fromkeys(v.strip() for v in values if v.strip()))

    mode = payload.get("summary_detail", "detail")
    if mode not in ("summary", "detail"):
        raise ScheduleValidationError("Choose summary or detail mode.")
    recipients = payload.get("recipients", ["self"])
    if recipients != ["self"]:
        raise PermissionError("The pilot only supports delivery to the schedule owner's verified account email.")

    freshness = payload.get("freshness_policy") or {"action": "skip", "max_age_hours": 48}
    if not isinstance(freshness, dict) or freshness.get("action") not in ("skip", "warn", "delay"):
        raise ScheduleValidationError("Choose a supported freshness action.")
    max_age = freshness.get("max_age_hours", 48)
    if not isinstance(max_age, int) or not 1 <= max_age <= 168:
        raise ScheduleValidationError("Freshness max_age_hours must be between 1 and 168.")
    max_delay = freshness.get("max_delay_hours", 24)
    if freshness["action"] == "delay" and (not isinstance(max_delay, int) or not 1 <= max_delay <= 72):
        raise ScheduleValidationError("Delay max_delay_hours must be between 1 and 72.")

    return {
        "report_id": report_id, "report_version": report["version"],
        "companies": sorted(companies), "lobs": sorted(lobs), "filters": clean_filters,
        "columns": columns, "sort": sort, "summary_detail": mode,
        "totals": bool(payload.get("totals", True)), "date_basis": report["date_basis"],
        "period": period, "start_date": payload.get("start_date") if period == "fixed_range" else None,
        "end_date": payload.get("end_date") if period == "fixed_range" else None,
        "frequency": frequency, "timezone": timezone_name, "run_at_local": run_at_local,
        "weekday": weekday if frequency == "weekly" else None,
        "monthday": monthday if frequency == "monthly" else None,
        "recipients": ["self"], "owner_id": int(user["id"]),
        "status": "paused", "freshness_policy": freshness,
        "start_at": payload.get("start_at"), "end_at": payload.get("end_at"),
    }


def safe_excel_text(value):
    """Escape untrusted text that Excel might interpret as a formula."""
    if value is None:
        return ""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value
