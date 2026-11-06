"""Job profit report: reading, the grand-total proof, versions, column order and extra columns.
Run:  python scripts/run_profit_test.py <folder with the Excel files>
"""
import os, random, sys, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import openpyxl
from openpyxl import Workbook
from app.db import get_engine
from app import processor as P, profit as J

folder = sys.argv[1] if len(sys.argv) > 1 else "."
NG = os.path.join(folder, "1793934145789_New_globeJob_Profit_Analysis_Report.xlsx"); NCS = os.path.join(folder, "1793934145789_NCS_Job_Profit_Analysis_Report__1_.xlsx")
tmp = tempfile.mkdtemp(); ok = True
def check(label, cond, detail=""):
    global ok; ok &= bool(cond); print(("PASS  " if cond else "FAIL  ") + label + (f"   [{detail}]" if detail else ""))
def raw_rows(path): return [list(r) for r in openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0].iter_rows(values_only=True)]
def write(name, rows):
    wb = Workbook(); ws = wb.active
    for r in rows: ws.append(r)
    p = os.path.join(tmp, name); wb.save(p); return p

engine = get_engine("sqlite:///" + os.path.join(tmp, "profit.db")); t0 = datetime(2026, 11, 5, 9, 0); k = [0]
def at(): k[0] += 1; return t0 + timedelta(hours=k[0])

print("== 1. Both real reports ==")
for label, f, lines in (("New Globe", NG, 1120), ("Neutral Consolidation", NCS, 90)):
    r = P.ingest_file(engine, f, at())      # the normal entry point finds out by itself that this is a profit report
    check(f"{label}: loaded through the normal entry point", r["status"] == "promoted" and r["new"] == lines, f"{r['new']} charge lines")
snap = J.profit_snapshot(engine)
for co, inc, exp in (("NG", 39690149.19, 5525944.92), ("NCS", 2598228.86, 54081.32)):
    s = snap[snap.company == co]
    check(f"{co}: income, expense and profit equal the report's own grand total", abs(s.income.sum() - inc) < 0.01 and abs(s.expense.sum() - exp) < 0.01 and abs(s.profit.sum() - (inc - exp)) < 0.01, f"income {s.income.sum():,.2f}, expense {s.expense.sum():,.2f}")
check("the two Organization columns became customer and party", snap[snap.company == "NG"].customer.iloc[0] != "" and snap[snap.company == "NG"].party.iloc[0] != "")
check("the NCS-only columns (Container TEU, Documentation Executive, Co-Load Type) are kept", all(c in snap[snap.company == "NCS"].extra.iloc[0] for c in ("Documentation Executive", "Container TEU")))
check("the same file again is ignored", P.ingest_file(engine, NG, at())["status"] == "duplicate")

print("\n== 2. Column order and extra columns do not matter ==")
rows = raw_rows(NG); hdr = rows[2]; width = len(hdr)
org = [j for j, h in enumerate(hdr) if h == "Organization"]
order = list(range(width)); rest = [j for j in order if j not in org]; random.Random(3).shuffle(rest)
shuf = []
for j in rest[:3]: shuf.append(j)
shuf += [org[0]] + rest[3:8] + [org[1]] + rest[8:]            # shuffled, but the two Organization columns keep their relative order
def permute(rows, order, extra=None):
    out = []
    for i, r in enumerate(rows):
        r = list(r) + [None] * (width - len(r)); row = [r[j] for j in order]
        if extra: row.append(extra[0] if i == 2 else (extra[1] if i > 2 and r[0] not in (None, "", "Total") and not str(r[0]).startswith("Generated") and r[5] not in ("Total", "Job Total") else None))
        out.append(row if i >= 2 else r)
    return out
res = P.ingest_file(engine, write("shuffled.xlsx", permute(rows, shuf, ("Cost Centre", "CC-1"))), at())
check("columns shuffled and a new column added: nothing counted as changed", res["status"] == "promoted" and (res["new"], res["changed"], res["ended"]) == (0, 0, 0), f"new={res.get('new')} changed={res.get('changed')} gone={res.get('ended')} {res.get('message', '')}")
check("the new column is stored on every line", J.profit_snapshot(engine, "NG").extra.map(lambda e: e.get("Cost Centre") == "CC-1").all())

print("\n== 3. Real changes, and jobs are judged one by one ==")
idx = [i for i, r in enumerate(rows) if i > 2 and r[5] not in (None, "", "Total", "Job Total") and r[0] not in (None, "", "Total") and (r[11] or 0) > 0][:1][0]
chg = [list(r) for r in rows]; chg[idx][11] = chg[idx][11] + 500
tot = [i for i, r in enumerate(chg) if r[0] == "Total"][0]; chg[tot][11] = chg[tot][11] + 500            # the grand total moves with it, as the ERP would
r = P.ingest_file(engine, write("changed.xlsx", chg), at())
check("one amount edited: exactly one line changed", r["status"] == "promoted" and r["changed"] == 1 and r["new"] == 0 and r["ended"] == 0, f"changed={r.get('changed')}")
jobs = []
for i, r_ in enumerate(rows):
    if i > 2 and r_[2] and r_[2] not in jobs: jobs.append(r_[2])
keep = set(jobs[:60]); part = [r_ for i, r_ in enumerate(rows) if i <= 2 or (r_[2] in keep) or (r_[0] in (None, "") and False)]
tl = [sum((r_[11] or 0) for i, r_ in enumerate(part) if i > 2 and r_[2]), sum((r_[12] or 0) for i, r_ in enumerate(part) if i > 2 and r_[2])]
part.append(["Total", None, None, None, None, None, None, None, None, None, None, round(tl[0], 2), round(tl[1], 2), round(tl[0] - tl[1], 2), None, None, None])
before = len(J.profit_snapshot(engine, "NG"))
r = P.ingest_file(engine, write("partial.xlsx", part), at())
check("a file with far fewer lines than are held for the same dates is held for review, nothing changes", r["status"] == "needs_review" and len(J.profit_snapshot(engine, "NG")) == before, r["message"][:100])
mrows = [list(r_) for r_ in chg]; li = next(i for i, r_ in enumerate(mrows) if i > idx and i > 2 and r_[5] not in (None, "", "Total", "Job Total") and r_[0] not in (None, "", "Total") and (r_[11] or 0) > 0)
gi = [i for i, r_ in enumerate(mrows) if r_[0] == "Total"][0]; mrows[gi][11] = round(mrows[gi][11] - mrows[li][11], 2); mrows[gi][13] = round(mrows[gi][11] - mrows[gi][12], 2); del mrows[li]
r = P.ingest_file(engine, write("lineless.xlsx", mrows), at())
check("a single charge line that vanishes from the file is marked 'not present'", r["status"] == "promoted" and r["ended"] == 1 and r["new"] == 0, f"no longer present={r.get('ended')}")

print("\n== 5. One-time previous year, then a daily full-year file ==")
from datetime import timedelta as TD
def retitle(rows, frm, to):
    rows = [list(r) for r in rows]; rows[0][0] = rows[0][0].replace(frm, to); return rows
def is_line(i, r): return i > 2 and r[0] not in (None, "", "Total") and not str(r[0]).startswith("Generated") and r[5] not in ("Total", "Job Total")
def fix_totals(rows):
    ls = [r for i, r in enumerate(rows) if is_line(i, r)]; inc = round(sum(r[11] or 0 for r in ls), 2); exp = round(sum(r[12] or 0 for r in ls), 2)
    g = [i for i, r in enumerate(rows) if r[0] == "Total"][0]; rows[g][11], rows[g][12], rows[g][13] = inc, exp, round(inc - exp, 2); return rows
def prev_year(rows):
    out = [list(r) for r in rows]
    for i, r in enumerate(out):
        if is_line(i, r):
            r[2] = r[2] + "-25"
            for c in (3, 7, 10):
                if r[c]: r[c] = r[c] - TD(days=365)
    return out
FULL = "01-Nov-2026 to 30-Nov-2026"
y26 = lambda rws: retitle(rws, FULL, "01-Jan-2026 to 31-Dec-2026")
y25 = lambda rws: retitle(rws, FULL, "01-Jan-2025 to 31-Dec-2025")
eng2 = get_engine("sqlite:///" + os.path.join(tmp, "years.db")); kk = [0]
def at2(): kk[0] += 1; return t0 + timedelta(hours=kk[0])
base_rows = raw_rows(NG)
r25 = P.ingest_file(eng2, write("y25.xlsx", y25(prev_year(base_rows))), at2()); n25 = r25["new"]
check("last year's full-year report loads (one time)", r25["status"] == "promoted", f"{n25} lines")
r26 = P.ingest_file(eng2, write("y26.xlsx", y26(base_rows)), at2()); n26 = r26["new"]
snap2 = J.profit_snapshot(eng2, "NG")
check("this year's daily full-year file loads and last year is NOT touched", r26["status"] == "promoted" and r26["ended"] == 0 and len(snap2) == n25 + n26, f"2025 lines {int(snap2.job_no.str.endswith('-25').sum())}, 2026 lines {int((~snap2.job_no.str.endswith('-25')).sum())}")
jb = [r_[2] for i, r_ in enumerate(base_rows) if is_line(i, r_)]; gone_job = jb[0]; k_gone = sum(1 for j in jb if j == gone_job)
drop_rows = [r_ for i, r_ in enumerate(base_rows) if not (is_line(i, r_) and r_[2] == gone_job)]
# also remove the Total / Job Total rows that belonged to the job, as the ERP would (they carry no job number, so cut up to its Job Total row)
cut, out_rows, skipping = 0, [], False
for i, r_ in enumerate(base_rows):
    if is_line(i, r_) and r_[2] == gone_job: skipping = True; continue
    if skipping and r_[5] in ("Total", "Job Total"):
        if r_[5] == "Job Total": skipping = False
        continue
    out_rows.append(list(r_))
res = P.ingest_file(eng2, write("y26_day2.xlsx", y26(fix_totals(out_rows))), at2())
snap2 = J.profit_snapshot(eng2, "NG")
check("a whole job missing from the next daily full-year file is marked 'not present'", res["status"] == "promoted" and res["ended"] == k_gone and res["new"] == 0, f"no longer present={res.get('ended')} (the job had {k_gone} lines)")
check("last year still has every line", int(snap2.job_no.str.endswith("-25").sum()) == n25)
chg_rows = [list(r_) for r_ in out_rows]; ci = next(i for i, r_ in enumerate(chg_rows) if is_line(i, r_) and (r_[11] or 0) > 0); chg_rows[ci][11] += 250
res = P.ingest_file(eng2, write("y26_day3.xlsx", y26(fix_totals(chg_rows))), at2())
check("next day: one amount changed, nothing else", res["status"] == "promoted" and (res["new"], res["changed"], res["ended"]) == (0, 1, 0), f"new={res.get('new')} changed={res.get('changed')} gone={res.get('ended')}")
fix25 = [list(r_) for r_ in prev_year(base_rows)]; ci25 = next(i for i, r_ in enumerate(fix25) if is_line(i, r_) and (r_[11] or 0) > 0); fix25[ci25][11] += 99
res = P.ingest_file(eng2, write("y25_fix.xlsx", y25(fix_totals(fix25))), at2()); snap2 = J.profit_snapshot(eng2, "NG")
check("a correction to last year changes one line and leaves this year alone", res["status"] == "promoted" and res["changed"] == 1 and res["ended"] == 0 and int((~snap2.job_no.str.endswith("-25")).sum()) == n26 - k_gone, f"changed={res.get('changed')}")
res = P.ingest_file(eng2, write("y26_old.xlsx", y26(fix_totals(chg_rows)) + []), t0)
check("an older copy of the full-year file cannot replace a newer one", res["status"] in ("stale", "duplicate"), res["message"][:80])
half = [list(r_) for i, r_ in enumerate(chg_rows) if i <= 2 or (r_[2] not in (None, "") and jb.index(r_[2]) % 2 == 0 if r_[2] in jb else True)]
res = P.ingest_file(eng2, write("y26_half.xlsx", y26(fix_totals(half))), at2())
check("a full-year file with half the lines is held for review", res["status"] == "needs_review", res["message"][:90])
cov = J.profit_snapshot(eng2, "NG"); check("nothing changed by the held file", len(cov) == n25 + n26 - k_gone)

from datetime import date
cv = J.profit_coverage(eng2, date(2026, 11, 6), 3)
check("history by year for profit: 2024 missing, 2025 and 2026 loaded and covered", cv[cv.year == 2024].lines.iloc[0] == 0 and cv[cv.year == 2025].lines.iloc[0] == n25 and cv.import_covers_year.tolist() == [False, True, True], cv[["year", "lines", "import_covers_year"]].values.tolist())
iss = P.health(eng2, date(2027, 1, 3), t0 + timedelta(hours=kk[0] + 1))
check("at the new year the admin is told the profit report's date range has run out", any(i["issue"] == "range_expired" and i["report_type"] == "JP" for i in iss), [i["message"][:60] for i in iss if i["report_type"] == "JP"][:1])

print("\n== 4. Bad files ==")
bad = [list(r) for r in rows]; bad[idx][11] = bad[idx][11] + 777            # a line changes but the grand total does not
r = P.ingest_file(engine, write("badsum.xlsx", bad), at())
check("lines that do not add up to the grand total are rejected, with both numbers", r["status"] == "failed" and "grand total" in r["message"], r["message"][:110])
nocol = [[v for j, v in enumerate(list(r_) + [None] * (width - len(r_))) if j != hdr.index("Income (INR)")] for r_ in rows]
r = P.ingest_file(engine, write("nocol.xlsx", nocol), at())
check("a report missing Income (INR) is rejected, naming the column", r["status"] == "failed" and "Income (INR)" in r["message"], r["message"])
print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
