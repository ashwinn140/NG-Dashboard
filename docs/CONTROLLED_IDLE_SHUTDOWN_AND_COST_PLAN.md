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
- Current eviction is count-based (`if len(cache) > 20: cache.clear()`), not byte-bounded LRU.
- Import worker clears full dataset/cache before every import attempt to avoid retaining the dataset alongside a large workbook.
- Worker calls `warm()` after the queue empties, even when the batch did not promote new data.

Next code change should be small and independently tested:
1. Measure encoded cache entry bytes and RSS under representative user scopes.
2. Implement a conservative configurable byte budget plus maximum entry count and LRU eviction.
3. Preserve the exact permission/version cache key and lock discipline.
4. Test eviction, replacement, version invalidation, permission isolation and concurrent access.
5. Preserve the import-time memory release until representative workbook peak-memory tests prove a safer alternative.
6. Change warm-up only after proving failed/duplicate/stale/held imports cannot trigger an unnecessary full rebuild and successful promotion still appears on the next request.

Do not change finance calculations, shipment/JPR matching, source ERP attributes, import idempotency, permissions, filters, exports or visuals.

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
- No cache eviction or warm-up code changed in this branch yet.
