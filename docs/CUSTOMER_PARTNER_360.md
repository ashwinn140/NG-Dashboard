# Customer & Partner 360

A normal signed-in user can open `/customer360` through the dashboard navigation. It consumes the existing server-scoped `/api/dataset`; company, LOB and financial permissions remain server enforced. Saved combinations use the existing CSRF-protected preferences API under `partner360` and belong to the logged-in user.

Relationships: Any role, Customer, Shipper, Consignee, Origin Agent, Destination Agent; countries, ports, branch and sales. AND across fields, OR across values, exact normalized source names (case-insensitive). No fuzzy organization matching or cross-company code consolidation. Explicit agent fields only: generic Booking Through / Overseas Agent / Agent Name are not substituted.

Operational totals use Shipment Date; financial totals use Job Date. Finance retains all authorized financial rows including clearance/road without registers. Source filters are evaluated separately; the relationship and period determine which source contributes. Matched register rows are counted once; separate unmatched finance rows preserve totals. Table and CSV mask out-of-period financial amounts. Record scope can require both sources to match relationship filters. Source metadata, period comparison dates and missing coverage are visible.

Finance KPIs: job count, income, expense, booked GP and margin. Operations-only accounts see shipments, air weight and ocean TEUs. The view includes interval trends, markets (Top 10/25/50/all), mode mix, unique counterparties, source exceptions, lock/invoice status, searchable records and a source detail drawer. CSV respects active filters and finance permissions, with spreadsheet formula escaping.

Validation: Python source/permission/saved-view tests, production build reproducibility and existing financial/import regression tests; jsdom tests for date isolation, combined filters, deduplication, saved views, drawer and CSV; existing dashboard audit. Run `python -m unittest discover -s tests`; `node frontend/tests/customer360_test.js` (jsdom required); `python scripts/build_audit_fixture.py` followed by `node frontend/tests/data_audit.js`.

Data limitations: historical figures reflect loaded reports; no inference of missing prior activity. No receivables/collection measures. Missing source values remain blank. Historical imports and hourly sync behavior are unchanged.
