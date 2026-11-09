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
        if not company or not job_no or not job_date or not lob or not customer:
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
                "lob": lob, "customer": customer, "owners": set([owner] if owner else []),
            }
        elif owner:
            item["owners"].add(owner)

    result = []
    for item in grouped.values():
        owners = item.pop("owners")
        owner = next(iter(owners)) if len(owners) == 1 else ""
        result.append({
            "company": item["company"],
            "job_no": item["job_no"],
            "job_date": item["job_date"],
            "lob": item["lob"],
            "job_owner": owner or "Owner unavailable",
            "owner_status": "available" if len(owners) == 1 else "conflicting" if len(owners) > 1 else "missing",
        })
    result.sort(key=lambda item: (
        item["job_date"], item["job_no"].casefold(),
        item["lob"].casefold(), item["company"]
    ), reverse=True)
    return result[:max(0, min(int(limit), 5))]
