# Consolidated implementation checkpoint

**Started:** 2026-11-09  
**Production baseline:** `930f1a86e4f2f1b3133ac20feccd76bbd76894f5`  
**Railway deployment:** `8e945181-daab-43ef-ab87-6f66e3c7069a` — SUCCESS  
**Working branch:** `audit/consolidated-implementation-2026-11-09`  
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
| Reconciliation entry-point coverage | Pending | Shared card renderer lacks a general action; audit visual-by-visual |
| Origin/destination multi-select | Pending | Root cause isolated in lane aggregation |
| Latest/last-five job owners | Blocked pending source field confirmation | Job Owner exists; authoritative Job No. not yet confirmed |
| Cross-LOB inactivity | Pending | Need inspect current implementation and permission-scoped source |
| Finance independent audit | Blocked pending accepted source workbooks and current DB snapshot | Historical sample audit is not full current certification |
| Visual explanations and source traceability | Pending | Runtime inventory and coverage matrix required |
| Variance/date comparisons | Pending | Full audit not yet run |
| Ingestion/data quality | Pending | Verify scheduler, report completeness and current import health |
| UX/responsive/accessibility | Pending | Runtime/browser audit required |
| Production smoke tests | Blocked | No authenticated browser session available |

## Tests and changes
- Tests executed in this session: none yet.
- Files changed in this branch: this checkpoint only.
- Commits in this branch: checkpoint commit to be recorded after creation.
- Production deployment status: unchanged; no new deployment.

## Next exact actions
1. Implement and behavior-test the shared Top Lanes filter correction.
2. Add explicit, metric-backed reconciliation controls to the supported visuals, with ranking selection context; leave unsupported visuals without misleading evidence and record the reason.
3. Run the synthetic runtime visual inventory and produce a coverage matrix.
4. Inspect customer/job-owner and cross-LOB source data contracts.
5. Complete finance, date/variance and ingestion audits only to the extent supported by accepted source files and current snapshot evidence.
6. Run all backend/frontend/security/export tests, review the diff, and deploy only independently safe work.
