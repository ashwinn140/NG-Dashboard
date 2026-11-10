"""Phase 2 pure calculations. No database, imports, routes or production UI dependencies.

Functions operate on explicitly validated inputs; no implicit customer identity or
financial record matching is performed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median


@dataclass(frozen=True)
class GPBridge:
    previous_gp: float | None
    current_gp: float | None
    volume_impact: float | None
    yield_impact: float | None
    change: float | None
    status: str


def gp_bridge(previous_shipments: int, previous_gp: float | None,
              current_shipments: int, current_gp: float | None) -> GPBridge:
    """Exact volume/yield bridge when both periods have positive denominators.

    An unavailable GP or a zero shipment denominator is NOT treated as zero GP.
    """
    if previous_shipments < 0 or current_shipments < 0:
        raise ValueError("Shipment counts cannot be negative")
    if previous_gp is None or current_gp is None:
        return GPBridge(previous_gp, current_gp, None, None, None, "incomplete_gp")
    change = current_gp - previous_gp
    if previous_shipments == 0 or current_shipments == 0:
        return GPBridge(previous_gp, current_gp, None, None, change, "not_comparable")
    prior_yield = previous_gp / previous_shipments
    current_yield = current_gp / current_shipments
    volume = (current_shipments - previous_shipments) * prior_yield
    yield_effect = current_shipments * (current_yield - prior_yield)
    return GPBridge(previous_gp, current_gp, volume, yield_effect, change, "ok")


def customer_activity(shipment_dates: list[date], as_of: date) -> dict:
    """Conservative, explainable 30/60/90 day inactivity signal.

    Requires >=3 distinct historical shipment dates; seasonal and sparse
    customers remain insufficient_history rather than being called lost.
    """
    dates = sorted({d for d in shipment_dates if d <= as_of})
    if len(dates) < 3:
        return {"status": "insufficient_history", "threshold_days": None, "days_since_last": (as_of - dates[-1]).days if dates else None}
    intervals = [(b - a).days for a, b in zip(dates, dates[1:])]
    cadence = median(intervals)
    threshold = 30 if cadence <= 14 else 60 if cadence <= 30 else 90
    days = (as_of - dates[-1]).days
    status = "active" if days <= threshold else "at_risk" if days <= threshold * 1.5 else "inactive"
    return {"status": status, "threshold_days": threshold, "days_since_last": days}

LOB_ORDER = ("AE", "AI", "OE", "OI")


def cross_lob_customer_activity(dates_by_lob: dict, as_of: date,
                                selected_lobs: list[str],
                                visible_lobs: list[str],
                                complete_company_sources: bool) -> dict:
    """Classify selected-LOB inactivity without overstating company-wide loss.

    Dates are supplied from permission-scoped current shipment registers.
    Company-wide inactivity is eligible only when all four LOBs are visible
    and each has a promoted source snapshot. The result is bounded by loaded
    snapshot history, not an all-time guarantee.
    """
    visible_set = set(visible_lobs)
    visible = [lob for lob in LOB_ORDER if lob in visible_set]
    selected_set = set(selected_lobs)
    selected = [lob for lob in LOB_ORDER if lob in selected_set and lob in visible]
    if not selected:
        selected = visible

    per_lob = {}
    all_dates = set()
    for lob in visible:
        dates = sorted({d for d in dates_by_lob.get(lob, []) if isinstance(d, date) and d <= as_of})
        all_dates.update(dates)
        per_lob[lob] = {
            **customer_activity(dates, as_of),
            "last_shipment": dates[-1].isoformat() if dates else None,
        }

    overall = customer_activity(sorted(all_dates), as_of)
    inactive_selected = [lob for lob in selected if per_lob[lob]["status"] == "inactive"]
    active_selected = [lob for lob in selected if per_lob[lob]["status"] in ("active", "at_risk")]
    active_elsewhere = [
        lob for lob in visible if lob not in selected
        and per_lob[lob]["status"] in ("active", "at_risk")
    ]
    complete = bool(complete_company_sources and set(visible) == set(LOB_ORDER))

    if active_selected:
        classification = "active_in_selected_scope"
    elif inactive_selected and active_elsewhere:
        classification = "inactive_in_selected_lob_active_elsewhere"
    elif complete and overall["status"] == "inactive":
        classification = "verified_company_wide_inactivity"
    elif inactive_selected:
        classification = "inactive_in_selected_lob_no_other_visible_activity"
    else:
        classification = "insufficient_history"

    company_wide_status = overall["status"] if complete else "not_verified_incomplete_scope_or_sources"
    return {
        "classification": classification,
        "selected_lobs": selected,
        "inactive_selected_lobs": inactive_selected,
        "active_selected_lobs": active_selected,
        "active_elsewhere_lobs": active_elsewhere,
        "per_lob": per_lob,
        "company_wide_status": company_wide_status,
        "company_wide_verified": complete and overall["status"] == "inactive",
        "company_wide_activity": overall,
        "visible_lobs": visible,
        "source_coverage_complete": complete,
    }
