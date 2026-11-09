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



## Continued work — 9 November 2026, evening

### Dashboard visible-JavaScript rendering incident — fixed and deployed
- User screenshot showed the dashboard filter panel followed by a large block of JavaScript rendered as page text.
- Root cause: generated `app/web/dashboard.html` contained seven `<!doctype html>` document starts inside script content and unbalanced script tags. The corruption pattern is consistent with JavaScript replacement-string expansion (`$&`, `$'`, etc.) while inserting minified JS into HTML.
- Rebuilt from canonical `frontend/production_shell.html`, `frontend/vendor/fflate.js`, `frontend/vendor/d3.min.js` and `frontend/app_prod.js` using callback/literal replacement. Correct artifact: 706,922 bytes, exactly one doctype, 8 opening and 8 closing script tags.
- `frontend/build_prod.py` now fails closed unless the generated document has exactly one doctype, balanced script tags and no remaining production placeholders.
- PR #23 merged as `a3a5ff5be7c8da2837bd807649c04a0d201d2fdc`; CI run `42636124126` SUCCESS; Railway deployment `45990086-c012-4b11-8c6b-9fabb9bf0e9a` SUCCESS.

### Finance quality evidence extension — merged and deployed
- PR #24 merged as `1be22360ed858b44ece6884796828ffbc1fb234f`; CI run `42636584444` SUCCESS; Railway deployment `14e9b3b0-69b3-4304-85bf-c87f0e199f8b` SUCCESS.
- Added `profit.expected_cost_only` as a separately traceable estimate for positive-income jobs with exactly zero recorded expense, using same-LOB booked expense/income benchmark, overall authorized fallback, then zero. Explicitly disclosed as estimated exposure, not booked cost/liability.
- Added evidence actions to expected-cost, cost-not-booked and loss-making visuals. Visible loss list and evidence metric now exclude billing-pending jobs consistently.
- No booked GP formula, source data, DB schema, or permissions changed.

### Current production health after both releases
- Railway NG-Dashboard Online, 1/1 replica, zero warnings/criticals, zero recent failures, no pending work.
- Latest production commit: `1be22360ed858b44ece6884796828ffbc1fb234f`.
- HTTP request telemetry at check time: 392 observed requests, 0 HTTP 5xx (telemetry window; not a browser test).
- PostgreSQL remained attached; no migration or production data write was performed.
- Public web-reader access was unavailable and no authenticated browser session was available. Do not claim pixel/browser-level confirmation. Ask the user to hard-refresh the authenticated page (Ctrl+Shift+R) to bypass cached HTML/JS.

### Remaining work, ordered
1. Verify screenshot fix in the user's authenticated browser after hard refresh; inspect console/network if any further error remains.
2. Continue metric explanation coverage: 80 previously unverified calculations and 47 visuals missing explanation blocks from the synthetic inventory; verify formulas before attaching reconciliation actions.
3. Obtain current accepted ERP source workbooks / current production import metadata to certify Job Owner, Job No., last-five distinct jobs, finance totals and invoice/ageing quality. Do not infer coverage from synthetic fixtures or old samples.
4. Implement cross-LOB inactivity/lost-customer classification only after permission-scoped complete relationship history and source keys are verified.
5. Continue variance/date-basis audit, Report Scheduler authorization and Help/User Guide only after source and security acceptance criteria are defined.
6. Authenticated browser/responsive QA remains outstanding.


## Continued work — Job Owner readiness — 9 November 2026

### Source-to-visual and source-workbook clarification
- The prior checkpoint statement that accepted ERP workbooks were unavailable is only partially current. The detailed audit in docs/DASHBOARD_AUDIT_2026-11-07.md records two original workbooks recovered and independently reconciled row-by-row: NG current FY 2026 (134,655 charge lines) and NCS FY2025 (53,150 charge lines), 187,805 total, zero unmatched rows, SHA-256 matching promoted import metadata.
- The remaining NG FY2025 and NCS current-FY original charge-wise workbooks are not row-level certified. Their API/import metadata reconciliation is not equivalent to original workbook reconciliation.
- Historical 2025 Job Profit Analysis Reports are Basis: Job Date, one row per job, and contain no Charge or Billing Date columns. They cannot fill January–March 2025 billing-date gaps. Do not merge those amounts into billing-date data.
- SharePoint direct access returned HTTP 403 in the prior audit; no access control was bypassed.

### PR #25 — Job Owner readiness diagnostics
- PR #25 merged to main as c84c2b8c344e8f5c75cc52c1dabd5e5142c074fe.
- GitHub Actions: Phase 2 isolated tests run 42639016021 SUCCESS; full metric-traceability run 42639016055 SUCCESS. Production build reproduction, full backend/permission/Excel tests, frontend metric contracts and synthetic runtime inventory all passed.
- Railway deployment c0c98f5c-4edd-4aa5-8fd7-ee12346fb80d SUCCESS for the exact merged SHA, region iad. NG-Dashboard Online, 1/1 replica, no warnings/criticals or recent failures at deployment verification.
- Admin-only /api/admin/phase2/source-readiness now returns aggregate job_history_quality by company/LOB: distinct job counts, uniquely matched register jobs, ambiguous/unmatched matches, owner populated/missing counts, JPR/register owner source counts, duplicate identities and coverage percentages.
- Admin page now displays a Job Owner data completeness table. It does not expose job numbers, customer names, owner names or financial amounts.
- Matching mirrors the existing dashboard logic: company + job number + exact date first; number-only fallback second; expected LOB register filter; only one candidate accepted. Ambiguous and unmatched jobs never get a guessed owner.
- JPR Job Owner source values retain precedence, including explicit blanks. Optional header matching now handles case/spacing variants for new imports and existing stored extras.
- No schema migration, import promotion, business-record change, financial formula change or source data write was performed.

### Current workstream status
| Workstream | Status | Evidence / limitation |
|---|---|---|
| Screenshot rendering defect | Fixed and deployed | PR #23, CI success, canonical HTML rebuilt with one doctype and balanced scripts; authenticated browser confirmation still needed |
| Finance expected-cost evidence | Implemented and deployed | PR #24 and full CI success; estimates are explicitly not booked expense |
| Job Owner header readiness | Implemented and deployed | Admin source-readiness header table |
| Job Owner row-level completeness | Implemented and deployed | Aggregate-only, admin-only current-snapshot diagnostics; authenticated admin page must be inspected to obtain actual live coverage values |
| Last five distinct jobs in Operations → Customers | Not yet implemented | Wait for live row-level completeness and source-key review; must use distinct jobs and repeat owners, with deterministic date/job tie-break |
| Cross-LOB inactivity/lost customer | Pending | Existing inactivity is selected-scope only; complete company/LOB authorization and customer identity history must be proven |
| Original workbook reconciliation | Partially complete | 187,805 rows independently reconciled across two originals; two other accepted originals still not independently row-level reconciled |
| Variance/date and ingestion audits | Pending | Continue against source-backed accepted reports and live snapshot metadata |
| Authenticated browser/responsive QA | Pending | No authenticated browser session available in this continuation |

### Next exact actions
1. Inspect the new Job Owner data completeness table in the authenticated admin portal. Use actual current-snapshot counts to decide if owner history is sufficiently complete by company/LOB.
2. Only then implement Operations → Customers latest owner + last five distinct jobs. Retain repeated owners, include job number/date/owner/LOB, stable tie-break, and authorized Excel export. Do not substitute salesperson or relationship owner.
3. Add cross-LOB customer inactivity only after complete authorized coverage and canonical customer identity are verified. Distinguish selected-LOB inactivity from customer-wide inactivity.
4. Continue independent finance and variance/date audits with the two remaining original source workbooks and current production snapshot.
5. Verify the screenshot fix in an authenticated browser after hard refresh; do not equate CI or HTTP telemetry with browser visual confirmation.


## Continued work — Last five distinct customer jobs — 9 November 2026

### Production readiness decision from live Job Owner completeness screenshot
- Screenshot supplied by Ashwin shows owner coverage: NCS Air Export 99.88% (6 missing / 4,998), NCS Air Import 100% (512), NCS Sea Export 99.72% (8 / 2,871), NCS Sea Import 100% (282); NG Air Export 99.62% (87 / 22,740), NG Air Import 99.96% (4 / 9,565), NG Sea Export 99.73% (22 / 8,065), NG Sea Import 99.93% (2 / 2,748). GEN and FFWD ROAD DOM are also 100% in the screenshot.
- No ambiguous or unmatched jobs are shown. Register matched is zero in each displayed company/LOB row, so the screenshot does not evidence register fallback; populated owners are from JPR.
- Decision: proceed with last-five distinct jobs; never infer the missing 129 Air/Sea owners. Render missing/conflicting source owners as "Owner unavailable".

### PR #26 — shipped
- PR #26 merged to main as 0c2d8a91b6d2f347f0cd7c18dd89d538cac9282f.
- GitHub Actions Phase 2 isolated tests and full metric traceability checks both SUCCESS. Full backend/permissions/Excel suite (143 tests), production build reproduction, frontend audit (including Operations Customers recent-jobs modal), and synthetic runtime visual inventory all passed.
- Railway deployment c4af607f-84e1-4784-b6eb-822b80796e58 SUCCESS for exact merged SHA, region iad. NG-Dashboard Online, 1/1 replica, no warnings/criticals or recent failures. Post-deploy telemetry at verification: 427 HTTP requests, 0 4xx, 0 5xx, 0% error rate.
- Operations → Customers now includes a "View jobs" action per customer. Modal shows the five most recent distinct jobs with company, job number, Job Date, LOB and JPR Job Owner; latest owner/date are identified above the table.
- Customer Excel export now has a separate "Last 5 Jobs" worksheet, batched in groups of 100 customers.
- API is authenticated, CSRF-protected and revalidates company/LOB scope. Operations-only users can use it without finance permission. It returns no financial values.
- Distinct identity is company + LOB + Job No. + Job Date. Sorting is newest Job Date first, with deterministic job/LOB/company tie-breaks. Repeated owners are preserved. Missing or conflicting JPR owners show unavailable. No salesperson or shipment-register owner substitution.
- History uses current loaded JPR snapshot, Basis: Job Date; it is independent of the selected dashboard date window but respects the permitted company/LOB scope and current operational filters. It is not an all-time guarantee beyond loaded JPR history.
- No schema changes, data writes, import promotions, or financial calculations were made.

### Remaining work
1. Authenticated browser verification on the live dashboard: open Operations → Customers, use View jobs, inspect the last five jobs for representative NG/NCS customers, and verify the Last 5 Jobs Excel worksheet. Automated frontend tests and deployment are green, but no authenticated live browser session was available during this continuation.
2. Continue cross-LOB inactivity / lost-customer analysis only after validating canonical customer identity and authorized history coverage. Keep selected-LOB inactivity distinct from customer-wide inactivity.
3. Continue the outstanding two original ERP workbook row-level reconciliations, variance/date audit and finance ingestion audit.


## Continuation checkpoint — 9 November 2026, 20:55 IST

### Verified current production baseline
- Repository: `ashwinn140/NG-Dashboard`, production branch `main`.
- Production commit: `49a470e5462bdfcced10adf00974e81d91fd15c6`.
- Railway deployment: `1a3a3433-21b8-45c5-8126-9d57fe73b1e8`, SUCCESS; production service online, 1/1 replica, zero active warnings/criticals, zero recent failures, no pending work.
- Production domain: `ng-dashboard-production.up.railway.app`; Postgres and the NG-Dashboard persistent volume remain attached.
- GitHub Actions/Railway deployment status for the production commit reports success. Latest runtime logs show application startup and successful HTTP 200 responses for the dashboard, /api/me, preferences, metric definitions and dataset.
- No authenticated browser session is available in this continuation. Do not claim browser interaction or screenshot verification.
- No production data, database schema or Railway configuration was changed.

### PR #27 — defensive correction in review
- Branch: `fix/customer-history-owner-consistency-2026-11-09`.
- PR: https://github.com/ashwinn140/NG-Dashboard/pull/27
- Finding: for duplicate JPR rows sharing company + LOB + Job No. + Job Date, one blank Job Owner plus one populated Job Owner could be treated as available or conflicting depending on source-row order.
- Change: normalize missing owner to an explicit `None` member in the owner set, so blank + populated is always conflicting and displays `Owner unavailable`; add regression coverage for both row orders.
- Scope limited to `app/customer_history.py` and `tests/test_customer_history.py`. No schema, financial, permission, source-data or production changes.
- PR opened; CI status had not yet appeared at checkpoint time. Do not merge or deploy until CI passes and the diff is reviewed.

### Additional audit notes / next work
1. The customer-history endpoint currently checks customer visibility against current shipment rows, then returns JPR history. It is CSRF-protected and checks company/LOB authorization; continue review of customer identity/name-collision behavior before building company-wide lost-customer logic.
2. Customer identity in the dataset is currently normalized customer name, not a proven stable ERP customer code. Do not infer identity merges or company-wide inactivity from similar names.
3. Cross-LOB inactivity/lost-customer intelligence remains pending. Existing Customer 360 activity is selected-scope only; any company-wide claim must require complete coverage of every relevant authorized LOB.
4. Original charge-wise source reconciliation remains partial: NG current FY2026 and NCS FY2025 were independently row-reconciled (187,805 lines, zero unmatched); NG FY2025 and NCS current FY2026 originals remain uncertified at row level. Searchable Library did not surface those remaining source workbooks.
5. Continue variance/date-basis, ingestion completeness, metric-definition coverage, and Report Scheduler/HTML Help work only with validated source and security evidence. Never activate real recurring report sends until authorization, recipient and delivery tests pass.
6. Re-check the last-five-jobs modal and Excel worksheet in an authenticated browser when a user session becomes available.
