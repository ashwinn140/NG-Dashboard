"""Database tables. Works on SQLite (local testing) and Postgres (Railway) with no code change."""
import os
from sqlalchemy import (JSON, Column, Date, DateTime, Float, ForeignKey, Index, Integer, MetaData,
                        String, Table, Text, UniqueConstraint, create_engine)

metadata = MetaData()

# One row per file received, whatever happened to it.
imports = Table(
    "imports", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("company", String(10), index=True), Column("report_type", String(4), index=True),
    Column("report_time", DateTime), Column("received_at", DateTime),
    Column("file_name", Text), Column("file_sha256", String(64), index=True), Column("subject", Text),
    Column("source_ref", Text),          # e.g. the Gmail message id
    Column("row_count", Integer), Column("status", String(20)),   # promoted / duplicate / stale / failed / needs_review
    Column("message", Text),
    Column("new_rows", Integer), Column("changed_rows", Integer), Column("ended_rows", Integer),
    Column("range_from", Date), Column("range_to", Date), Column("scope_branches", Text),   # what the file covers (from its title rows)
    Column("columns", Text),                    # JSON list of the report's column names (to spot added/removed columns)
    Column("file_path", Text),           # where the original file is archived (Drive / storage)
    Column("source", String(20)),               # email / manual
    Column("uploaded_by", Text),         # who uploaded it, for manual uploads
    Column("approved_by", Text), Column("override_reason", Text),   # for held reports someone approved
)

# Which import is "current" for each company + report.
current_import = Table(
    "current_import", metadata,
    Column("company", String(10), primary_key=True), Column("report_type", String(4), primary_key=True),
    Column("import_id", Integer, ForeignKey("imports.id")),
)

# Every shipment version ever seen. A row is "open" (present in the current report) while to_import is empty.
# Any past snapshot = versions with from_import <= N and (to_import empty or > N).
shipments = Table(
    "shipments", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("company", String(10)), Column("report_type", String(4)), Column("key", Text),
    Column("from_import", Integer), Column("to_import", Integer),
    Column("ended_reason", String(20)),         # changed / not_present   (never "completed")
    Column("row_hash", String(40)),
    Column("shipment_no", Text), Column("shipment_date", Date),
    Column("branch", Text), Column("customer", Text), Column("shipper", Text), Column("consignee", Text),
    Column("job_owner", Text), Column("carrier", Text),
    Column("origin", Text), Column("origin_code", Text), Column("destination", Text), Column("destination_code", Text),
    Column("gross_wt", Float), Column("chargeable_wt", Float), Column("teus", Float), Column("volume", Float),
    Column("cargo_type", Text), Column("consol_type", Text), Column("nomination", Text), Column("status", Text),
    Column("ops_locked_on", Date), Column("fin_locked_on", Date), Column("stage", Text),
    Column("extra", JSON),                      # every column of the original report, so any column can be a filter
)
Index("ix_ship_open", shipments.c.company, shipments.c.report_type, shipments.c.to_import)
Index("ix_ship_key", shipments.c.company, shipments.c.report_type, shipments.c.key)


def get_engine(url: str | None = None):
    url = url or os.environ.get("DATABASE_URL") or "sqlite:///data/dashboard.db"
    if url.startswith("postgres://"):                      # Railway style
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    engine = create_engine(url, future=True)
    metadata.create_all(engine)
    return engine


# Who did what in the admin portal (retention, approvals and so on).
admin_log = Table(
    "admin_log", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("at", DateTime), Column("user", String(120)), Column("action", String(60)), Column("detail", Text),
)


# Job profit snapshots. New-format rows contain one job total and are marked in extra.
# Legacy charge rows remain archived in this table but are excluded from job-based reporting.
profit_lines = Table(
    "profit_lines", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("company", String(10)), Column("key", Text),
    Column("from_import", Integer), Column("to_import", Integer), Column("ended_reason", String(20)), Column("row_hash", String(40)),
    Column("branch", Text), Column("lob", Text), Column("job_no", Text), Column("job_date", Date),
    Column("customer", Text), Column("charge", Text), Column("trans_no", Text), Column("trans_date", Date),
    Column("party", Text), Column("party_ref_no", Text), Column("party_ref_date", Date),
    Column("income", Float), Column("expense", Float), Column("profit", Float),
    Column("trade_lane", Text), Column("commodity", Text),
    Column("extra", JSON),
)
Index("ix_profit_open", profit_lines.c.company, profit_lines.c.to_import)
Index("ix_profit_job", profit_lines.c.company, profit_lines.c.job_no)


# ----------------------------------------------------------------------------- production tables
users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(200), unique=True, index=True), Column("user_id", String(60), unique=True, index=True),   # user_id: optional login name
    Column("name", String(120)), Column("role", String(20)),                # admin / management / operations / finance
    Column("companies", String(40)), Column("lobs", String(40)),            # e.g. "NG,NCS" and "AE,AI,OE,OI"; empty = all
    Column("finance", Integer, default=0),                                  # 1 = may see money (profit, billing, rates)
    Column("active", Integer, default=1), Column("pw_hash", String(300)), Column("pw_set_at", DateTime),
    Column("fail_count", Integer, default=0), Column("locked_until", DateTime), Column("created_at", DateTime), Column("last_login", DateTime),
)
sessions = Table(
    "sessions", metadata,
    Column("id", String(64), primary_key=True), Column("user_id", Integer, index=True), Column("csrf", String(64)),
    Column("created_at", DateTime), Column("expires_at", DateTime), Column("method", String(20)),
)
login_tokens = Table(                                                        # one-time email links and 6-digit codes (only hashes are kept)
    "login_tokens", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("email", String(200), index=True),
    Column("token_hash", String(64)), Column("code_hash", String(64)), Column("created_at", DateTime), Column("expires_at", DateTime),
    Column("used", Integer, default=0), Column("attempts", Integer, default=0),
)
uploads = Table(                                                             # every file received, queued for loading
    "uploads", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("file_name", Text), Column("path", Text),
    Column("source", String(20)), Column("subject", Text), Column("sender", Text), Column("gmail_id", Text),
    Column("report_time", DateTime), Column("received_at", DateTime), Column("uploaded_by", Text),
    Column("status", String(20), index=True), Column("result", JSON),       # queued / processing / done / failed
    Column("approve", Integer, default=0), Column("reason", Text),
)
org_master = Table(                                                          # Organization master (agent details), refreshed about every two weeks
    "org_master", metadata,
    Column("norm_key", String(200), primary_key=True), Column("company", String(10), primary_key=True), Column("name", String(300)), Column("country", String(100)),
    Column("sales", String(120)), Column("network", String(300)), Column("conf", String(300)),
    Column("contact", String(200)), Column("email", String(200)), Column("updated_at", DateTime),
)
prefs = Table(                                                               # per-user saved visuals, views and definitions
    "prefs", metadata,
    Column("user_id", Integer, primary_key=True), Column("name", String(40), primary_key=True), Column("value", JSON), Column("updated_at", DateTime),
)
settings = Table(
    "settings", metadata,
    Column("key", String(60), primary_key=True), Column("value", Text),
)

# Durable report scheduling. Definitions and run history are separate so a
# worker restart or a second replica cannot silently lose or duplicate a run.
report_schedules = Table(
    "report_schedules", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("owner_id", Integer, ForeignKey("users.id"), nullable=False, index=True),
    Column("report_id", String(60), nullable=False), Column("report_version", Integer, nullable=False),
    Column("definition", JSON, nullable=False),  # allowlisted, normalized scheduler contract
    Column("status", String(20), nullable=False, default="paused", index=True),
    Column("next_run_at", DateTime, index=True), Column("last_run_at", DateTime),
    Column("last_error", Text), Column("created_at", DateTime), Column("updated_at", DateTime),
)

report_runs = Table(
    "report_runs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("schedule_id", Integer, ForeignKey("report_schedules.id"), nullable=False, index=True),
    Column("scheduled_for", DateTime, nullable=False),
    Column("idempotency_key", String(160), nullable=False, unique=True),
    Column("status", String(24), nullable=False, default="queued", index=True),
    Column("attempts", Integer, nullable=False, default=0),
    Column("period_start", Date), Column("period_end_exclusive", Date),
    Column("freshness", JSON), Column("row_count", Integer), Column("file_size", Integer),
    Column("file_sha256", String(64)), Column("provider_status", String(32)),
    Column("provider_message_id", String(200)), Column("error_code", String(80)), Column("error_message", Text),
    Column("retry_after", DateTime, index=True), Column("started_at", DateTime),
    Column("finished_at", DateTime), Column("created_at", DateTime),
    UniqueConstraint("schedule_id", "scheduled_for", name="uq_report_run_schedule_instant"),
)
Index("ix_report_schedule_due", report_schedules.c.status, report_schedules.c.next_run_at)
Index("ix_report_run_claim", report_runs.c.status, report_runs.c.retry_after, report_runs.c.created_at)
