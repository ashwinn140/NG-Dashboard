"""Proves the processor copes with the ERP changing its export, and exercises the admin upload actions.
Run:  python scripts/run_robustness_test.py <folder with the Excel files>
Uses one real report (New Globe Sea Import) and rewrites it in different ways.
"""
import os, random, sys, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import openpyxl, pandas as pd
from openpyxl import Workbook
from app.db import get_engine, imports
from app import processor as P

folder = sys.argv[1] if len(sys.argv) > 1 else "."
SRC = os.path.join(folder, "1793879006568_Ship_Reg_OI_NG1.xlsx")
tmp = tempfile.mkdtemp()
ok = True
def check(label, cond, detail=""):
    global ok; ok &= bool(cond); print(("PASS  " if cond else "FAIL  ") + label + (f"   [{detail}]" if detail else ""))

# ---- helpers: load the sheet as raw cells so headers (even repeated ones) can be reordered, renamed, added, removed
raw = pd.read_excel(SRC, header=None, dtype=object)
HDR = 3
TITLE = raw.iloc[:HDR].values.tolist()
def fresh():
    hdr = list(raw.iloc[HDR]); body = raw.iloc[HDR + 1:].reset_index(drop=True).copy(); body.columns = range(len(hdr)); return hdr, body
def write(name, hdr, body, title=None):
    wb = Workbook(); ws = wb.active
    for r in (title or TITLE): ws.append([None if (isinstance(v, float) and v != v) else v for v in r][:len(hdr)])
    ws.append([None if (isinstance(v, float) and v != v) else v for v in hdr])
    for r in body.itertuples(index=False): ws.append([None if (v is None or (not isinstance(v, str) and pd.isna(v))) else (v.to_pydatetime() if isinstance(v, pd.Timestamp) else v) for v in r])
    path = os.path.join(tmp, name); wb.save(path); return path
def col(hdr, name): return hdr.index(name)

engine = get_engine("sqlite:///" + os.path.join(tmp, "t.db"))
t0 = datetime(2026, 11, 5, 9, 0); step = [0]
def at(): step[0] += 1; return t0 + timedelta(hours=step[0])
def run(path, **kw): return P.ingest_file(engine, path, kw.pop("t", None) or at(), **kw)

hdr, body = fresh()
check("source file has repeated headers (Unit, Unit.1 ...) so the order test is meaningful", sum(1 for h in hdr if h == "Unit") > 1, f"{sum(1 for h in hdr if h == 'Unit')} columns named Unit")
base = run(write("base.xlsx", hdr, body))
check("baseline loaded", base["status"] == "promoted", f"{base['new']} rows")
N = base["new"]

print("\n== A. Column ORDER does not matter ==")
hdr, body = fresh(); order = list(range(len(hdr))); random.Random(7).shuffle(order)
r = run(write("shuffled.xlsx", [hdr[i] for i in order], body[order]))
check("columns shuffled randomly: nothing new, changed or missing", r["status"] == "promoted" and (r["new"], r["changed"], r["ended"]) == (0, 0, 0), f"new={r.get('new')} changed={r.get('changed')} gone={r.get('ended')}")

print("\n== B. EXTRA columns do not matter ==")
hdr, body = fresh(); hdr2 = hdr + ["Remarks 2026", "Another new blank column"]; body2 = body.copy(); body2[len(hdr)] = "note"; body2[len(hdr) + 1] = None
r = run(write("extra.xlsx", hdr2, body2))
check("two new columns added: nothing counted as changed", r["status"] == "promoted" and (r["new"], r["changed"], r["ended"]) == (0, 0, 0), r["message"])
snap = P.snapshot(engine, "NG", "OI"); check("the new column is stored for every shipment", snap["extra"].map(lambda e: e.get("Remarks 2026") == "note").all())
hdr, body = fresh(); idx = col(hdr, "Customer Branch") if "Customer Branch" in hdr else 10
hdr3 = hdr + ["Remarks 2026"]; body3 = body.copy(); body3[len(hdr)] = "note"
keep = [i for i in range(len(hdr)) if i != idx]
r = run(write("removed.xlsx", [hdr[i] for i in keep] + ["Remarks 2026"], body3[keep + [len(hdr)]]))
check("a column removed: nothing counted as changed", r["status"] == "promoted" and (r["new"], r["changed"], r["ended"]) == (0, 0, 0), r["message"])

print("\n== C. A real change is still caught when the columns also changed ==")
hdr, body = fresh(); si = col(hdr, "Status"); old_status = body.iloc[5, si]; body.iloc[5, si] = "Changed In Test"
hdr_c = hdr + ["Yet another column"]; body[len(hdr)] = "x"
r = run(write("realchange.xlsx", hdr_c, body))
check("exactly one shipment changed", r["status"] == "promoted" and (r["new"], r["changed"], r["ended"]) == (0, 1, 0), f"changed={r.get('changed')}")

print("\n== D. Header spelling, blank rows, footer, text dates ==")
hdr, body = fresh(); hdr_d = [("  job   owner " if h == "Job Owner" else ("SHIPMENT DATE" if h == "Shipment Date" else h)) for h in hdr]
body.iloc[5, si] = "Changed In Test"      # keep the change from step C so only formatting differs
dcol = col(hdr, "Shipment Date"); body[dcol] = pd.to_datetime(body[dcol]).dt.strftime("%d/%m/%Y")   # text dates, day first
blank = pd.DataFrame([[None] * len(hdr)], columns=body.columns); footer = pd.DataFrame([[None] * len(hdr)], columns=body.columns); footer.iloc[0, 0] = "Total"; footer.iloc[0, 5] = 123
r = run(write("formatting.xlsx", hdr_d, pd.concat([body, blank, footer], ignore_index=True)))
check("odd header case/spacing, text dates (dd/mm/yyyy), a blank row and a footer row: nothing counted as changed", r["status"] == "promoted" and (r["new"], r["changed"], r["ended"]) == (0, 0, 0), f"{r['message']}")

print("\n== E. Admin upload: preview first, then load ==")
hdr, body = fresh(); body.iloc[5, si] = "Changed In Test"; body.iloc[7, si] = "Changed In Test 2"
p = write("manual.xlsx", hdr, body); before = len(P.list_imports(engine))
pv = P.preview_file(engine, p, at())
check("preview says what would happen and writes nothing", pv["verdict"] == "ready" and pv["changed"] == 1 and len(P.list_imports(engine)) == before, f"{pv['company']} {pv['report_type']}, {pv['rows']} rows, new={pv['new']} changed={pv['changed']} gone={pv['ended']}")
r = run(p, source="manual", uploaded_by="admin@example.com")
check("manual upload loads through the same rules and is logged", r["status"] == "promoted" and P.list_imports(engine).iloc[0]["source"] == "manual" and P.list_imports(engine).iloc[0]["uploaded_by"] == "admin@example.com")
pv2 = P.preview_file(engine, p, at()); check("uploading the same file again is flagged as a duplicate", pv2["verdict"] == "duplicate")
hdr, body = fresh(); body.iloc[5, si] = "Changed In Test"; body.iloc[9, si] = "Changed In Test 3"
p_old = write("manual_old.xlsx", hdr, body); pv3 = P.preview_file(engine, p_old, t0); check("a different file whose report time is older than the current data is flagged as older", pv3["verdict"] == "stale", pv3["message"])
bad = os.path.join(tmp, "notareport.xlsx"); wb = Workbook(); wb.active.append(["hello"]); wb.save(bad)
check("a random Excel file is rejected with a clear reason", P.preview_file(engine, bad)["verdict"] == "rejected", P.preview_file(engine, bad)["message"])

print("\n== F. Held-for-review queue: approve with a reason ==")
hdr, body = fresh(); small = body.iloc[: int(len(body) * 0.7)]
held = run(write("small.xlsx", hdr, small), source="manual", uploaded_by="admin@example.com")
check("a report with 30% fewer rows is held and current data is untouched", held["status"] == "needs_review" and len(P.snapshot(engine, "NG", "OI")) == N, held["message"])
check("approving without a reason is refused", P.approve_import(engine, held["import_id"], "admin@example.com", " ")["status"] == "error")
a = P.approve_import(engine, held["import_id"], "admin@example.com", "Branch closed, report intentionally smaller")
check("approved with a reason: loaded, and the missing shipments are 'not present'", a["status"] == "promoted" and a["ended"] == N - len(small), f"gone={a.get('ended')}")
log = P.list_imports(engine); row = log[log.id == a["import_id"]].iloc[0]
check("the approval is logged with who and why", row["approved_by"] == "admin@example.com" and "intentionally" in row["override_reason"])
check("the held entry is marked approved", log[log.id == held["import_id"]].iloc[0]["status"] == "approved")

print("\n== G. Failed import can be retried from the archived original ==")
hdr, body = fresh(); bad_hdr = [("Shipment No" if h == "Shipment No" else h) for h in hdr]; k = col(hdr, "Customer"); keep = [i for i in range(len(hdr)) if i != k]
f = run(write("nocustomer.xlsx", [hdr[i] for i in keep], body[keep]))
check("a report missing a needed column is rejected with the column named", f["status"] == "failed" and "Customer" in f["message"], f["message"])
rt = P.retry_import(engine, f["import_id"]); check("retrying while still broken fails again, and is logged", rt["status"] == "failed")

print("\n== H. Email subject cross-check ('Shipment Register - Ocean Import - NGL') ==")
def variant(i, tag):
    hdr, body = fresh(); body.iloc[i, si] = tag; return write(f"subj_{i}.xlsx", hdr, body)
cur0 = P.current_import_id(engine, "NG", "OI")
r = run(variant(12, "Subject test 1"), subject="Shipment Register - Ocean Import - NGL")
check("subject agrees with the file: loads normally", r["status"] == "promoted", r["message"])
cur1 = P.current_import_id(engine, "NG", "OI")
r = run(variant(13, "Subject test 2"), subject="Shipment Register - Ocean Export - NGL")
check("subject says Ocean Export but the file is Sea Import: held, current data untouched", r["status"] == "needs_review" and P.current_import_id(engine, "NG", "OI") == cur1, r["message"])
held_subj = r["import_id"]
r = run(variant(14, "Subject test 3"), subject="Shipment Register - Ocean Import - NCS")
check("subject says NCS but the file is New Globe: held", r["status"] == "needs_review" and "company" in r["message"], r["message"])
pv = P.preview_file(engine, variant(15, "Subject test 4"), at(), subject="Shipment Register - Air Import - NGL")
check("the upload preview shows the mismatch before anything is loaded", pv["verdict"] == "needs_review", pv["message"])
a = P.approve_import(engine, held_subj, "admin@example.com", "ERP subject template was wrong; file is correct")
check("an admin can approve a held mismatch with a reason", a["status"] == "promoted", f"loaded as import {a.get('import_id')}")
r = run(variant(16, "Subject test 5"), subject="Daily report")
check("a subject that cannot be read is not an error, and the log says it was not cross-checked", r["status"] == "promoted" and "not cross-checked" in r["message"], r["message"])
r = run(variant(17, "Subject test 6"), subject="RE: Shipment Register - Sea Import - NGL")
check("a reply or forward prefix does not matter", r["status"] == "promoted", r["message"])

print("\n== I. History: last year stays when this year's register arrives ==")
engine = get_engine("sqlite:///" + os.path.join(tmp, "history.db"))      # a fresh database for this section
step[0] = 100
def retitle(frm, to): return [[(c.replace(frm, to) if isinstance(c, str) else c) for c in row] for row in TITLE]
def year_file(name, years_back, title, keep=None, status_tag=None, drop_first=0):
    hdr, body = fresh(); dcol = col(hdr, "Shipment Date")
    if years_back: body[dcol] = pd.to_datetime(body[dcol]) - pd.DateOffset(years=years_back)
    if status_tag: body.iloc[3, col(hdr, "Status")] = status_tag
    if keep is not None: body = body[body[col(hdr, "Branch")].isin(keep)]
    return write(name, hdr, body.iloc[drop_first:], title)
T25, T26 = retitle("2026", "2025"), TITLE
def by_year(): s = P.snapshot(engine, "NG", "OI"); y = pd.to_datetime(s["shipment_date"]).dt.year; return int((y == 2025).sum()), int((y == 2026).sum())
r = run(year_file("y25.xlsx", 1, T25)); check("last year's full register loads (the one-time backfill)", r["status"] == "promoted", f"{r['new']} rows")
r = run(year_file("y26.xlsx", 0, T26)); n25, n26 = by_year()
check("this year's register loads next: last year is NOT overwritten and nothing is marked 'no longer present'", r["status"] == "promoted" and r["ended"] == 0 and (n25, n26) == (N, N), f"2025 rows kept={n25}, 2026 rows={n26}, no longer present={r['ended']}")
r = run(year_file("y26b.xlsx", 0, T26, drop_first=1)); n25, n26 = by_year()
check("a shipment missing from this year's report is marked 'not present', and only that one", r["status"] == "promoted" and r["ended"] == 1 and n25 == N, f"no longer present={r['ended']}, 2025 rows kept={n25}")
r = run(year_file("y25b.xlsx", 1, T25, status_tag="Corrected last year")); n25, n26 = by_year()
check("last year can be corrected later without touching this year", r["status"] == "promoted" and r["changed"] == 1 and r["ended"] == 0 and n26 == N - 1, f"changed={r['changed']}, 2026 rows still={n26}")
r = run(year_file("y25c.xlsx", 1, T25, status_tag="Older copy"), t=t0)
check("an older copy of last year's report cannot replace the newer one", r["status"] == "stale", r["message"])
mum = ["Mumbai"]; titleM = [list(row) for row in T26]; titleM[2] = [str(c).split("Branch :")[0] + "Branch :Mumbai" if isinstance(c, str) else c for c in titleM[2]]
r = run(year_file("y26_mumbai.xlsx", 0, titleM, keep=mum, status_tag="Mumbai only run")); n25, n26 = by_year()
check("a report that says it covers only Mumbai leaves every other branch untouched", r["status"] == "promoted" and r["ended"] == 0 and n26 >= N - 1 - 5, f"no longer present={r['ended']}, 2026 rows still={n26}")
r = run(year_file("y26_silent.xlsx", 0, T26, keep=mum, status_tag="Silently filtered"))
check("the same Mumbai-only file claiming to cover ALL branches is held for review", r["status"] == "needs_review", r["message"])
pv = P.preview_file(engine, year_file("pv.xlsx", 0, T26, status_tag="Preview"), at())
check("the upload preview says what dates and branches a file covers", str(pv["covers_from"]) == "2026-01-01" and str(pv["covers_to"]) == "2026-12-31" and len(pv["covers_branches"]) > 5, f"{pv['covers_from']} to {pv['covers_to']}, {len(pv['covers_branches'])} branches")

print("\n== Imports log (latest first) ==")
pd.set_option("display.width", 220, "display.max_colwidth", 70)
print(P.list_imports(engine)[["id", "status", "source", "row_count", "new_rows", "changed_rows", "ended_rows", "message"]].head(14).to_string(index=False))
print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
