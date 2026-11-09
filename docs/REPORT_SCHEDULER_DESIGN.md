# Generic Report Scheduler — Pilot Design

Version: 0.1  
Date: 9 November 2026  
Status: design baseline; scheduled email delivery remains disabled until all security and correctness gates pass.

## Scope and first pilot

A reusable report scheduler, not one implementation per report. The first catalog is deliberately limited to three reports whose current sources and permissions are already present:

1. **Shipment Register** — detail rows from the four permitted shipment registers (AE, AI, OE, OI), based on Shipment Date.
2. **Customer Performance** — customer-level shipment counts, mode/LOB split, air chargeable weight, sea TEUs, latest shipment date and visible-LOB coverage; no finance fields.
3. **Job Profitability** — detail/summary from the existing simple Job Profit Analysis Report, based on Job Date; finance permission required. No charge-wise source workbook is required.

Other catalog candidates remain disabled until their metric/source/permission definitions are verified.

## Definition model

Persist: report ID and version, owner, company and LOB scope, allowlisted filters, selected and ordered columns, sort, summary/detail mode, totals, fixed date basis, relative/fixed period, frequency, timezone, local run time, weekday/day-of-month, approved recipients, freshness policy, start/end, enabled/paused/disabled status, next run, last run and delivery history.

No arbitrary SQL, table names, raw expressions or unrestricted field selection. Column IDs, filters, sort keys and parameters must come from the report's catalog schema.

## Relative periods and time

Supported period vocabulary: yesterday, today-to-date, last 7 completed days, last 30 completed days, prior calendar week, current month-to-date, prior calendar month, current FY-to-date, prior FY and fixed range. Date basis is report-defined, not user-overridable: Shipment Date for operational reports and Job Date for Job Profitability.

Store schedule timezone as an IANA name and local time separately from UTC next-run timestamps. Compute DST/month-end/leap-year boundaries deterministically. For ambiguous local times use a documented fold policy; for nonexistent local times move to the next valid local minute and record the adjustment.

## Security and recipients

- Resolve the owner from the current users table at execution time. Inactive users cannot receive reports.
- Revalidate company, LOB and finance permission at execution time. If access was revoked or narrowed, never reuse the stale creation-time scope.
- Pilot recipient policy: owner only. The recipient is resolved to the owner's current verified account email at execution time; user-supplied external addresses are rejected unless a later explicit admin allowlist/approval feature is implemented.
- Finance reports are visible and schedulable only for users with finance permission.
- Every schedule change, manual run, pause/resume, recipient policy decision and delivery attempt is audited.
- Scheduled email worker is disabled by default behind `REPORT_SCHEDULER_ENABLED=false`. No real customer/financial emails are sent until the full permission, duplicate, Excel, freshness, retry and recipient tests pass and an administrator explicitly enables it.

## Durable execution architecture

PostgreSQL-backed schedule definitions and run queue. A unique idempotency key is derived from schedule ID + scheduled UTC instant + report version. Due schedules create one queued run per idempotency key. Workers claim queue rows transactionally with `FOR UPDATE SKIP LOCKED`; multiple replicas cannot claim the same run. A restart resumes queued/retryable runs. Bounded retries use exponential backoff; permanent validation/security failures do not retry.

State distinctions: scheduled, queued, generating, generated, submitted, provider_accepted, delivered (only if provider evidence exists), failed, skipped_stale, cancelled. SMTP acceptance is not inbox delivery. Provider status/message ID and timestamps are stored separately.

## Freshness and source coverage

Check the relevant current promoted import for every selected company/LOB immediately before generating the workbook. Apply the schedule's explicit policy: skip and notify, delay within a configured maximum, or warn and send. Never silently label stale data as current. Workbook metadata includes source/import timestamp, date range, freshness status, filters and date basis.

## Excel quality

Use openpyxl. Each workbook has a title, company/LOB, generated timestamp, report period, date basis, filters, source freshness, headers, frozen rows, autofilters, correct date/currency/percentage formats, totals and calculation notes. Prevent formula injection from ERP text by escaping strings beginning with =, +, -, @, tab or carriage return. Apply file-size and row limits; if exceeded, split into clearly named sheets/files or fail with a recorded reason—never truncate silently. Validate row counts and totals against the interactive report calculations.

## UI and lifecycle

Create, preview, test-generate, activate, edit, duplicate, pause, resume, run now, deactivate and inspect history. Preview shows exact filters, selected columns, period/date basis, sample, estimated rows, next run and recipient count. Initial test action is a dry-run generation; actual test email is only available after the scheduler feature is explicitly enabled and still sends only to the owner.

Admin/history shows owner, report, frequency, next/last run, recipient count and status. Per-run history shows period, freshness, row count, file size, attempts, provider status, errors and run timestamps.

## Mandatory test matrix

- Daily/weekly/monthly, selected weekdays and day-of-month.
- Timezone changes, DST gaps/folds, month-end, leap year and fiscal-year boundaries.
- Shipment Date vs Job Date; fixed and relative periods; exact end-exclusive boundaries.
- Empty and zero-row reports, stale/missing imports, delay/skip/warn behavior.
- Role/finance/company/LOB permission changes after schedule creation.
- Inactive/deleted owner, unauthorized recipient, owner email change.
- Concurrent workers, worker restart, duplicate queue creation, idempotent retry and permanent failure.
- Large exports, Excel formulas, formula injection, totals, formats, row count and parity with on-screen report.
- Provider timeout/rejection vs provider acceptance; never claim delivery without evidence.

## Release gates

1. Core schema/period/Excel tests pass.
2. Server-side access checks and execution-time revalidation pass.
3. Queue idempotency/concurrency/restart tests pass.
4. Email provider status semantics and approved-recipient tests pass.
5. Authenticated browser and manual dry-run QA pass.
6. Only then enable `REPORT_SCHEDULER_ENABLED` in Railway with administrator approval.
