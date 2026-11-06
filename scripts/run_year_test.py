"""Years that move: the history window, coverage by year, the ERP date range running out, and admin-approved retention.
Run:  python scripts/run_year_test.py <folder with the Excel files>
"""
import os, sys, tempfile
from datetime import date, datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
from openpyxl import Workbook
from sqlalchemy import select
from app.db import admin_log, get_engine
from app import processor as P

folder = sys.argv[1] if len(sys.argv) > 1 else "."
SRC = os.path.join(folder, "1793879006568_Ship_Reg_OI_NG1.xlsx")
tmp = tempfile.mkdtemp(); ok = True
def check(label, cond, detail=""):
    global ok; ok &= bool(cond); print(("PASS  " if cond else "FAIL  ") + label + (f"   [{detail}]" if detail else ""))

raw = pd.read_excel(SRC, header=None, dtype=object); HDR = 3
TITLE = raw.iloc[:HDR].values.tolist(); hdr0 = list(raw.iloc[HDR])
def year_file(year, back):
    body = raw.iloc[HDR + 1:].reset_index(drop=True).copy(); body.columns = range(len(hdr0)); dcol = hdr0.index("Shipment Date")
    if back: body[dcol] = pd.to_datetime(body[dcol]) - pd.DateOffset(years=back)
    title = [[(c.replace("2026", str(year)) if isinstance(c, str) else c) for c in row] for row in TITLE]
    wb = Workbook(); ws = wb.active
    for r in title: ws.append([None if (isinstance(v, float) and v != v) else v for v in r][:len(hdr0)])
    ws.append([None if (isinstance(v, float) and v != v) else v for v in hdr0])
    for r in body.itertuples(index=False): ws.append([None if (v is None or (not isinstance(v, str) and pd.isna(v))) else (v.to_pydatetime() if isinstance(v, pd.Timestamp) else v) for v in r])
    p = os.path.join(tmp, f"y{year}.xlsx"); wb.save(p); return p

engine = get_engine("sqlite:///" + os.path.join(tmp, "years.db"))
base = datetime(2026, 11, 5, 9, 0)
print("== A. The window is relative to today ==")
check("2026, 3 years -> 1 Jan 2024 to 31 Dec 2026", P.history_window(date(2026, 11, 6), 3) == (date(2024, 1, 1), date(2026, 12, 31)))
check("on 3 Jan 2027 the same setting moves to 2025-2027", P.history_window(date(2027, 1, 3), 3) == (date(2025, 1, 1), date(2027, 12, 31)))
check("a 5-year setting reaches back further", P.history_window(date(2026, 11, 6), 5)[0] == date(2022, 1, 1))

check("India's April-March: on 6 Nov 2026 the window is Apr 2024 to Mar 2027", P.history_window(date(2026, 11, 6), 3, 4) == (date(2024, 4, 1), date(2027, 3, 31)))
check("still the same window on 1 Feb 2027 (still FY 2026-27)", P.history_window(date(2027, 2, 1), 3, 4) == (date(2024, 4, 1), date(2027, 3, 31)))
check("it moves on 2 Apr 2027 (FY 2027-28 begins)", P.history_window(date(2027, 4, 2), 3, 4) == (date(2025, 4, 1), date(2028, 3, 31)))
check("slot labels read FY 2026-27", [s["label"] for s in P.year_slots(date(2026, 11, 6), 3, 4)] == ["FY 2024-25", "FY 2025-26", "FY 2026-27"])

print("\n== B. Coverage by year: what is loaded, what is missing ==")
r = P.ingest_file(engine, year_file(2026, 0), base); n = r["new"]
cov = P.coverage(engine, date(2026, 11, 6), 3); c26 = cov[cov.year == 2026].iloc[0]; c24 = cov[cov.year == 2024].iloc[0]
check("only 2026 loaded: 2026 has rows, 2024 and 2025 are empty", c26.rows == n and c24.rows == 0 and cov[cov.year == 2025].iloc[0].rows == 0, f"2026={c26.rows}, 2025=0, 2024=0")
P.ingest_file(engine, year_file(2025, 1), base + timedelta(hours=1)); P.ingest_file(engine, year_file(2024, 2), base + timedelta(hours=2))
cov = P.coverage(engine, date(2026, 11, 6), 3)
check("after loading 2025 and 2024 every year in the window is filled and covered", (cov.rows == n).all() and cov.import_covers_year.tolist() == [True, True, True], cov[["year", "rows", "import_covers_year"]].values.tolist())

print("\n== B2. The same data seen as accounting years (April-March) ==")
months = pd.to_datetime(raw.iloc[HDR + 1:, hdr0.index("Shipment Date")]).dt.month; A = int((months >= 4).sum()); B = int((months < 4).sum())
fy = P.coverage(engine, date(2026, 11, 6), 3, 4)
check("FY rows combine two calendar-year files correctly", fy.rows.tolist() == [n, n, A], f"{fy.label.tolist()} rows={fy.rows.tolist()} (Apr-Dec of one year + Jan-Mar of the next)")
check("only years fully covered by the loaded files say so", fy.import_covers_year.tolist() == [True, True, False], "FY 2026-27 runs to Mar 2027 but the ERP range ends Dec 2026")
pvf = P.retention_preview(engine, date(2027, 4, 2), 3, 4)
check("accounting-year retention on 2 Apr 2027 keeps Apr 2025 onward", pvf["window_start"] == date(2025, 4, 1) and pvf["rows_before_window"] == n + B, f"{pvf['rows_before_window']} rows before {pvf['window_start']}")

print("\n== C. The new year: the ERP date range runs out ==")
now = base + timedelta(hours=3)
check("in November 2026 there is nothing to flag", P.health(engine, date(2026, 11, 6), now) == [])
issues = P.health(engine, date(2027, 1, 3), now + timedelta(days=60))
check("on 3 Jan 2027 the admin is told the ERP range still ends in 2026", any(i["issue"] == "range_expired" for i in issues), [i["message"][:70] for i in issues if i["issue"] == "range_expired"])
P.ingest_file(engine, year_file(2027, -1), base + timedelta(days=60, hours=1))
check("after the 2027 report arrives the range warning is gone", not any(i["issue"] == "range_expired" for i in P.health(engine, date(2027, 1, 3), base + timedelta(days=60, hours=2))))
check("a report that stops arriving is flagged", any(i["issue"] == "no_recent_report" for i in P.health(engine, date(2027, 1, 3), base + timedelta(days=80))))

print("\n== D. Retention follows the window and needs an admin reason ==")
pv = P.retention_preview(engine, date(2027, 1, 3), 3)
check("3 years on 3 Jan 2027: only 2024 falls outside the window", pv["window_start"] == date(2025, 1, 1) and pv["rows_before_window"] == n, f"{pv['rows_before_window']} rows before {pv['window_start']}")
check("4 years would keep everything", P.retention_preview(engine, date(2027, 1, 3), 4)["rows_before_window"] == 0)
check("removal without a reason is refused", P.apply_retention(engine, "admin@example.com", " ", date(2027, 1, 3), 3)["status"] == "error")
out = P.apply_retention(engine, "admin@example.com", "Window moved to 2025-2027", date(2027, 1, 3), 3)
cov = P.coverage(engine, date(2027, 1, 3), 3)
check("approved: 2024 removed, 2025 to 2027 untouched", out["removed"] == n and (cov.rows == n).all() and cov.year.min() == 2025, f"removed={out['removed']}")
with engine.connect() as conn: log = conn.execute(select(admin_log)).mappings().all()
check("the removal is logged with who and why", len(log) == 1 and log[0]["user"] == "admin@example.com" and "Window moved" in log[0]["detail"])
print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
