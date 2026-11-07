"""Settings you may need to change. Everything else reads from here."""
import os


def replace_reports() -> bool:
    """Opt-in replacement; existing installations keep version history by default."""
    mode = os.environ.get("REPORT_STORAGE_MODE", "versioned").strip().lower()
    if mode not in ("versioned", "replace"):
        raise ValueError("REPORT_STORAGE_MODE must be versioned or replace")
    return mode == "replace"

# Company name printed in row 1 of each report  ->  short code used in the app.
COMPANIES = {
    "new globe logistik llp": "NG",
    "neutral consolidation services llp": "NCS",
}
COMPANY_LABELS = {"NG": "New Globe", "NCS": "Neutral Consolidation"}

# Text inside the brackets of row 2, e.g. "Shipment Register(Air Export)"  ->  report code.
REPORT_TYPES = {
    "air export": "AE",
    "air import": "AI",
    "sea export": "OE",
    "sea import": "OI",
}
REPORT_LABELS = {"AE": "Air Export", "AI": "Air Import", "OE": "Sea Export", "OI": "Sea Import", "JP": "Job Profit"}

# A shipment is identified by these two columns together (Shipment No alone repeats in the ERP).
KEY_COLUMNS = ("Shipment No", "Shipment Date")

# A report missing any of these columns is rejected.
REQUIRED_COLUMNS = ("Shipment No", "Shipment Date", "Branch", "Customer", "Status", "Job Owner")

# If a new report has this much fewer rows than the current one, it is held for review
# instead of replacing the current data (protects against partial or filtered reports).
MAX_ROW_DROP = 0.10

# Standard field -> possible column names in the ERP export (first match wins).
# Every other column is still stored (in "extra") so any column can be used as a filter.
SOURCE_COLUMNS = {
    "shipment_no": ["Shipment No"], "shipment_date": ["Shipment Date"],
    "branch": ["Branch"], "customer": ["Customer"], "shipper": ["Shipper"], "consignee": ["Consignee"],
    "job_owner": ["Job Owner"], "carrier": ["Airline", "Shipping Line"],
    "origin": ["Loading Port"], "destination": ["Discharge Port"],
    "gross_wt": ["Gross Weight"], "chargeable_wt": ["Chargeable Wt"], "teus": ["TEUs"], "volume": ["Volume"],
    "cargo_type": ["Cargo Type"], "consol_type": ["Consol Type"],
    "nomination": ["Self/Agent Nomination (UDF)"], "status": ["Status"],
    "ops_locked_on": ["Operations Locked On"], "fin_locked_on": ["Financials Locked On"],
}
NUMERIC_FIELDS = ("gross_wt", "chargeable_wt", "teus", "volume")
DATE_FIELDS = ("shipment_date", "ops_locked_on", "fin_locked_on")

# Source columns holding dates (read as real dates even if the ERP exports them as text, day first).
DATE_FIELDS_SOURCE = ("Shipment Date", "Operations Locked On", "Financials Locked On")

# The ERP's email subject looks like "Shipment Register - Ocean Export - NGL". It is used only as a cross-check
# against what is inside the file: a mismatch holds the file for review. A subject that cannot be read is not an error.
SUBJECT_COMPANIES = {"ngl": "NG", "new globe": "NG", "ncs": "NCS", "neutral consolidation": "NCS"}
SUBJECT_REPORTS = {"air export": "AE", "air import": "AI", "ocean export": "OE", "sea export": "OE", "ocean import": "OI", "sea import": "OI"}

# Job profit analysis ("Charge wise Detail"). Columns are read by name, so their order never matters and extra columns are kept.
PROFIT_REQUIRED = ("Location", "LOB", "Job No.", "Charge", "Income (INR)", "Expense (INR)")
PROFIT_TOLERANCE = 1.0          # rupees: how far the lines may differ from the report's own grand total before the file is rejected
