"""Reads an ERP shipment register, checks it, and loads it as a new snapshot.

Rules (all enforced here, in this order):
  1. The same file twice            -> recorded as "duplicate", nothing changes.
  2. A report older than the current -> recorded as "stale", never replaces newer data.
  3. Missing key columns / bad keys / bad dates -> "failed", current data stays as it was.
  4. Far fewer rows than the current report -> "needs_review", current data stays until an admin approves.
  5. Otherwise "promoted": new / changed / no-longer-present shipments are applied in ONE transaction.
A shipment that disappears from a report is marked "not_present" - never "completed".

Robust to the ERP changing its export:
  * Column ORDER never matters (columns are read by name).
  * EXTRA columns never matter: they are stored, and adding or removing one is never counted as a change.
  * Header case / spacing differences are tolerated ("job  owner" = "Job Owner").
  * Blank columns, blank rows and footer/total rows are ignored.
  * Dates may be real Excel dates or text such as 05/11/2026 (day first).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, replace
from datetime import date, datetime

import pandas as pd
from sqlalchemy import and_, bindparam, delete, func, insert, or_, select, text, true, update

from . import config
from .db import admin_log, current_import, imports, shipments, settings


class ReportError(Exception):
    """The file is not a recognisable shipment register."""


@dataclass
class Register:
    company: str
    report_type: str
    df: pd.DataFrame
    title: str
    dup_cols: list = field(default_factory=list)      # repeated headers such as Unit, Unit.1 (position-dependent)
    dropped_rows: int = 0                               # blank / footer rows ignored
    range_from: date | None = None                      # the dates this report covers, read from its title rows
    range_to: date | None = None
    branches: list | None = None                        # the branches this report covers, if the title lists them
    range_source: str = "title"                         # "title" or "data" (fallback: earliest and latest shipment date)

    @property
    def hash_cols(self):
        return [c for c in self.df.columns if c not in self.dup_cols]


# ---------------------------------------------------------------- reading
def _hnorm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


_KNOWN = {}
for _n in (list(config.REQUIRED_COLUMNS) + list(config.KEY_COLUMNS) + [c for cs in config.SOURCE_COLUMNS.values() for c in cs]):
    _KNOWN[_hnorm(_n)] = _n


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _cell(v) -> str:
    """One Excel cell as a stable text value (so the same data always gives the same text)."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return ""
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.strftime("%Y-%m-%d") if (v.hour, v.minute, v.second) == (0, 0, 0) else v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else f"{v:.6f}".rstrip("0").rstrip(".")
    return str(v).strip()


def _to_dates(s: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    return pd.to_datetime(s, errors="coerce", dayfirst=True, format="mixed")


def clean_columns(df: pd.DataFrame):
    """Tidy headers; ignore empty unnamed columns; flag position-dependent repeated headers."""
    keep = [not (str(c).startswith("Unnamed:") and df[c].isna().all()) for c in df.columns]
    df = df.loc[:, keep]
    names, seen = [], set()
    for c in df.columns:
        c2 = re.sub(r"\s+", " ", str(c)).strip()
        canon = _KNOWN.get(_hnorm(c2))
        name = canon if (canon and canon not in seen) else c2
        names.append(name)
        seen.add(name)
    df = df.copy()
    df.columns = names
    dup = []
    for c in df.columns:
        m = re.match(r"^(.*)\.(\d+)$", c)
        if m and m.group(1) in df.columns:
            dup.append(c)
    return df, dup


def read_register(path: str) -> Register:
    """Identify company + report type from the title rows, then read the table."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    head, hdr_idx = [], None
    for i, row in enumerate(wb.worksheets[0].iter_rows(min_row=1, max_row=12, values_only=True)):
        vals = [c for c in row if c is not None]
        if any(_hnorm(v) == "shipmentno" for v in vals):
            hdr_idx = i
            break
        head.append(vals)
    wb.close()
    if hdr_idx is None:
        raise ReportError("Header row ('Shipment No') not found in the first 12 rows")
    company_text = str(head[0][0]).strip() if head and head[0] else ""
    company = config.COMPANIES.get(re.sub(r"\s+", " ", company_text).lower())
    if not company:
        raise ReportError(f"Unknown company in title row: '{company_text}'")
    title = str(head[1][0]).strip() if len(head) > 1 and head[1] else ""
    m = re.search(r"\(([^)]*)\)", title)
    report = config.REPORT_TYPES.get(m.group(1).strip().lower()) if m else None
    if not report:
        raise ReportError(f"Unknown report type in title row: '{title}'")
    df, dup = clean_columns(pd.read_excel(path, header=hdr_idx))
    for col in config.DATE_FIELDS_SOURCE:
        if col in df.columns:
            df[col] = _to_dates(df[col])
    dropped = 0
    if "Shipment No" in df.columns and "Shipment Date" in df.columns:
        no = df["Shipment No"].map(_cell)
        # blank lines and "Total" / "Grand total" footers carry no shipment date; a real shipment with no date still fails loudly
        blank = df["Shipment Date"].isna() & ((no == "") | no.str.lower().str.match(r"^(grand\s+)?total"))
        dropped = int(blank.sum())
        df = df[~blank].reset_index(drop=True)
    txt = str(head[2][0]) if len(head) > 2 and head[2] else ""
    rf = rt = None
    m2 = re.search(r"Date\s*Range\s*:\s*(\d{1,2}-[A-Za-z]{3}-\d{4})\s*To\s*(\d{1,2}-[A-Za-z]{3}-\d{4})", txt, re.I)
    if m2:
        try:
            rf, rt = (datetime.strptime(x, "%d-%b-%Y").date() for x in m2.groups())
        except ValueError:
            rf = rt = None
    source = "title"
    if rf is None and "Shipment Date" in df.columns and df["Shipment Date"].notna().any():
        rf, rt, source = df["Shipment Date"].min().date(), df["Shipment Date"].max().date(), "data"
    mb = re.search(r"Branch\s*:\s*([^\n]+)", txt, re.I)
    branches = [x.strip() for x in mb.group(1).split(",") if x.strip()] if mb else None
    return Register(company, report, df, title, dup, dropped, rf, rt, branches, source)


# ---------------------------------------------------------------- checking
def validate(df: pd.DataFrame) -> list[str]:
    problems = []
    missing = [c for c in config.REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return [f"Missing required columns: {', '.join(missing)}"]
    if len(df) == 0:
        return ["The report has no rows"]
    no = df["Shipment No"].map(_cell)
    dt = pd.to_datetime(df["Shipment Date"], errors="coerce")
    if (no == "").any():
        problems.append(f"{int((no == '').sum())} rows have no Shipment No")
    if dt.isna().any():
        problems.append(f"{int(dt.isna().sum())} rows have a missing or unreadable Shipment Date")
    if not problems:
        keys = no + "|" + dt.dt.strftime("%Y-%m-%d")
        if keys.duplicated().any():
            problems.append(f"{int(keys.duplicated().sum())} rows repeat the same Shipment No + Shipment Date")
    return problems


# ---------------------------------------------------------------- standardising
def standardise(reg: Register) -> list[dict]:
    """One dict per shipment: key, standard fields, hash and every original column."""
    cells = reg.df.map(_cell)
    cols = list(cells.columns)
    pick = {f: next((c for c in cands if c in cols), None) for f, cands in config.SOURCE_COLUMNS.items()}
    port_code = re.compile(r"^\(([A-Za-z0-9]{5})\)")
    skip = set(reg.dup_cols)
    out_rows = []
    for rec in cells.to_dict("records"):
        extra = {k: v for k, v in rec.items() if v != ""}
        row = {f: (rec[c] if c else "") for f, c in pick.items()}
        for f in config.NUMERIC_FIELDS:
            try:
                row[f] = float(row[f]) if row[f] != "" else None
            except ValueError:
                row[f] = None
        for f in config.DATE_FIELDS:
            row[f] = datetime.strptime(row[f][:10], "%Y-%m-%d").date() if row[f] else None
        for side in ("origin", "destination"):
            m = port_code.match(row[side])
            row[side + "_code"] = m.group(1).upper() if m else ""
        row["stage"] = ("Pending ops lock" if not row["ops_locked_on"]
                        else "Financials open" if not row["fin_locked_on"] else "Closed")
        row["key"] = f"{row['shipment_no']}|{row['shipment_date']:%Y-%m-%d}"
        hash_src = {k: v for k, v in extra.items() if k not in skip}
        row["row_hash"] = hashlib.sha1(json.dumps(hash_src, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        row["extra"] = extra
        out_rows.append(row)
    return out_rows


# ---------------------------------------------------------------- subject cross-check
def parse_subject(subject: str):
    """Read company and report from a subject such as 'Shipment Register - Ocean Export - NGL'. Returns (company, report); either may be None."""
    low = re.sub(r"\s+", " ", (subject or "").lower())
    report = next((code for phrase, code in sorted(config.SUBJECT_REPORTS.items(), key=lambda kv: -len(kv[0])) if phrase in low), None)
    company = next((code for phrase, code in sorted(config.SUBJECT_COMPANIES.items(), key=lambda kv: -len(kv[0])) if re.search(r"\b" + re.escape(phrase) + r"\b", low)), None)
    return company, report


def _subject_problem(reg: "Register", subject: str):
    """None if the subject agrees with the file (or cannot be read); otherwise a message describing the mismatch."""
    company, report = parse_subject(subject)
    bad = []
    if company and company != reg.company:
        bad.append(f"company {config.COMPANY_LABELS[company]} in the subject but {config.COMPANY_LABELS[reg.company]} in the file")
    if report and report != reg.report_type:
        bad.append(f"report {config.REPORT_LABELS[report]} in the subject but {config.REPORT_LABELS[reg.report_type]} in the file")
    return ("Subject and file disagree: " + "; ".join(bad) + ". Held for review") if bad else None


# ---------------------------------------------------------------- deciding and loading
def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _current(conn, c, t):
    return conn.execute(
        select(imports.c.id, imports.c.report_time, imports.c.row_count, imports.c.columns)
        .join(current_import, current_import.c.import_id == imports.c.id)
        .where(current_import.c.company == c, current_import.c.report_type == t)).first()


def _plan(conn, reg: Register, rows: list[dict], cur) -> dict:
    """Work out exactly what loading this report would do (writes nothing)."""
    c, t = reg.company, reg.report_type
    open_rows = _open_rows(conn, reg)
    old = {r.key: (r.id, r.row_hash) for r in open_rows}
    in_scope_ids = {r.key: r.id for r in open_rows if _in_scope(reg, r.shipment_date, r.branch)}
    prev_cols = set(json.loads(cur.columns)) if cur is not None and cur.columns else None
    new_cols = set(reg.hash_cols)
    added = sorted(new_cols - prev_cols) if prev_cols is not None else []
    removed = sorted(prev_cols - new_cols) if prev_cols is not None else []
    new_keys = {r["key"] for r in rows}
    to_insert, changed_ids, inplace, differing = [], [], [], []
    n_new = n_changed = 0
    for r in rows:
        prev = old.get(r["key"])
        if prev is None:
            n_new += 1
            to_insert.append(r)
        elif prev[1] != r["row_hash"]:
            differing.append((r, prev[0]))
    if differing and (added or removed):
        # The column set changed: only compare the columns both reports have. A new or dropped column is not a change.
        common = prev_cols & new_cols
        old_extra = {}
        for chunk in _chunks([i for _, i in differing], 500):
            for row in conn.execute(select(shipments.c.id, shipments.c.extra).where(shipments.c.id.in_(chunk))):
                old_extra[row.id] = row.extra or {}
        for r, oid in differing:
            a, b = old_extra.get(oid, {}), r["extra"]
            if all(a.get(k, "") == b.get(k, "") for k in common):
                inplace.append({"b_id": oid, "b_extra": b, "b_hash": r["row_hash"]})
            else:
                n_changed += 1
                changed_ids.append(oid)
                to_insert.append(r)
    else:
        for r, oid in differing:
            n_changed += 1
            changed_ids.append(oid)
            to_insert.append(r)
    ended_ids = [i for k, i in in_scope_ids.items() if k not in new_keys]   # only shipments this report was supposed to contain
    return dict(old_count=len(old), existing_ids={k: v[0] for k, v in old.items()}, to_insert=to_insert, changed_ids=changed_ids, ended_ids=ended_ids, inplace=inplace,
                new=n_new, changed=n_changed, ended=len(ended_ids), added=added, removed=removed)


def _notes(reg: Register, plan: dict | None, subject: str = "") -> str:
    bits = []
    if subject and parse_subject(subject) == (None, None):
        bits.append("Subject not recognised, so it was not cross-checked")
    if plan and plan["added"]:
        bits.append("Columns added: " + ", ".join(plan["added"][:15]) + (" ..." if len(plan["added"]) > 15 else ""))
    if plan and plan["removed"]:
        bits.append("Columns removed: " + ", ".join(plan["removed"][:15]) + (" ..." if len(plan["removed"]) > 15 else ""))
    if reg.range_source == "data":
        bits.append("Date range not found in the title rows; the earliest and latest shipment dates were used")
    if reg.dropped_rows:
        bits.append(f"{reg.dropped_rows} blank or footer rows ignored")
    return "; ".join(bits)


def _in_scope(reg: Register, d, branch) -> bool:
    """Is a shipment inside what this report covers (its dates and branches)? Only those can be judged 'no longer present'."""
    if reg.range_from and d is not None and (d < reg.range_from or d > reg.range_to):
        return False
    if reg.branches and (branch or "").strip().lower() not in {b.lower() for b in reg.branches}:
        return False
    return True


def _open_rows(conn, reg: Register):
    return conn.execute(select(shipments.c.id, shipments.c.key, shipments.c.row_hash, shipments.c.shipment_date, shipments.c.branch).where(
        shipments.c.company == reg.company, shipments.c.report_type == reg.report_type, shipments.c.to_import.is_(None))).all()


def historical_freeze(conn, ranges, today: date | None = None):
    """Previously loaded past periods are static; missing periods can be seeded.

    Uses the same financial-year start setting as the dashboard. Does not delete
    or age out historical rows when the FY changes.
    """
    month = conn.execute(select(settings.c.value).where(settings.c.key == "fy_start_month")).scalar()
    month = int(month or 4)
    today = today or date.today()
    fy = lambda d: d.year - int(d.month < month)
    cutoff = date(fy(today), month, 1)
    covered = [(a, b) for a, b in ranges if a is not None and b is not None]
    return cutoff, lambda d: d is not None and d < cutoff and any(a <= d <= b for a, b in covered)


def _freeze_shipment_history(conn, reg: Register, plan: dict):
    if not config.static_history():
        return plan
    held = _open_rows(conn, reg)
    incoming_branches = {b.lower() for b in reg.branches} if reg.branches else None
    ranges = []
    for previous in conn.execute(select(imports.c.range_from, imports.c.range_to, imports.c.scope_branches).where(
            imports.c.company == reg.company, imports.c.report_type == reg.report_type, imports.c.status == "promoted")):
        old_branches = {b.lower() for b in json.loads(previous.scope_branches)} if previous.scope_branches else None
        if old_branches is None or (incoming_branches is not None and incoming_branches <= old_branches):
            ranges.append((previous.range_from, previous.range_to))
    cutoff, frozen = historical_freeze(conn, ranges)
    protected = {r.id for r in held if r.shipment_date and r.shipment_date < cutoff}
    plan["to_insert"] = [r for r in plan["to_insert"]
                         if plan["existing_ids"].get(r["key"]) not in protected
                         and (r["key"] in plan["existing_ids"] or not frozen(r["shipment_date"]))]
    plan["changed_ids"] = [i for i in plan["changed_ids"] if i not in protected]
    plan["ended_ids"] = [i for i in plan["ended_ids"] if i not in protected]
    plan["inplace"] = [r for r in plan["inplace"] if r["b_id"] not in protected]
    plan["new"] = sum(r["key"] not in plan["existing_ids"] for r in plan["to_insert"])
    plan["changed"] = len(plan["changed_ids"])
    plan["ended"] = len(plan["ended_ids"])
    return plan


def _decide(conn, reg: Register, file_sha: str, report_time: datetime, approve_review: bool, subject: str = ""):
    """Apply rules 1-4. Returns (status, message, current_row, rows, plan)."""
    c, t = reg.company, reg.report_type
    cutoff = config.history_start()
    if cutoff and reg.range_to and reg.range_to < cutoff:
        return "outside_history", f"Report predates the retained dashboard history ({cutoff}); original file retained", None, None, None
    dup = conn.execute(select(imports.c.id).where(imports.c.file_sha256 == file_sha, imports.c.status == "promoted")).first()
    if dup:
        return "duplicate", f"Identical file already loaded as import {dup[0]}", None, None, None
    cur = _current(conn, c, t)
    ov = conn.execute(select(imports.c.id, imports.c.report_time).where(
        imports.c.company == c, imports.c.report_type == t, imports.c.status == "promoted",
        or_(imports.c.range_from.is_(None), and_(imports.c.range_from <= reg.range_to, imports.c.range_to >= reg.range_from)) if reg.range_from else true())
        .order_by(imports.c.report_time.desc())).first()
    if ov and report_time <= ov.report_time:
        return "stale", f"Report time {report_time:%Y-%m-%d %H:%M} is not newer than the latest report for the same dates ({ov.report_time:%Y-%m-%d %H:%M})", cur, None, None
    if not approve_review:
        mismatch = _subject_problem(reg, subject)
        if mismatch:
            return "needs_review", mismatch, cur, None, None
    problems = validate(reg.df)
    if problems:
        return "failed", "; ".join(problems), cur, None, None
    held = sum(1 for r in _open_rows(conn, reg) if _in_scope(reg, r.shipment_date, r.branch))
    if held and not approve_review:
        drop = (held - len(reg.df)) / held
        if drop > config.MAX_ROW_DROP:
            return "needs_review", f"{len(reg.df)} rows vs {held} currently held for the same dates and branches ({drop:.0%} fewer): held for review", cur, None, None
    rows = standardise(reg)
    if config.replace_reports() and any(not _in_scope(reg, r["shipment_date"], r["branch"]) for r in rows):
        return "failed", "A shipment falls outside the report's dates or branches; existing data was kept", cur, None, None
    return "ok", "", cur, rows, _freeze_shipment_history(conn, reg, _plan(conn, reg, rows, cur))


def _record(conn, company, report_type, **values):
    values.setdefault("received_at", datetime.utcnow())
    return conn.execute(insert(imports).values(company=company, report_type=report_type, **values)).inserted_primary_key[0]


def process_register(engine, reg: Register, file_name: str, file_sha: str, report_time: datetime, source_ref: str = "",
                     approve_review: bool = False, file_path: str = "", source: str = "email", uploaded_by: str = "",
                     approved_by: str = "", override_reason: str = "", subject: str = "") -> dict:
    """Run the full rule set. Returns {import_id, status, message, new, changed, ended}."""
    cutoff = config.history_start()
    if cutoff and reg.range_from and reg.range_from < cutoff and reg.range_to and reg.range_to >= cutoff:
        reg = replace(reg, df=reg.df[pd.to_datetime(reg.df["Shipment Date"]) >= pd.Timestamp(cutoff)].copy(), range_from=cutoff)
    c, t = reg.company, reg.report_type
    base = dict(report_time=report_time, file_name=file_name, file_sha256=file_sha, source_ref=source_ref, row_count=len(reg.df),
                range_from=reg.range_from, range_to=reg.range_to, scope_branches=json.dumps(reg.branches) if reg.branches else None,
                file_path=file_path, source=source, uploaded_by=uploaded_by, approved_by=approved_by, override_reason=override_reason, subject=subject)
    with engine.begin() as conn:
        status, msg, cur, rows, plan = _decide(conn, reg, file_sha, report_time, approve_review, subject)
        if status != "ok":
            return dict(import_id=_record(conn, c, t, status=status, message=msg, **base), status=status, message=msg)
        note = _notes(reg, plan, subject)
        import_id = _record(conn, c, t, status="promoted", message=note, columns=json.dumps(reg.hash_cols), **base)
        replacing = config.replace_reports()
        for ids, reason in (() if replacing else ((plan["changed_ids"], "changed"), (plan["ended_ids"], "not_present"))):
            for chunk in _chunks(ids, 500):
                conn.execute(update(shipments).where(shipments.c.id.in_(chunk)).values(to_import=import_id, ended_reason=reason))
        if plan["inplace"]:      # same business data, only the column set changed: refresh stored columns without a new version
            conn.execute(update(shipments).where(shipments.c.id == bindparam("b_id")).values(extra=bindparam("b_extra"), row_hash=bindparam("b_hash")), plan["inplace"])
        inserts = plan["to_insert"]
        if replacing:
            # Only missing shipments inside this report's dates/branches are removed.
            for chunk in _chunks(plan["ended_ids"], 500):
                conn.execute(delete(shipments).where(shipments.c.id.in_(chunk)))
            inserts = []
            for row in plan["to_insert"]:
                oid = plan["existing_ids"].get(row["key"])
                if oid is None:
                    inserts.append(row)
                else:
                    conn.execute(update(shipments).where(shipments.c.id == oid).values(**row, from_import=import_id, to_import=None, ended_reason=None))
        for chunk in _chunks(inserts, 2000):
            conn.execute(insert(shipments), [dict(r, company=c, report_type=t, from_import=import_id) for r in chunk])
        conn.execute(update(imports).where(imports.c.id == import_id).values(new_rows=plan["new"], changed_rows=plan["changed"], ended_rows=plan["ended"]))
        if cur:
            conn.execute(update(current_import).where(current_import.c.company == c, current_import.c.report_type == t).values(import_id=import_id))
        else:
            conn.execute(insert(current_import).values(company=c, report_type=t, import_id=import_id))
        return dict(import_id=import_id, status="promoted", message=note, new=plan["new"], changed=plan["changed"], ended=plan["ended"])


def ingest_file(engine, path: str, report_time: datetime, source_ref: str = "", approve_review: bool = False,
                source: str = "email", uploaded_by: str = "", approved_by: str = "", override_reason: str = "", subject: str = "") -> dict:
    """Entry point for an email attachment or a manual upload: read, identify, check, load."""
    from . import profit            # the job profit report has its own layout and rules
    layout = profit.profit_layout(path)
    if layout == "job_summary":
        return profit.ingest_profit(engine, path, report_time, source, uploaded_by, approve_review, subject, source_ref)
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    sha = sha256_file(path)
    if layout == "charge_detail":
        with engine.begin() as conn:
            iid = _record(conn, None, "JP", report_time=report_time, file_name=name, file_sha256=sha,
                          source_ref=source_ref, status="failed", message=profit.LEGACY_MESSAGE,
                          file_path=path, source=source, uploaded_by=uploaded_by, subject=subject)
        return dict(import_id=iid, status="failed", message=profit.LEGACY_MESSAGE)
    try:
        reg = read_register(path)
    except ReportError as e:
        with engine.begin() as conn:
            iid = _record(conn, None, None, report_time=report_time, file_name=name, file_sha256=sha, source_ref=source_ref,
                          status="failed", message=str(e), file_path=path, source=source, uploaded_by=uploaded_by, subject=subject)
        return dict(import_id=iid, status="failed", message=str(e))
    return process_register(engine, reg, name, sha, report_time, source_ref, approve_review, path, source, uploaded_by, approved_by, override_reason, subject)


def preview_file(engine, path: str, report_time: datetime | None = None, subject: str = "") -> dict:
    """Admin 'upload' screen, step 1: say what loading this file WOULD do, without changing anything."""
    report_time = report_time or datetime.utcnow()
    try:
        reg = read_register(path)
    except ReportError as e:
        return dict(verdict="rejected", message=str(e))
    with engine.connect() as conn:
        status, msg, cur, rows, plan = _decide(conn, reg, sha256_file(path), report_time, False, subject)
    dates = pd.to_datetime(reg.df["Shipment Date"], errors="coerce") if "Shipment Date" in reg.df.columns else pd.Series(dtype="datetime64[ns]")
    out = dict(company=reg.company, report_type=reg.report_type, covers_from=reg.range_from, covers_to=reg.range_to, covers_branches=reg.branches, rows=len(reg.df), date_from=None if dates.empty else dates.min().date(),
               date_to=None if dates.empty else dates.max().date(), verdict={"ok": "ready"}.get(status, status), message=msg, notes=_notes(reg, plan, subject))
    if plan:
        out.update(new=plan["new"], changed=plan["changed"], ended=plan["ended"], columns_added=plan["added"], columns_removed=plan["removed"])
    return out


# ---------------------------------------------------------------- admin actions
def list_imports(engine, status: str | None = None, limit: int = 200) -> pd.DataFrame:
    q = select(imports).order_by(imports.c.id.desc()).limit(limit)
    if status:
        q = q.where(imports.c.status == status)
    return pd.read_sql(q, engine)


def approve_import(engine, import_id: int, approved_by: str, reason: str) -> dict:
    """An admin approves a report that was held for review (for example a deliberately smaller report)."""
    with engine.connect() as conn:
        r = conn.execute(select(imports).where(imports.c.id == import_id)).mappings().first()
    if not r or r["status"] != "needs_review":
        return dict(status="error", message="Only reports held for review can be approved")
    if not reason.strip():
        return dict(status="error", message="A reason is required")
    res = ingest_file(engine, r["file_path"], r["report_time"], r["source_ref"] or "", True, r["source"] or "email", r["uploaded_by"] or "", approved_by, reason, r["subject"] or "")
    if res["status"] == "promoted":
        with engine.begin() as conn:
            conn.execute(update(imports).where(imports.c.id == import_id).values(status="approved", message=f"Approved by {approved_by} and loaded as import {res['import_id']}"))
    return res


def retry_import(engine, import_id: int) -> dict:
    """Run a failed import again from the archived original (for example after a fix)."""
    with engine.connect() as conn:
        r = conn.execute(select(imports).where(imports.c.id == import_id)).mappings().first()
    if not r or r["status"] != "failed" or not r["file_path"]:
        return dict(status="error", message="Only failed imports with an archived file can be retried")
    res = ingest_file(engine, r["file_path"], r["report_time"], r["source_ref"] or "", False, r["source"] or "email", r["uploaded_by"] or "", "", "", r["subject"] or "")
    with engine.begin() as conn:
        conn.execute(update(imports).where(imports.c.id == import_id).values(status="retried", message=f"Retried as import {res['import_id']}: {res['status']}"))
    return res


# ---------------------------------------------------------------- reading back
def current_import_id(engine, company: str, report_type: str):
    with engine.connect() as conn:
        r = conn.execute(select(current_import.c.import_id).where(
            current_import.c.company == company, current_import.c.report_type == report_type)).first()
    return r[0] if r else None


def snapshot(engine, company: str, report_type: str, import_id: int | None = None) -> pd.DataFrame:
    """The report exactly as it stood at a given import (default: the current one)."""
    if config.replace_reports() and import_id is not None:
        raise ReportError("Past snapshots are unavailable in replacement mode")
    import_id = import_id or current_import_id(engine, company, report_type)
    q = select(shipments).where(
        shipments.c.company == company, shipments.c.report_type == report_type,
        shipments.c.from_import <= import_id, or_(shipments.c.to_import.is_(None), shipments.c.to_import > import_id))
    return pd.read_sql(q, engine)


def diff(engine, company: str, report_type: str, import_a: int, import_b: int) -> dict:
    """Compare two snapshots: new, changed (with the columns that changed) and no longer present."""
    a = snapshot(engine, company, report_type, import_a).set_index("key")
    b = snapshot(engine, company, report_type, import_b).set_index("key")
    new_keys = b.index.difference(a.index)
    gone_keys = a.index.difference(b.index)
    both = a.index.intersection(b.index)
    changed_keys = [k for k in both if a.at[k, "row_hash"] != b.at[k, "row_hash"]]
    fields = {}
    for k in changed_keys:
        ea, eb = a.at[k, "extra"], b.at[k, "extra"]
        fields[k] = sorted(col for col in set(ea) | set(eb) if ea.get(col, "") != eb.get(col, ""))
    return dict(new=b.loc[new_keys], gone=a.loc[gone_keys], changed_keys=changed_keys, changed_fields=fields)


# ---------------------------------------------------------------- years that move (relative history) and the ERP's date range
from datetime import timedelta


def year_slots(today: date | None = None, years: int = 3, fy_start_month: int = 1) -> list[dict]:
    """The years kept and compared, relative to today. fy_start_month=1 is the calendar year; 4 is India's April-March accounting year.
    The window always ends with the year (or accounting year) that contains today, so it moves by itself."""
    today = today or date.today()
    current = today.year if today.month >= fy_start_month else today.year - 1        # the year in which the current (financial) year began
    slots = []
    for y in range(current - years + 1, current + 1):
        start, end = date(y, fy_start_month, 1), date(y + 1, fy_start_month, 1) - timedelta(days=1)
        slots.append(dict(year=y, start=start, end=end, label=str(y) if fy_start_month == 1 else f"FY {y}-{(y + 1) % 100:02d}"))
    return slots


def history_window(today: date | None = None, years: int = 3, fy_start_month: int = 1):
    slots = year_slots(today, years, fy_start_month)
    return slots[0]["start"], slots[-1]["end"]


def _covered(ranges, start: date, end: date) -> bool:
    """Do the import date ranges, taken together, cover every day from start to end?"""
    reach = start
    for a, b in sorted(ranges):
        if a > reach:
            break
        reach = max(reach, b + timedelta(days=1))
        if reach > end:
            return True
    return reach > end


def coverage(engine, today: date | None = None, years: int = 3, fy_start_month: int = 1) -> pd.DataFrame:
    """For every company + report and every year in the window: shipments held, and whether imports together covered the whole year."""
    slots = year_slots(today, years, fy_start_month)
    with engine.connect() as conn:
        rows = conn.execute(select(shipments.c.company, shipments.c.report_type, shipments.c.shipment_date).where(
            shipments.c.to_import.is_(None), shipments.c.shipment_date >= slots[0]["start"])).all()
        imps = conn.execute(select(imports.c.company, imports.c.report_type, imports.c.range_from, imports.c.range_to).where(
            imports.c.status == "promoted", imports.c.range_from.is_not(None))).all()
    pairs = sorted({(r.company, r.report_type) for r in imps} | {(r.company, r.report_type) for r in rows})
    out = []
    for c, t in pairs:
        ranges = [(i.range_from, i.range_to) for i in imps if i.company == c and i.report_type == t]
        mine = [r.shipment_date for r in rows if r.company == c and r.report_type == t and r.shipment_date]
        for sl in slots:
            out.append(dict(company=c, report_type=t, year=sl["year"], label=sl["label"], rows=sum(1 for d in mine if sl["start"] <= d <= sl["end"]),
                            import_covers_year=_covered(ranges, sl["start"], sl["end"])))
    return pd.DataFrame(out)


def health(engine, today: date | None = None, now: datetime | None = None, max_age_hours: float = 36.0) -> list[dict]:
    """Problems the admin portal should show and email about: the ERP date range has run out (new year), or reports stopped arriving."""
    today, now = today or date.today(), now or datetime.utcnow()
    issues = []
    with engine.connect() as conn:
        rows = conn.execute(select(imports.c.company, imports.c.report_type, imports.c.range_from, imports.c.range_to, imports.c.report_time, imports.c.status)
                            .where(imports.c.status.in_(["promoted", "duplicate"]), imports.c.company.is_not(None))).all()
    for c, t in sorted({(r.company, r.report_type) for r in rows}):
        mine = [r for r in rows if r.company == c and r.report_type == t]
        promoted = [r for r in mine if r.status == "promoted" and r.range_to]
        if promoted and not any(r.range_from <= today <= r.range_to for r in promoted):
            last_end = max(r.range_to for r in promoted)
            issues.append(dict(company=c, report_type=t, issue="range_expired", message=f"The ERP report only covers dates up to {last_end:%d %b %Y}, but today is {today:%d %b %Y}. Change the schedule's date range in the ERP so new shipments are included."))
        latest = max(r.report_time for r in mine)
        if (now - latest).total_seconds() > max_age_hours * 3600:
            issues.append(dict(company=c, report_type=t, issue="no_recent_report", message=f"No report received since {latest:%d %b %Y %H:%M}."))
    return issues


def retention_preview(engine, today: date | None = None, years: int = 3, fy_start_month: int = 1) -> dict:
    """What would be removed if history were limited to the window: shipment versions dated before its first day."""
    start, _ = history_window(today, years, fy_start_month)
    with engine.connect() as conn:
        n = conn.execute(select(func.count()).select_from(shipments).where(shipments.c.shipment_date < start)).scalar()
    return dict(window_start=start, rows_before_window=n)


def _retention_maintenance(engine, configure=False):
    """Reclaim reusable space without a second copy of the database or weaker durability."""
    if engine.dialect.name != "postgresql":
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        if configure and os.environ.get("REPORT_SMALL_DATABASE") == "1":
            conn.execute(text("ALTER SYSTEM SET min_wal_size = '32MB'"))
            conn.execute(text("ALTER SYSTEM SET max_wal_size = '64MB'"))
            conn.execute(text("SELECT pg_reload_conf()"))
        if not configure:
            conn.execute(text("VACUUM (ANALYZE) shipments"))
        conn.execute(text("CHECKPOINT"))


def apply_retention(engine, approved_by: str, reason: str, today: date | None = None, years: int = 3, fy_start_month: int = 1) -> dict:
    """Admin action: remove shipments older than the window. A reason is required and the action is logged."""
    if not reason.strip():
        return dict(status="error", message="A reason is required")
    from sqlalchemy import delete
    start, _ = history_window(today, years, fy_start_month)
    _retention_maintenance(engine, configure=True)
    removed, batches = 0, 0
    while True:
        with engine.begin() as conn:
            ids = conn.execute(select(shipments.c.id).where(shipments.c.shipment_date < start).limit(250)).scalars().all()
            if not ids:
                break
            removed += conn.execute(delete(shipments).where(shipments.c.id.in_(ids))).rowcount
        batches += 1
        if batches % 32 == 0:
            _retention_maintenance(engine)
    _retention_maintenance(engine)
    with engine.begin() as conn:
        conn.execute(insert(admin_log).values(at=datetime.utcnow(), user=approved_by, action="retention", detail=f"Removed {removed} shipment versions dated before {start}. Years kept: {years}. Year starts in month {fy_start_month}. Reason: {reason}"))
    return dict(status="done", removed=removed, window_start=start)

