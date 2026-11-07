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
