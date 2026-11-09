# Production verification — 9 November 2026

Scope: existing production dashboard, Jan 2025 onward. No import approvals, retries, reversals, financial formula changes, or dataset mutations.

## Verified before release
- Authenticated administrator access and live dashboard, Help, Calculation & records, and admin read endpoints.
- Actual production Excel downloads inspected as workbooks, including contributing records, comparison records, reconciliation, filters and lineage. Company/year control totals matched accepted-import audit controls and independently aggregated API records to paise. This is not a new inspection of original accepted source workbook bytes or independent SQL reconciliation.
- Company/date filters, partial LOB search, multiple matching selections, clear all, and negative-baseline comparison.
- Desktop layout and narrow CSS viewport reflow at 454 and 340 pixels; no outer page horizontal overflow. Physical mobile/touch testing was not performed.
- Installed Apps Script collectReports trigger: Every hour, Head, owned by the authenticated project owner. Recent hourly executions completed; trigger UI displayed 0% error rate. Trigger inspected and cancelled without saving.

## Confirmed targeted fixes
- Admin JPR freshness counts and provenance now use current job-summary scope instead of retained legacy charge history.
- Coverage table identifies report/LOB instead of presenting indistinguishable company/year rows.
- Evidence currency cells display two decimals; underlying records and export precision unchanged.
- Filter popovers no longer stringify null placeholders.
- Repository collector installer and conflicting README cadence align with the verified live hourly trigger; deployed Apps Script not modified.

## Fresh validation
149 backend tests passed; all 14 frontend suites passed, including data audit and runtime inventory. Generated dashboard rebuilt. Financial calculations unchanged.

## Limits and follow-up
Original accepted source workbook bytes require read-only retrieval from production storage or matching original files. Independent SQL validation requires read-only PostgreSQL access. Latest JPR receipt predates the current shipment-register receipts; successful trigger executions alone do not establish that a newer JPR was sent. Historical failed/review imports remain untouched; 2024 is outside business scope. Live non-admin account acceptance and physical mobile testing are not completed. PR 40 remains open, PR 42 draft preserved, PR 28 deferred; Customer & Partner 360 and Email Scheduler stay frozen/deferred.

Release and post-deployment results must be recorded only after Railway reaches terminal SUCCESS and live rechecks complete. No private production figures are included in this checkpoint.
