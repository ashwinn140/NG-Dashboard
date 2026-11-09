"""Job-level profit snapshots, scoped by Job Date. Legacy charge reports are rejected."""
from __future__ import annotations

import hashlib
import json
import re
from itertools import chain, islice
from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd
from sqlalchemy import and_, bindparam, delete, insert, select, true, update

from . import config
from .db import imports, profit_lines
from .processor import ReportError, _cell, _chunks, _hnorm, _record, _to_dates, historical_freeze, sha256_file

FORMAT = "job_summary_v1"
_KNOWN = {_hnorm(n): n for n in list(config.PROFIT_REQUIRED) + ["Organization", "Trade Lane", "Commodity", "Job Owner"]}
DATE_COLS = ("Job Date", "Revenue Recognition Date", "Financial Lock Date", "Operation Lock Date", "House Date", "Master Date")


def current_jobs():
    """Exclude retained legacy charge rows from all job-based finance calculations."""
    return (profit_lines.c.to_import.is_(None), profit_lines.c.extra["_format"].as_string() == FORMAT)


def summary_imports(rows):
    return [r for r in rows if "Job Date" in json.loads(r.columns or "[]") and "Charge" not in json.loads(r.columns or "[]")]


@dataclass
class ProfitReport:
    company: str
    df: pd.DataFrame
    title: str
    range_from: date | None
    range_to: date | None
    basis: str
    grand: dict
    columns: list = field(default_factory=list)


def _sheet_rows(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        yield from wb.worksheets[0].iter_rows(values_only=True)
    finally:
        wb.close()


LEGACY_MESSAGE = "The previous charge-wise profit format is no longer supported. Upload Job Profit Analysis Report with Basis: Job Date, one row per job, and an explicit From/to range."


def profit_layout(path: str) -> str | None:
    try:
        rows = list(islice(_sheet_rows(path), 12))
        title = re.sub(r"\s+", " ", str(rows[0][0] or "")).lower() if rows else ""
        if "charge wise detail" in title:
            return "charge_detail"
        if "job profit analysis report" in title:
            return "job_summary"
    except Exception:
        pass
    return None


def is_profit_report(path: str) -> bool:
    return profit_layout(path) == "job_summary"


def replacement_issue(rep: ProfitReport) -> str | None:
    if rep.range_from is None or rep.range_to is None or rep.range_from > rep.range_to or _hnorm(rep.basis) != "jobdate":
        return "Job profit requires Basis: Job Date and an explicit valid From/to range; existing data was kept"
    dates = pd.to_datetime(rep.df.get("Job Date", pd.Series(dtype=object)), errors="coerce").dt.normalize()
    if dates.isna().any() or ((dates < pd.Timestamp(rep.range_from)) | (dates > pd.Timestamp(rep.range_to))).any():
        return "A job has no valid Job Date or falls outside the report range; existing data was kept"
    return None


def read_profit(path: str) -> ProfitReport:
    stream = _sheet_rows(path)
    rows = list(islice(stream, 12))
    title = str(rows[0][0] or "") if rows else ""
    clean_title = re.sub(r"\s+", " ", title).lower()
    if "job profit analysis report" not in clean_title or "charge wise detail" in clean_title:
        raise ReportError(LEGACY_MESSAGE)
    first = re.sub(r"\s+", " ", title.split("\n")[0]).strip().lower()
    company = config.COMPANIES.get(first)
    if not company:
        raise ReportError(f"Unknown company in title row: '{title.splitlines()[0]}'")
    rf = rt = None
    m = re.search(r"From\s+(\d{1,2}-[A-Za-z]{3}-\d{4})\s+to\s+(\d{1,2}-[A-Za-z]{3}-\d{4})", title, re.I)
    if m:
        try:
            rf, rt = (datetime.strptime(x, "%d-%b-%Y").date() for x in m.groups())
        except ValueError as e:
            raise ReportError("Invalid report date range") from e
    basis = next((str(r[0]).split(":", 1)[-1].strip() for r in rows if r and r[0] and str(r[0]).lower().startswith("basis")), "")
    hi = next((i for i, r in enumerate(rows) if any(_hnorm(c) == "jobno" for c in r if c is not None)), None)
    if hi is None:
        raise ReportError("Header row ('Job No.') not found in the first 12 rows")
    names = [(_KNOWN.get(_hnorm(c), re.sub(r"\s+", " ", str(c)).strip()) if c is not None and str(c).strip() else None) for c in rows[hi]]
    normalized = [_hnorm(n) for n in names if n]
    if len(normalized) != len(set(normalized)):
        raise ReportError("Duplicate column names are ambiguous; keep one column for each field")
    missing = [c for c in config.PROFIT_REQUIRED if c not in names]
    if missing or "Charge" in names or any(_hnorm(n or "") == "charge" for n in names):
        raise ReportError("Missing required columns: " + ", ".join(missing) if missing else LEGACY_MESSAGE)
    lines, grand = [], {}
    for r in chain(rows[hi+1:], stream):
        d = {n: ("" if v is None else v) for n, v in zip(names, r) if n}
        loc, job = str(d.get("Location", "")).strip(), str(d.get("Job No.", "")).strip()
        if job.lower() in ("", "total") and any(str(v).strip().lower() == "total" for v in d.values()):
            if grand:
                raise ReportError("More than one grand-total row was found")
            grand = d
        elif (not job or job.lower().startswith("generated")) and any(str(v).strip().lower().startswith("generated by") for v in d.values()):
            continue
        elif any(v != "" for v in d.values()):
            if grand:
                raise ReportError("Job rows found after the grand total")
            lines.append(d)
    df = pd.DataFrame(lines, columns=[n for n in names if n])
    for c in ("Income (INR)", "Expense (INR)", "Profit (INR)"):
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "", regex=False), errors="coerce")
    for c in DATE_COLS:
        if c in df.columns:
            df[c] = _to_dates(df[c].replace("", pd.NA))
    return ProfitReport(company, df, title, rf, rt, basis, grand, [n for n in names if n])


def validate_profit(rep: ProfitReport) -> list[str]:
    df = rep.df
    missing = [c for c in config.PROFIT_REQUIRED if c not in df.columns]
    if missing:
        return [f"Missing required columns: {', '.join(missing)}"]
    if len(df) == 0:
        return ["The report has no jobs"]
    out = []
    import numpy as np
    for col in ("Income (INR)", "Expense (INR)", "Profit (INR)"):
        vals = pd.to_numeric(df[col], errors="coerce")
        if not np.isfinite(vals).all():
            out.append(f"Invalid or missing amount in {col}")
        want = pd.to_numeric(str(rep.grand.get(col, "")).replace(",", ""), errors="coerce")
        if pd.isna(want) or not np.isfinite(want):
            out.append(f"Missing or invalid report grand total for {col}")
        elif abs(vals.sum() - want) > 0.005:
            out.append(f"Jobs total {vals.sum():,.2f} for {col}, but the report total is {want:,.2f}")
    if ((df["Income (INR)"] - df["Expense (INR)"] - df["Profit (INR)"]).abs() > 0.005).any():
        out.append("A job's profit does not equal income minus expense")
    if df[["Job No.", "Location", "LOB"]].apply(lambda c: c.astype(str).str.strip().eq("")).any().any():
        out.append("Every job needs a Job No., Location and LOB")
    if df.duplicated(["Job No.", "Job Date", "LOB"]).any():
        out.append("Duplicate job number/date/LOB rows would double-count finance")
    issue = replacement_issue(rep)
    if issue:
        out.append(issue)
    return out


def _mode(lob: str):
    t = lob.upper()
    return ("Air" if "AIR" in t else "Sea" if "SEA" in t else "Road" if "ROAD" in t else "Other",
            "Export" if "EXP" in t else "Import" if "IMP" in t else "Domestic" if "DOM" in t else "Other",
            "Customs clearance" if t.startswith("CCL") else "Freight forwarding" if t.startswith("FFWD") else "General")


def standardise_profit(rep: ProfitReport) -> list[dict]:
    cells = rep.df.map(_cell)
    seq: dict = {}
    out = []
    ic_names = {_hnorm(n) for n in config.COMPANIES}
    columns = list(rep.df.columns)
    for values, raw_values in zip(cells.itertuples(index=False, name=None), rep.df.itertuples(index=False, name=None)):
        rec, raw = dict(zip(columns, values)), dict(zip(columns, raw_values))
        extra = dict(rec); extra["_format"] = FORMAT
        inc, exp = float(raw.get("Income (INR)", 0) or 0), float(raw.get("Expense (INR)", 0) or 0)
        g = lambda k: str(rec.get(k, ""))          # noqa: E731
        base = "job|" + json.dumps([g("Job No."), g("Job Date"), g("LOB")], ensure_ascii=False)
        n = seq[base] = seq.get(base, 0) + 1
        dt = lambda k: (raw.get(k).date() if pd.notna(raw.get(k)) else None) if k in raw and raw.get(k) is not None else None   # noqa: E731
        mode, direction, kind = _mode(g("LOB"))
        row = dict(company=rep.company, key=f"{base}#{n}", branch=g("Location"), lob=g("LOB"), job_no=g("Job No."), job_date=dt("Job Date"),
                   customer=g("Organization"), charge="", trans_no="", trans_date=None, party="",
                   party_ref_no="", party_ref_date=None, income=inc, expense=exp, profit=round(inc - exp, 2),
                   trade_lane=g("Trade Lane"), commodity=g("Commodity"), extra=extra)
        hash_src = {k: v for k, v in extra.items() if k not in ("Profit (INR)", "Profit Margin %")}
        row["row_hash"] = hashlib.sha1(json.dumps(hash_src, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        out.append(row)
    return out


def process_profit(engine, rep: ProfitReport, file_name: str, file_sha: str, report_time: datetime, file_path: str = "", source: str = "email",
                   uploaded_by: str = "", approve_review: bool = False, subject: str = "", source_ref: str = "") -> dict:
    """Duplicate / older / bad / suspiciously smaller / promote, as for the registers. Lines are compared per job."""
    base = dict(report_time=report_time, file_name=file_name, file_sha256=file_sha, row_count=len(rep.df), range_from=rep.range_from,
                range_to=rep.range_to, file_path=file_path, source=source, uploaded_by=uploaded_by, subject=subject, source_ref=source_ref)
    c = rep.company
    with engine.begin() as conn:
        def stop(status, msg):
            return dict(import_id=_record(conn, c, "JP", status=status, message=msg, **base), status=status, message=msg)
        cutoff = config.history_start()
        if cutoff and rep.range_to and rep.range_to < cutoff:
            return stop("outside_history", f"Report predates the retained dashboard history ({cutoff}); original file retained")
        dup = conn.execute(select(imports.c.id).where(imports.c.file_sha256 == file_sha, imports.c.status == "promoted")).first()
        if dup:
            return stop("duplicate", f"Identical file already loaded as import {dup[0]}")
        overlap = and_(imports.c.range_from <= rep.range_to, imports.c.range_to >= rep.range_from) if rep.range_from else true()
        last = conn.execute(select(imports.c.id, imports.c.report_time).where(imports.c.company == c, imports.c.report_type == "JP", imports.c.status == "promoted", imports.c.columns.not_like('%"Charge"%'), overlap)
                            .order_by(imports.c.report_time.desc())).first()
        if last and report_time <= last.report_time:
            return stop("stale", f"Report time {report_time:%Y-%m-%d %H:%M} is not newer than the latest report for the same dates ({last.report_time:%Y-%m-%d %H:%M})")
        problems = validate_profit(rep)
        if problems:
            return stop("failed", "; ".join(problems))
        replacing = config.replace_reports()
        issue = replacement_issue(rep)
        if issue:
            return stop("needs_review", issue)
        rows = standardise_profit(rep)
        jobs = {r["job_no"] for r in rows}
        replacing = config.replace_reports()
        held = conn.execute(select(profit_lines.c.id, profit_lines.c.key, profit_lines.c.row_hash, profit_lines.c.job_no, profit_lines.c.from_import, profit_lines.c.job_date).where(
            profit_lines.c.company == c, *current_jobs())).all()
        if replacing:
            in_jobs = [h for h in held if h.job_date and rep.range_from <= h.job_date <= rep.range_to]
            scoped = {h.id for h in in_jobs}
            incoming_keys = {r["key"] for r in rows}
            if any(h.key in incoming_keys and h.id not in scoped for h in held):
                return stop("needs_review", "A profit key conflicts with data outside the replacement range; existing data was kept")
        elif rep.range_from is not None:
            spans = {r.id: (r.range_from, r.range_to) for r in conn.execute(select(imports.c.id, imports.c.range_from, imports.c.range_to).where(imports.c.id.in_({h.from_import for h in held})))} if held else {}
            def covered(h):                 # was this line loaded by a file whose dates overlap this one?
                a = spans.get(h.from_import)
                return a is None or a[0] is None or (a[0] <= rep.range_to and a[1] >= rep.range_from)
            in_jobs = [h for h in held if covered(h)]
        else:                               # dates unreadable: judge only the jobs the file lists
            in_jobs = [h for h in held if h.job_no in jobs]
        if in_jobs and not approve_review:
            drop = (len(in_jobs) - len(rows)) / len(in_jobs)
            if drop > config.MAX_ROW_DROP:
                return stop("needs_review", f"{len(rows)} lines vs {len(in_jobs)} held for the same dates ({drop:.0%} fewer): held for review")
        iid = _record(conn, c, "JP", status="promoted", message=f"Job Date; {len(rep.df):,} jobs; source totals reconciled: income {rep.df['Income (INR)'].sum():.2f}, expense {rep.df['Expense (INR)'].sum():.2f}, profit {rep.df['Profit (INR)'].sum():.2f}", **base)
        old = {r.key: (r.id, r.row_hash) for r in held}
        new_keys = {r["key"] for r in rows}
        pc = conn.execute(select(imports.c.columns).where(imports.c.company == c, imports.c.report_type == "JP", imports.c.status == "promoted",
                                                          imports.c.columns.is_not(None)).order_by(imports.c.report_time.desc())).first()
        prev_cols, new_cols = (set(json.loads(pc[0])) if pc else None), set(rep.columns)
        schema_changed = prev_cols is not None and prev_cols != new_cols
        add, chg_ids, inplace, differing = [], [], [], []
        n_new = n_chg = 0
        for r in rows:
            prev = old.get(r["key"])
            if prev is None:
                n_new += 1
                add.append(r)
            elif prev[1] != r["row_hash"]:
                differing.append((r, prev[0]))
        if differing and schema_changed:       # a column was added or removed: compare only the columns both reports have
            common = (prev_cols & new_cols) - {"Profit (INR)", "Profit Margin %"}
            old_extra = {}
            for ch in _chunks([i for _, i in differing], 500):
                for row in conn.execute(select(profit_lines.c.id, profit_lines.c.extra).where(profit_lines.c.id.in_(ch))):
                    old_extra[row.id] = row.extra or {}
            for r, oid in differing:
                a, b = old_extra.get(oid, {}), r["extra"]
                if all(a.get(k, "") == b.get(k, "") for k in common):
                    inplace.append({"b_id": oid, "b_extra": b, "b_hash": r["row_hash"]})
                else:
                    n_chg += 1
                    chg_ids.append(oid)
                    add.append(r)
        else:
            for r, oid in differing:
                n_chg += 1
                chg_ids.append(oid)
                add.append(r)
        gone = [r.id for r in in_jobs if r.key not in new_keys]
        if config.static_history():
            ranges = conn.execute(select(imports.c.range_from, imports.c.range_to).where(
                imports.c.company == c, imports.c.report_type == "JP", imports.c.status == "promoted", imports.c.id != iid, imports.c.columns.not_like('%"Charge"%'))).all()
            cutoff, frozen = historical_freeze(conn, ranges)
            protected = {r.id for r in held if r.job_date and r.job_date < cutoff}
            add = [r for r in add if (old.get(r["key"], (None,))[0] not in protected)
                   and (r["key"] in old or not frozen(r["job_date"]))]
            chg_ids = [i for i in chg_ids if i not in protected]
            gone = [i for i in gone if i not in protected]
            inplace = [r for r in inplace if r["b_id"] not in protected]
            n_new = sum(r["key"] not in old for r in add)
            n_chg = len(chg_ids)
        for ids, why in (() if replacing else ((chg_ids, "changed"), (gone, "not_present"))):
            for ch in _chunks(ids, 500):
                conn.execute(update(profit_lines).where(profit_lines.c.id.in_(ch)).values(to_import=iid, ended_reason=why))
        if inplace:
            conn.execute(update(profit_lines).where(profit_lines.c.id == bindparam("b_id")).values(extra=bindparam("b_extra"), row_hash=bindparam("b_hash")), inplace)
        if replacing:
            for ch in _chunks(gone, 500):
                conn.execute(delete(profit_lines).where(profit_lines.c.id.in_(ch)))
            inserts = []
            for row in add:
                previous = old.get(row["key"])
                if previous is None:
                    inserts.append(row)
                else:
                    conn.execute(update(profit_lines).where(profit_lines.c.id == previous[0]).values(**row, from_import=iid, to_import=None, ended_reason=None))
            add = inserts
        for ch in _chunks(add, 2000):
            conn.execute(insert(profit_lines), [dict(r, from_import=iid) for r in ch])
        conn.execute(update(imports).where(imports.c.id == iid).values(new_rows=n_new, changed_rows=n_chg, ended_rows=len(gone), columns=json.dumps(rep.columns)))
        return dict(import_id=iid, status="promoted", message="", new=n_new, changed=n_chg, ended=len(gone))


def ingest_profit(engine, path: str, report_time: datetime, source: str = "email", uploaded_by: str = "", approve_review: bool = False, subject: str = "", source_ref: str = "") -> dict:
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    sha = sha256_file(path)
    try:
        rep = read_profit(path)
    except ReportError as e:
        with engine.begin() as conn:
            iid = _record(conn, None, "JP", report_time=report_time, file_name=name, file_sha256=sha, status="failed", message=str(e), file_path=path, source=source, uploaded_by=uploaded_by, subject=subject, source_ref=source_ref)
        return dict(import_id=iid, status="failed", message=str(e))
    return process_profit(engine, rep, name, sha, report_time, path, source, uploaded_by, approve_review, subject, source_ref)


def profit_snapshot(engine, company: str | None = None) -> pd.DataFrame:
    q = select(profit_lines).where(*current_jobs())
    if company:
        q = q.where(profit_lines.c.company == company)
    return pd.read_sql(q, engine)


def profit_coverage(engine, today: date | None = None, years: int = 3, fy_start_month: int = 1) -> pd.DataFrame:
    """For every company and every year in the window: profit lines held (by Job Date), and whether the loaded reports together cover the whole year."""
    from .processor import _covered, year_slots
    slots = year_slots(today, years, fy_start_month)
    with engine.connect() as conn:
        rows = conn.execute(select(profit_lines.c.company, profit_lines.c.job_date).where(*current_jobs(), profit_lines.c.job_date >= slots[0]["start"])).all()
        imps = summary_imports(conn.execute(select(imports.c.company, imports.c.range_from, imports.c.range_to, imports.c.columns).where(imports.c.report_type == "JP", imports.c.status == "promoted", imports.c.range_from.is_not(None))).all())
    out = []
    for c in sorted({i.company for i in imps} | {r.company for r in rows}):
        ranges = [(i.range_from, i.range_to) for i in imps if i.company == c]
        mine = [r.job_date for r in rows if r.company == c and r.job_date]
        for sl in slots:
            out.append(dict(company=c, year=sl["year"], label=sl["label"], lines=sum(1 for d in mine if sl["start"] <= d <= sl["end"]), import_covers_year=_covered(ranges, sl["start"], sl["end"])))
    return pd.DataFrame(out)

