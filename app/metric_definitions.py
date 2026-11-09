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
