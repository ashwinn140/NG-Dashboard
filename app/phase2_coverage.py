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
