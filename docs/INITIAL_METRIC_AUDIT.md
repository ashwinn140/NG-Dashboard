# Verified initial source and calculation audit — 2026-11-09

Scope: source inspection only on feature/metric-traceability-review. No production change.

## Confirmed source schema from app/config.py
Shipment Register required: `Shipment No`, `Shipment Date`, `Branch`, `Customer`, `Status`, `Job Owner`.
Shipment identity is composite `Shipment No` + `Shipment Date`; never deduplicate on shipment number alone.
Optional mapped source columns: `Shipper`, `Consignee`, `Airline` / `Shipping Line`, `Loading Port`, `Discharge Port`, `Gross Weight`, `Chargeable Wt`, `TEUs`, `Volume`, `Cargo Type`, `Consol Type`, `Self/Agent Nomination (UDF)`, `Operations Locked On`, `Financials Locked On`.
JPR required columns: `Location`, `LOB`, `Job No.`, `Job Date`, `Organization`, `Income (INR)`, `Expense (INR)`, `Profit (INR)`.
These are code-configured headers, not yet verified against a particular latest production upload.

## Critical semantic finding
`frontend/pr_core.js::recomputeJobsP()` currently defines:
- status 1 / 'Cost not booked': expense == 0 and income > 0.
- status 2 / 'Billing pending': income <= 0 and expense > 0.
- status 3 / 'Loss-making': (income - expense) < -1, after statuses 1 and 2.
- status 4 / 'Low margin': income > 0 and (income-expense)/income < configured lowMargin, after earlier statuses.
- otherwise status 0.
The labels in `frontend/pr_pages.js::ppQuality()` use this classification. **Billing pending is inferred from financial amounts, NOT a verified ERP invoice/billing status.** It is possible for a billed job to have zero income in this source or for unbilled jobs to have other patterns. Business confirmation required before representing this as actual unbilled jobs.

## Existing capabilities and gaps
- `frontend/pr_pages.js::ppJobs()` already provides search, sorting and Excel export of filtered jobs, but table display is limited by `S.def.jobRows`. Its export uses the full searched list; it is not yet a universal side drawer.
- `frontend/pr_pages.js::ppQuality()` clicking a KPI applies a job-status filter to all views rather than opening a drawer.
- `app/server.py` exposes `/api/dataset` with permission-filtered payload; `/customer360` is a separate page. Universal server-side drilldown/export endpoints do not yet exist.
- `app/processor.py` handles source column order by name and stores extra columns; changes in column ordering should not break standard mappings.
- `app/config.py` uses `Job Date` as JPR date basis. Any comparison with Shipment Register's `Shipment Date` must disclose the different basis.

## Required next implementation gate
1. Validate actual latest uploaded header arrays and the transformations in `app/profit.py` and `app/dataset.py`.
2. Resolve semantic ambiguity of 'Billing pending': either rename as 'Costs booked, no income recorded' or use an actual verified invoice-status field. Do not silently change production semantics.
3. Build metric registry and reconciliation tests from verified source/aggregation code before modifying charts.
4. Preserve server-side authorization in new endpoints; do not treat client-side dataset filtering as a security boundary.
