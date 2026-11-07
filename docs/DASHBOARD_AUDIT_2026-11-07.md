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

The initial release used synthetic data. On 8 November (IST), the user supplied an
explicitly authorized superadmin account, resolving the production sign-in blocker.
The live continuation below supersedes that limitation. Original workbook bytes
were not available through the current administration API or filename searches,
so a fresh row-by-row source-workbook reconstruction is still not claimed.

The live dashboard and expanded filters were subsequently inspected in a real
browser. The old sticky overlap was absent in the inspected desktop layout;
real iPhone/Safari confirmation remains separate.
The older source-workbook year test requires ERP sample files absent from this
workspace and was not completed. Synthetic history/replacement tests passed.

Report-specific exports are preferred for full underlying records. The universal
'Export visible data' remains explicitly limited to visible table rows and exposed
chart series. Customer canonicalization is name-based; stable ERP customer IDs
would make future identity consolidation more reliable.

No database migrations, source-record changes, retention changes or import
schedule changes are included in this release. No chatbot or new analytical
feature has been introduced.


## Live continuation — 8 November 2026 (IST)

Authorized production account: administrator, unrestricted companies and LOBs,
finance enabled. No credentials or session identifiers are stored in this report.
All audit access was read-only; imports and source data were not changed.

### Reconciliation performed

- 47,424 shipment rows and 471,116 finance lines were retrieved from the production
  API. The former BI URL returned HTTP 410 for the authenticated account.
- **109 live source/structural checks passed**: shipment row counts matched the
  promoted calendar-year import counts for every company/LOB/year; finance line
  counts matched the four promoted FY imports; metadata counts and encoded column
  alignment reconciled; no duplicate shipment number/date business keys were
  found within any company/LOB; weight units remained consistent.
- **144 DOM/calculation/export checks passed on live data**, exercising the same
  25 pages plus local restricted-scope derivations from those records. Real
  operations/restricted-finance user sessions were not impersonated or changed.
- Grouped income and expense reconcile to the overall finance totals to currency
  precision (tolerance INR 0.005, half a paisa). Binary floating-point summation
  differs slightly by grouping order, below one paisa; the prior synthetic-only
  tolerance of INR 0.000001 was unnecessarily strict for INR 7.1 billion of data.
- Across all currently loaded billing dates, income is **INR 7,134,523,570.04**,
  expense **INR 6,064,694,554.05**, and booked profit **INR 1,069,829,015.99**.
  API sums agree with database-derived finance metadata to the cent. This is an
  internal database/API/visual reconciliation, not an independent accounting sign-off.

| Company | LOB | 2025 promoted/API rows | 2026 promoted/API rows |
| --- | --- | ---: | ---: |
| NG | AE | 11,260 | 9,825 |
| NG | AI | 4,620 | 4,369 |
| NG | OE | 3,712 | 3,189 |
| NG | OI | 1,363 | 1,097 |
| NCS | AE | 2,826 | 2,207 |
| NCS | AI | 329 | 59 |
| NCS | OE | 1,659 | 619 |
| NCS | OI | 150 | 140 |

These are loaded annual file totals, not a like-for-like growth comparison.
The latest shipment date is 7 November 2026.

### Findings and follow-up corrections

1. Finance source reports begin **1 April 2025** for both companies. Shipment
   records begin January 2025. Thus calendar-year finance comparisons requesting
   January–March 2025 have no loaded source report for those months. A visible
   reporting-context note now discloses this while keeping uploaded-record values
   and variances available, as requested.
2. The initial All dates view compares a multi-year range with a range shifted by
   one year, creating overlapping dates. A context note now flags the overlap and
   directs users to select one year for an annual comparison. No date selection or
   saved view is silently changed.
3. The footer incorrectly said this was a review version without profit. Replaced
   with accurate date-basis, units and uploaded-record wording.
4. Import queue was empty. There were **11 held profit uploads** lacking an explicit
   billing-date replacement range and **6 failed header detections** in earlier
   attempts. Later FY files were promoted successfully. Earlier failures/holds are
   retained for traceability and were not approved, retried, deleted or used to
   overwrite current records. Recurring profit exports should include an explicit
   billing-date range to avoid future holds.
5. Source attribution quality remains a business-data issue: many shipments name
   Administrator as salesperson, and some finance jobs have no corresponding
   forwarding register (including customs/general/road jobs). Such figures remain
   visible under their actual or unmatched classification rather than being guessed.

No source totals were changed by these follow-up context/footer corrections.
