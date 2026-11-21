# Controlled Idle Shutdown and Cost Optimisation Plan

**Branch:** `cost-optimisation/idle-shutdown-and-db-audit`  
**Status:** Design and read-only database audit only. No production changes.

## User-approved operating policy

- NG-Dashboard should be available from 09:00 to 20:00 India Standard Time (Asia/Kolkata).
- At 20:00, request shutdown only after all authenticated users have ended their sessions and all protected background work has completed.
- If users or protected work remain active, defer shutdown and re-check. Never terminate an active import, JPR operation, scheduled report, export, or other durable job.
- At 09:00, start/wake NG-Dashboard and verify `/healthz` before considering it available.
- During the workday, an hour with no genuine authenticated user activity is a candidate for sleep, but only when no protected job is active.
- Postgres must remain online.
- Manual administrator override and an auditable status/reason are required.

## Critical platform constraint

Railway Serverless App Sleep is traffic-driven, not an authenticated-session-aware scheduler. Its sleep eligibility is based on outbound traffic inactivity (the platform documentation describes a five-minute threshold); database connections, telemetry, polling, NTP and other outbound traffic may keep the service awake. It does not implement a configurable one-hour logged-in-user idle timeout or a guaranteed 20:00/09:00 IST operating schedule.

Therefore, do not treat `sleepApplication=true` as proof that the requested policy is implemented. Avoid adding an in-process timer: the process cannot reliably wake itself after it has stopped.

## Safe architecture required before production implementation

A separate, always-available control plane must own the schedule. It must not depend on the dashboard process being alive. Before implementation, choose and verify a supported Railway mechanism/API for stopping and starting only the NG-Dashboard service, including authentication, idempotency and failure recovery. Do not assume a Railway cron job can start a stopped service without testing the exact supported API.

The controller must:
1. Run on an independent schedule in `Asia/Kolkata` (20:00 and 09:00), with timezone/DST behaviour explicit.
2. Query durable activity state, not an in-memory counter.
3. Check authenticated activity heartbeat timestamps and active sessions; distinguish real user interaction from browser polling/health checks.
4. Check durable job state in the database: queued/processing imports, report runs, scheduler executions, and any other critical operation identified in code.
5. At 20:00, defer while any user session is active or protected work is running. Recheck on a bounded cadence and expose the defer reason.
6. During the day, only consider sleep after 60 minutes without genuine authenticated activity AND zero protected work.
7. At 09:00, start the service idempotently, wait for deployment/health readiness, verify `/healthz`, then publish availability.
8. Fail safe: on controller/API/database uncertainty, leave the dashboard running. Never stop Postgres.
9. Support a manual keep-awake/disable-shutdown override, with expiry and audit log.
10. Emit lifecycle events and alerts for deferred, stopped, started, failed, and health-check outcomes.

## Application activity instrumentation design

- Use authenticated, CSRF-protected activity heartbeats triggered by actual user interaction (not every API poll).
- Store last activity durably per session/user with bounded update frequency to avoid write amplification.
- Do not log passwords, tokens, raw session cookies, or sensitive payloads.
- Session expiry/logout must be respected. A stale open browser tab must not count as active forever.
- Add a durable protected-job registry or use existing authoritative job tables and statuses. Identify all job types before defining the shutdown predicate.
- Keep readiness endpoints and background worker semantics separate from user activity.
- Validate behaviour with multiple users, expired sessions, browser sleep/resume, network loss, long-running imports, report runs and admin override.

## Dataset cache and rebuild optimisation

Existing verified findings in `app/server.py`:
- Full dataset is retained in `Store.full`.
- Restricted gzip payloads are held in `Store.cache`, keyed by data version, company scope, LOB scope and finance permission.
- Current eviction was count-based (`if len(cache) > 20: cache.clear()`), not byte-bounded LRU. PR implementation now replaces it with `ByteBoundedLRU`: default 64 MiB and 20 entries, configurable with `DATASET_CACHE_MAX_BYTES` and `DATASET_CACHE_MAX_ENTRIES`. It tracks compressed payload bytes, moves cache hits to the MRU end, evicts oldest entries until both ceilings are met, and does not retain an entry larger than the byte budget. The existing permission/version key is unchanged.
- Import worker clears full dataset/cache before every import attempt to avoid retaining the dataset alongside a large workbook.
- Worker previously called `warm()` after every empty queue, including after failed, duplicate, stale and held imports. It now warms only after at least one successful promotion in the batch; multiple queued promotions are coalesced into one rebuild. A no-op/failed import still releases the in-memory full dataset before processing to avoid workbook + dataset peak overlap, but it no longer forces an immediate rebuild when the queue drains.

Next code change should be small and independently tested:
1. Measure encoded cache entry bytes and RSS under representative user scopes.
2. Implemented a conservative configurable byte budget plus maximum entry count and LRU eviction (64 MiB / 20 entries by default).
3. Preserve the exact permission/version cache key and lock discipline.
4. Test eviction, replacement, version invalidation, permission isolation and concurrent access.
5. Preserve the import-time memory release until representative workbook peak-memory tests prove a safer alternative.
6. Cache helper unit tests cover byte eviction, LRU order, entry count, replacement accounting, oversized payloads, clear/reset, pop accounting and value type. A dedicated GitHub Actions workflow runs these tests and compiles the changed Python modules.
7. Warm-up now runs only after a successful promotion; failed/duplicate/stale/held imports do not trigger an unnecessary full rebuild. Successful promotions still rebuild once after the queue drains.

Do not change finance calculations, shipment/JPR matching, source ERP attributes, import idempotency, permissions, filters, exports or visuals.

## Current Railway resource baseline (21 Nov 2026)

Read-only Railway service metrics were sampled over the preceding 168 hours (5-minute sampling; 2,017 samples per service). RAM figures below are average and observed maximum, in GiB:

| Service | Average RAM | Maximum RAM | Current RAM | Notes |
|---|---:|---:|---:|---|
| NG-Dashboard | 1.450 | 2.995 | 1.330 | Largest application RAM consumer |
| Postgres | 0.732 | 1.209 | 0.903 | Must remain online |
| AI-Insights | 0.086 | 0.269 | 0.083 | Already sleeping when status was checked |

These are observed resource metrics, not billed amounts or forecasts. CPU_USAGE is reported in Railway's raw usage units and should not be presented as a percentage. Disk metrics reflect observed disk usage, not necessarily the billable volume allocation. The next cost comparison must use equivalent billing windows and service-level resource charges, not infer savings from RAM averages alone.

## Daily report replacement and historical retention findings

The application has two report storage modes. `REPORT_STORAGE_MODE=versioned` is the default and retains superseded shipment/JPR row versions in the database. `REPORT_STORAGE_MODE=replace` updates current rows in place and deletes rows that disappeared from the incoming report scope. Both modes keep the current dashboard data in the active rows; `dataset.build_full()` reads only `to_import IS NULL`, so superseded version rows are not copied into the in-memory dashboard dataset. In versioned mode they still increase database storage over time, and import-history metadata grows with every received file.

The repository already has a dedicated synthetic replacement regression suite (`scripts/test_daily_replacement.py`) covering repeated daily changes, cross-year preservation, branch/date scope safety, duplicate/stale/row-drop protection, JPR replacement, and static financial-year history. The CI workflow now runs this suite alongside the new cache/retention tests.

Production service variable names include `REPORT_STORAGE_MODE` and `REPORT_STATIC_HISTORY`, but the connected Railway account does not expose their values to this session. I have not guessed the active setting or changed production. To meet the stated policy safely, confirm the deployed value and exercise the exact production-like dataset in a Railway fork/staging environment before switching to `replace` plus static-history protection. The switch is reversible at the setting level but does not recreate old version snapshots already deleted by replacement mode.

Retention previously removed only old shipment rows, not `profit_lines`. The preview/apply implementation now counts and removes both shipment and job-profit rows before the retained window, with separate counts in the audit result. It does not delete import audit metadata or source workbook files.

## Protected job inventory (code review)

The durable job states confirmed in the current code are:
- Imports: `uploads.status` values `queued` and `processing` are active/protected. The importer marks a row `processing` before ingestion and requeues interrupted work after a worker crash.
- Scheduled reports: `report_runs.status` values `queued`, `retry_wait` (when due), and `generating` are active/protected. The worker claims a run by changing it to `generating`; interrupted runs older than 30 minutes are recovered to `retry_wait`.
- Report schedules themselves are definitions, not executing jobs. Paused/disabled schedules must not be counted as active work unless a manual run is already queued.

Coverage gap: the code review has not yet established a durable registry for every potentially long-running synchronous export/admin operation or future worker. The shutdown predicate must not be activated until routes and frontend flows are inventoried and any operation that can outlive a request has an authoritative durable state. A queued report retry with a future `retry_after` should be treated as pending work at shutdown unless the owner explicitly chooses a safe defer policy.

## Postgres audit

Run `ops/postgres_readonly_audit.sql` with a read-only monitoring role. It contains inspection queries only; no DDL, VACUUM, ANALYZE, configuration changes, or data writes.

Review:
- current connection states and wait events;
- database and relation sizes;
- largest tables and indexes;
- sequential/index scan counters and dead tuples;
- available query statistics (only if pg_stat_statements is installed and permitted).

Capture query plans for identified expensive queries separately, with representative bind values and without exposing customer data. Do not add indexes or change pool/memory settings until query latency, connection checkout behaviour and production workload are understood.

## Validation gates

- Unit tests for heartbeat authentication, stale-session handling, activity throttling and job-protection predicate.
- Controller tests for 20:00 deferral, 09:00 wake, DST/timezone, retries, duplicate events, API/database outage and manual override.
- Import/JPR/report/export regression tests.
- Cache tests for permission isolation, byte accounting, LRU ordering and version invalidation.
- Database audit is read-only and does not alter schema/data.
- Staging exercise of stop/start lifecycle and health check before any production activation.
- Compare equivalent billing periods by service/resource; separate RAM, CPU, volume, backup and egress.
- No merge/deployment or production Railway configuration changes until all gates pass and a reviewed implementation PR exists.

## Explicitly not done

- No production shutdown/start schedule created.
- No user-activity or heartbeat code deployed.
- No production service stopped, restarted or redeployed.
- No Postgres configuration/schema/data changed.
- Byte-bounded cache primitive and isolated tests have been added on this branch; integration into `Store.dataset_for()` is implemented. No representative production dataset benchmark has been run, so the 64 MiB default remains a conservative initial ceiling, not a measured optimum.
- Retention preview/apply now includes job-profit rows in addition to shipment rows; import metadata and archived source workbooks remain outside this retention action.
- Warm-up behaviour is now promotion-gated; no-op/failed imports no longer cause an immediate full dataset rebuild.
