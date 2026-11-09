# Consolidated implementation checkpoint

**Started:** 2026-11-09  
**Historical baseline:** `930f1a86e4f2f1b3133ac20feccd76bbd76894f5`  
**Current production commit:** `cfaefc4164bf91223dd85871a8606d9dcced6b73`  
**Current Railway deployment:** `852077f3-5b97-4be7-94fc-a2be30136db5` — SUCCESS  
**Previous working branch:** `audit/consolidated-implementation-2026-11-09`  
**Current continuation branch:** `audit/continuation-readiness-2026-11-09`  
**Production URL:** https://ng-dashboard-production.up.railway.app/

## Baseline verification
- GitHub default branch is `main`; latest commit at inspection is `930f1a86`.
- Railway production NG-Dashboard is online with 1/1 replica, zero active warnings/criticals, zero recent failures and no pending work.
- AI-Insights and Postgres are online; neither is in scope for modification.
- No production data has been changed.
- No authenticated live browser session is available in this working environment. Do not claim browser smoke tests.

## Initial audit findings

### Reconciliation UX
- The last release added explicit reconciliation to shared KPI cards through `metric_trace.js`.
- The shared non-KPI `card()` renderer in `frontend/app_prod.js` currently adds only the inline business explanation; it does not add a general reconciliation action.
- Some custom visual cards have their own explicit `Calculation & records` action, but this does not cover all regular dashboard cards.
- The current metric evidence API has server-side finance checks, permission-scoped datasets, snapshot binding and export handling. Any new visual action must reuse those contracts and must not invent evidence for a visual with no matching metric definition.
- Existing ranking click behavior applies filters. Do not attach drawer opening to the rank row itself.

### Origin/destination filtering
- `mask()` already implements OR within each selected dimension and AND across dimensions by intersecting the per-dimension masks.
- `laneAgg()` explicitly calls `mask({skip: ['origin', 'destination']})`. This removes both selected port dimensions from the Top Lanes aggregation and is the identified reason unrelated lanes can remain visible after selecting multiple origins and a destination.
- Planned correction: use the normal selected-filter mask for the lanes aggregation and add a behavioral regression test with multiple origins and one destination. Validate both the overview ranking and Lanes page because they share `laneAgg()`.

### Customer job-owner history
- Shipment registers have a canonical `Job Owner` source mapping.
- The configured standard shipment columns do not include a canonical `Job No.`; extra ERP columns are retained, but the authoritative job-number field and its availability in all eight registers still need source confirmation.
- Do not substitute salesperson, agent owner or another role. Last-five means five most recent distinct jobs, retaining repeated owner names.

### Cross-LOB inactivity
- Must be computed only from the user's authorized company/LOB data. Company-wide inactivity cannot be asserted for a user without visibility across the relevant LOBs.
- Adaptive inactivity threshold implementation must be inspected before any change.

### Finance/source reconciliation
- Existing audit documentation describes a previous sample reconciliation: four JPR files and three of eight shipment registers, with 57 Excel-to-dataset checks passing and 92/95 displayed-vs-Excel checks passing (three expectation failures in the audit script were manually reviewed).
- That prior evidence is a partial sample, not a complete audit of the current PostgreSQL production snapshot or all requested metrics.
- Original source workbooks are not currently present in the searchable Library results. Live Excel-to-PostgreSQL reconciliation is therefore blocked until the actual accepted source files are accessible.
- The prior audit reported possible volume-unit anomalies (CCM values and implausible CBM magnitudes) but explicitly left conversion/capping decisions unresolved. Do not alter volume values without source validation and an approved rule.

### Visual inventory
- `scripts/audit_visual_contract.py` is static-only.
- `frontend/tests/runtime_inventory.js` renders registered pages against synthetic fixtures and produces a visual inventory. It must be run with the fixture builder and interpreted as synthetic coverage, not production browser evidence.
- Several visual explanations are intentionally marked unverified. Do not replace those with title-derived formula guesses.

## Scope and release guardrails
- Work only in this repository and the NG-Dashboard Railway service.
- No changes to production business records, database schema, JPR promotion, source mapping or permissions without a validated need and tests.
- Do not deploy a release with unexplained financial discrepancies or failed critical/security tests.
- Each stage must be tested and recorded here. Deploy only a safe, independently validated subset.

## Workstream status
| Workstream | Status | Notes |
|---|---|---|
| Baseline inspection | Completed | GitHub and Railway checked |
| Reconciliation entry-point coverage | Implemented and tested awaiting broader coverage | PR #19 adds metric-backed explicit controls to supported visuals; synthetic inventory: 236/408 unique visuals have actions, 172 do not; no action is attached where calculation is unverified |
| Origin/destination multi-select | Completed and production-verified | PR #19 changed `laneAgg()` to honor the normal active filter mask; regression coverage passed in CI; deployed in `cfaefc4` |
| Latest/last-five job owners | Blocked pending source field confirmation | Job Owner exists; authoritative Job No. not yet confirmed |
| Cross-LOB inactivity | Pending | Current Customer 360 activity is filtered to submitted relationship indices; Opportunity Finder is admin-only and reports potential whitespace only with all four LOBs available; not equivalent to lost-customer cross-LOB classification |
| Finance independent audit | Blocked pending accepted source workbooks and current DB snapshot | Historical sample audit is not full current certification |
| Visual explanations and source traceability | Pending | Synthetic runtime inventory completed: 408 unique page/title visuals; 281 verified, 80 unverified, 47 without explanation; 0 runtime errors |
| Variance/date comparisons | Pending | Full audit not yet run |
| Ingestion/data quality | Pending | Verify scheduler, report completeness and current import health |
| UX/responsive/accessibility | Pending | Runtime/browser audit required |
| Production deployment verification | Completed and production-verified | Railway confirms commit `cfaefc4`, deployment SUCCESS, 1/1 replica, no pending work or critical issues; authenticated browser smoke tests remain blocked |

## Tests and changes
- PR #19 CI run: `42631763353` — SUCCESS.
- Railway production deployment: `852077f3-5b97-4be7-94fc-a2be30136db5` — SUCCESS.
- No production business records or schema were modified.
- No changes to AI-Insights or unrelated Railway services.
- Current continuation branch starts from deployed `main` commit `cfaefc4164bf91223dd85871a8606d9dcced6b73`.

## Next exact actions
1. Implement and behavior-test the shared Top Lanes filter correction.
2. Add explicit, metric-backed reconciliation controls to the supported visuals, with ranking selection context; leave unsupported visuals without misleading evidence and record the reason.
3. Run the synthetic runtime visual inventory and produce a coverage matrix.
4. Inspect customer/job-owner and cross-LOB source data contracts.
5. Complete finance, date/variance and ingestion audits only to the extent supported by accepted source files and current snapshot evidence.
6. Run all backend/frontend/security/export tests, review the diff, and deploy only independently safe work.


## Post-release continuation — 9 November 2026

### Release evidence
- PR #19 merged successfully as `cfaefc4164bf91223dd85871a8606d9dcced6b73`.
- Railway deployment `852077f3-5b97-4be7-94fc-a2be30136db5` is SUCCESS for the exact merged commit, branch `main`, region `iad`.
- Railway production environment reports NG-Dashboard Online, 1/1 replica, zero warnings/criticals, zero recent failures and no pending work.
- Container logs confirm PostgreSQL connection, application startup complete and Uvicorn listening on port 8080.
- GitHub commit status for the merged SHA reports the Railway deployment success.
- Public website opening through the available web reader was inaccessible; no authenticated browser session is available. Do not claim browser-level functional smoke tests.

### PR #19 implementation and CI
- `frontend/app_prod.js`: lane aggregation now uses the normal active filter mask rather than skipping origin and destination; supported visuals receive explicit metric-backed Calculation & records actions without auto-opening.
- `app/web/metric_trace.js`, `frontend/tests/visual_trace_test.js`, `frontend/tests/runtime_inventory.js`, `tests/test_visual_explanation_contract.py`, `.github/workflows/metric-traceability.yml`, `audit/implementation_checkpoint.md` updated in PR #19.
- GitHub Actions run `42631763353`, job `metric-unit`, completed SUCCESS. Logged test evidence includes 139/139 backend/finance fixture checks, Customer360 test, metric trace selection, explicit-only reconciliation, custom visual trace and synthetic runtime inventory. Production build reproduction passed.
- Synthetic inventory: 414 role/page visual instances; 408 unique role/page/title visuals; 159 KPIs; 249 cards; 71 table-bearing visuals; 31 chart-bearing visuals; 236 with reconciliation actions; 172 without; 281 calculation-verified; 80 explanation present but calculation unverified; 47 without explanation; zero runtime errors; all registered pages visited. No reconciliation action was attached to an unverified calculation.
- These are synthetic CI checks, not live production data or authenticated browser verification.

### Additional source and product findings
- `app/dataset.py` maps authoritative `Job Owner` from source JPR extra fields first, falling back to the matched shipment register only when the JPR field is absent. The JPR dataset has `Job No.`, `Job Date` and LOB; however current accepted production source-header coverage for `Job Owner` across both source types has not yet been confirmed.
- Shipment-register processor preserves extra source columns, so a source `Job No.` may exist without being a canonical standard column. Do not assume it exists in every LOB.
- `/api/admin/phase2/source-readiness` currently reports only customer code, salesperson, shipment number and shipment date across the eight shipment-register company/LOB snapshots. It does not yet report Job Owner or job number coverage.
- Customer 360 `/api/metrics/activity` groups activity from the supplied relationship-filtered operational indices. It is an adaptive inactivity signal, not a complete cross-LOB lost-customer classification.
- Opportunity Finder is admin-only and requires all four LOB sources and full LOB authorization; it reports potential whitespace, not confirmed demand or company-wide lost customers.
- Library search found the audit patch and knowledge-transfer documents but did not surface the actual accepted ERP `.xlsx` source workbooks. Prior 57/57 and 92/95 reconciliation evidence relates to a limited historical sample, not current production snapshot certification.
- Current synthetic visual inventory and previous source audit are not substitutes for live production data reconciliation.

### Current workstream status
| Workstream | Status | Evidence / limitation |
|---|---|---|
| Production release for PR #19 | Completed and production-verified | Exact Railway commit/deployment and health confirmed |
| Lane multi-select correction | Completed and production-verified | Regression CI passed; deployed |
| Explicit reconciliation UX | Implemented and tested awaiting broader coverage | Supported visual controls exist; 172/408 unique visuals lack an action, and some are intentionally unsupported |
| Visual explanation coverage | Pending | 80 unverified calculations and 47 missing explanation blocks |
| Job owner / last-five distinct jobs | Blocked pending source field confirmation | Job No. exists in JPR model; source-header coverage across current imports is not verified |
| Cross-LOB inactivity / lost customer | Pending | Existing activity endpoint is selected-scope only; opportunity finder is not a lost-customer classifier |
| Finance source-to-production reconciliation | Blocked | Actual accepted source workbooks/current production snapshot not available through this session |
| Invoice/volume/ageing data quality | Pending | Code contains placeholder handling; independent source-level validation remains incomplete |
| Variance/date audit | Pending | Needs full formula/date-basis audit and actual source evidence |
| Report Scheduler | Pending | Not implemented; must not activate scheduled sends without authorization tests |
| HTML Help & User Guide | Pending | Not implemented |
| Authenticated browser/responsive QA | Blocked | No authenticated browser session/tool available |

