"""Phase 2 read-only source-field coverage diagnostics.

Only import metadata is inspected. No shipment rows, names, or financial data
are exposed. This module is deliberately independent of the ingestion worker.
"""
import json
import re

EXPECTED = ("NG", "NCS")
LOBS = ("AE", "AI", "OE", "OI")
FIELDS = {
    "customer_code": ("customercode", "customerno", "customercodeno", "organizationcode", "orgcode"),
    "sales_person": ("salesperson",),
    "shipment_number": ("shipmentno",),
    "shipment_date": ("shipmentdate",),
}


def _norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def report_field_coverage(rows):
    """Summarize last promoted import per company/LOB from supplied mappings.

    rows: mappings with company, report_type, columns, id. Sorted or unsorted.
    Returns no raw import data. Missing reports are explicit, not zero rows.
    """
    latest = {}
    for row in rows:
        company, lob = row.get("company"), row.get("report_type")
        if company not in EXPECTED or lob not in LOBS:
            continue
        key = (company, lob)
        if key not in latest or int(row["id"]) > int(latest[key]["id"]):
            latest[key] = row
    result = []
    for company in EXPECTED:
        for lob in LOBS:
            row = latest.get((company, lob))
            if row is None:
                result.append({"company": company, "lob": lob, "status": "no_promoted_import", "fields": {}})
                continue
            try:
                columns = json.loads(row.get("columns") or "[]")
                if not isinstance(columns, list):
                    raise ValueError("not a list")
                names = {_norm(c) for c in columns}
                fields = {field: any(candidate in names for candidate in aliases) for field, aliases in FIELDS.items()}
                result.append({"company": company, "lob": lob, "status": "ok", "fields": fields})
            except (TypeError, ValueError):
                result.append({"company": company, "lob": lob, "status": "invalid_column_metadata", "fields": {}})
    return result


# Job-history readiness is deliberately separate from the eight-register field
# coverage above. It reports header availability only; it does not claim that
# a JPR job can be matched to a register row or that every owner is populated.
JOB_HISTORY_REPORTS = ("AE", "AI", "OE", "OI", "JP")
JOB_HISTORY_FIELDS = {
    "job_number": ("jobno", "jobnumber"),
    "job_date": ("jobdate",),
    "job_owner": ("jobowner",),
    "lob": ("lob", "lineofbusiness"),
    "shipment_number": ("shipmentno",),
    "shipment_date": ("shipmentdate",),
}


def job_history_field_coverage(rows):
    """Return latest promoted source-header coverage for the five report types.

    Shipment registers need Shipment No, Shipment Date and Job Owner.
    JPR needs Job No., Job Date and LOB; Job Owner is optional there because
    the dataset can fall back to the uniquely matched shipment register.
    This is metadata-only and does not inspect or expose customer/job rows.
    """
    latest = {}
    for row in rows:
        company, report = row.get("company"), row.get("report_type")
        if company not in EXPECTED or report not in JOB_HISTORY_REPORTS:
            continue
        key = (company, report)
        if key not in latest or int(row["id"]) > int(latest[key]["id"]):
            latest[key] = row

    result = []
    for company in EXPECTED:
        for report in JOB_HISTORY_REPORTS:
            row = latest.get((company, report))
            if row is None:
                result.append({
                    "company": company, "report_type": report,
                    "status": "no_promoted_import", "fields": {},
                    "required_fields_present": False,
                })
                continue
            try:
                columns = json.loads(row.get("columns") or "[]")
                if not isinstance(columns, list):
                    raise ValueError("not a list")
                names = {_norm(c) for c in columns}
                fields = {
                    field: any(candidate in names for candidate in aliases)
                    for field, aliases in JOB_HISTORY_FIELDS.items()
                }
                required = (
                    ("job_number", "job_date", "lob")
                    if report == "JP"
                    else ("shipment_number", "shipment_date", "job_owner")
                )
                result.append({
                    "company": company, "report_type": report,
                    "status": "ok" if all(fields[k] for k in required) else "missing_required_fields",
                    "fields": fields,
                    "required_fields_present": all(fields[k] for k in required),
                    "job_owner_source": (
                        "jpr_source_column" if report == "JP" and fields["job_owner"]
                        else "matched_register_fallback" if report == "JP"
                        else "shipment_register"
                    ),
                })
            except (TypeError, ValueError):
                result.append({
                    "company": company, "report_type": report,
                    "status": "invalid_column_metadata", "fields": {},
                    "required_fields_present": False,
                })
    return result


# Aggregated, read-only job-owner readiness. This intentionally returns counts only;
# it never returns customer names, job numbers, owner names or financial amounts.
def _job_report_type(lob):
    value = str(lob or "").upper()
    if "AIR" in value and "EXP" in value:
        return "AE"
    if "AIR" in value and "IMP" in value:
        return "AI"
    if "SEA" in value and "EXP" in value:
        return "OE"
    if "SEA" in value and "IMP" in value:
        return "OI"
    return None

def _job_lob_label(lob):
    report = _job_report_type(lob)
    return {"AE": "Air Export", "AI": "Air Import", "OE": "Sea Export", "OI": "Sea Import"}.get(report, str(lob or "").strip() or "(missing LOB)")


def _day_key(value):
    from datetime import date, datetime
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value or "").strip()[:10]


def job_history_data_quality(register_rows, job_rows):
    """Summarize current JPR-to-register match and owner completeness.

    Matching mirrors the dashboard's conservative join: company + job number +
    exact job/shipment date first, then company + job number fallback, filtered
    to the expected LOB register. Only a single candidate is accepted.
    JPR Job Owner takes precedence when the column is present, including an
    explicit blank; register Job Owner is used only when that JPR field is absent.
    """
    from collections import defaultdict

    by_key, by_no = defaultdict(list), defaultdict(list)
    register_stats = defaultdict(lambda: {"rows": 0, "owner_populated": 0})
    for row in register_rows:
        company = str(row.get("company") or "").strip().upper()
        report = str(row.get("report_type") or "").strip().upper()
        number = str(row.get("shipment_no") or "").strip()
        day = _day_key(row.get("shipment_date"))
        owner = str(row.get("job_owner") or "").strip()
        if company not in EXPECTED or report not in LOBS or not number or not day:
            continue
        item = {"report_type": report, "job_owner": owner}
        by_key[(company, number, day)].append(item)
        by_no[(company, number)].append(item)
        stats = register_stats[(company, report)]
        stats["rows"] += 1
        stats["owner_populated"] += bool(owner)

    grouped = defaultdict(list)
    invalid = defaultdict(int)
    for row in job_rows:
        company = str(row.get("company") or "").strip().upper()
        lob = str(row.get("lob") or "").strip()
        number = str(row.get("job_no") or "").strip()
        day = _day_key(row.get("job_date"))
        if company not in EXPECTED:
            continue
        group_key = (company, _job_lob_label(lob))
        if not number or not day or not lob:
            invalid[group_key] += 1
            continue
        grouped[(company, lob, number, day)].append(row)

    results = {}
    def bucket(company, lob):
        key = (company, lob)
        return results.setdefault(key, {
            "company": company, "lob": lob, "job_count": 0,
            "matched_register_jobs": 0, "ambiguous_register_matches": 0,
            "unmatched_register_jobs": 0, "register_not_applicable": 0,
            "duplicate_job_identities": 0, "invalid_job_rows": 0,
            "job_owner_populated": 0, "job_owner_missing": 0,
            "owner_from_jpr": 0, "owner_from_register": 0,
            "jpr_owner_explicitly_blank": 0,
            "register_rows": 0, "register_owner_populated": 0,
        })

    for (company, source_lob, number, day), rows in grouped.items():
        lob = _job_lob_label(source_lob)
        stats = bucket(company, lob)
        stats["job_count"] += 1
        if len(rows) != 1:
            stats["duplicate_job_identities"] += 1
            stats["job_owner_missing"] += 1
            continue

        row = rows[0]
        extra = row.get("extra") if isinstance(row.get("extra"), dict) else {}
        owner_key = next((k for k in extra if _norm(k) == "jobowner"), None)
        if owner_key is not None:
            owner = str(extra.get(owner_key) or "").strip()
            if owner:
                stats["owner_from_jpr"] += 1
                stats["job_owner_populated"] += 1
            else:
                stats["jpr_owner_explicitly_blank"] += 1
                stats["job_owner_missing"] += 1
            continue

        is_clearance = _norm(source_lob).startswith("ccl") or "customsclearance" in _norm(source_lob)
        if is_clearance:
            stats["register_not_applicable"] += 1
            stats["job_owner_missing"] += 1
            continue

        candidates = by_key.get((company, number, day), [])
        if not candidates:
            candidates = by_no.get((company, number), [])
        expected = _job_report_type(source_lob)
        if expected:
            candidates = [candidate for candidate in candidates if candidate["report_type"] == expected]

        if len(candidates) > 1:
            stats["ambiguous_register_matches"] += 1
            stats["job_owner_missing"] += 1
        elif not candidates:
            stats["unmatched_register_jobs"] += 1
            stats["job_owner_missing"] += 1
        else:
            stats["matched_register_jobs"] += 1
            if candidates[0]["job_owner"]:
                stats["owner_from_register"] += 1
                stats["job_owner_populated"] += 1
            else:
                stats["job_owner_missing"] += 1

    for (company, report), reg in register_stats.items():
        lob = {"AE": "Air Export", "AI": "Air Import", "OE": "Sea Export", "OI": "Sea Import"}[report]
        stats = bucket(company, lob)
        stats["register_rows"] = reg["rows"]
        stats["register_owner_populated"] = reg["owner_populated"]

    for (company, lob), count in invalid.items():
        bucket(company, lob)["invalid_job_rows"] += count

    output = []
    for stats in results.values():
        jobs = stats["job_count"]
        stats["job_owner_coverage_pct"] = round(100 * stats["job_owner_populated"] / jobs, 2) if jobs else None
        stats["register_owner_coverage_pct"] = round(100 * stats["register_owner_populated"] / stats["register_rows"], 2) if stats["register_rows"] else None
        stats["status"] = "no_jobs" if not jobs else (
            "ready" if stats["job_owner_missing"] == 0 and stats["duplicate_job_identities"] == 0 and stats["invalid_job_rows"] == 0
            else "partial"
        )
        output.append(stats)
    return sorted(output, key=lambda row: (row["company"], row["lob"]))
