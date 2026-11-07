# Daily replacement and dashboard resource use

Replacement scope approved by the owner on 7 November 2026. Live verification is recorded below after deployment.

## Verified production baseline

70,315 active shipments: 21,383 from 2023, 23,013 from 2024 and 25,919 from 2025.
No duplicate company/report/shipment-number/date keys and no previous row versions.
The database measured 167 MB; PostgreSQL transaction logs separately measured 208 MB.
No 2026 shipments were loaded at the time of the audit.

## Proposed behaviour

Production configuration: `REPORT_STORAGE_MODE=replace`.
The default remains `versioned`, including after code deployment without this variable.

* A shipment is matched by company, report type, shipment number and shipment date.
* Changed shipments update the existing row; unchanged shipments keep their row.
* A missing shipment is removed only inside the incoming report's dates and branches.
* Other reporting periods and branches remain stored. Loading a 2026 report does not remove 2023–2025.
* A suspicious reduction of more than 10% remains held for admin review.
* Identical files and stale reports are ignored; invalid or out-of-scope shipment data is rejected.
* Profit replacement requires an explicit billing-date range, valid transaction dates and no key conflict outside that range.
* Replacement keeps current business data, rather than previous versions of changed or missing records.
  The dashboard explains why its before/after comparison is unavailable in this mode.
* Existing previous versions, original files and Gmail messages are not purged by this release.
  Old archive removal needs a separate reviewed retention rule.

The approved replacement rule would apply automatically to future valid imports. No bulk cleanup is proposed now.

## Resource changes

* Dashboard queries fetch only the fields the UI uses; original columns remain in the database.
* Stable shipment order is restored in Python, avoiding the database's sort of wide JSON records.
* Profit dashboard reads omit unused original-column JSON.
* Before/after comparisons fetch full JSON only for actually changed shipments.
* The worker prepares the dashboard after draining its import batch, rather than after every file.
* Profit-file detection reads the first three Excel rows instead of loading the entire workbook once just to identify it.
* Repeated deliveries of the same bytes and filename reuse their monthly archived workbook.

No database log settings, billing changes, volume resize, schema migration or data purge is included.
The existing 500 MB trial volume may still need more capacity when 2026 data is loaded.

## Static history and the daily financial-year refresh

`REPORT_STATIC_HISTORY=1` protects previously loaded periods before the current financial year.
The FY boundary uses the existing `fy_start_month` dashboard setting (default April).
Existing historical rows cannot be updated or removed by a later report; new records within a
previously covered historical report period are ignored. A missing historical period may still
be seeded once. This also permits separate calendar-year files to complete an April–March FY.
The current FY continues to update in place. At the FY rollover, the former current year's
records become static automatically; nothing is aged out or deleted.

Profit protection uses billing dates. Job-date summary reports do not substitute for charge-wise
detail and are not loaded into the billing-date finance visuals. Replacement-mode Undo is disabled
because earlier row versions are not retained; corrections use a replacement report instead.

Two additional integration tests verify static shipment/profit history, calendar-year baselines,
current-FY updates and protection from unsafe Undo: nine replacement tests in total.

## Validation

`python -W ignore::DeprecationWarning scripts/test_daily_replacement.py`

Seven synthetic integration cases cover repeated daily changes, historical and branch preservation,
review holds, duplicate and stale deliveries, malformed report scopes, profit date boundaries,
default version history, dashboard-output parity, access restrictions and duplicate-file archival.

`python -W ignore::DeprecationWarning scripts/benchmark_dashboard.py`

A fresh local SQLite database with 70,315 synthetic shipments and 100 unused ERP columns per row
built the dashboard in 5.78 seconds, with 301.2 MiB peak process RSS. This is a local sizing check,
not proof of production PostgreSQL performance or a future Railway bill.

Eight existing mailer tests also pass. Live import and dashboard checks remain required after deployment.

## Approved calendar history reduction (7 November 2026)

Retain 1 January 2025 onward: static calendar 2025 plus daily calendar 2026.
The user approved deletion of pre-2025 dashboard records; source workbooks and Gmail remain intact.
Set history_years=2 and fy_start_month=1. REPORT_HISTORY_START=2025-01-01 prevents older report replay.
Retention deletes in batches of 250, vacuums reusable space, and checkpoints PostgreSQL.
REPORT_SMALL_DATABASE=1 opts into min_wal_size=32MB and max_wal_size=64MB for the 500 MB volume; durability stays enabled.
IMPORTS_PAUSED=1 pauses the queue during maintenance; set 0 to resume after cleanup.
11 data integration checks and 8 mailer checks pass. The sample-based year test is unavailable without its original workbook fixture.
