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

## Continuation checkpoint — 9 November 2026, 21:xx IST

### Current repository and production state
- Repository: `ashwinn140/NG-Dashboard`; default branch `main`.
- Latest main commit at checkpoint: `2cdebb53b0771e5b9d1525dc85c4b2a7ec68c3a4`.
- Production Railway is still on commit `b8dc0c442cbb3230803262e215ae1f11efaa32c8`, deployment `c1c36f08-e94c-4723-8d70-aaf36dce92da`, SUCCESS.
- Production environment has no staged changes or pending deployment work. PostgreSQL and the existing persistent volumes remain attached.
- PR #29 was merged as `2cdebb53b0771e5b9d1525dc85c4b2a7ec68c3a4`; GitHub Actions run `42647512306` completed SUCCESS. Steps passed: dependency setup, production build reproduction, backend/permission/Excel suite, synthetic fixture generation, frontend/metric contract audit, synthetic runtime visual inventory.
- PR #29 adds Customer 360 cross-LOB activity breakdowns, adaptive LOB-level activity states, selected-LOB versus other-visible-LOB context and synthetic regression tests. It uses only the already authorized loaded dataset, exact source-name matching and explicit scope caveats. No schema, permission, finance or production data changes.
- The merge has NOT yet been deployed to Railway. Do not call PR #29 production-verified.
- Commit `05abb1506da077c68f3a3c8f39582c41f5f77b8a` records the agreed simple-JPR source scope in this checkpoint's audit documentation.

### Binding source-scope decision from Ashwin — 9 November 2026
- Continue using the existing simple **Job Profit Analysis Report (JPR)** in its current format, with Job Date as the finance reporting basis.
- Charge-wise source workbooks are NOT required for this project. Do not continue searching Gmail, SharePoint or Library for missing charge-wise originals, and do not block completion on their availability.
- Do not require Billing Date or charge-level reconciliation for the agreed JPR scope. Do not mislabel Job Date as Billing Date or infer a billing date from it.
- Finance/variance validation must use the currently accepted JPR dataset, existing import metadata, calculations, permissions, API, UI and exports. Preserve clear limitations around missing periods and unmatched finance records.
- This decision does not authorize production source-data changes, import promotions or financial formula changes.

### Workstreams and next actions
| Workstream | Status | Next action / evidence |
|---|---|---|
| Baseline and existing production release | Completed and production-verified | Continue to preserve current live commit until final safe release |
| Origin/destination multi-select | Completed and production-verified | PR #19 fix deployed; preserve OR-within-field / AND-across-fields behavior |
| Operations last-five jobs / Job Owner | Implemented and production-verified | PR #26 deployed; authenticated live browser confirmation still outstanding |
| Cross-LOB Customer 360 activity | Implemented and tested awaiting deployment | PR #29 merged; CI run 42647512306 SUCCESS; verify Railway deployment later |
| Finance / variance audit on simple JPR | Pending | Audit formula parity, Job Date windows, current/prior/YoY/partial periods, zero/negative baselines, role access, drilldown and Excel export; do not seek charge-wise files |
| Visual explanations / Calculation & records coverage | Pending | Synthetic inventory previously found 80 unverified calculations and 47 visuals without explanations; complete verified visual dictionary and explicit-action coverage without attaching unverified formulas |
| Report Scheduler | Pending | Implement only after durable queue, permission-at-execution, approved recipients, freshness, idempotency, delivery evidence and failure/retry tests |
| Integrated HTML Help & User Guide | Pending | Build in-app searchable guide and visual dictionary, synchronized with code/tests; no separate PDF/Word manual |
| Authenticated browser, responsive and accessibility QA | Blocked pending authenticated browser session | Test 1920/1366/768/390 px, Operations View jobs, Customer 360, filters, explicit reconciliation, exports and keyboard/focus behavior |
| Final release | Pending | Only after critical finance/security tests and browser/data QA; deploy a verified subset and confirm exact Railway commit/health |

### Remaining work count
- The previous outstanding charge-wise workbook reconciliation is removed from scope by the owner's explicit decision.
- Five principal workstreams remain before release readiness: (1) simple-JPR finance/variance audit, (2) visual explanation/reconciliation coverage, (3) secure Report Scheduler, (4) integrated HTML Help/User Guide, and (5) authenticated browser/responsive/security QA.
- Final merge/deployment verification is a release gate after those workstreams, not a substitute for them.

## Production continuation — 9 November 2026, after PR #30

### PR #30 — customer GP concentration guard
- PR #30 merged as `3067c6d0855ded2d72b66b657f71890a73a22028`.
- GitHub Actions run `42648430744` completed SUCCESS for head `aa03454a2f2a67708362cf35a10bf3029e85a78c`. Production build, backend/permission/Excel suite, frontend metric contract checks and synthetic visual inventory all passed.
- Changed `app/metric_execution.py`, `app/metric_definitions.py`, `frontend/app_prod.js`, `tests/test_metric_execution.py` and `frontend/tests/data_audit.js`.
- Biggest Customer Share retains largest customer GP / total net GP when total net GP is positive. It is unavailable when total net GP is zero or negative. Frontend KPI trace and backend evidence use the same rule. Added tests for positive, zero and negative net GP.
- Added variance tests confirming negative-baseline percentage changes use absolute baseline magnitude and zero baselines are unavailable.

### Current production deployment
- Railway NG-Dashboard deployment `0ad58d2a-2409-4c2c-8192-0e0f90a0c6ce` — SUCCESS, branch `main`, exact commit `3067c6d0855ded2d72b66b657f71890a73a22028`, region `iad`.
- This deployment includes PR #29 cross-LOB Customer 360 and PR #30 finance correction. The prior intermediate deployment for PR #29 was superseded; current deployment is the authoritative live release.
- Runtime logs show volume mount, application startup complete, PostgreSQL database connection and Uvicorn listening on port 8080. No HTTP telemetry rows were returned for this immediate post-deploy log query; do not claim authenticated browser smoke testing.
- Production environment reports no staged changes or pending work. Existing PostgreSQL and persistent application volume remain attached. No schema migration or production business-data modification was made.

### Updated synthetic visual inventory
- Artifact from successful PR #29 CI run `42647512306` was downloaded and inspected.
- 414 role/page visual instances; 408 unique role/page/title visuals; 159 KPIs; 249 cards; 71 table-bearing visuals; 31 chart-bearing visuals; all registered pages visited; zero synthetic runtime errors.
- 289/408 have verified calculation explanations; 72 have an explanation but the calculation remains unverified; 47 have no explanation. This supersedes earlier inventory counts of 281/80/47.
- These figures are synthetic inventory, not authenticated browser or live production evidence. Continue to classify wrapper/untitled cards and non-record visuals appropriately rather than inventing drill-down evidence.

### Finance and operational audit findings on agreed simple-JPR scope
- JPR ingestion is explicitly `job_summary_v1`, Basis: Job Date, one row per job. Import validation checks the report grand totals, validates Profit = Income - Expense within the configured tolerance, rejects missing Job No./Location/LOB, rejects duplicate Job No. + Job Date + LOB rows and preserves the prior accepted data on invalid replacements.
- The finance audit should use this accepted simple JPR and its current Job Date basis. No charge-wise source workbook is needed or to be pursued.
- Invoice placeholder handling is covered by `tests/test_invoice_reference.py`: blank, zero, N/A, NIL and Pending do not count as invoice references; text references without parseable dates count as references but have no invoice date.
- Ageing tests include a later-finance-date regression and verify operational ageing remains based on latest shipment-register date, not a later finance date.
- **Volume-unit issue remains unresolved and must not be certified:** `app/dataset.py::volume_cbm` currently converts Volume when *any* repeated Unit column (Unit, Unit.1 … Unit.7) equals CCM. This can incorrectly convert a row when CCM belongs to weight/package or another measure rather than Volume. The existing `tests/test_volume_units.py` exercises several unit positions but does not establish which unit header is actually paired with Volume in the accepted shipment-register source. Correct design is to derive the Volume unit from the corresponding Volume-adjacent source column/header position, not OR together every repeated Unit column. Do not guess the index or rewrite production data without a source-header mapping verified from an accepted shipment-register source or its exact preserved header order.
- Customer concentration denominator defect is fixed and production-deployed. Remaining finance audit still includes the complete visual/date/variance/filter/export parity review.

### Remaining principal workstreams
1. Complete simple-JPR finance and variance audit, including metric parity, all variance/date edge cases, finance permissions, drilldown and Excel exports. No charge-wise workbook dependency.
2. Complete visual explanation and Calculation & records coverage. Start with 72 unverified calculation explanations and 47 missing explanation blocks in the latest synthetic inventory; do not add evidence actions where a correct metric/source mapping cannot be proved.
3. Implement a secure generic Report Scheduler with durable server-side queue, execution-time permissions, approved recipients, freshness policy, idempotency, retry/restart/concurrency handling and accurate provider delivery states. Existing `app/mailer.py` supports SMTP/Resend but no scheduler persistence/worker/UI was found. Do not activate real scheduled emails before full security and delivery tests.
4. Build the integrated searchable HTML Help & User Guide and Visual Dictionary inside the app, synchronized with shared metric metadata and CI. No separate PDF/Word manual.
5. Authenticated browser, responsive, keyboard/accessibility and production smoke QA remains blocked until an authenticated browser session is available. Synthetic jsdom tests are not a substitute.

### Release posture
- PR #29 and PR #30 are merged, CI-passing and included in the current production commit.
- This is an incremental production release, not final project completion. Keep working on the five remaining principal workstreams. Do not declare final readiness until critical finance/security tests, visual coverage, scheduler safety, guide synchronization and authenticated browser QA are complete or explicitly recorded as blocked with evidence.

## Latest continuation — PR #31 and PR #32 deployed

- PR #31 merged at `fff3662b688bb1bd4332f45c477bb108faf305af`; CI run `42649189412` SUCCESS.
- PR #32 merged at `e1df8cc32db8e8af8bef5820a45571cc44ceb53e`; CI run `42649548516` SUCCESS, including the new `frontend/tests/help_guide_test.js`.
- Railway production deployment `7c5276b5-b698-46ca-b1a4-4a437ad5b180` SUCCESS, exact commit `e1df8cc32db8e8af8bef5820a45571cc44ceb53e`, 9 Nov 2026 15:56 UTC. Startup logs show PostgreSQL, application startup complete and Uvicorn listening. HTTP telemetry query returned no rows; authenticated browser smoke test remains outstanding.
- PR #31 volume fix is in production. New imports persist the Volume-adjacent unit in `extra._volume_unit_source`; existing legacy rows use only the audited `Unit.5` column. No schema migration or data rewrite.
- PR #32 in-app Help and searchable Metric Dictionary is in production at `/help`; metric definitions are loaded through the existing permission-filtered endpoint. Navigation includes Help & User Guide. The guide clearly distinguishes code-verified mapping from independent source reconciliation.
- Help guide test verifies source-field search, permission-filtered definitions and that finance-only definitions are not client-side synthesized for an operations-only response.

### Updated remaining work count after PR #32
Four principal workstreams remain:
1. Finish the simple-JPR finance/variance audit and remaining source-to-visual reconciliation, including any unresolved source mappings (volume mapping now fixed).
2. Finish the visual explanation/Calculation & records audit: latest available synthetic inventory remains 408 role/page/title visuals with 72 unverified calculations and 47 missing explanation blocks. Re-run inventory after visual work; classify wrappers separately and do not invent evidence actions.
3. Design and implement the secure Report Scheduler with durable queue, permission-at-execution, safe recipient rules, freshness, idempotency, retries and actual delivery tests. No scheduler has been deployed; mailer capability alone is not a scheduler.
4. Complete authenticated browser, responsive, accessibility and production smoke QA; synthetic jsdom tests do not replace it.

The integrated HTML Help/User Guide is now complete enough for the first production release and is no longer a remaining workstream. Final release readiness is still pending the four items above.


## Production verification continuation — 9 November 2026, after PR #34

### Current repository and deployment
- Latest inspected main commit: `d1ffca38b2eba2d39693a89582daa5316e9323bc` (PR #34, verified visual explanations).
- PR #34 is merged. It adds page-specific calculation explanations and a synthetic jsdom coverage test for high-value visuals. It does not change formulas, source data, permissions or evidence payloads.
- Railway production deployment: `59faedfd-328b-4c7c-94be-2c5041c59aeb`, SUCCESS, exact main commit `d1ffca38`; NG-Dashboard Online, 1/1 replica. AI-Insights and Postgres are also online, each 1/1. Zero active warnings/criticals, zero recent failures, and no pending Railway work.
- Production source remains `ashwinn140/NG-Dashboard` / `main`; Postgres and the persistent `/data` volume remain attached. No staged Railway changes.
- Runtime HTTP log sample: 501 requests, 500 HTTP 200 and one HTTP 303 redirect; no HTTP 4xx/5xx in the sampled entries. This is service telemetry, not authenticated browser QA.
- Current GitHub combined commit status surfaced the Railway deployment success. A distinct CI check/run for PR #34 was not independently surfaced by the available status query; retrieve the exact GitHub Actions run evidence before the next merge. PR #34's description says the new jsdom test is run in CI, but do not infer a successful run from the deployment status.

### Production performance observations
- In the sampled 500 HTTP events, `/api/dataset`: 89 calls, p50 522 ms, p90 1,643 ms, max 4,058 ms.
- `/api/metrics/evidence`: 6 calls, p50 999 ms, max 10,963 ms.
- Admin-only `/api/admin/phase2/source-readiness`: 5 calls, p50 4,909 ms, max 5,754 ms.
- No HTTP errors were observed. The evidence and source-readiness endpoints are performance follow-ups, not correctness failures. Review query/data-copy costs and add targeted performance tests before optimizing; do not weaken scope checks or reduce audit detail.

### Source and finance review
- The simple JPR contract remains: `Job Profit Analysis Report`, one row per job, Basis: Job Date, required identity fields and report grand-total validation; booked GP is Income less Expense and source Profit is checked during import.
- No Chargewise/charge-wise workbook is required or in scope. Do not seek those files or infer Billing Date from Job Date.
- Prior sample reconciliation evidence remains historical and partial; it is not certification of the current live PostgreSQL snapshot. No production financial records were changed.
- Metric evidence implementation is permission-scoped and validates record indices against the user's already restricted dataset. It derives job profit from Income less Expense and uses composite job identity. Variance percentages use the absolute prior value and return unavailable for zero baselines.
- Authenticated live browser and current production data-to-UI/export reconciliation were not performed in this session. Do not claim them passed.

### PR #34 visual-explanation scope
- Added verified explanations for summary alerts/variance/trends, top customer/salesperson/branch rankings, scorecards, agent reports, profitability explorer, customer income-vs-margin, billing ageing/slow billing, invoice-month comparisons, finance variance, JPR status and register matching, plus visual builder/templates.
- Added `frontend/tests/visual_explanation_coverage_test.js` covering 15 high-value visuals. This is focused synthetic coverage, not proof that all runtime visuals are verified.
- Re-run the full synthetic runtime visual inventory after PR #34 and update the counts. The earlier 408-visual inventory (289 verified, 72 unverified, 47 missing explanations) predates PR #34 and is stale.

### Updated remaining principal workstreams
1. **Simple-JPR finance and variance audit:** verify all relevant formulas, Job Date windows, current/prior/YoY/partial periods, zero/negative baselines, permissions, drill-down evidence and Excel export parity. No charge-wise dependency.
2. **Visual explanation and reconciliation coverage:** regenerate the runtime inventory after PR #34; verify each remaining calculation from implementation; attach explicit Calculation & records only where evidence is correctly mapped; classify unsupported/wrapper visuals without inventing explanations or evidence.
3. **Secure Report Scheduler:** still not implemented. Design a durable queue, execution-time permission checks, approved recipients, freshness policy, idempotency, retries/restarts/concurrency and provider delivery states. Do not send real scheduled emails until security and delivery tests pass.
4. **Authenticated browser/responsive/accessibility QA:** still blocked by lack of an authenticated browser session. Cover 1920/1366/768/390 px, Operations last-five jobs, Customer 360, filters, explicit reconciliation, exports, keyboard and focus behavior when a session becomes available.

### Work performed in this continuation
- Rechecked GitHub main, PR #34, Railway production configuration, service health, runtime HTTP telemetry and application source paths.
- Reviewed JPR parsing/validation, metric evidence aggregation and source/date-basis declarations.
- Identified the performance observations above for follow-up.
- No source code, database schema, production business data, environment variables or Railway configuration changed.
- Created continuation branch `audit/production-verification-2026-11-09` from the deployed main commit to preserve this checkpoint update without changing production.



## Cross-LOB PR #28 CI review — 9 November 2026

- PR #28 head `c2683d8e7589a5ffa8783f3602fcb0db5dda25b0` was checked against its actual GitHub Actions run.
- Run `42646614859`, Metric traceability checks, failed in the backend test stage. The isolated Phase 2 unit workflow `42646614298` passed.
- Backend suite ran 163 tests and ended with 2 failures and 1 error:
  1. `test_metric_api.py::test_activity_review_is_scoped_and_does_not_call_sparse_history_lost` raises `KeyError: 'status'` because the legacy assertion expects the old top-level response field after the response contract changed to `selected_lob_activity.classification`.
  2. `test_cross_lob_activity_api.py::test_full_scope_identifies_active_customer_in_another_lob` got `insufficient_history` instead of `inactive_in_selected_lob_active_elsewhere`.
  3. `test_cross_lob_activity_api.py::test_restricted_user_cannot_learn_other_lob_activity` got `insufficient_history` instead of `inactive_in_selected_lob_no_other_visible_activity`.
- Build succeeded; later fixture/frontend/runtime steps were skipped because backend suite failed. No visual inventory artifact was uploaded.
- PR #28 cannot be merged or deployed. Its current base has conflicts with main and must be updated.
- Additional code-review observation: recent-JPR SQL predicate uses `lower(trim(customer))`, while Python grouping collapses all whitespace and uses `casefold()`; add consistent normalization and regression coverage for repeated internal spaces.
- A review comment documenting these failures and required remediation was posted to PR #28. A formal GitHub REQUEST_CHANGES review was unavailable because this account is the PR author.
- No source code, production data, database schema or deployment was changed.
- Next steps: rebase/update PR #28 on latest main; diagnose why seeded AE/OI register history is not present in classifier inputs (assert query result counts and per-LOB dates); update stale legacy API test to new response contract; align customer-name matching; rerun full Metric traceability workflow and isolated tests. Do not merge until green.


### Follow-up test-only diagnostic commits on PR #28
- Updated `tests/test_metric_api.py` to assert the new nested `selected_lob_activity.classification` response contract rather than the removed legacy top-level `status`.
- Added assertion diagnostics to the two cross-LOB API integration tests so the complete per-LOB classifier result is printed if the classification still fails.
- PR #28 head now reports `dedbb7ebe6f363fcd5d6f7f781984968499d5659`.
- The GitHub workflow query did not surface a new run for this updated head during this session. The previous failing run `42646614859` is still the only verified CI evidence; the test-only commits are not yet certified.
- Root cause of the two per-LOB integration classification failures remains unresolved. Do not infer that the test-only changes fixed them. Continue with a run that exposes `per_lob` / `last_shipment` values, then correct the data/query path.
- The PR remains open, diverged from main (15 commits ahead, 10 behind at last comparison), and non-mergeable. Do not merge or deploy.


## Master-prompt reconciliation against production — 9 November 2026

### Reconciliation basis and scope override
- Definitive baseline: master prompt `NG_Performance_Hub_Final_Master_Prompt.md` (19 sections), reconciled against deployed `main` commit `d1ffca38b2eba2d39693a89582daa5316e9323bc` and Railway deployment `59faedfd-328b-4c7c-94be-2c5041c59aeb` (SUCCESS).
- Owner's latest source decision supersedes any older wording or audit artifacts: use only the existing simple, job-level Job Profit Analysis Report (JPR), one row per job, Basis: Job Date. Do not add charge-wise/Chargewise analysis, seek charge-wise workbooks, require Billing Date, or infer Billing Date from Job Date.
- This is a documentation/reconciliation checkpoint only. No product code, database, production data, environment variables, or Railway configuration changed.

### Current production verification
- Railway production NG-Dashboard is Online, 1/1 replica, deployment SUCCESS for exact commit `d1ffca38`; PostgreSQL is Online, and there is no staged/pending Railway work. No active warnings/criticals or recent failures were reported.
- Sampled runtime telemetry: 501 HTTP events, 500 responses 200 and one 303; no 4xx/5xx in that sample. This is service telemetry, not an authenticated browser test.
- Production URL: https://ng-dashboard-production.up.railway.app/
- Authenticated browser verification, responsive/accessibility checks and current live JPR-to-PostgreSQL-to-API-to-visual-to-Excel reconciliation have not been performed in this session. Do not claim them complete.

### Master prompt requirement disposition

| Master prompt area | Reconciled status | Deployed evidence / remaining boundary |
|---|---|---|
| Baseline, source rules, role/LOB security foundation | Completed and production-verified | Main/deployment inspected; permission-scoped dataset and metric evidence contracts exist. Continue targeted permission/export regression tests. |
| Production shell/build integrity | Completed and production-verified | PR #23 fixed malformed generated HTML/visible-JavaScript incident and added fail-closed build checks; deployed. |
| Origin/destination multi-select semantics | Completed and production-verified | PR #19 lane aggregation uses the normal active filter mask; OR within a field and AND across fields. Preserve existing regression coverage; do not rebuild. |
| Explicit reconciliation framework | Completed for supported metric-backed visuals; overall coverage audit pending | PR #19/metric trace infrastructure provides explicit evidence actions without opening on ordinary KPI/ranking clicks. Keep unsupported visuals without fabricated records. Re-inventory all runtime visuals after PR #34. |
| Operations last-five distinct jobs and Job Owner | Completed and production-verified | PR #25 source-readiness diagnostics and PR #26 recent-jobs endpoint/UI are merged and deployed. Preserve tests for distinct job identity, repeated owners, missing/conflicting owner, company/LOB scope and export. Authenticated live UI check remains outstanding. |
| Customer 360 cross-LOB activity | Implemented and production-verified for visible-LOB context | PR #29 adds per-LOB activity breakdown from currently loaded, permission-scoped shipment rows; source-name matching and incomplete-snapshot caveats are explicit. `frontend/tests/customer360_test.js` covers separate LOB histories, active elsewhere and sparse history. It is not a stable customer-code master or proof of company-wide inactivity. |
| PR #28 server-side cross-LOB classifier | Pending; not merge/deploy ready | PR #28 remains open, diverged (15 ahead/10 behind at last comparison), and its verified CI run failed (163 backend tests: 2 failures, 1 error). Test-only commits do not have a surfaced new CI run. Because deployed Customer 360 already exposes visible-LOB context, compare the exact remaining acceptance gap before investing further; do not duplicate the deployed feature or weaken history thresholds. |
| Simple-JPR finance model | Core implementation deployed; full current production audit pending | JPR is `job_summary_v1`, one row per job, Job Date basis; Income, Expense and GP/Profit = Income − Expense validation are implemented. Prior independent JPR sample checks exist in historical audit artifacts, but are not current production snapshot certification. No charge-wise work is in scope. |
| Finance controls / exception evidence | Completed for specific shipped controls; full finance audit pending | PR #24 expected-cost estimate is explicitly an estimate, not booked cost/liability; PR #30 customer concentration guard and zero/negative-baseline variance handling are deployed. Invoice placeholder handling and Job Date period tests exist. Audit all finance metrics, filters, evidence and Excel parity against the accepted simple JPR. |
| Volume-unit correction | Completed and production-verified | PR #31 stores the Volume-adjacent unit for new imports and uses the audited legacy fallback. Preserve `tests/test_volume_units.py`; do not alter source values or introduce a new conversion without evidence. |
| Invoice placeholder handling | Implemented and tested | Existing tests cover blank, 0, N/A, NIL and Pending as non-invoice references. Validate against current operational source snapshots during the remaining operations audit. |
| Visual explanations / Visual Dictionary | Partially completed; coverage audit pending | PR #32 Help/Metric Dictionary is live. PR #34 adds source-backed explanations and `frontend/tests/visual_explanation_coverage_test.js` covers 15 high-value visuals. The earlier 408-visual inventory predates PR #34 and is stale; regenerate before assigning any remaining visual work. |
| Variance/date behavior | Partially covered; complete audit pending | Existing targeted tests cover current/prior periods, FY/calendar boundaries, leap-day clamping, partial periods, zero baseline and negative baseline behavior. Audit all finance/operations variance views, exact date labels, missing-history states, filters, evidence and export parity. |
| Integrated HTML Help & User Guide | Completed and production-verified | PR #32 deployed `/help`, search and permission-filtered Metric Dictionary; `frontend/tests/help_guide_test.js` is retained. Do not create a separate PDF/Word manual or rebuild the guide. |
| Report Scheduler | Pending — genuinely missing capability | No durable scheduler/queue, execution-time authorization, recipient approval workflow, freshness gate, idempotency, retry/restart/concurrency controls or delivery history UI is deployed. Build only after design/security acceptance criteria and tests are ready. |
| Business Pulse / Finance Control Tower / optional intelligence | Evaluate, do not blindly build | Reuse existing pages where adequate. Add only capabilities justified by verified business value, source feasibility, security and acceptance tests. KRKP must not be guessed. |
| Authenticated browser, responsive, accessibility and final production smoke | Blocked | No authenticated browser session/tool is available in this continuation. Keep this explicit; synthetic jsdom and HTTP telemetry are not substitutes. |
| Full source-to-export reconciliation and ingestion/data health | Pending / partly blocked by evidence | Need current accepted simple JPR source and current production import/snapshot evidence. Library search surfaced audit patches and prior reconciliation artifacts, not the actual current accepted JPR source workbooks. Do not substitute charge-wise workbooks. |

### Targeted acceptance tests to retain (do not replace with broad, untargeted rewrites)
- Lane/filter and explicit-only trace behavior: existing PR #19 regression coverage and `frontend/tests/metric_trace_test.js` / `frontend/tests/metric_drawer_test.js`.
- Customer job history: `tests/test_customer_history.py`, `frontend/tests/ops_pages_fixes_test.js`, and the existing API scope/export tests.
- Customer 360 cross-LOB and restricted visibility: `frontend/tests/customer360_test.js`; retain sparse-history and visible-LOB assertions.
- Finance formulas and variance: `tests/test_metric_execution.py`, `frontend/tests/data_audit.js`, `frontend/tests/metric_trace_test.js`.
- Invoice/volume data rules: `tests/test_invoice_reference.py`, `tests/test_volume_units.py`; retain operational-ageing regression coverage already in the suite.
- Help/metric dictionary: `frontend/tests/help_guide_test.js`.
- Post-PR #34 visual explanations: `frontend/tests/visual_explanation_coverage_test.js` (15 targeted high-value visuals). Add coverage only for a verified gap discovered by the regenerated inventory.
- Existing backend permission, API, export and production-build checks remain release gates.

### Work only on verified defects, audit gaps and missing capabilities

1. Regenerate the synthetic runtime visual inventory against commit `d1ffca38` and classify each remaining item as verified explanation, unverified calculation, missing explanation, wrapper/container, or unsupported/no record-level evidence. Do not reuse the pre-PR #34 408-visual counts.
2. Run a focused simple-JPR finance/variance audit: Income, Expense, GP, margin, job count, profit/job, customer/branch/LOB attribution, negative-profit and zero/negative baselines, Job Date period boundaries, missing comparison history, permission scope, metric evidence and Excel export parity. Clearly separate source validation from code-level tests. Do not add charge-wise logic.
3. Audit operational data rules against currently accepted shipment snapshots: invoice placeholders, volume mapping (already corrected in code), operational/finance ageing date bases, job matching, source freshness and import coverage. Change code only if a reproducible defect is demonstrated.
4. Reconcile PR #28 with deployed PR #29 Customer 360 behavior. Retain PR #28 as unmerged until a concrete unmet acceptance requirement is demonstrated, its integration data path is diagnosed, and its branch is updated from current main with green full CI. Do not weaken inactivity thresholds.
5. Treat the generic secure Report Scheduler as the one major missing capability. Design first; implement durable queue, permission checks at execution, approved recipients, freshness policy, idempotency, bounded retries, restart/concurrency safety, accurate provider states and audit history. Do not activate real customer/financial emails before end-to-end security and delivery tests pass.
6. Obtain an authorized browser session for 1920/1366/768/390 px, keyboard/focus, last-five jobs, Customer 360, filter, explicit reconciliation, export and production smoke checks. Until then, report this gate as Blocked.

### Release posture
- Do not rebuild deployed features already listed as complete.
- Do not merge/deploy PR #28 based on the current failing evidence.
- Do not change production data, schemas, source mappings or financial formulas merely to make an audit pass.
- Only create a feature branch for a reproducible defect or a genuinely missing capability; keep the targeted acceptance test for that defect with the change.
- Next checkpoint should record exact regenerated inventory results, JPR audit evidence, operational audit results, any PR decision, scheduler design/tests, and browser QA availability.


## Post-PR #34 runtime visual inventory — actual CI artifact

- Workflow: Metric traceability checks, run `42651799372`, head `6695b8dc06a98a18a241f371986b530acef29306`, conclusion SUCCESS. All workflow steps passed, including production build reproduction, backend/permissions/Excel reconciliation, frontend/metric contract audit, runtime visual inventory and artifact upload.
- Artifact: `ng-dashboard-visual-inventory`, artifact ID `13690870682`, SHA-256 `e9bb3066c632b9fa8c6676fce558627ad4885c3a8d22788b3b0ef3dcf61f0e91`.
- Runtime coverage: 414 role/page instances; 408 unique role/page/title entries; 0 runtime errors; 0 registered pages unvisited.
- Classification across unique role/page/title entries: 374 with explanations; 360 calculation-verified; 14 explanation-present but calculation-unverified; 34 with no explanation.
- The 34 no-explanation entries reduce to 16 shared wrapper/builder containers (untitled page wrappers and the Build a visual setup card), not missing business calculations. Do not create explanations for these containers.
- Across 176 distinct group/page/kind/title definitions, 16 are wrappers/builders and 160 are substantive business visuals. Of those 160, 153 are calculation-verified and 7 are not yet verified.
- Reconciliation action coverage: 108 of the 160 substantive visual definitions expose a Calculation & records action; 45 calculation-verified definitions do not. The remaining 7 unverified definitions correctly have no evidence action yet. Do not blanket-add actions: some no-action entries are documentation/status cards or already detailed record tables, and multi-source visuals require their own evidence design.
- The seven substantive but calculation-unverified visual definitions are: Profit overview — From income to profit; Income and expense by week; How healthy are the jobs?; Profit compare — Period by period: profit; Biggest increases by branch; Biggest decreases by branch; Variance by branch. Verify the implemented aggregation and date/period behavior before adding evidence actions.
- High-value verified action gaps include Operations Compare — Running total and Period by period (both use Shipment Date and have exact current/prior source rows); Summary — Top N customers by profit, Top N sales people by profit and Top N branches by profit (simple JPR, Job Date); and selected branch profitability tables/charts. Metadata cards and already-detailed tables remain excluded unless a separate source-evidence need is demonstrated.
- PR #35 was opened to add Calculation & records to the two Operations Compare charts only. It uses the existing metric trace path and adds targeted tests for current and comparison Shipment Date masks. PR #35 CI run `42656564418` was in progress at this checkpoint; no merge or deployment has occurred.
- Next evidence-only visual work after PR #35: add narrowly scoped actions to the three Summary Top N JPR rankings only if targeted tests confirm that the drawer returns the full selected job-level JPR population used to compute those rankings. Do not attach one-measure actions to multi-measure or mixed-source cards (e.g. scorecards, Income against margin, shipment-vs-invoice dual-date charts) without a purpose-built multi-source evidence contract.


## Secure Report Scheduler — implementation discovery and design guardrails

### Verified current state
- No `report_schedules`, `report_runs`, durable outbox, or report-delivery tables exist in `app/db.py`; no scheduled-report API routes or worker were found in `app/server.py`.
- `app/mailer.py` already supports HTTPS delivery through Resend or SMTP and is used by the sign-in email flow. It returns only a boolean, has no report-attachment support or provider message ID, and keeps its test/development OUTBOX in process memory. It is not a durable scheduler or delivery ledger.
- The `users` table already stores active status, role, companies, LOBs and finance permission. These must be re-read at execution time; schedule-time permissions cannot be trusted later.
- Existing exports and metric evidence are snapshot-bound. Scheduled output must reuse the existing permitted dataset/metric/export path, not issue new ad hoc SQL or reconstruct financial totals.
- No report-scheduler feature is currently deployed. Do not describe the existing login email as scheduled report delivery.

### Safe v1 design (before code)
1. Persist schedules, due occurrences, run records and delivery attempts in PostgreSQL. Use a dedicated worker or scheduled worker process; never use in-memory timers or FastAPI background tasks as the durable queue.
2. Claim due work transactionally with row locking/lease expiry and a unique occurrence key (schedule + scheduled local occurrence). Make worker restart and concurrent replicas safe.
3. Revalidate the owner and every recipient at execution: active account, current role, company/LOB scope and finance permission. Generate one recipient-specific report per scope; never send a combined multi-recipient report that leaks broader data.
4. V1 recipients should be existing active dashboard users only. Do not permit arbitrary external email addresses until an explicit admin approval and data-classification policy exists.
5. Deliver a login-required in-app report link, not a public URL or attachment, in v1. The report endpoint must re-check the recipient's current permissions and the run's snapshot. A revoked user must not be able to retrieve a previously scheduled report.
6. Apply a freshness gate across every source required by the report. If the shipment register or simple JPR is stale/missing, mark the run skipped-stale, notify the owner, and send no data.
7. Extend the mail transport separately from sign-in mail: structured provider response/message ID, bounded timeout, sanitized errors, provider idempotency where supported, and an explicit unknown-delivery state for ambiguous SMTP outcomes. Do not silently retry an ambiguous send if that could duplicate sensitive reports.
8. Support pause, resume, edit, cancel, timezone-aware daily/weekly/monthly cadence, DST-safe occurrence calculation, preview/test-to-self, and a complete audit trail of schedule changes, execution, skip/failure reasons and delivery states.
9. Keep the current simple job-level JPR as the only finance source and use Job Date. Do not add Chargewise/charge-wise analysis, attachments, or external recipients in v1.

### Required acceptance tests before enabling delivery
- Permission revocation and user deactivation between schedule creation and execution.
- Finance vs operations user visibility; company and LOB isolation; per-recipient report generation.
- Unauthorized/external recipient rejection and admin-only approval path if later added.
- Stale/missing shipment or JPR source blocks delivery; fresh source binds the exact snapshot.
- Duplicate occurrence, two concurrent workers, lease expiry, restart recovery, retry backoff, cancellation while queued/running, and ambiguous provider timeout.
- Delivery provider success/failure/unknown states; no credentials, report contents or provider response bodies in logs.
- Report link requires login, enforces recipient scope at retrieval, expires/revokes safely, and cannot be forwarded to a broader-privilege user.
- Export content matches the existing on-demand report for the same user, filters and snapshot.


## Production baseline update after targeted evidence fixes — 9 November 2026

- The latest deployed production commit is now `f79b6285efb9742ea4892c5744473eb259916679`, Railway deployment `6c5a073a-080a-46f5-8767-91cf04b86272`, status SUCCESS, region `iad`.
- PR #35 (`0757124f`) deployed the Calculation & records action on Operations Compare's Running total and Period by period visuals. Its full Metric traceability workflow passed.
- PR #36 (`f79b6285`) deployed Calculation & records actions on Summary's Top N customers, sales people and branches by profit. Its full Metric traceability workflow passed.
- Post-deployment HTTP sample for the new active deployment returned HTTP 200 for `/`, `/api/me`, `/api/dataset`, `/api/prefs`, `/api/metrics/definitions`, and `/assets/metric_trace.js`; no 4xx/5xx appeared in the retrieved sample. This is a production HTTP smoke check, not authenticated browser/responsive/accessibility acceptance.
- PR #37 (`feature/profit-compare-evidence-2026-11-09`) is open and not deployed. It corrects the Profit Compare evidence period-state mismatch, adds evidence actions to four Profit Compare visuals, verifies the seven previously unverified finance explanations, and corrects margin-band labels with edge tests. Latest CI run `42658738004` is queued after the first run caught a missing sort-state fixture in the new test; the fixture was corrected without changing product behavior.
- The post-PR #34 artifact is now an historical baseline for explanation coverage; PR #35/#36 add five evidence actions. Regenerate the runtime inventory after PR #37 is merged/deployed before stating the new action-coverage counts.
- The deployed source contract remains the simple job-level JPR, one row per job, Job Date. No Chargewise/charge-wise code or data source has been introduced.


## Post-PR #37 visual inventory — full CI result

- Workflow `42658738004` completed SUCCESS on PR #37 and generated artifact `ng-dashboard-visual-inventory` (artifact ID `13693871273`).
- 414 role/page instances; 408 unique role/page/title entries; zero runtime errors; zero registered pages unvisited.
- 379 role/page entries have explanations and all 379 are calculation-verified. The earlier 14 unverified entries are now zero.
- The 35 role/page entries without explanations reduce to 16 shared wrapper/builder definitions (untitled containers and Build a visual); none is a missing business calculation.
- Across 176 distinct group/page/kind/title definitions, 160 are substantive business visuals and all 160 now have verified explanations. The other 16 are wrappers/builders.
- 117 of 160 substantive visuals expose Calculation & records. The remaining 43 must be classified individually; some are status/metadata cards, multi-measure/multi-source visuals, or already detailed record tables and should not receive an inaccurate single-metric action.
- PR #35 and #36 added five actions (Operations Compare Running total/Period by period; Summary Top N customers/sales people/branches). PR #37 added four actions (Profit Compare Period by period, Biggest increases/decreases, Variance by branch) and fixed Profit Compare trace periods to use `S.pcmp` rather than Operations `S.cmp`.
- PR #37 also completed verified explanations for all seven formerly unverified finance visuals and corrected margin-band labels for the actual rounding and negative-expense (>100% margin) behavior.
- Next targeted candidates are one-measure compare cards and source-backed rankings. Do not add actions to mixed-source or dual-date visuals until the evidence request can represent all contributing measures/date bases accurately.


## Simple job-level JPR preservation check

- `app/profit.py` validates the simple Job Profit Analysis Report contract, checks the report-level Profit against Income less Expense, and rejects duplicate job identities at the job/date/LOB grain.
- `app/store.py` selects current JPR imports while excluding charge-detail imports via the source-column metadata filter; no charge-wise calculation path was added.
- Existing targeted tests in `tests/test_profit_import_layout.py` cover the legacy Charge wise Detail layout being explicitly flagged and confirm that charge/party-level columns are not exposed in the normalized dataset. These tests remain in the CI workflow.
- All new evidence actions and explanations in PRs #35–#37 use the existing job-level JPR and Job Date where finance is involved. No Chargewise source workbook or charge-wise analysis is required or introduced.
