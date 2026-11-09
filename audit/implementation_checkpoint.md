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
