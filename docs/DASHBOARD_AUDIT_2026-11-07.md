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
The live continuation below supersedes that limitation. Original workbook bytes were initially unavailable through the administration API
and filename searches. The source-workbook continuation below recovered two
originals and reconciled 187,805 rows. The other two accepted finance source
workbooks remain outside that row-level verification.

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


## Original-workbook continuation — 8 November 2026 (IST)

### Recovered originals and row-level results

The NCS FY2025 original was located by browsing uploaded workbook metadata after
filename search missed its non-breaking spaces. The NG current-year original was
recovered from the project's Gmail attachment. SHA-256 matches the corresponding
promoted import metadata for both files.

| Original source | Billing-date window | Raw/API charge lines | Income (INR) | Expense (INR) | Raw/API unmatched rows |
| --- | --- | ---: | ---: | ---: | ---: |
| NG current FY | 1 Apr 2026–31 Mar 2027 | 134,655 | 3,066,992,924.29 | 2,607,633,027.47 | 0 |
| NCS FY2025 | 1 Apr 2025–31 Mar 2026 | 53,150 | 544,429,246.68 | 455,505,680.74 | 0 |

**187,805 charge lines reconcile row by row.** Comparison used multisets, preserving
repeated lines, across job number, job date, billing date, charge, party, branch,
LOB, income and expense at paise precision. The source/API empty-label convention
was normalized (blank source values appear as '(blank)' in dictionary labels).
Both source reports also pass their own grand-total validation.

This supersedes the prior absence of source-workbook verification for these two
specific imports. It does not certify the remaining NG FY2025 or NCS current-FY
originals. Their internal API/metadata reconciliations remain as recorded above.
The supplied SharePoint folder returned HTTP 403 to direct read access; that
restriction was not bypassed and no unrelated Microsoft credentials were used.

### Why the historical uploads cannot fill the billing gap

The actual emailed 2025 originals contain **Job Profit Analysis Report** with
**Basis: Job Date**, one row per job, and no Charge or billing Date columns.
They contain 23,823 NG job rows and 5,522 NCS job rows. Their January–March 2025
activity is job-dated, so those amounts cannot be inserted as January–March
billing-date charge lines. Existing billing-date source coverage remains the
correct disclosed limit until suitable charge-wise exports are supplied.

### Import-flow correction

- Added content-based detection of the known job-summary layout. Preview now
  explains that charge-wise detail with Billing Date and a From/to range is
  required. Ingestion records it as an unsupported JP import with the same clear
  message, instead of attempting to parse it as a Shipment Register.
- Summary uploads cannot overwrite active finance data, including when an upload
  attempts an approval override. Original source-reference metadata is retained.
- Preview and ingestion now share replacement-date validation. Job-date charge
  reports, missing billing dates and lines outside the declared billing range
  show needs_review in both paths, closing the 'ready in preview, held on upload'
  discrepancy.
- Valid shipment registers and valid billing-date charge reports keep their
  existing flow. Whitespace-normalized charge-detail titles are recognized.
- **48 Python regression checks pass**, including seven new layout, preservation,
  approval-override, end-of-day timestamp and preview/import parity checks. The four actual recovered
  workbook layouts also classify as expected.

### Salesperson source quality

25,273 of 47,424 shipment records have Administrator as salesperson; none have
a blank salesperson. Administrator assignments are retained as actual source values. An ERP job owner,
master-sales owner or another employee is not substituted without a documented
business mapping. The existing unassigned-sales warnings remain appropriate;
these source values are not a calculation defect.

## Source-scope decision — 9 November 2026 (IST)

The project owner has confirmed that the dashboard will continue using the **simple Job Profit Analysis Report (JPR), in its existing format and Job Date basis**. Charge-wise source workbooks are not required for this project. Do not pursue or request additional charge-wise workbooks through Gmail, SharePoint or other sources, and do not block finance/variance review or release readiness on their availability.

- Use the accepted simple JPR dataset and its existing company/LOB/job-level dimensions for booked income, expense and gross profit.
- Retain Job Date as the finance reporting basis. Do not describe Job Date as Billing Date or infer a billing-date range from it.
- Keep the existing source-coverage disclosure for missing historical months and any unmatched finance jobs. Missing Billing Date is not a blocker for the agreed JPR-based reporting scope.
- Any future charge-wise analysis would be a separate, explicitly requested scope; it is not part of the current delivery or acceptance criteria.
- Continue the finance/variance audit against the current JPR records, calculation definitions, permissions, exports and visual reconciliation. No source import or production data change is authorized by this decision.
