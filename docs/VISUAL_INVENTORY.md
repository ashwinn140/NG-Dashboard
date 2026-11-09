# Visual inventory scope and decisions

`VISUAL_INVENTORY.csv` inventories literal KPI/card constructions in canonical production code, including source line references. Dynamic labels, D3 marks and table-only interfaces require the supplementary runtime audit; this static list is not proof of universal drill-down coverage.

Customer360: selection builder; shipment, financial-job, income, cost, GP, margin cards; three-interval activity/GP chart; market ranks; mode ranks; counterparty network; profitability exceptions; lock/invoice status; searchable paginated job table; source drawer; saved views. Source-specific AND/OR filters and independent Shipment Date/Job Date remain. Explicit origin/destination agents are preserved.

Opportunity Finder: admin-only whitespace candidates; full result list (former 200-row truncation removed); company/source coverage and empty-state explanation. It is not an inactivity/lost-business report. No GP/revenue opportunity value is inferred. Composite shipment identity now includes shipment date when counting repeated shipment numbers.

Administration: overview, users, ingestion/held imports, historical uploads, freshness, reconciliation coverage, source readiness, settings/retention. These are operational/administrative evidence; not all can meaningfully drill into jobs (e.g. user counts). Permissions retained.

Consolidation decision: retain context-specific leadership and finance totals; removing those would remove management visibility. Reuse one explanation/evidence/export UI across both dashboard pages rather than creating duplicate implementations. No existing metric removed. Further per-visual redesign remains pending verification.
