"""Phase 2 Opportunity Finder — pure, read-only cross-service whitespace signals.

This module never queries the database or changes the existing dashboard.
Caller must supply only authorized, company-scoped, customer-code-verified rows.
"""
from collections import defaultdict
from datetime import date

LOBS = ("AE", "AI", "OE", "OI")
MIN_SHIPMENTS = 3


def find_opportunities(rows, as_of: date, window_days: int = 180,
                       min_shipments: int = MIN_SHIPMENTS):
    """Return explainable whitespace opportunities for existing active customers.

    Each input row: company, customer_code, lob, shipment_id, shipment_date.
    Rows must already be permission-filtered by caller. An absent LOB is a
    *potential* opportunity, not proof of demand or a lost customer.
    Only current-window activity is counted, using distinct shipment IDs.
    """
    if not 1 <= window_days <= 366:
        raise ValueError("window_days must be between 1 and 366")
    if min_shipments < 1:
        raise ValueError("min_shipments must be positive")
    from datetime import timedelta
    start = as_of - timedelta(days=window_days - 1)
    grouped = defaultdict(lambda: defaultdict(set))
    for row in rows:
        company = str(row.get("company") or "").strip().upper()
        customer = str(row.get("customer_code") or "").strip()
        lob = str(row.get("lob") or "").strip().upper()
        shipment_id = str(row.get("shipment_id") or "").strip()
        when = row.get("shipment_date")
        if not (company in ("NG", "NCS") and customer and lob in LOBS and shipment_id
                and isinstance(when, date) and not hasattr(when, "hour")
                and start <= when <= as_of):
            continue
        grouped[(company, customer)][lob].add(shipment_id)
    result = []
    for (company, customer), lob_counts in grouped.items():
        active = {lob: len(ids) for lob, ids in lob_counts.items() if ids}
        total = sum(active.values())
        if total < min_shipments:
            continue
        missing = [lob for lob in LOBS if lob not in active]
        if not missing:
            continue
        result.append({
            "company": company, "customer_code": customer,
            "active_lobs": dict(sorted(active.items())),
            "candidate_lobs": missing, "shipment_count": total,
            "signal": "cross_service_whitespace",
            "confidence": "review_required",
            "reason": "Customer has recent shipments in some LOBs but none in the listed LOBs during the selected window.",
        })
    return sorted(result, key=lambda x: (-x["shipment_count"], x["company"], x["customer_code"]))
