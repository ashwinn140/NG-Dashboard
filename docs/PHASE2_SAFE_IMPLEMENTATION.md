# NG Dashboard Phase 2 — isolated implementation contract

Status: development only. Production baseline: 6a4e50bfd50d27e6a4dc52d79dd9927556fca859.
This branch must not be merged or deployed without explicit verification and acceptance.

## Approved business rules
- Salesperson attribution: ERP Sales Person, never silently substitute Job Owner or Booking Thru.
- Customer identity: ERP customer code, company-scoped; approved audited alias mapping.
- Inactivity: adaptive 30/60/90 days using historical shipment cadence; insufficient history is a distinct state; never label lost without approved confirmation/rule.
- Profitability: Gross Profit and GP per shipment, with valid job matching and currency normalization.
- Morning briefing: on login, initially opt-in/feature-flagged; never replace the current default until approved.
- Company/LOB access: NG/NCS and AE/AI/OE/OI enforced server-side for UI, APIs, drilldowns, and Excel.
- Nomination: preserve ERP source values; display Self Nomination as Free Hand.

## Baseline behavior to protect
Login and sessions; role/company/LOB/finance permissions; current leadership overview; all existing reports, variation and sales; filters and restored wide filter layout; existing Excel exports; Gmail ingestion; admin user rights and copy rights; historical retention; current profit computations.

## Phase 0 implementation tasks (do not change production)
1. Audit source report headers for customer code, ERP Sales Person, unique shipment/job key, dates, currency, and financial link keys. Flag missing identifiers; do not infer identity from names.
2. Define canonical metric dictionary, period boundaries, zero-denominator behavior, missing GP behavior, source date precedence, and financial reconciliation.
3. Extend existing admin reconciliation diagnostics, read-only and additive. Never alter report ingestion/promotion decisions in the first change.
4. Design paginated drill-down API with strict server-side company/LOB/finance authorization, input validation, bounded page size, and authorized export.
5. Add independent unit, integration, authorization, and regression tests with synthetic fixtures before implementing UI.
6. Use separate, reversible modules; no destructive schema changes; no silent rewrites of historical records.
7. Only then implement customer, sales, variance, heatmap, and briefing behind disabled feature flags.

## Release gates
- No baseline regressions; compare source ERP counts/GP to report, drilldown, and exports.
- Verify restricted NG/NCS/LOB and non-finance users cannot retrieve unauthorized rows or metadata.
- Verify missing source fields or partial financial matching produce explicit unavailable/incomplete results.
- Test duplicate/stale/failed imports, nulls, changed customer aliases, date boundaries, and historical retention.
- Confirm Railway resource usage, query pagination, backups, migration rollback, and deploy/rollback instructions.
- Manual UAT with NG and NCS before enabling new features.
- No merge or deployment merely because tests pass: explicit release decision required.

## Planned modules (not yet implemented)
- app/analytics/metrics.py
- app/analytics/identity.py
- app/analytics/reconciliation.py
- app/analytics/drilldown.py
- app/analytics/variance.py
- app/analytics/customer.py
- app/analytics/sales.py
- app/analytics/profitability.py
- app/analytics/briefing.py
- tests/phase2/

## Known source questions to resolve before calculations
- shipments currently has customer and job_owner; dedicated customer_code and salesperson need source mapping verification.
- profit_lines has company, lob, job_no, income/expense/profit; verify unique join and reporting date alignment.
- org_master uses normalized name keys; do not use as an authoritative customer-code crosswalk without approval.
- Profit reports currently reference INR income/expense; validate whether all inputs and derived GP share this currency.
- Existing retention mode may limit historic customer-lifecycle inference.
