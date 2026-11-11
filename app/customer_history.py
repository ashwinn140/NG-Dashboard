"""Source-backed latest distinct job history for Operations > Customers.

This module deliberately returns no financial values. It reads the current
Job Profit Analysis snapshot and never infers missing Job Owner values.
"""
from collections import defaultdict
from datetime import date, datetime


LOB_CODES = {
    ("Air", "Export"): "AE",
    ("Air", "Import"): "AI",
    ("Sea", "Export"): "OE",
    ("Sea", "Import"): "OI",
}


def _header_key(value):
    return "".join(ch.casefold() for ch in str(value or "") if ch.isalnum())


def _iso_day(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value or "").strip()[:10]


def is_named_customer(value):
    """Return False for the explicit blank bucket used by dashboard data."""
    customer = " ".join(str(value or "").split())
    return bool(customer) and customer.casefold() not in {"(blank)", "blank"}


def build_recent_jobs(rows, lobs=None, limit=5):
    """Return the newest distinct company/LOB/job/date identities.

    Repeated source rows for one identity collapse to one job. If duplicate
    source rows disagree on Job Owner, the owner is shown as unavailable
    rather than choosing one arbitrarily. Missing JPR owners are never
    backfilled from a shipment register or salesperson field.
    """
    allowed_lobs = set(lobs or [])
    grouped = {}
    for row in rows:
        company = str(row.get("company") or "").strip().upper()
        job_no = str(row.get("job_no") or "").strip()
        lob = str(row.get("lob") or "").strip()
        job_date = _iso_day(row.get("job_date"))
        customer = " ".join(str(row.get("customer") or "").split())
        if not company or not job_no or not job_date or not lob or not is_named_customer(customer):
            continue
        mode = "Air" if "AIR" in lob.upper() else "Sea" if "SEA" in lob.upper() else "Road" if "ROAD" in lob.upper() else "Other"
        direction = "Export" if "EXP" in lob.upper() else "Import" if "IMP" in lob.upper() else "Domestic" if "DOM" in lob.upper() else "Other"
        code = LOB_CODES.get((mode, direction), "OTHER")
        if allowed_lobs and code not in allowed_lobs:
            continue
        extra = row.get("extra") if isinstance(row.get("extra"), dict) else {}
        owner_key = next((key for key in extra if _header_key(key) == "jobowner"), None)
        owner = str(extra.get(owner_key) or "").strip() if owner_key is not None else ""
        identity = (company, lob, job_no, job_date)
        item = grouped.get(identity)
        if item is None:
            grouped[identity] = {
                "company": company, "job_no": job_no, "job_date": job_date,
                "lob": lob, "customer": customer, "owners": {owner or None},
            }
        else:
            item["owners"].add(owner or None)

    result = []
    for item in grouped.values():
        owners = item.pop("owners")
        owner = next(iter(owners)) if len(owners) == 1 else None
        result.append({
            "company": item["company"],
            "job_no": item["job_no"],
            "job_date": item["job_date"],
            "lob": item["lob"],
            "job_owner": owner or "Owner unavailable",
            "owner_status": "available" if len(owners) == 1 and owner else "conflicting" if len(owners) > 1 else "missing",
        })
    result.sort(key=lambda item: (
        item["job_date"], item["job_no"].casefold(),
        item["lob"].casefold(), item["company"]
    ), reverse=True)
    return result[:max(0, min(int(limit), 5))]


def build_last_shipment_owners(shipment_rows, jpr_rows, lobs=None, target_date=None):
    """Map each customer's latest shipment date to its JPR Job Owner.

    Shipment-to-job identity follows the dashboard's existing matching rule:
    company + shipment number + exact date first; if no exact-date job exists,
    fall back only when the shipment number and report/LOB identify one job.
    A date with multiple shipments is reported only when all owners agree.
    """
    allowed_lobs = set(lobs or [])
    target_date = _iso_day(target_date) if target_date else None
    jobs_by_number = defaultdict(list)
    grouped_jobs = {}

    for row in jpr_rows:
        company = str(row.get("company") or "").strip().upper()
        job_no = str(row.get("job_no") or "").strip()
        lob = str(row.get("lob") or "").strip()
        job_date = _iso_day(row.get("job_date"))
        if not company or not job_no or not job_date or not lob:
            continue
        mode = "Air" if "AIR" in lob.upper() else "Sea" if "SEA" in lob.upper() else "Road" if "ROAD" in lob.upper() else "Other"
        direction = "Export" if "EXP" in lob.upper() else "Import" if "IMP" in lob.upper() else "Domestic" if "DOM" in lob.upper() else "Other"
        report_type = LOB_CODES.get((mode, direction))
        if allowed_lobs and report_type not in allowed_lobs:
            continue
        extra = row.get("extra") if isinstance(row.get("extra"), dict) else {}
        owner_key = next((key for key in extra if _header_key(key) == "jobowner"), None)
        owner = str(extra.get(owner_key) or "").strip() if owner_key is not None else ""
        identity = (company, job_no, job_date, lob, report_type)
        if identity not in grouped_jobs:
            grouped_jobs[identity] = {
                "company": company, "job_no": job_no, "job_date": job_date,
                "lob": lob, "report_type": report_type, "owners": {owner or None},
            }
        else:
            grouped_jobs[identity]["owners"].add(owner or None)

    for job in grouped_jobs.values():
        jobs_by_number[(job["company"], job["job_no"])].append(job)

    latest_by_customer = {}
    for row in shipment_rows:
        company = str(row.get("company") or "").strip().upper()
        report_type = str(row.get("report_type") or "").strip().upper()
        shipment_no = str(row.get("shipment_no") or "").strip()
        shipment_date = _iso_day(row.get("shipment_date"))
        customer = " ".join(str(row.get("customer") or "").split())
        key = customer.casefold()
        if not company or not report_type or not shipment_no or not shipment_date or not is_named_customer(customer):
            continue
        if allowed_lobs and report_type not in allowed_lobs:
            continue
        if target_date and shipment_date != target_date:
            continue
        item = {
            "company": company, "report_type": report_type,
            "shipment_no": shipment_no, "shipment_date": shipment_date,
        }
        current = latest_by_customer.get(key)
        if current is None or shipment_date > current["date"]:
            latest_by_customer[key] = {"customer": customer, "date": shipment_date, "shipments": [item]}
        elif shipment_date == current["date"]:
            current["shipments"].append(item)

    results = {}
    for key, latest in latest_by_customer.items():
        owners, incomplete = set(), False
        shipment_ids = set()
        for shipment in latest["shipments"]:
            identity = (shipment["company"], shipment["shipment_no"], shipment["shipment_date"], shipment["report_type"])
            if identity in shipment_ids:
                continue
            shipment_ids.add(identity)
            candidates = [
                job for job in jobs_by_number.get((shipment["company"], shipment["shipment_no"]), [])
                if job["report_type"] == shipment["report_type"]
            ]
            exact = [job for job in candidates if job["job_date"] == shipment["shipment_date"]]
            matched = exact if exact else candidates
            # Multiple distinct JPR jobs for one shipment are ambiguous; do not guess.
            if len(matched) != 1:
                incomplete = True
                continue
            job = matched[0]
            job_owners = job["owners"]
            if len(job_owners) != 1 or None in job_owners:
                incomplete = True
                continue
            owners.add(next(iter(job_owners)))

        if incomplete or not owners:
            owner, status = "Owner unavailable", "unmatched_or_conflicting"
        elif len(owners) > 1:
            owner, status = "Multiple owners", "multiple"
        else:
            owner, status = next(iter(owners)), "available"
        results[key] = {
            "customer": latest["customer"],
            "last_shipment_date": latest["date"],
            "last_shipment_job_owner": owner,
            "last_shipment_owner_status": status,
            "last_shipment_numbers": sorted({s["shipment_no"] for s in latest["shipments"]}),
        }
    return results

def visible_report_types_for_scopes(lob_scopes):
    """Return report types needed to validate a mixed customer-history batch.

    Each request may carry a different LOB scope. A blank scope means the
    caller is unrestricted by LOB, so the batch must inspect all supported
    operational reports before validating customer visibility.
    """
    scopes = [set(scope or []) for scope in lob_scopes]
    if scopes and all(scopes):
        return sorted(set.union(*scopes))
    return ["AE", "AI", "OE", "OI"]

def normalize_customer_sql(column):
    """SQL expression matching the dashboard's whitespace-normalized names.

    Keep this portable across SQLite test databases and PostgreSQL production.
    """
    from sqlalchemy import func
    value = column
    for whitespace in ("\t", "\n", "\r", "\f", "\v", "\x85", "\u00a0", "\u1680", "\u2000", "\u2001", "\u2002", "\u2003", "\u2004", "\u2005", "\u2006", "\u2007", "\u2008", "\u2009", "\u200a", "\u2028", "\u2029", "\u202f", "\u205f", "\u3000"):
        value = func.replace(value, whitespace, " ")
    value = func.trim(value)
    for _ in range(8):
        value = func.replace(value, "  ", " ")
    return func.lower(func.trim(value))
