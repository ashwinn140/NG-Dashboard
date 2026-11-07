# Dashboard removal and correctness audit — 7 November 2026

Base: `1c608b8f60b069da68f12a68570961a16df94b8d` on `ashwinn140/NG-Dashboard:main`.
Scope: current production frontend, server routing, ingestion/version replacement,
dataset construction, company/LOB/finance restrictions, date masks, grouped totals,
variance, visual-builder measures and operational Excel visibility.

## Released corrections

- Removed the Business Intelligence BETA card and page. The former authenticated
  URL returns HTTP 410. The main dashboard and its existing report pages remain.
- Removed the sticky filter header that could cover filter controls on mobile.
- Removed production demo-row generation and remaining visible demo guidance.
- Calendar-year KPI comparisons use the same dates in the preceding year, clamping
  29 February to 28 February, rather than subtracting 365 days.
- Leadership and Finance comparison KPIs expose current and previous values,
  including a zero prior baseline. Summary variance no longer suppresses absolute
  finance changes when no prior-period charge lines exist; percentages remain
  unavailable for zero or negative baselines.
- Shipment/finance matching requires a unique candidate and respects known LOB.
  Reused numbers without a unique date match stay unmatched; their income and
  expense remain in finance totals. Matched salesperson/lane figures can therefore
  move to the existing '(no register match)' bucket instead of a guessed party.
- Finance job counts distinguish company, job number, job date and LOB. Source
  diagnostic job counts use the same identity dimensions.
- Removed pre-aggregation rounding of chargeable/gross weight, TEUs and CBM;
  frontend numeric arrays use double precision. Display formatting is unchanged.
- Lane dictionary keys no longer rely on a fixed 1,000-destination multiplier;
  dictionary codes use 32-bit arrays to avoid 65,535-code truncation.
- Operations-only responses redact buy/sell rates. Financial saved visuals reject
  access, and operations summary/scorecard/Excel omit financial content.
- Empty register scopes safely preserve unmatched finance lines.
- Production builds now use the actual production script and shell. The legacy
  review string-replacement build could overwrite later production-only UI fixes.
  `sh frontend/build.sh` reproduces the committed deployed page.

## Validation and evidence

- 41 Python regression checks pass, including replacement/history, projected
  dataset equivalence, financial totals, ambiguity, exact date/LOB matching,
  source precision, empty scopes, rate redaction and route authentication/removal.
- 144 DOM/calculation/export checks pass using controlled synthetic ERP records:
  192 shipments and 48 finance lines, both companies, all four LOBs and two years.
  Synthetic source income: INR 7,440; expense: INR 2,664; profit: INR 4,776.
- All 25 report pages exercise their render paths for administrator and restricted
  finance scope; 14 accessible pages exercise operations-only scope. Across these
  64 page/scope runs, there are no script errors.
- Company/LOB/date filtered totals reconcile to independent fixture-array sums.
  Grouped income/expense reconcile across company, report, branch, customer,
  salesperson, lane, LOB, charge and intercompany classifications.
- Visual-builder additive measures reconcile to fixture totals. The operations
  scorecard Excel ZIP is opened and inspected to exclude monetary columns.
- Leap-year boundary and zero-prior-finance variance regressions pass.
- JavaScript syntax passes and production rebuild output is checked.

## Limits and follow-up

These checks establish code behavior on known inputs. They do **not** establish
row-by-row agreement with current production ERP exports. Automated approval review
blocked signing into a previously shared production account and downloading
production/admin records because account authorization was unverified. No live
source numerical tie-out is claimed.

A raster browser launch was unavailable in this execution environment; DOM render
and CSS position checks passed, but real iPhone/Safari visual confirmation remains.
The older source-workbook year test requires ERP sample files absent from this
workspace and was not completed. Synthetic history/replacement tests passed.

Report-specific exports are preferred for full underlying records. The universal
'Export visible data' remains explicitly limited to visible table rows and exposed
chart series. Customer canonicalization is name-based; stable ERP customer IDs
would make future identity consolidation more reliable.

No database migrations, source-record changes, retention changes or import
schedule changes are included in this release. No chatbot or new analytical
feature has been introduced.
