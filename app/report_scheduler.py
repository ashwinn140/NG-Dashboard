"""Core contracts for the durable, permission-aware Excel report scheduler.

No worker is started from this module. Scheduling is deliberately inert until
server-side queue, permissions, freshness and delivery controls are integrated.
"""
from __future__ import annotations

import calendar
import json
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
            "teus", "volume_cbm", "stage", "shipper", "consignee", "carrier",
            "origin_agent", "destination_agent", "nomination", "consol_type",
            "cargo_type", "trade_lane", "loading_country", "discharge_country",
            "collection_executive", "business_dimension", "incoterms", "freight_type",
            "contract_type", "commodity_type", "co_load_type", "document_executive",
            "place_of_execution", "container_types", "customer_branch", "booking_thru",
            "unit", "unit_1", "unit_2", "unit_3", "unit_4", "unit_5", "unit_6", "unit_7",
            "invoice_first_date", "invoice_count", "billing_reference_status", "buy_rate", "sell_rate",
        ),
        "summary_columns": (
            "company", "customer", "shipments", "air_shipments", "ocean_shipments",
            "air_chargeable_weight_t", "ocean_teus", "lob_count", "last_shipment_date",
        ),
        "filters": ("customer", "branch", "agent", "salesperson", "job_owner", "status",
                    "stage", "shipper", "consignee", "carrier", "origin", "destination",
                    "origin_agent", "destination_agent", "nomination", "consol_type",
                    "cargo_type", "trade_lane", "loading_country", "discharge_country",
                    "collection_executive", "business_dimension", "incoterms", "freight_type",
                    "contract_type", "commodity_type", "co_load_type", "customer_branch", "booking_thru", "billing_reference_status"),
    },
    "customer_performance": {
        "version": 1, "title": "Customer Shipment Performance", "permission": "operations",
        "date_basis": "Shipment Date", "date_array": "date",
        "columns": (
            "company", "customer", "shipments", "air_shipments",
            "ocean_shipments", "air_chargeable_weight_t", "ocean_teus",
            "lob_count", "last_shipment_date",
        ),
        "summary_columns": (
            "company", "customer", "shipments", "air_shipments", "ocean_shipments",
            "air_chargeable_weight_t", "ocean_teus", "lob_count", "last_shipment_date",
        ),
        "filters": ("customer", "branch", "agent", "salesperson", "job_owner", "status",
                    "stage", "shipper", "consignee", "carrier", "origin", "destination",
                    "origin_agent", "destination_agent", "nomination", "consol_type",
                    "cargo_type", "trade_lane", "loading_country", "discharge_country",
                    "collection_executive", "business_dimension", "incoterms", "freight_type",
                    "contract_type", "commodity_type", "co_load_type", "booking_thru", "billing_reference_status"),
    },
    "job_profitability": {
        "version": 1, "title": "Job Profitability", "permission": "finance",
        "date_basis": "Job Date", "date_array": "p.jd",
        "columns": (
            "company", "lob", "job_no", "job_date", "customer", "branch",
            "mode", "direction", "service", "salesperson", "income", "expense", "profit",
            "margin", "trade_lane", "intercompany", "transaction_date",
        ),
        "summary_columns": (
            "company", "lob", "customer", "branch", "jobs", "income", "expense", "profit", "margin",
        ),
        "filters": ("customer", "branch", "salesperson", "lob", "mode", "direction", "service",
                    "trade_lane", "intercompany"),
    },
}


class ScheduleValidationError(ValueError):
    pass


def _parse_date(value: str, label: str) -> date:
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
    start, end = _parse_date(start_date, "start_date"), _parse_date(end_date, "end_date")
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
    if report_id == "shipment_register" and not user.get("finance") and set(payload.get("columns") or ()) & {"buy_rate", "sell_rate"}:
        raise PermissionError("Finance permission is required to include shipment buy/sell rates.")

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
    weekday = payload.get("weekday", 0 if frequency == "weekly" else None)
    monthday = payload.get("monthday", 1 if frequency == "monthly" else None)
    if frequency == "weekly" and (not isinstance(weekday, int) or not 0 <= weekday <= 6):
        raise ScheduleValidationError("Weekly schedules require weekday 0–6 (Monday=0).")
    if frequency == "monthly" and (not isinstance(monthday, int) or not 1 <= monthday <= 31):
        raise ScheduleValidationError("Monthly schedules require a day from 1 to 31.")

    period = payload.get("period", "last_7_completed_days" if frequency == "weekly" else "yesterday")
    if period not in PERIODS:
        raise ScheduleValidationError("Choose a supported relative or fixed date period.")
    if period == "fixed_range":
        period_bounds(period, date.today(), start_date=payload.get("start_date"), end_date=payload.get("end_date"))

    mode = payload.get("summary_detail", "summary" if report_id == "customer_performance" else "detail")
    if mode not in ("summary", "detail"):
        raise ScheduleValidationError("Choose summary or detail mode.")
    if report_id == "customer_performance" and mode != "summary":
        raise ScheduleValidationError("Customer Performance is a summary report in the pilot.")
    available_columns = report["summary_columns"] if mode == "summary" else report["columns"]
    columns = payload.get("columns") or list(available_columns)
    if not isinstance(columns, list) or not columns or len(columns) != len(set(columns)):
        raise ScheduleValidationError("Select one or more unique report columns.")
    if not set(columns).issubset(set(available_columns)):
        raise ScheduleValidationError("One or more selected columns are not available in this report mode.")
    sort = payload.get("sort") or {"field": columns[0], "direction": "asc"}
    if not isinstance(sort, dict) or sort.get("field") not in available_columns or sort.get("direction") not in ("asc", "desc"):
        raise ScheduleValidationError("Choose a valid sort field and direction.")

    filters = payload.get("filters") or {}
    if not isinstance(filters, dict) or not set(filters).issubset(set(report["filters"])):
        raise ScheduleValidationError("One or more filters are not supported by this report.")
    clean_filters = {}
    for key, values in filters.items():
        if not isinstance(values, list) or len(values) > 100 or any(not isinstance(v, str) or len(v) > 200 for v in values):
            raise ScheduleValidationError("Filter values must be lists of at most 100 text values.")
        clean_filters[key] = list(dict.fromkeys(v.strip() for v in values if v.strip()))

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

    start_at = payload.get("start_at")
    end_at = payload.get("end_at")
    try:
        start_at = datetime.fromisoformat(start_at.replace("Z", "+00:00")) if start_at else None
        end_at = datetime.fromisoformat(end_at.replace("Z", "+00:00")) if end_at else None
    except (TypeError, ValueError):
        raise ScheduleValidationError("Schedule start/end must be ISO timestamps.")
    if start_at and start_at.tzinfo is None or end_at and end_at.tzinfo is None:
        raise ScheduleValidationError("Schedule start/end timestamps must include a timezone.")
    if start_at and end_at and end_at <= start_at:
        raise ScheduleValidationError("Schedule end must be after schedule start.")
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
        "start_at": start_at.isoformat() if start_at else None,
        "end_at": end_at.isoformat() if end_at else None,
    }


def safe_excel_text(value):
    """Escape untrusted text that Excel might interpret as a formula."""
    if value is None:
        return ""
    if isinstance(value, str) and value.lstrip(" \t\r\n")[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value

# --------------------------------------------------------------------------- dataset -> workbook pilot
from io import BytesIO
from datetime import date as _date_cls, timedelta as _timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, LineChart, Reference

EPOCH = _date_cls(1970, 1, 1)
MAX_EXPORT_ROWS = 100_000
MAX_WORKBOOK_BYTES = 20 * 1024 * 1024


def _day(value):
    if value is None or value < 0:
        return None
    return EPOCH + _timedelta(days=int(value))


def _column(D, key, index, profit=False):
    entry = D.get("cols", {}).get(key)
    if not entry:
        return ""
    codes = entry.get("pc" if profit else "c") or []
    if index >= len(codes):
        return ""
    code = codes[index]
    values = entry.get("d") or []
    return values[code] if isinstance(code, int) and 0 <= code < len(values) else ""


def _match_filters(row, filters):
    for key, values in filters.items():
        if values and str(row.get(key) or "").strip().casefold() not in {v.casefold() for v in values}:
            return False
    return True


def _sort_rows(rows, definition):
    key = definition["sort"]["field"]
    reverse = definition["sort"]["direction"] == "desc"
    present = [r for r in rows if r.get(key) is not None]
    missing = [r for r in rows if r.get(key) is None]
    present.sort(key=lambda r: r[key].casefold() if isinstance(r[key], str) else r[key], reverse=reverse)
    return present + missing


def _shipment_rows(D, definition, start, end):
    companies, lobs = set(definition["companies"]), set(definition["lobs"])
    rows = []
    for i, rep_index in enumerate(D.get("rep", [])):
        company, lob = D["reps"][rep_index]
        if company not in companies or lob not in lobs:
            continue
        shipment_date = _day(D["date"][i])
        if shipment_date is None or not start <= shipment_date < end:
            continue
        mode = "Air" if lob.startswith("A") else "Ocean"
        row = {
            "company": company, "lob": lob, "shipment_no": D["no"][i],
            "shipment_date": shipment_date,
            "customer": _column(D, "customer", i),
            "branch": _column(D, "branch", i),
            "agent": _column(D, "agent", i),
            "salesperson": _column(D, "x_salesperson", i) or _column(D, "salesperson", i),
            "job_owner": _column(D, "job_owner", i),
            "origin": _column(D, "origin", i),
            "destination": _column(D, "destination", i),
            "status": _column(D, "status", i),
            "stage": _column(D, "stage", i),
            "shipper": _column(D, "shipper", i), "consignee": _column(D, "consignee", i),
            "carrier": _column(D, "carrier", i), "origin_agent": _column(D, "origin_agent", i),
            "destination_agent": _column(D, "destination_agent", i),
            "nomination": _column(D, "nomination", i), "consol_type": _column(D, "consol", i),
            "cargo_type": _column(D, "cargo", i), "trade_lane": _column(D, "x_tradelanename", i),
            "loading_country": _column(D, "x_loadingcountry", i), "discharge_country": _column(D, "x_dischargecountry", i),
            "collection_executive": _column(D, "x_collectionexecutive", i),
            "business_dimension": _column(D, "x_businessdimension", i),
            "incoterms": _column(D, "x_incoterms", i), "freight_type": _column(D, "x_freighttype", i),
            "contract_type": _column(D, "x_contracttype", i), "commodity_type": _column(D, "x_commoditytype", i),
            "co_load_type": _column(D, "x_coloadtype", i),
            "document_executive": _column(D, "x_documentexecutiveudf", i),
            "place_of_execution": _column(D, "x_placeofexecution", i),
            "container_types": _column(D, "x_containertypes", i),
            "customer_branch": _column(D, "x_customerbranch", i),
            "unit": _column(D, "x_unit", i),
            "unit_1": _column(D, "x_unit1", i), "unit_2": _column(D, "x_unit2", i),
            "unit_3": _column(D, "x_unit3", i), "unit_4": _column(D, "x_unit4", i),
            "unit_5": _column(D, "x_unit5", i), "unit_6": _column(D, "x_unit6", i),
            "unit_7": _column(D, "x_unit7", i),
            "booking_thru": _column(D, "x_bookingthru", i),
            "invoice_first_date": _day(D.get("inv1", [None] * len(D["no"]))[i]),
            "invoice_count": int(D.get("invN", [0] * len(D["no"]))[i] or 0),
            "billing_reference_status": ("Reference present" if int(D.get("invN", [0] * len(D["no"]))[i] or 0) > 0 else "No reference recorded"),
            "buy_rate": (float(D.get("rbuy", [0] * len(D["no"]))[i]) if D.get("user", {}).get("finance") and D.get("rbf", [0] * len(D["no"]))[i] in (1, 2) else None),
            "sell_rate": (float(D.get("rsell", [0] * len(D["no"]))[i]) if D.get("user", {}).get("finance") and D.get("rsf", [0] * len(D["no"]))[i] in (1, 2) else None),
            "operations_locked_on": _day(D["ops"][i]),
            "financials_locked_on": _day(D["fin"][i]),
            "gross_weight_t": float(D["gross"][i] or 0),
            "chargeable_weight_t": float(D["chg"][i] or 0),
            "teus": float(D["teus"][i] or 0),
            "volume_cbm": float(D["cbm"][i] or 0),
            "_mode": mode,
        }
        if _match_filters(row, definition["filters"]):
            rows.append(row)
    return rows


def _customer_rows(shipment_rows):
    groups = {}
    for r in shipment_rows:
        customer = " ".join(str(r.get("customer") or "").split())
        if not customer or customer.casefold() in {"(blank)", "blank"}:
            continue
        key = (r["company"], customer.lower())
        g = groups.setdefault(key, {
            "company": r["company"], "customer": customer, "shipments": 0,
            "air_shipments": 0, "ocean_shipments": 0,
            "air_chargeable_weight_t": 0.0, "ocean_teus": 0.0,
            "lob_set": set(), "last_shipment_date": None,
        })
        g["shipments"] += 1
        g["air_shipments"] += int(r["_mode"] == "Air")
        g["ocean_shipments"] += int(r["_mode"] == "Ocean")
        if r["_mode"] == "Air":
            g["air_chargeable_weight_t"] += r["chargeable_weight_t"]
        else:
            g["ocean_teus"] += r["teus"]
        g["lob_set"].add(r["lob"])
        if g["last_shipment_date"] is None or r["shipment_date"] > g["last_shipment_date"]:
            g["last_shipment_date"] = r["shipment_date"]
    out = []
    for g in groups.values():
        g["lob_count"] = len(g.pop("lob_set"))
        g.pop("_mode", None)
        out.append(g)
    return out


def _job_rows(D, definition, start, end):
    companies, lobs = set(definition["companies"]), set(definition["lobs"])
    company_codes = ("NG", "NCS")
    lob_map = {"Air Export": "AE", "Air Import": "AI", "Ocean Export": "OE", "Ocean Import": "OI",
               "Sea Export": "OE", "Sea Import": "OI"}
    P = D.get("p") or {}
    rows = []
    for i, co_code in enumerate(P.get("co", [])):
        company = company_codes[int(co_code)] if int(co_code) in (0, 1) else ""
        lob_label = _column(D, "p_lob", i, True)
        lob = lob_map.get(str(lob_label), "")
        if company not in companies or lob not in lobs:
            continue
        job_date = _day(P.get("jd", [])[i])
        if job_date is None or not start <= job_date < end:
            continue
        income, expense = float(P["income"][i] or 0), float(P["expense"][i] or 0)
        profit = income - expense
        row = {
            "company": company, "lob": lob,
            "job_no": _column(D, "p_job", i, True),
            "job_date": job_date,
            "customer": _column(D, "customer", i, True),
            "branch": _column(D, "branch", i, True),
            "mode": _column(D, "p_mode", i, True),
            "direction": _column(D, "p_direction", i, True),
            "service": _column(D, "p_kind", i, True),
            "salesperson": _column(D, "jp_sales_person", i, True),
            "trade_lane": _column(D, "x_tradelanename", i, True),
            "intercompany": _column(D, "p_ic", i, True),
            "transaction_date": _day(P.get("td", [-1] * len(P.get("co", [])))[i]),
            "income": income, "expense": expense, "profit": profit,
            "margin": profit / income if income > 0 else None,
        }
        if _match_filters(row, definition["filters"]):
            rows.append(row)
    return rows


def _summary_rows(report_id, rows):
    if report_id == "customer_performance":
        return _customer_rows(rows)
    if report_id == "shipment_register":
        return _customer_rows(rows)
    if report_id == "job_profitability":
        groups = {}
        for r in rows:
            key = (r["company"], r["lob"], r["customer"], r["branch"])
            g = groups.setdefault(key, {"company": r["company"], "lob": r["lob"], "customer": r["customer"],
                                         "branch": r["branch"], "jobs": 0, "income": 0.0, "expense": 0.0})
            g["jobs"] += 1
            g["income"] += r["income"]
            g["expense"] += r["expense"]
        for g in groups.values():
            g["profit"] = g["income"] - g["expense"]
            g["margin"] = g["profit"] / g["income"] if g["income"] > 0 else None
        return list(groups.values())
    return rows


def build_report_rows(D, definition, start, end):
    """Build the pilot report rows from the already per-user-restricted dataset."""
    report_id = definition["report_id"]
    if report_id == "job_profitability":
        rows = _job_rows(D, definition, start, end)
    else:
        rows = _shipment_rows(D, definition, start, end)
        if report_id == "customer_performance":
            rows = _customer_rows(rows)
    if definition["summary_detail"] == "summary" and report_id != "customer_performance":
        rows = _summary_rows(report_id, rows)
    return _sort_rows(rows, definition)


def _add_visuals_sheet(wb, rows, report_id, start, end):
    """Add chart summaries plus the exact chart data as an accessible table."""
    ws = wb.create_sheet("Visuals")
    ws.sheet_view.showGridLines = False
    ws.append(["Report visuals"])
    ws["A1"].font = Font(bold=True, size=16, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor="173142")
    ws.append(["Charts summarize the same filtered rows shown on the Report sheet."])
    if not rows:
        ws.append(["No records in the selected period and filters."])
        return

    if report_id == "job_profitability":
        by_customer = {}
        by_month = {}
        for row in rows:
            customer = str(row.get("customer") or "(Unspecified)")
            group = by_customer.setdefault(customer, {"jobs": 0, "income": 0.0, "expense": 0.0, "profit": 0.0})
            group["jobs"] += 1
            for key in ("income", "expense", "profit"):
                group[key] += float(row.get(key) or 0)
            day = row.get("job_date")
            if day:
                month = day.strftime("%Y-%m")
                m = by_month.setdefault(month, {"income": 0.0, "expense": 0.0, "profit": 0.0})
                for key in ("income", "expense", "profit"):
                    m[key] += float(row.get(key) or 0)
        ws.append([])
        ws.append(["Top customers by recorded gross profit", "Jobs", "Income (INR)", "Expense (INR)", "Profit (INR)"])
        top = sorted(by_customer.items(), key=lambda item: item[1]["profit"], reverse=True)[:12]
        for name, values in top:
            ws.append([safe_excel_text(name), values["jobs"], values["income"], values["expense"], values["profit"]])
        if top:
            chart = BarChart()
            chart.type = "bar"
            chart.style = 10
            chart.title = "Top customers by recorded gross profit"
            chart.y_axis.title = "Customer"
            chart.x_axis.title = "INR"
            chart.height, chart.width = 8, 16
            chart.add_data(Reference(ws, min_col=5, min_row=4, max_row=3 + len(top)), titles_from_data=False)
            chart.set_categories(Reference(ws, min_col=1, min_row=4, max_row=3 + len(top)))
            ws.add_chart(chart, "G3")
        start_row = max(ws.max_row + 3, 20)
        ws.cell(start_row, 1, "Monthly profitability trend")
        ws.cell(start_row + 1, 1, "Month")
        for j, key in enumerate(("income", "expense", "profit"), 2):
            ws.cell(start_row + 1, j, key.title() + " (INR)")
        for i, (month, values) in enumerate(sorted(by_month.items()), start_row + 2):
            ws.cell(i, 1, month)
            for j, key in enumerate(("income", "expense", "profit"), 2):
                ws.cell(i, j, values[key])
        if by_month:
            chart = LineChart()
            chart.title = "Monthly income, expense and gross profit"
            chart.y_axis.title = "INR"
            chart.x_axis.title = "Job month"
            chart.height, chart.width = 8, 16
            chart.add_data(Reference(ws, min_col=2, max_col=4, min_row=start_row + 1, max_row=start_row + 1 + len(by_month)), titles_from_data=True)
            chart.set_categories(Reference(ws, min_col=1, min_row=start_row + 2, max_row=start_row + 1 + len(by_month)))
            ws.add_chart(chart, "G20")
    else:
        by_customer = {}
        by_lob = {}
        by_month = {}
        for row in rows:
            customer = str(row.get("customer") or "(Unspecified)")
            by_customer[customer] = by_customer.get(customer, 0) + 1
            lob = str(row.get("lob") or "(Unspecified)")
            by_lob[lob] = by_lob.get(lob, 0) + 1
            day = row.get("shipment_date")
            if day:
                month = day.strftime("%Y-%m")
                by_month[month] = by_month.get(month, 0) + 1
        ws.append([])
        ws.append(["Top customers by shipments", "Shipments"])
        top = sorted(by_customer.items(), key=lambda item: item[1], reverse=True)[:12]
        for name, count in top:
            ws.append([safe_excel_text(name), count])
        if top:
            chart = BarChart()
            chart.type = "bar"
            chart.style = 10
            chart.title = "Top customers by shipments"
            chart.y_axis.title = "Customer"
            chart.x_axis.title = "Shipments"
            chart.height, chart.width = 8, 16
            chart.add_data(Reference(ws, min_col=2, min_row=4, max_row=3 + len(top)), titles_from_data=False)
            chart.set_categories(Reference(ws, min_col=1, min_row=4, max_row=3 + len(top)))
            ws.add_chart(chart, "E3")
        start_row = max(ws.max_row + 3, 20)
        ws.cell(start_row, 1, "Shipments by line of business")
        ws.cell(start_row + 1, 1, "LOB")
        ws.cell(start_row + 1, 2, "Shipments")
        for i, (lob, count) in enumerate(sorted(by_lob.items()), start_row + 2):
            ws.cell(i, 1, lob)
            ws.cell(i, 2, count)
        if by_lob:
            chart = BarChart()
            chart.title = "Shipments by line of business"
            chart.y_axis.title = "Shipments"
            chart.height, chart.width = 8, 12
            chart.add_data(Reference(ws, min_col=2, min_row=start_row + 1, max_row=start_row + 1 + len(by_lob)), titles_from_data=True)
            chart.set_categories(Reference(ws, min_col=1, min_row=start_row + 2, max_row=start_row + 1 + len(by_lob)))
            ws.add_chart(chart, "E20")
        trend_row = max(ws.max_row + 3, 38)
        ws.cell(trend_row, 1, "Monthly shipment trend")
        ws.cell(trend_row + 1, 1, "Month")
        ws.cell(trend_row + 1, 2, "Shipments")
        for i, (month, count) in enumerate(sorted(by_month.items()), trend_row + 2):
            ws.cell(i, 1, month)
            ws.cell(i, 2, count)
        if by_month:
            chart = LineChart()
            chart.title = "Monthly shipment trend"
            chart.y_axis.title = "Shipments"
            chart.x_axis.title = "Shipment month"
            chart.height, chart.width = 8, 12
            chart.add_data(Reference(ws, min_col=2, min_row=trend_row + 1, max_row=trend_row + 1 + len(by_month)), titles_from_data=True)
            chart.set_categories(Reference(ws, min_col=1, min_row=trend_row + 2, max_row=trend_row + 1 + len(by_month)))
            ws.add_chart(chart, "R3")
    for row_cells in ws.iter_rows():
        for cell in row_cells:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for column in ("A", "B", "C", "D", "E"):
        ws.column_dimensions[column].width = 24


def build_report_workbook(D, definition, start, end, freshness, generated_at=None):
    """Create a formatted, bounded XLSX attachment. No truncation is permitted."""
    from datetime import datetime as _datetime
    report = REPORT_CATALOG[definition["report_id"]]
    generated_at = generated_at or _datetime.now(UTC)
    rows = build_report_rows(D, definition, start, end)
    if len(rows) > MAX_EXPORT_ROWS:
        raise ScheduleValidationError("The report exceeds the 100,000-row pilot limit; narrow the filters or split the report.")
    columns = definition["columns"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.sheet_view.showGridLines = False
    ws.append([report["title"]])
    ws.append(["Companies", ", ".join(definition["companies"]), "LOBs", ", ".join(definition["lobs"])])
    ws.append(["Period", f"{start.isoformat()} to {(end - _timedelta(days=1)).isoformat()}", "Date basis", definition.get("date_basis") or report.get("date_basis", "Report date")])
    ws.append(["Filters", json.dumps(definition["filters"], ensure_ascii=False, sort_keys=True)])
    ws.append(["Freshness", json.dumps(freshness, ensure_ascii=False, sort_keys=True), "Generated UTC", generated_at.astimezone(UTC).isoformat(timespec="seconds")])
    ws.append([columns_name for columns_name in columns])
    header_row = 6
    for row in rows:
        ws.append([safe_excel_text(row.get(col)) for col in columns])
    if definition.get("totals") and rows:
        totals = []
        for col in columns:
            if col in ("income", "expense", "profit", "gross_weight_t", "chargeable_weight_t", "teus", "volume_cbm",
                       "shipments", "air_shipments", "ocean_shipments", "jobs", "air_chargeable_weight_t", "ocean_teus", "invoice_count"):
                totals.append(sum(float(r.get(col) or 0) for r in rows))
            elif col in ("buy_rate", "sell_rate"):
                totals.append("")  # Rates are unit values, not additive totals.
            elif col == "margin":
                inc = sum(float(r.get("income") or 0) for r in rows)
                gp = sum(float(r.get("profit") or 0) for r in rows)
                totals.append(gp / inc if inc > 0 else None)
            elif col in ("shipment_no", "job_no"):
                totals.append(f"Rows: {len(rows)}")
            else:
                totals.append("TOTAL" if col == columns[0] else "")
        ws.append(totals)

    ws.freeze_panes = "A7"
    last_col = get_column_letter(max(1, len(columns)))
    if rows:
        ws.auto_filter.ref = f"A{header_row}:{last_col}{header_row + len(rows)}"
    ws["A1"].font = Font(bold=True, size=16, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor="173142")
    for cell in ws[header_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="087D79")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[header_row].height = 28
    for col_idx, col in enumerate(columns, 1):
        letter = get_column_letter(col_idx)
        values = [str(ws.cell(row=r, column=col_idx).value or "") for r in range(1, min(ws.max_row, 50) + 1)]
        ws.column_dimensions[letter].width = min(36, max(12, max((len(v) for v in values), default=12) + 2))
        for row_idx in range(7, ws.max_row + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            if col in ("shipment_date", "job_date", "transaction_date", "invoice_first_date", "operations_locked_on", "financials_locked_on", "last_shipment_date") and cell.value:
                cell.number_format = "dd-mmm-yyyy"
            elif col in ("income", "expense", "profit"):
                cell.number_format = '"₹"#,##0.00;[Red]-"₹"#,##0.00'
            elif col in ("buy_rate", "sell_rate"):
                cell.number_format = "#,##0.000"
            elif col == "margin":
                cell.number_format = "0.0%"
            elif col in ("gross_weight_t", "chargeable_weight_t", "air_chargeable_weight_t", "teus", "ocean_teus", "volume_cbm"):
                cell.number_format = "#,##0.000"
    for row_idx in range(7, ws.max_row + 1):
        for cell in ws[row_idx]:
            cell.alignment = Alignment(vertical="top")
    _add_visuals_sheet(wb, rows, definition["report_id"], start, end)
    output = BytesIO()
    wb.save(output)
    content = output.getvalue()
    if len(content) > MAX_WORKBOOK_BYTES:
        raise ScheduleValidationError("The generated workbook exceeds the 20 MB pilot limit; narrow the filters.")
    return {"content": content, "filename": f"{definition['report_id']}_{start.isoformat()}_{(end - _timedelta(days=1)).isoformat()}.xlsx",
            "row_count": len(rows), "file_size": len(content)}
