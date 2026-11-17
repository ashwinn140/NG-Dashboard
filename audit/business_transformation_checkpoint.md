# Current-state verification — 9 November 2026

This checkpoint supersedes stale workstream counts in implementation_checkpoint.md. Scope follows the supplied definitive handover. No source records, finance formulas, import promotions, permissions, schema, schedules or unrelated services were changed.

## Baseline independently checked

- Main and Railway both at 75e704e228d5add2d08b9e7ba3d2d6587a93e72d before this label-only release.
- Railway NG-Dashboard deployment f761fabb-f268-4b2e-af4c-ef5baab401fc: SUCCESS.
- PRs 35, 36, 37, 38 and 39 confirmed merged; their commits are part of main. Covers operations comparisons, summary profit rankings, independent Profit Compare periods/evidence and customer growth/decline evidence.
- Working branch: audit/current-state-verification-75e704e. Latest release result will be recorded on its PR after rollout.

## Completed verification

- Materialized current source at the exact baseline; rebuilt canonical dashboard.
- 147 Python tests passed, including JPR validation, permissions, metric execution, customer history, volume unit association, invoice placeholders and variance guard cases.
- 141/141 data audit checks passed. Fourteen frontend suites passed: data audit, operations page fixes, Customer360 shared regression, metric trace, drawer, explicit reconciliation, Help Guide, visual trace, visual explanation coverage, cost-lag warning, operational age reference, quality explanations, live threshold explanations and runtime inventory.
- Fresh synthetic inventory: 414 role/page instances, 408 unique role/page/title entries, 374 entries with verified explanation text, zero explanations marked unverified, 34 entries without blocks, zero unvisited pages, zero runtime errors, zero evidence actions attached to unverified formulas. Entries without blocks are untitled structural wrappers or visual-builder containers. Deduplication across roles produces 174 page/title entries, of which 158 have explanations; the 16 remaining entries are wrappers/builder containers. These count definitions differ from the historical 160 substantive-visual tally; do not infer new missing business formulas from aggregate differences.
- Explanation workstream has no remaining unverified calculation blocks in the exercised synthetic pages. This is code/runtime verification, not independent certification of original ERP source files or authenticated production browser acceptance.
- Simple job-level JPR remains the source, using Job Date and Income minus Expense. Charge-detail layouts remain excluded. Existing tests verify invalid replacement preservation and duplicate-job checks.

## Small confirmed handover mismatch corrected

Customer & Partner 360 was not visibly marked BETA in current navigation/page titles. Only label text was changed to Customer & Partner 360 (BETA) in the production shell and Customer360 page, then the canonical page was rebuilt. Customer360 functionality remains frozen. Its shared regression suite passed after the label edit.

## PR review

- PR40 remains open at head 2d6e65eb998456c5c9c2ff3662687f62ac133c57. Reviewed three-file diff: adds an explicit locked/no-invoice evidence action and tests, reusing an existing metric. It is additional evidence coverage, not a confirmed production-breaking defect. Not merged automatically. Its action explains the uninvoiced subset; the existing table also includes other locked-shipment measures, so full table-column evidence semantics still merit acceptance review before release.
- PR28 is customer inactivity work and remains deferred; do not merge it as part of this phase.

## Production/browser limits and next actions

- Cloud browser reached the live site's sign-in page. No authenticated browser session is available. Secure browser sign-in is required before actual dashboard interactions, screenshots, 1920/1366/768/390 responsive checks and keyboard/accessibility acceptance. Do not enter chat credentials into browser automation or claim a synthetic DOM run is an authenticated browser test.
- Current accepted simple-JPR source-to-PostgreSQL-to-API-to-screen-to-export reconciliation still needs authorized live data/source access. Historical sample audits and synthetic totals do not certify today's production snapshot. No charge-wise workbook search or Billing Date reconstruction is required or authorized by this checkpoint.
- Current ingestion freshness, held 2024 profitability status and actual hourly-fetch behavior require live administrative evidence; not inferred from a healthy container or old checkpoint.
- No visual redesign or financial formula changes made without a confirmed defect. Broad UI refinement remains unverified until browser acceptance is possible.
- Customer360 BETA frozen; Email Report Scheduler deferred; charge-wise JPR and unrelated apps excluded.
- Exact continuation: securely authenticate the existing production browser, perform targeted main-dashboard acceptance and available authorized JPR/API/Excel reconciliation, inspect current import/freshness state, then fix only confirmed defects. Preserve the verified explanation work and avoid repeating its implementation.

## Release safety

Only label text and checkpoint documentation are in this release. Production rollback before rollout: f761fabb-f268-4b2e-af4c-ef5baab401fc / main 75e704e. No database rollback required. Release rollout and public health result will be recorded on the PR; authenticated acceptance remains explicitly outstanding.

## Continuation verification — 9 November 2026 (live GitHub/Railway reads)

### Current repository and production state
- Rechecked GitHub main: `004b7a6e3f66317375d28c84249110ed109e6490` (merge of PR #41).
- PR #41 is merged. PR #40 remains open at `2d6e65eb998456c5c9c2ff3662687f62ac133c57`; PR #28 remains open and deferred.
- PR #40's Metric traceability checks workflow run 42660496371 completed SUCCESS. Its single job ran production build, backend/permissions/Excel reconciliation suite, frontend metric-contract audit and synthetic visual inventory. This is CI evidence only, not live database reconciliation.
- Railway project `Performance Dashboard Production`, production environment `410fd484-cba1-4ade-b831-b6c76e0018e1`: dashboard, Postgres and AI-Insights are all online (1/1 replicas each), zero active warnings/criticals, zero recent failures and no pending work.
- Current dashboard deployment `a30fb086-e1a0-4a9b-abbf-be8541bde149` SUCCESS, serving main commit `004b7a6...`. Previous `f761fabb...` is REMOVED/superseded. Public health requests returned HTTP 200. No deployment was initiated during this continuation.
- Runtime logs include successful `/api/dataset`, `/api/metrics/definitions`, `/api/me` and `POST /api/metrics/evidence` responses. This verifies API request success, not financial reconciliation.

### PR #40 review continuation
- Current PR head is unchanged; PR is mergeable and open. No submitted reviews or inline review threads are present.
- Patch attaches the existing `ops.locked_no_invoice` metric to the existing billing worklist visual and preserves the selected grouping dimension. Existing server metric eligibility is operations lock date > 0 and invoice count == 0; the action returns the locked/uninvoiced subset and explicitly describes its as-of scope.
- Workflow run `42660496371` and job `129310447609` completed SUCCESS at 17:02 UTC, including the focused backend evidence test and frontend binding assertion.
- No merge performed. Continue to require acceptance that the evidence action represents the locked/uninvoiced subset, not every displayed billing measure.

### Live configuration and source checks
- Dashboard service follows `ashwinn140/NG-Dashboard` main, region iad, persistent `/data` volume. Postgres has its persistent data volume in iad. No service configuration changes or pending patches.
- Railway OAuth returns variable names only. No variable values or SQL endpoint are available through this connection; no secrets were copied or queried.
- Dashboard and Postgres 24-hour samples were available; no immediate resource remediation is indicated. PostgreSQL deploy logs include repeated SSL `unexpected eof while reading` connection messages despite successful deployment and normal API activity. They remain an observation, not a diagnosed outage.
- Repository source confirms JPR `job_summary_v1`, Job Date basis, one row per job, Income − Expense, grand-total validation, duplicate identity Job No. + Job Date + LOB, and explicit rejection of charge-detail input. No formula/source architecture change.
- Repository source confirms import admin has `needs_review`/failed/promoted states, history coverage and data-freshness views. Live held 2024 status and current company/report completeness remain unverified.

### Ingestion cadence clarification
- `gmail/ERP_Mail_Collector.gs` defines `TRIGGER_HOURS: 3` and `installTrigger()` creates an Apps Script time-based trigger every three hours.
- README also describes a 15-minute Apps Script polling hop. This may be a separate integration/polling stage; documentation alone does not prove either live trigger is installed/enabled or that the end-to-end schedule is healthy.
- Actual Apps Script trigger state and live admin import/freshness records still require authenticated Google Apps Script/admin access.

### Outstanding acceptance and evidence
- Secure authenticated browser acceptance is still outstanding; unauthenticated/public checks and server log records do not substitute for user-session acceptance, responsive testing or keyboard/accessibility checks.
- Source workbook → PostgreSQL → API → screen/export financial reconciliation remains outstanding. No live SQL read, import metadata query, workbook download or authenticated finance-role visibility check was possible through the current connectors.
- No source files, imports, financial formulas, database schema, permissions, schedules, services or production configuration changed in this continuation. No deploy was initiated.
- Continue with secure admin/browser and read-only SQL access; reconcile current simple JPR totals and historical coverage, inspect held 2024 imports and actual Apps Script triggers, perform targeted authenticated acceptance, then update this checkpoint on an isolated branch. Preserve all exclusions: no charge-wise reconstruction, no scheduler build, no Customer360 expansion, no PR #28 merge.
