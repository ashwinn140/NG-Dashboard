"""Admin actions that go beyond the processor: preview a profit file, undo the latest load, settings."""
from datetime import datetime
from sqlalchemy import select, update, delete, insert, func, and_, true
from . import config, profit as J, processor as P
from .db import imports, shipments, profit_lines, current_import, admin_log, settings


def log(engine, user, action, detail=""):
    with engine.begin() as c: c.execute(insert(admin_log).values(at=datetime.utcnow(), user=user, action=action, detail=str(detail)[:2000]))


def preview_any(engine, path: str, report_time: datetime | None = None, subject: str = "") -> dict:
    """What loading this file would do, without changing anything (registers and the job profit report)."""
    report_time = report_time or datetime.utcnow()
    layout = J.profit_layout(path)
    if layout == "charge_detail": return preview_profit(engine, path, report_time)
    if layout == "job_summary":
        return dict(kind="Job-level profit summary", report_type="JP", verdict="rejected", message=J.JOB_SUMMARY_MESSAGE)
    out = P.preview_file(engine, path, report_time, subject); out.setdefault("kind", "Shipment register"); out["kind"] = "Shipment register"; return out


def preview_profit(engine, path: str, report_time: datetime) -> dict:
    try: rep = J.read_profit(path)
    except P.ReportError as e: return dict(kind="Job profit report", verdict="rejected", message=str(e))
    sha = P.sha256_file(path); problems = J.validate_profit(rep); c = rep.company
    out = dict(kind="Job profit report", company=c, report_type="JP", covers_from=rep.range_from, covers_to=rep.range_to, basis=rep.basis, rows=len(rep.df), jobs=int(rep.df["Job No."].nunique()),
               income=round(float(rep.df["Income (INR)"].sum()), 2), expense=round(float(rep.df["Expense (INR)"].sum()), 2), verdict="ready", message="", notes=[])
    with engine.connect() as conn:
        dup = conn.execute(select(imports.c.id).where(imports.c.file_sha256 == sha, imports.c.status == "promoted")).first()
        overlap = and_(imports.c.range_from <= rep.range_to, imports.c.range_to >= rep.range_from) if rep.range_from else true()
        last = conn.execute(select(imports.c.id, imports.c.report_time).where(imports.c.company == c, imports.c.report_type == "JP", imports.c.status == "promoted", overlap).order_by(imports.c.report_time.desc())).first()
        held = conn.execute(select(func.count()).select_from(profit_lines).where(profit_lines.c.company == c, profit_lines.c.to_import.is_(None))).scalar()
    if dup: out.update(verdict="duplicate", message=f"Identical file already loaded as import {dup[0]}")
    elif last and report_time <= last.report_time: out.update(verdict="stale", message=f"A newer report for the same dates is already loaded ({last.report_time:%Y-%m-%d %H:%M})")
    elif problems: out.update(verdict="failed", message="; ".join(problems))
    elif J.replacement_issue(rep): out.update(verdict="needs_review", message=J.replacement_issue(rep))
    else:
        out["notes"].append(f"{len(rep.df):,} charge lines for {rep.range_from} to {rep.range_to}, {out['jobs']:,} jobs. Lines already held for other dates are left untouched.")
        if held and rep.range_from is None: out["notes"].append("The date range could not be read, so only the jobs in this file are compared.")
    return out


def undo_last_import(engine, import_id: int, by: str, reason: str) -> dict:
    """Takes back the latest load of a report: removes what it added and re-opens what it closed."""
    if config.replace_reports(): raise ValueError("Undo is unavailable in replacement mode because previous row versions are not kept. Upload a corrected current-period report instead.")
    if not reason.strip(): raise ValueError("Please give a reason.")
    with engine.begin() as conn:
        imp = conn.execute(select(imports).where(imports.c.id == import_id)).first()
        if not imp or imp.status != "promoted": raise ValueError("Only a loaded report can be undone.")
        newer = conn.execute(select(func.count()).select_from(imports).where(imports.c.company == imp.company, imports.c.report_type == imp.report_type, imports.c.status == "promoted", imports.c.id > import_id)).scalar()
        if newer: raise ValueError("Only the latest load of a report can be undone.")
        t = profit_lines if imp.report_type == "JP" else shipments
        removed = conn.execute(delete(t).where(t.c.from_import == import_id)).rowcount
        reopened = conn.execute(update(t).where(t.c.to_import == import_id).values(to_import=None, ended_reason=None)).rowcount
        conn.execute(update(imports).where(imports.c.id == import_id).values(status="undone", message=f"Undone by {by}: {reason}"[:1000]))
        if imp.report_type != "JP":
            prev = conn.execute(select(imports.c.id).where(imports.c.company == imp.company, imports.c.report_type == imp.report_type, imports.c.status == "promoted").order_by(imports.c.id.desc())).first()
            conn.execute(delete(current_import).where(current_import.c.company == imp.company, current_import.c.report_type == imp.report_type))
            if prev: conn.execute(insert(current_import).values(company=imp.company, report_type=imp.report_type, import_id=prev[0]))
    log(engine, by, "undo_import", f"import {import_id}: {reason} (removed {removed}, re-opened {reopened})")
    return dict(removed=removed, reopened=reopened)


DEFAULT_SETTINGS = {"history_years": "3", "fy_start_month": "4", "max_age_hours": "36", "alert_email": ""}


def get_settings(engine) -> dict:
    with engine.connect() as c: rows = dict(c.execute(select(settings.c.key, settings.c.value)).all())
    return {k: rows.get(k, v) for k, v in DEFAULT_SETTINGS.items()}


def put_settings(engine, vals: dict, by: str) -> dict:
    ok = {}
    for k, v in vals.items():
        if k not in DEFAULT_SETTINGS: continue
        v = str(v).strip()
        if k == "history_years" and not (v.isdigit() and 1 <= int(v) <= 10): raise ValueError("History years must be between 1 and 10.")
        if k == "fy_start_month" and not (v.isdigit() and 1 <= int(v) <= 12): raise ValueError("Financial year start month must be 1 to 12.")
        if k == "max_age_hours" and not (v.replace(".", "", 1).isdigit() and 1 <= float(v) <= 720): raise ValueError("Report age limit must be between 1 and 720 hours.")
        ok[k] = v
    with engine.begin() as c:
        for k, v in ok.items():
            c.execute(delete(settings).where(settings.c.key == k)); c.execute(insert(settings).values(key=k, value=v))
    log(engine, by, "settings", ok); return get_settings(engine)


def get_flag(engine, key: str, default: str = "") -> str:
    with engine.connect() as c: r = c.execute(select(settings.c.value).where(settings.c.key == key)).first()
    return r[0] if r else default


def set_flag(engine, key: str, value: str) -> None:
    with engine.begin() as c:
        c.execute(delete(settings).where(settings.c.key == key)); c.execute(insert(settings).values(key=key, value=value))

