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
