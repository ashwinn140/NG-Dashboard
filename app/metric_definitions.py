"""Auditable source-backed definitions for existing JPR KPIs.

This module is deliberately side-effect free. It does not query production data,
change ingestion, or alter the existing dashboard calculations.
"""
from dataclasses import asdict, dataclass, replace
from typing import Optional


@dataclass(frozen=True)
class MetricDefinition:
    id: str
    title: str
    meaning: str
    outcome: str
    report: str
    source_columns: tuple[str, ...]
    date_column: str
    formula: str
    aggregation: str
    exclusions: str
    caveat: str = ""
    readiness: str = "code_verified"

    def explain(self) -> str:
        parts = [
            self.title,
            "What it means: " + self.meaning,
            "Why it matters: " + self.outcome,
            "Source report: " + self.report,
            "Exact source columns: " + ", ".join(self.source_columns),
            "Calculation: " + self.formula,
            "Aggregation: " + self.aggregation,
            "Reporting date: " + self.date_column,
            "Exclusions and conditions: " + self.exclusions,
        ]
        if self.caveat:
            parts.append("Important limitation: " + self.caveat)
        return "\n".join(parts)

    def public_dict(self) -> dict:
        d = asdict(self)
        d["finance_required"] = self.id.startswith("profit.") or self.id.startswith("ops.rate_")
        ratios={'profit.margin','profit.cost_coverage','profit.biggest_customer','profit.matched_share','ops.invoiced_share','ops.rate_usable','ops.customer_concentration'}
        counts={'profit.jobs','profit.customers','profit.customers_80','profit.loss_customers','profit.rate_matched_count','profit.rows','profit.cost_not_booked_proxy','profit.billing_pending_proxy','profit.loss_making','profit.low_margin','profit.negative_income_rows','profit.intercompany_proxy'}
        d["unit"] = 'ratio' if self.id in ratios else 'INR per tonne' if self.id=='profit.air_yield' else 'INR per TEU' if self.id=='profit.ocean_yield' else 'INR' if self.id.startswith('profit.') and self.id not in counts else 'kg' if self.id=='ops.air_weight_kg' else 'tonnes' if self.id=='ops.air_weight' else 'TEU' if self.id=='ops.teu' else 'CBM' if self.id=='ops.volume' else 'days' if self.id in {'ops.lock_lag','ops.invoice_lag','ops.lock_invoice_lag','ops.oldest_open'} else 'INR per kg' if self.id in {'ops.rate_sell','ops.rate_buy','ops.rate_margin_kg'} else 'INR' if self.id=='ops.rate_margin' else 'count'
        d["version"] = globals().get("REGISTRY_VERSION", "2")
        finance_required = self.id.startswith("profit.") or self.id.startswith("ops.rate_")
        is_profit = self.id.startswith("profit.")
        mapped = {
            "Income (INR)": "profit_lines.income",
            "Expense (INR)": "profit_lines.expense",
            "Profit (INR)": "derived from profit_lines.income - profit_lines.expense; source value validated on import",
            "Job No.": "profit_lines.job_no",
            "Job Date": "profit_lines.job_date",
            "LOB": "profit_lines.lob",
            "Location": "profit_lines.branch",
            "Organization": "profit_lines.customer; blank values remain unassigned; no shipment-register fallback",
            "Shipment No": "shipments.shipment_no",
            "Shipment Date": "shipments.shipment_date",
            "Customer": "shipments.customer; blank values remain unassigned",
            "Branch": "shipments.branch; JPR Location maps to profit_lines.branch",
            "Shipper": "shipments.shipper",
            "Consignee": "shipments.consignee",
            "Job Owner": "shipments.job_owner",
            "Carrier": "shipments.carrier",
            "Airline": "shipments.carrier",
            "Shipping Line": "shipments.carrier",
            "Loading Port": "shipments.origin",
            "Discharge Port": "shipments.destination",
            "Origin": "shipments.origin",
            "Destination": "shipments.destination",
            "Gross Weight": "shipments.gross_wt",
            "Chargeable Wt": "shipments.chargeable_wt",
            "TEUs": "shipments.teus",
            "Volume": "shipments.volume",
            "Cargo Type": "shipments.cargo_type",
            "Consol Type": "shipments.consol_type",
            "Self/Agent Nomination (UDF)": "shipments.nomination",
            "Status": "shipments.status",
            "Operations Locked On": "shipments.ops_locked_on",
            "Financials Locked On": "shipments.fin_locked_on",
            "Invoice No. & Date": "shipments.extra; parsed into invoice reference count and first invoice date",
            "Billing Details": "shipments.extra; parsed into invoice references and dates",
            "Buy Rate (UDF)": "shipments.extra; parsed into buy rate and rate-quality flags",
            "Sell Rate (UDF)": "shipments.extra; parsed into sell rate and rate-quality flags",
            "Sales Person": "source-specific extra field in shipments or profit_lines",
            "Trade Lane": "shipments.extra or profit_lines.trade_lane, depending on source report",
            "Trade Lane Name": "shipments.extra",
            "Loading Country": "shipments.extra",
            "Discharge Country": "shipments.extra",
            "Origin Agent": "shipments.extra",
            "Destination Agent": "shipments.extra",
            "Overseas Agent": "shipments.extra",
            "Booking Thru": "shipments.extra",
            "Commodity": "profit_lines.commodity or source-specific extra field",
        }
        d["database_fields"] = {col: mapped.get(col, "Source mapping pending validation") for col in self.source_columns}
        d["identity"] = ["company", "lob", "job_no", "job_date"] if is_profit else ["company", "report_type", "shipment_no", "shipment_date"]
        d["permissions"] = "Server-scoped company and LOB access" + ("; finance access required" if finance_required else "")
        d["null_handling"] = "Metric-specific: zero recorded amounts remain zero; ratios are unavailable when required denominators are not positive. Blank customer buckets remain in company totals where defined but are excluded from named-customer counts and rankings. No cross-report fallback identity is inferred."
        d["validation"] = "Code mapping verified; independent accepted-source reconciliation pending"
        d["explanation"] = self.explain() + "\nIdentity: " + ", ".join(d["identity"]) + "\nMapped database fields: " + str(d["database_fields"]) + "\nAccess: " + d["permissions"] + "\nMissing values: " + d["null_handling"] + "\nValidation: " + d["validation"]
        return d


JPR = "Job Profit Analysis Report (Basis: Job Date)"
JOB_COLUMNS = ("Job No.", "Job Date", "LOB")
DEFINITIONS = {
    "profit.income": MetricDefinition(
        "profit.income", "Income", "Total income recorded in eligible JPR rows; this alone does not verify invoicing.",
        "Understand income recognized in the selected period.", JPR,
        ("Income (INR)",) + JOB_COLUMNS, "Job Date",
        "Sum of Income (INR) for eligible job rows.", "SUM; amounts in INR",
        "Only rows surviving current user permissions, filters and reporting window.",
        "Dashboard can optionally switch its profit time basis; the current frontend uses Job Date by default, but alternative date basis requires separate source validation."),
    "profit.expense": MetricDefinition(
        "profit.expense", "Expense", "Total expense recorded for eligible JPR jobs.",
        "Understand booked costs in the selected period.", JPR,
        ("Expense (INR)",) + JOB_COLUMNS, "Job Date",
        "Sum of Expense (INR) for eligible job rows.", "SUM; amounts in INR",
        "Only rows surviving current user permissions, filters and reporting window."),
    "profit.gp": MetricDefinition(
        "profit.gp", "Gross profit", "Income less expense recorded for eligible JPR jobs.",
        "Assess job-level profitability from booked income and costs.", JPR,
        ("Income (INR)", "Expense (INR)", "Profit (INR)") + JOB_COLUMNS,
        "Job Date", "SUM(Income (INR) - Expense (INR)); JPR validates Profit (INR) equals Income minus Expense.",
        "SUM; amounts in INR", "Only eligible JPR rows; no estimation of unbooked costs."),
    "profit.jobs": MetricDefinition(
        "profit.jobs", "Jobs", "Distinct eligible jobs represented in the JPR.",
        "Measure job coverage without counting duplicate records as separate jobs.", JPR,
        JOB_COLUMNS, "Job Date", "Count distinct job identifiers in the dashboard's filtered profit dataset; verify composite identity against the source.",
        "COUNT DISTINCT", "Only eligible JPR rows. Source rejects duplicate Job No. / Job Date / LOB within an import.",
        "Verify cross-company grouping and historical job identity against current dataset join before audit sign-off."),
    "profit.margin": MetricDefinition(
        "profit.margin", "Gross profit margin",
        "Gross profit as a share of recorded income for the selected JPR jobs.",
        "Assess profitability relative to income.", JPR,
        ("Income (INR)", "Expense (INR)") + JOB_COLUMNS, "Job Date",
        "If total income > 0: (total income - total expense) / total income; otherwise no percentage.",
        "RATIO OF SUMS, not average of individual job margins",
        "Eligible filtered rows only; the dashboard displays a dash when income is not positive."),
    "profit.cost_not_booked_proxy": MetricDefinition(
        "profit.cost_not_booked_proxy", "No costs recorded",
        "Jobs with positive aggregated income and exactly zero aggregated expense.",
        "Find jobs where cost completeness needs investigation.", JPR,
        ("Income (INR)", "Expense (INR)") + JOB_COLUMNS, "Job Date",
        "Per dashboard job: income > 0 and expense == 0; count qualifying jobs.",
        "COUNT DISTINCT dashboard jobs", "Uses the current frontend classification precedence.",
        "Zero recorded expense does not establish that no cost was incurred.",
        "business_validation_required"),
    "profit.loss_making": MetricDefinition(
        "profit.loss_making", "Loss-making jobs",
        "Jobs with recorded expense exceeding recorded income by more than INR 1.",
        "Identify recorded losses for review.", JPR,
        ("Income (INR)", "Expense (INR)") + JOB_COLUMNS, "Job Date",
        "After higher-priority job-status categories: income - expense < -1; count classified jobs.",
        "COUNT DISTINCT dashboard jobs", "The current status classification checks no-cost and no-income conditions first.",
        "A job can have a negative calculated result yet be assigned a different status by the existing precedence."),
    "profit.billing_pending_proxy": MetricDefinition(
        "profit.billing_pending_proxy", "Costs booked, no income recorded",
        "Jobs whose JPR expense is positive while income is zero or negative.",
        "Identify jobs needing investigation of income recognition or billing.", JPR,
        ("Income (INR)", "Expense (INR)") + JOB_COLUMNS, "Job Date",
        "For each dashboard job, if aggregated expense > 0 and aggregated income <= 0, classify as status 2; count qualifying jobs.",
        "COUNT DISTINCT jobs", "Current dashboard status precedence applies: cost-not-booked first, then this category.",
        "This financial proxy does NOT prove that an invoice has not been raised.",
        "business_validation_required"),
}


def get_metric(metric_id: str) -> Optional[MetricDefinition]:
    return DEFINITIONS.get(metric_id)


def all_metrics() -> list[dict]:
    return [m.public_dict() for m in DEFINITIONS.values()]

# Versioned additions verified against canonical app_prod.js and dataset.py.
REGISTRY_VERSION = '3'
for key,title,column,formula in [
 ('ops.shipments','Shipments','Shipment No','COUNT DISTINCT(company, report_type, Shipment No, Shipment Date)'),
 ('ops.air_weight','Air chargeable weight (tonnes)','Chargeable Wt','SUM(Chargeable Wt / 1000) for Air Export and Air Import registers'),
 ('ops.teu','Ocean TEUs','TEUs','SUM(TEUs) for Ocean Export and Ocean Import registers'),
 ('ops.volume','Volume (CBM)','Volume','SUM(Volume) for eligible register rows')]:
 DEFINITIONS[key]=MetricDefinition(key,title,'Operational measure from accepted Shipment Registers.','Understand the selected operational activity.','Shipment Register',(column,'Shipment No','Shipment Date'),'Shipment Date',formula,'COUNT DISTINCT' if key=='ops.shipments' else 'SUM','Authorized company and department scope; current filter and date window.','Configured source mapping; actual upload header validation remains pending.')
DEFINITIONS['profit.per_job']=MetricDefinition('profit.per_job','Profit per job','Booked gross profit divided by distinct jobs.','Assess average booked profitability.',JPR,('Income (INR)','Expense (INR)')+JOB_COLUMNS,'Job Date','SUM(Income - Expense) / COUNT DISTINCT(company, LOB, Job No., Job Date)','RATIO OF SUMS','Authorized filtered JPR jobs; blank when no jobs.')
from dataclasses import replace
DEFINITIONS['profit.jobs']=replace(DEFINITIONS['profit.jobs'],formula='COUNT DISTINCT(company, LOB, Job No., Job Date)',caveat='Composite identity verified in canonical frontend/app_prod.js; source-level reconciliation remains pending.')
DEFINITIONS['profit.income']=replace(DEFINITIONS['profit.income'],caveat='Current accepted job-summary reports use Job Date; billing date is unavailable and is not inferred.')
DEFINITIONS['profit.cost_coverage']=MetricDefinition('profit.cost_coverage','Jobs with cost booked','Share of eligible jobs with positive recorded expenses.','Assess recorded cost coverage.',JPR,('Expense (INR)',)+JOB_COLUMNS,'Job Date','COUNT DISTINCT jobs with Expense > 0 / COUNT DISTINCT jobs','RATIO OF DISTINCT COUNTS','Zero and negative expenses are not counted as positive cost coverage.')
DEFINITIONS['profit.expected_adjusted']=MetricDefinition('profit.expected_adjusted','Profit after expected costs','Booked GP less modeled costs for positive-income jobs with exactly zero recorded expense.','Estimate how profit could change as missing expenses are booked.',JPR,('Income (INR)','Expense (INR)')+JOB_COLUMNS,'Job Date','SUM(Income - Expense) - SUM(zero-expense positive job income * same-LOB benchmark expense/income ratio)','RATIO OF SUMS benchmark; SUM expected costs','Benchmark uses all authorized loaded positive-income/positive-expense jobs, ignoring selection dates; falls back to overall authorized ratio, then zero if no benchmark.','An estimate, not confirmed GP. Partially booked costs are not estimated; benchmarks can combine authorized companies.','code_verified_source_audit_pending')
DEFINITIONS['profit.expected_cost_only']=MetricDefinition('profit.expected_cost_only','Expected costs on jobs with none booked','Estimated expense for selected jobs with positive income and exactly zero recorded expense.','Identify the modeled cost exposure behind jobs with no cost recorded.',JPR,('Income (INR)','Expense (INR)')+JOB_COLUMNS,'Job Date','SUM(Income × benchmark expense/income ratio) for selected jobs where Income > 0 and Expense = 0. Benchmark ratio is calculated from all authorized loaded jobs with positive income and expense, grouped by LOB.','SUM expected cost in INR; benchmark is ratio of sums','Selected jobs only for the expected-cost total. Benchmark population ignores the current selection dates and uses all authorized loaded positive-income/positive-expense jobs; same-LOB ratio falls back to overall authorized ratio, then zero if no benchmark.','An estimate, not booked expense or confirmed liability. Partially booked costs are not estimated; benchmark can combine authorized companies.','code_verified_source_audit_pending')
for key,title,formula,columns in [
 ('ops.active_customers','Active customers','Count distinct named source customer names with at least the configured minimum number of selected shipments; blank customer bucket excluded',('Customer',)),
 ('ops.waiting_lock','Waiting for operations lock','Count shipments in Pending ops lock stage',('Operations Locked On','Financials Locked On')),
 ('ops.financials_open','Operations locked, financials open','Count shipments in Financials open stage',('Operations Locked On','Financials Locked On')),
 ('ops.old_open','Old open shipments','Count non-closed shipments older than configured oldDays, using the latest available operational date',('Shipment Date','Operations Locked On','Financials Locked On')),
 ('ops.oldest_open','Oldest open shipment (days)','MAX(latest operational date - Shipment Date) for non-closed shipments; zero if no open shipments',('Shipment Date','Operations Locked On','Financials Locked On')),
 ('ops.lock_lag','Days from ops lock to financial lock','Average(Financials Locked On - Operations Locked On) where both dates are recorded',('Operations Locked On','Financials Locked On')),
 ('ops.invoiced_share','Shipments invoiced','Count selected shipments with an invoice/billing reference / selected shipments',('Invoice No. & Date','Billing Details')),
 ('ops.invoice_lag','Days from shipment to first invoice','Average(first parsed invoice date - Shipment Date) where the invoice date is available',('Invoice No. & Date','Billing Details','Shipment Date')),
 ('ops.lock_invoice_lag','Days from ops lock to first invoice','Average(first parsed invoice date - Operations Locked On) where both dates are available',('Invoice No. & Date','Billing Details','Operations Locked On')),
 ('ops.operations_locked','Operations-locked shipments','Count shipment-register rows with an Operations Locked On date',('Operations Locked On',)),
 ('ops.locked_no_invoice','Locked but not invoiced','Count operations-locked shipments without an invoice/billing reference',('Invoice No. & Date','Billing Details','Operations Locked On')),
 ('ops.overdue_invoice','Old locked shipments without invoice reference','Count operations-locked shipments without invoice references beyond configured unbilledDays',('Invoice No. & Date','Billing Details','Operations Locked On'))]:
 DEFINITIONS[key]=MetricDefinition(key,title,'Operational indicator from accepted Shipment Registers.','Identify operational activity and records requiring review.','Shipment Register',columns+('Shipment No','Shipment Date'),'Shipment Date',formula,'COUNT / SUM / MEAN as defined','Preserves existing selected date scope or explicitly all-date scope; configured thresholds and latest-source aging date are disclosed.','Source invoice references do not prove accounting settlement; missing optional fields remain unavailable.')
for key,title,formula in [
 ('profit.customers','Customers','COUNT DISTINCT named source Organization names in eligible JPR rows; the (blank) bucket is excluded'),
 ('profit.customers_80','Customers making 80% of profit','Count largest positive-profit named customers until cumulative positive GP reaches 80% of positive GP for named customers; the (blank) bucket is excluded'),
 ('profit.biggest_customer','Biggest customer share','Largest named customer GP / total net GP, only when total net GP is positive; blank-customer GP remains in the total GP denominator'),
 ('profit.loss_customers','Loss-making customers','Count named customers with aggregate GP < 0; the (blank) bucket is excluded')]:
 DEFINITIONS[key]=MetricDefinition(key,title,'Customer-level grouping of recorded Job Profit Analysis amounts.','Assess customer concentration and profitability.',JPR,('Organization','Income (INR)','Expense (INR)')+JOB_COLUMNS,'Job Date',formula,'GROUP BY source Organization name','Customer rank page deliberately skips its own customer selection, retaining other filters.','Source names are the available identity; verified ERP customer codes are unavailable in the inspected JPR headers.')
for key,title,formula in [
 ('profit.air_yield','Air: profit per tonne','GP of matched air jobs / matched air chargeable tonnes'),
 ('profit.ocean_yield','Sea: profit per TEU','GP of matched ocean jobs / matched ocean TEUs'),
 ('profit.matched_share','Jobs matched to the register','Distinct matched JPR jobs / distinct eligible JPR jobs'),
 ('profit.best_dimension','Best selected dimension','Largest positive GP grouped by a nonblank selected source dimension value'),
 ('profit.rate_matched_count','Jobs compared','Count JPR jobs matched to air-export register records with usable rates'),
 ('profit.rate_matched_estimate','Estimated freight margin on matched jobs','Sum((Sell Rate - Buy Rate) * Chargeable Wt) once per matched JPR job'),
 ('profit.rate_matched_actual','Actual profit on matched jobs','Sum recorded income - expense on JPR jobs matched to air-export records with usable rates'),
 ('profit.rate_matched_difference','Actual minus estimated freight margin','Matched JPR GP - matched register freight-margin estimate')]:
 DEFINITIONS[key]=MetricDefinition(key,title,'Source-linked financial measure over eligible JPR jobs.','Inspect the source records and their recorded operational basis.',JPR,('Income (INR)','Expense (INR)')+JOB_COLUMNS,'Job Date',formula,'SUM / DISTINCT COUNT / RATIO as defined','Only unique company/LOB/date/job register matches; applicable selected dimension and rate policy.','Operational denominators come from matched registers; unmatched finance remains in general GP, not volume yields. Freight estimates exclude other charges.')
for key,title,formula in [
 ('ops.rate_air_exports','Air export shipments','Count air-export register records'),
 ('ops.rate_usable','With usable rates','Usable-rate air-export records / all selected air-export records'),
 ('ops.rate_sell','Average sell rate','SUM(Sell Rate * Chargeable Wt) / SUM(Chargeable Wt) for usable-rate air exports'),
 ('ops.rate_buy','Average buy rate','SUM(Buy Rate * Chargeable Wt) / SUM(Chargeable Wt) for usable-rate air exports'),
 ('ops.rate_margin_kg','Freight margin per kg','SUM((Sell Rate - Buy Rate) * Chargeable Wt) / SUM(Chargeable Wt)'),
 ('ops.rate_margin','Estimated freight margin','SUM((Sell Rate - Buy Rate) * Chargeable Wt) for usable-rate air exports'),
 ('ops.rate_below_buy','Selling below buy','Count usable-rate air-export records where Sell Rate < Buy Rate')]:
 DEFINITIONS[key]=MetricDefinition(key,title,'Estimated air-export freight economics from usable register rates.','Review pricing independently of booked JPR profit.','Shipment Register',('Buy Rate (UDF)','Sell Rate (UDF)','Chargeable Wt','Shipment No','Shipment Date'),'Shipment Date',formula,'COUNT / RATIO OF SUMS / SUM as defined','Positive weight and positive recognized INR rates within configured maximum; clean/text policy retained; foreign-currency/blank/lump values excluded.','Estimated freight only; financial permission required. Source rate text parsing is documented by the importer.')
DEFINITIONS['ops.air_weight_kg']=replace(DEFINITIONS['ops.air_weight'],id='ops.air_weight_kg',title='Air chargeable weight (kg)',formula='SUM(Chargeable Wt) for Air Export and Air Import registers')
DEFINITIONS['ops.invoiced_count']=MetricDefinition('ops.invoiced_count','Shipments invoiced by first invoice date','Count shipment records whose parsed first invoice date falls in the reporting window.','Compare invoicing activity on its own date basis.','Shipment Register',('Invoice No. & Date','Billing Details','Shipment No','Shipment Date'),'First parsed invoice date','COUNT DISTINCT shipment identities with a parsed first invoice date in the selected invoice window','COUNT DISTINCT','Other company/department/entity filters remain; source shipment date is not the reporting window for this metric.','Invoice references do not establish collection or settlement; unparseable invoice dates cannot contribute.')
DEFINITIONS['profit.low_margin']=MetricDefinition('profit.low_margin','Low-margin jobs','Jobs classified below the configured GP margin threshold after higher-priority financial statuses.','Identify margin conditions for review.',JPR,('Income (INR)','Expense (INR)')+JOB_COLUMNS,'Job Date','After no-cost, no-income and loss statuses: income > 0 and (income-expense)/income < configured low-margin threshold','COUNT DISTINCT','Preserves precedence and the existing INR 1 loss-rounding tolerance.','Recorded cost completeness affects this ratio.')
DEFINITIONS['profit.negative_income_rows']=MetricDefinition('profit.negative_income_rows','Negative income rows','JPR rows where recorded income is negative.','Review credits, reversals or other negative income.',JPR,('Income (INR)',)+JOB_COLUMNS,'Job Date','COUNT rows with Income (INR) < 0','COUNT','Eligible financial rows; this is not a verified document-type classification.','Negative income does not prove a credit note was issued.')
DEFINITIONS['profit.intercompany_proxy']=MetricDefinition('profit.intercompany_proxy','Company-name matched jobs','Jobs whose organization matches a configured alias of the other company.','Review potential intercompany activity.',JPR,('Organization',)+JOB_COLUMNS,'Job Date','Count eligible jobs flagged by configured other-company name aliases','COUNT DISTINCT','Name-based classification; do not infer group consolidation or elimination.','Reported company figures are combined without intercompany elimination.')
DEFINITIONS['ops.customer_concentration']=MetricDefinition('ops.customer_concentration','Top customers share','Share of selected operational activity attributable to the largest configured number of named customers; blank customer rows remain in the denominator but cannot rank.','Assess concentration of reported activity.','Shipment Register',('Customer','Shipment No','Shipment Date','Chargeable Wt','TEUs'),'Shipment Date','SUM(top N named-customer measure totals) / SUM(all selected measure totals, including unassigned customer rows)','RATIO OF GROUPED SUMS','Blank customer rows remain in the denominator but are excluded from named-customer rankings. Uses shipment count or the selected single-mode air-tonne/ocean-TEU measure.','Identity follows source names where customer codes are unavailable.')
for key,title in [('ops.period_new_customers','Customers only in current period'),('ops.period_absent_customers','Customers only in comparison period')]:
 DEFINITIONS[key]=MetricDefinition(key,title,'Named customers meeting the configured activity minimum in one selected period and having zero shipments in the other; blank customer bucket excluded.','Review changes in observed period activity.','Shipment Register',('Customer','Shipment No','Shipment Date'),'Shipment Date in the explicitly displayed current/comparison windows','COUNT distinct nonblank source customer names with period count >= activeMin and other period count = 0','COUNT DISTINCT CUSTOMER COHORT','The (blank) customer bucket is excluded. Uses all selected source records in both windows; source names where codes are unavailable.','This does not establish lifetime-new customers or confirmed lost business.')
DEFINITIONS['ops.invoice_reference_count']=MetricDefinition('ops.invoice_reference_count','Shipments with invoice references','Count selected shipments with an invoice or billing reference.','Review recorded invoicing references.','Shipment Register',('Invoice No. & Date','Billing Details','Shipment No','Shipment Date'),'Configured visual date basis; defaults to Shipment Date','COUNT shipment identities with invoice_count > 0','COUNT DISTINCT','Custom visual date basis and filters apply.','A reference does not prove payment; a parsed invoice date is not required unless that is the chosen date basis.')
DEFINITIONS['profit.rows']=replace(DEFINITIONS['profit.jobs'],id='profit.rows',title='Job records',formula='COUNT eligible accepted JPR rows',aggregation='COUNT ROWS')


# Explicitly version the source identity and blank-customer semantics used by the
# calculation/evidence API. These definitions must stay aligned with metric_execution.py.
DEFINITIONS['profit.jobs'] = replace(
    DEFINITIONS['profit.jobs'],
    formula='COUNT DISTINCT(company, LOB, Job No., Job Date)',
    caveat='Composite identity is company + LOB + Job No. + Job Date; independent source reconciliation remains pending.',
)
DEFINITIONS['profit.cost_coverage'] = replace(
    DEFINITIONS['profit.cost_coverage'],
    formula='COUNT DISTINCT jobs with Expense > 0 / COUNT DISTINCT eligible JPR jobs',
    aggregation='RATIO OF DISTINCT COUNTS',
    caveat='Both numerator and denominator use the same company/LOB/job/date identity; zero and negative expenses are not positive cost coverage.',
)
DEFINITIONS['profit.income'] = replace(
    DEFINITIONS['profit.income'],
    caveat='Current accepted job-summary reports use Job Date; billing date is unavailable and is not inferred.',
)
_REGISTER_MATCH_COLUMNS = ('Shipment No', 'Shipment Date')
DEFINITIONS['profit.air_yield'] = replace(
    DEFINITIONS['profit.air_yield'],
    source_columns=DEFINITIONS['profit.air_yield'].source_columns + ('Chargeable Wt',) + _REGISTER_MATCH_COLUMNS,
)
DEFINITIONS['profit.ocean_yield'] = replace(
    DEFINITIONS['profit.ocean_yield'],
    source_columns=DEFINITIONS['profit.ocean_yield'].source_columns + ('TEUs',) + _REGISTER_MATCH_COLUMNS,
)
DEFINITIONS['profit.matched_share'] = replace(
    DEFINITIONS['profit.matched_share'],
    source_columns=DEFINITIONS['profit.matched_share'].source_columns + _REGISTER_MATCH_COLUMNS,
)
_RATE_MATCH_COLUMNS = ('Buy Rate (UDF)', 'Sell Rate (UDF)', 'Chargeable Wt') + _REGISTER_MATCH_COLUMNS
for _metric_id in ('profit.rate_matched_count', 'profit.rate_matched_estimate', 'profit.rate_matched_actual', 'profit.rate_matched_difference'):
    DEFINITIONS[_metric_id] = replace(
        DEFINITIONS[_metric_id],
        source_columns=DEFINITIONS[_metric_id].source_columns + _RATE_MATCH_COLUMNS,
        caveat='Uses unique company/report-type/shipment-number/shipment-date matches; source rate parsing and independent financial reconciliation remain separate controls.',
    )
