# Beta Cost Optimisation Audit

**Date:** 2026-11-16  
**Repository:** `ashwinn140/NG-Dashboard`  
**Working branch:** `cost-optimisation/beta-safe-pass-1`  
**Production safety:** This audit makes no production configuration, database, scheduling, or deployment changes.

## Executive summary

The first safe optimisation target is the NG-Dashboard application process and its dataset lifecycle, not the frontend visual count and not the database server size.

The production app is online with one replica and one Uvicorn worker. Railway reports a 7-day average application memory of approximately **1.51 GB**, with a sampled maximum of **2.48 GB** and an 8 GB configured memory limit. Postgres averages approximately **0.84 GB**, with a sampled maximum of **2.72 GB** and an 8 GB configured memory limit. AI-Insights averages approximately **0.08 GB**, with a sampled maximum of **0.29 GB**. These are Railway service-level metrics, not a process-level memory attribution.

All three production services were online at audit time, with no reported recent deployment failures, active warnings, critical alerts, or pending Railway changes. This is a point-in-time status check, not a guarantee of continuous health.

## Evidence and findings

### 1. Dataset lifecycle is the leading application memory investigation

In `app/server.py`:

- `Store.full` retains the complete dataset in application memory.
- `dataset_for()` builds the full dataset on a cache miss or data-version mismatch.
- Per-user restricted datasets are gzip-compressed and retained in `Store.cache`.
- The cache is keyed by data version, company scope, line-of-business scope, and finance permission.
- The current cache policy clears the entire cache only when its entry count is greater than 20. It is not bounded by bytes and is not an LRU policy.
- `warm()` eagerly builds and retains the full dataset.
- When the import queue becomes empty, the worker calls `warm()`, including after a batch in which no new data was promoted.

This is directly evidenced code behaviour. The actual share of RAM attributable to each object has not yet been measured. Instrumentation is required before selecting final cache limits or changing warm-up behaviour.

### 2. Dataset construction is a second high-priority investigation

`app/dataset.py` builds the dashboard dataset from shipment reports and profit data, performs joins/matching and prepares dimensions and derived structures. This is a likely transient-memory hotspot because it combines database reads and Python/Pandas structures, but no per-stage allocation profile has yet been captured.

### 3. Import processing can create transient peaks

`app/processor.py` reads Excel data with Pandas and openpyxl, standardises rows, retains original ERP columns and prepares import data. It is important to preserve all source columns and current import validation/idempotency rules. Any memory optimisation must be benchmarked against representative workbooks, not just synthetic small examples.

### 4. Database configuration should be measured before tuning

`app/db.py` creates a SQLAlchemy engine without explicit pool settings. Do not assume this is a problem: inspect connection counts, checkout latency, query duration and Postgres activity before changing pool parameters or indexes.

### 5. Frontend visual inventory is not a memory ranking

The existing visual inventory contains 144 registered entries, but it is a static inventory of visual constructions, not a count of simultaneously rendered widgets or measured browser memory. The inventory documentation explicitly notes that dynamic labels, D3 marks and table-only interfaces need a supplementary runtime audit. Do not remove visuals based on these counts.

### 6. Keep the single-worker design

The Dockerfile and entrypoint intentionally run one Uvicorn worker because the importer runs inside the app process and processes one file at a time. Increasing worker count could multiply the in-memory full dataset and caches. Retain one worker unless the importer and shared state are first redesigned.

## Production baseline snapshot

| Service | 7-day average RAM | 7-day sampled maximum RAM | Configured memory limit | CPU average (Railway metric) |
|---|---:|---:|---:|---:|
| NG-Dashboard | 1.51 GB | 2.48 GB | 8 GB | 0.0064 |
| Postgres | 0.84 GB | 2.72 GB | 8 GB | 0.0104 |
| AI-Insights | 0.08 GB | 0.29 GB | 8 GB | 0.0019 |

Metric values are the Railway API's reported service-level summaries over the last 168 hours. CPU units are shown as returned by Railway and should not be interpreted as percentages. The configured limit is not necessarily the billable allocation or actual cost driver; obtain the Railway usage/billing breakdown before estimating currency savings.

## Recommended implementation sequence

### Phase A — Instrumentation first (safe, branch-only)

1. Add opt-in diagnostics around `DS.build_full()`, `DS.restrict()`, JSON serialisation and gzip compression.
2. Record elapsed time, row counts, output bytes, cache entry count and process RSS where supported.
3. Avoid logging customer data, shipment identifiers, credentials, or full dataset contents.
4. Add a repeatable benchmark using the existing synthetic benchmark fixture and representative anonymised production-shaped files where available.
5. Capture browser heap / long-task / page-load measurements for the most-used dashboard pages before frontend changes.

**Acceptance:** diagnostics are opt-in, have no effect on data outputs, do not expose sensitive data, and can be disabled without a redeploy if implemented through an environment flag.

### Phase B — Bounded cache (after instrumentation)

1. Replace the count-only cache clear with an explicit byte/entry budget and LRU eviction.
2. Make cache budget configurable with conservative defaults.
3. Ensure data-version changes invalidate stale entries.
4. Preserve permission-scope separation and never serve one user's cached dataset to another scope.
5. Add tests for eviction, version invalidation, permission isolation and concurrent access.

**Acceptance:** identical authorised users receive identical data; cross-scope leakage tests pass; cache memory is bounded; cache misses rebuild correctly.

### Phase C — Reconsider eager warm-up

1. Measure the cost and latency benefit of `warm()`.
2. Avoid rebuilding the full dataset after a duplicate, stale, failed or held import that did not change the promoted dataset.
3. Consider lazy first-request build after a promoted import if the warm-up cost materially outweighs first-request latency.
4. Keep a controlled/manual warm path if operationally needed.

**Acceptance:** successful promoted imports are reflected on the next dashboard data request; failed/duplicate/stale imports do not trigger unnecessary full rebuilds; first-request latency is measured and acceptable.

### Phase D — Dataset and importer optimisation

1. Profile `DS.build_full()` by stage and reduce redundant intermediate copies only where tests prove equivalence.
2. Profile `DS.restrict()` and serialisation separately.
3. Benchmark Excel parsing and standardisation on representative files.
4. Preserve original ERP attributes, shipment history, JPR matching, financial formulas and import idempotency.
5. Do not introduce incremental calculations until full-build parity can be demonstrated.

**Acceptance:** shipment counts, historical snapshots, JPR totals, financial aggregates, filters and exports reconcile exactly against the pre-change baseline.

### Phase E — Database and frontend

1. Measure query latency and Postgres activity before changing pool settings or adding indexes.
2. Profile high-traffic pages in a real browser before changing chart lifecycle, lazy rendering or table virtualisation.
3. Reuse existing components and preserve all context-specific management and finance metrics.
4. Keep any static asset/cache changes versioned and reversible.

**Acceptance:** query plans and response times improve without changing result sets; browser page coverage and interaction tests pass.

### Phase F — Cost validation

1. Capture Railway usage and billing by service and resource.
2. Compare equivalent seven-day windows before and after branch changes.
3. Benchmark conservative resource reductions only in a non-production environment or a separately approved test window.
4. Do not reduce production memory/CPU limits based solely on average usage.

**Acceptance:** savings are based on actual billable usage, with no regression in uptime, ingestion, response times or error rates.

## Daily refresh policy (recommendation only; not implemented)

The user has confirmed that daily shipment freshness is acceptable and that dashboard availability must remain 24×7.

A candidate schedule is:
- 09:00 IST: expected ERP report delivery.
- 09:30 IST: primary ingestion and validation.
- 13:30 IST: retry/missing-report check for late or failed files only.
- JPR: ingest when supplied; reconcile independently from shipment freshness.
- Finance cash/GSA/CAS: process on receipt or in the daily cycle, depending on source availability.

Do not change Apps Script triggers, Gmail processing, report schedules or production ingestion until the actual current trigger configuration and source delivery behaviour have been verified. Preserve manual admin refresh/retry.

## Explicitly out of scope without separate approval

- Production deployment or merge to `main`.
- Production Railway resource changes, service sleeping, restarts or scaling.
- Production schedule or Apps Script trigger changes.
- Database schema changes or destructive data operations.
- Removal or alteration of existing dashboard visuals, metrics, formulas, filters, exports or permissions.
- Changes to historical shipment/JPR retention or source ERP attributes.

## Next branch work

The next code change should be opt-in instrumentation and targeted tests, not speculative cache limits or resource reductions. Once instrumentation has established the actual allocation and latency profile, implement bounded caching and warm-up changes in small, independently testable commits.
