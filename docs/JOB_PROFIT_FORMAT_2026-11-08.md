# Job profit format replacement — 8 November 2026

The supported finance source is Job Profit Analysis Report, Basis: Job Date, for both NG and NCS. A file declares the company and date range in its title. Current and historical reports share the same parser and controls.

Columns are matched by normalized name, not position. Required headers: Location, LOB, Job No., Job Date, Organization, Income (INR), Expense (INR), Profit (INR). Optional fields are retained. Duplicate column names, duplicate job/date/LOB rows, invalid amounts, missing dates, out-of-range dates and incomplete totals are rejected. Each job profit and all three report grand totals reconcile before data promotion.

## Data transition

Legacy charge detail imports are rejected with a specific message. Existing charge records are retained for audit but excluded from job-based finance, preventing mixed-grain or duplicate totals. No historical billing-date totals are inferred or converted. Upload the new job-level reports for each company and historical period. Missing source coverage is disclosed while variances remain available from uploaded records.

Job Date drives finance filtering, summaries, comparisons, saved custom finance visual execution and exports. Charge/vendor pages, filters and visual-builder dimensions are removed. Existing unsupported saved visuals display an explanation; saved views omit obsolete filters and redirect the removed page to Profit overview.

Source job attributes take priority over register attributes. All customs, road and general job income/expense remains visible. Register-based weight metrics require a unique freight-register match; customs jobs cannot borrow forwarding weights. Operations and invoice-register reporting retain their original sources. The hourly Gmail trigger is unchanged.

## Validation

- Full supplied workbook: 19,918 NG jobs; income INR 3,724,348,164.38; expense INR 3,169,347,330.85; profit INR 555,000,833.53. No duplicate job/date/LOB keys; all three totals reconcile.
- Regression coverage includes reordered columns, NG/NCS isolation, historical/current date-scope isolation, obsolete-format rejection, bad totals/amounts/dates, source provenance and retained legacy-row exclusion.
- Dashboard rendering checks include finance and operations permissions, page rendering, group totals, custom visuals and exports.
