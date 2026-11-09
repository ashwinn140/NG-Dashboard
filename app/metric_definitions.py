"""Auditable source-backed definitions for existing JPR KPIs.

This module is deliberately side-effect free. It does not query production data,
change ingestion, or alter the existing dashboard calculations.
"""
from dataclasses import asdict, dataclass
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
        d["explanation"] = self.explain()
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
        "This is the existing frontend proxy labelled 'Billing pending'; it does NOT prove that an invoice has not been raised.",
        "business_validation_required"),
}


def get_metric(metric_id: str) -> Optional[MetricDefinition]:
    return DEFINITIONS.get(metric_id)


def all_metrics() -> list[dict]:
    return [m.public_dict() for m in DEFINITIONS.values()]

# Versioned additions verified against canonical app_prod.js and dataset.py.
REGISTRY_VERSION = '2'
for key,title,column,formula in [
 ('ops.shipments','Shipments','Shipment No','COUNT DISTINCT(company, department, Shipment No, Shipment Date)'),
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
