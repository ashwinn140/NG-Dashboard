# Business Intelligence Beta — Reconciliation audit (2026-11-07)

## Scope and evidence
Static code inspection of app/dataset.py, app/web/intelligence.html and app/phase2_opportunity.py. Railway deployment status checked separately. **No authenticated production dataset export, raw ERP report comparison, or row-by-row financial reconciliation was performed.** These are open acceptance gates, not passed tests.

## Confirmed findings
1. **Salesperson:** dataset.py normalizes "Sales Person" to x_salesperson. The initial BI UI used x_sales_person; corrected in commit b4dc47e. Actual populated values remain unverified.
2. **As-of dates:** initial BI measured activity against the browser's current date rather than latest available shipment. Changed to latest authorized shipment date in commit 1c8c788. This is still an operational proxy; it does not prove report completeness.
3. **Search filters:** initial management/retention/variance prior-period comparisons ignored customer search. Corrected in commit 1c8c788.
4. **Profit matching:** dataset.py matches financial lines to shipments on (company, job number, job date) and falls back to the first matching (company, job number) without an ambiguity guard. Therefore matched GP is not a certified ERP total, and unmatched lines are excluded from BI heatmap. This remains OPEN; no finance attribution changes should be made without a verified business key and source samples.
5. **Profit scope:** profit rows can have a billing/transaction date distinct from shipment date. BI heatmap filters by shipment date and only matched records; it is not comparable with a billing-date financial statement. OPEN.
6. **Retention:** uses a 365-day lookback and unique shipment dates, then median interval thresholds; seasonal business, report gaps, multiple same-day shipments and sparse history can distort activity classification. OPEN.
7. **Variance:** BI variance is shipment count only. It does not implement a complete GP volume/yield bridge. OPEN.
8. **Customer identity:** commercial customer is sourced from Shipment Register Customer; casing and whitespace canonicalization in dataset.py can merge similar strings, but no stable customer master ID is established. OPEN.
9. **Permissions:** dataset.restrict applies company, LOB and finance access; the BI page relies on /api/dataset scoped response. An authenticated multi-role test is still required.
10. **Opportunity Finder:** requires all four LOB imports and labels candidates as review-required; this is whitespace, not confirmed demand. Actual report coverage must be validated per date window and permissions.
11. **Presentation:** the shipment drill-down is limited to 300 rows, while headline totals use the entire selected period. The cap must be conspicuously disclosed and exports compared.
12. **Testing:** JavaScript syntax was checked; no authenticated browser run or source-to-dashboard numerical tie-out has been completed.

## Mandatory reconciliation matrix
For each NG/NCS x AE/AI/OE/OI combination, compare promoted ERP source to PostgreSQL active rows, /api/dataset authorized rows, original dashboard and BI beta for: shipment count; distinct shipment numbers; date min/max; distinct customer count; blank customer count; Sales Person nonblank and blank count; totals by salesperson; report/import IDs; duplicate business keys; and report coverage.
For JP separately: raw line count, income, expense, GP, unmatched job count, ambiguous job matches, date basis, intercompany exclusions and currency. Do not claim profit reconciliation until all tie.
Repeat for admin, restricted company, restricted LOB and no-finance users. Verify reporting-period edges, future-dated rows, negative GP, cancellations, zero-activity segments and missing imports.

## Release gate
Keep Business Intelligence explicitly BETA. Do not certify or publish GP and customer-loss claims as facts until source report and role-scoped data reconciliations pass. Existing main dashboard remains unchanged except the BI beta navigation card.
