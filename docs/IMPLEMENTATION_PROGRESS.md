# Implementation progress — NG Dashboard

## Current stage
Stage 1 baseline review in progress; full assignment NOT complete.

## Verified baseline
- Production main: 8281635b77f1dad04ba5520ceeafdfcfed18c1fa.
- Railway production deployment: 547a7402-eb35-4e9d-93e0-6ec28916084b, observed SUCCESS.
- Development branch: feature/metric-traceability-review; baseline fef3e07218678f82bc23bbe7cf463e7db4f3ebe0. Comparison reports ahead of main; six changed files. Existing Customer 360 work is included in branch ancestry.
- Registry unit tests executed locally: 4/4 passed. This is definition testing, NOT financial source reconciliation.
- Actual canonical frontend job key includes company, job dictionary identifier, Job Date and LOB.
- Initial audit references legacy pr_core.js/pr_pages.js; canonical implementation is frontend/app_prod.js. Documentation needs correction.
- Expected-cost benchmark uses all authorized loaded jobs, not selected date window; applies same-LOB expense/income ratio, overall fallback, only positive-income/zero-expense jobs. Not confirmed GP.

## Files modified
This progress file only on development branch. Registry/test source files retrieved locally unchanged for verification.

## Authority
User supplied MASTER EXECUTION INSTRUCTIONS authorize full implementation and tested deployment; earlier draft document's deployment exclusion is superseded. AI-Insights excluded. Ingestion cadence and retention unchanged.

## Tests
python -m unittest discover -s tests -p test_metric_definitions.py: 4 passed.

## Pending
Complete runtime baseline; complete visual inventory and source mapping; expand registry; shared drilldown and XLSX reconciliation; dashboard/Customer360 integration; financial label correction; variance/permission/source audits; responsive QA; release gates and deployment.

## Blocked
No confirmed external blocker yet. Source reconciliation has not been performed in this assignment.

## Deployment status
No new audit changes deployed. Current production remains the verified Customer 360 release above.

## Exact next action
Fetch feature branch server.py and CI workflow; materialize complete feature branch source at the new progress commit; run full backend/frontend baseline; inventory canonical page functions and current exports. Correct registry job identity and stale date-basis caveat from verified canonical code, with regression tests, before implementing shared metric execution and XLSX endpoints. Update this file after each stage. Continue on existing branch and PR #15; never replace production with partial registry-only changes.

## Stage 2–5 implementation in progress
Implemented shared scoped-record metric execution, snapshot-bound evidence and XLSX endpoints with CSRF/auth checks; reusable calculation drawer (search, sorting, pagination, copy, both periods, export); initial Dashboard and Customer360 KPI hooks; source-accurate no-income status label; operations definitions; composite job identity correction; expected-cost benchmark evidence and cost-coverage calculations.
Tests: full available suite 75 passed before adding API tests; 6 execution tests passed; 2 API integration tests passed; existing frontend audit 139/139 passed. Dependency packages restored locally after workspace cleanup. No production deployment of this audit work.
Still pending: exact per-visual contexts for explorer/special KPIs, complete visual inventory, remaining metric coverage, source reconciliation, export/large-data QA, broader UI integration, opportunities audit, release validation.
