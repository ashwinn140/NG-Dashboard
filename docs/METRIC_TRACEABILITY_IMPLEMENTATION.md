# NG Dashboard — metric traceability implementation contract (draft)

Status: development branch only; NOT deployed. Applies to Performance Dashboard and Customer 360.

## Non-negotiable behavior
1. Clicking any supported KPI or chart segment opens a right-side drawer with **all contributing authorized jobs**, not just a summary or paginated subset.
2. Drawer offers search, sorting, pagination, and an Excel export of the **entire authorized result set** (not only the visible page). Include filter summary, report period, data snapshot timestamp, source report, and reconciliation sheet.
3. Quick tooltip: human-readable business meaning and action. Expanded explanation: human-readable, copyable, including exact uploaded report name, exact original Excel headers, internal mapped fields, calculation/formula, date field, filter predicates, exclusions, distinctness and aggregation logic, refresh timestamp, and known limitations.
4. Never substitute invented source headers. If mapping is unverified, show "Definition awaiting source validation" and flag metric as not audit-ready.
5. Use a single server-owned metric definition registry for calculation and explanation metadata; do not independently hand-write frontend calculation descriptions.
6. Preserve existing metrics, comparisons and variance date windows while consolidating duplicate presentations.
7. Apply the same drawer, export, explanations, filter semantics and permission enforcement to Customer 360.

## Proposed metric registry interface
Each metric definition should expose:
- metric_id, version, display_name, business_meaning, business_outcome
- source_report_types[] and exact_original_headers[] (verified from ingest metadata)
- normalized_fields[], date_field, formula_expression_or_source_precomputed_field
- aggregation_type, distinct_key, filters, exclusions, null_policy, timezone
- drilldown_query_id, permission_scope, last_validated_at

## Audit and acceptance gates
- For a count of N distinct jobs, the export reconciliation sheet must report N unique eligible job keys, even when underlying source rows are repeated; retain detailed source rows separately if necessary.
- Chart segment, drawer query and export MUST reuse the same server-side predicates and snapshot identifier.
- Verify cross-company and LOB authorization on every API and Excel endpoint, including direct URL requests; money fields require financial permission.
- Confirm Customer 360 multi-select and partial-name matching use canonical entity keys while preserving original ERP values and exposing ambiguous matches for review.
- Never silently merge distinct organizations based on fuzzy names alone; record mapping provenance and allow manual overrides.
- Compare every existing metric and MoM/YoY variance against a baseline before UI consolidation.
- Test zero rows, duplicates, stale files, revised report column ordering, missing columns, negative GP, and date-boundary cases.
- Exports should use bounded streaming/async processing for large results, escape Excel formula-injection cells, and not expose unauthorized data.

## Build order
A. Inventory actual source schemas, ingest transformations, current metric queries, frontend visuals, and existing export endpoints.
B. Add registry and metric-definition validation tests.
C. Implement shared server-side drilldown and export query path.
D. Build reusable drawer and explanation UI.
E. Consolidate visuals and align Customer 360.
F. Reconciliation and permission regression suite.

## Out of scope
Report scheduler; production deployment; changes to ingestion schedule or historical data retention.
