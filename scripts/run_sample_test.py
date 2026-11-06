"""Loads the sample registers into a throw-away database and checks every rule.
Run:  python scripts/run_sample_test.py <folder with the Excel files>
"""
import os, sys, time
from collections import Counter
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db import get_engine
from app import processor as P

folder = sys.argv[1] if len(sys.argv) > 1 else "."
# (file, assumed report time). The two Sea Export files are two runs of the same report;
# the file with 3,175 rows is treated as the earlier run.
FILES = [
    ("1793879006568_Ship_Reg_AE_NG1.xlsx",  datetime(2026, 11, 5, 9, 0)),   # NG Air Export
    ("1793879006569_Ship_Reg_AI_NG1.xlsx",  datetime(2026, 11, 5, 9, 0)),   # NG Air Import
    ("Ship_Reg_OE_NG1_4_.xlsx",             datetime(2026, 11, 5, 9, 0)),   # NG Sea Export, earlier run
    ("1793879006568_Ship_Reg_OI_NG1.xlsx",  datetime(2026, 11, 5, 9, 0)),   # NG Sea Import
    ("Ship_Reg_AE_NCS1_3_.xlsx",            datetime(2026, 11, 5, 9, 0)),   # NCS Air Export
]
NEWER_OE = ("1793879006569_Ship_Reg_OE_NG1.xlsx", datetime(2026, 11, 5, 17, 0))

os.makedirs("data", exist_ok=True)
db = "data/sample_test.db"
if os.path.exists(db): os.remove(db)
engine = get_engine(f"sqlite:///{db}")
ok = True
def check(label, cond, detail=""):
    global ok; ok &= bool(cond)
    print(("PASS  " if cond else "FAIL  ") + label + (f"   [{detail}]" if detail else ""))

print("== 1. First load of each report ==")
for f, t in FILES:
    t0 = time.time(); r = P.ingest_file(engine, os.path.join(folder, f), t)
    reg = P.read_register(os.path.join(folder, f))
    print(f"  {P.config.COMPANY_LABELS[reg.company]:<22}{P.config.REPORT_LABELS[reg.report_type]:<12} rows={len(reg.df):>6}  -> {r['status']}  ({time.time()-t0:.0f}s)")
    check(f"{f} promoted with every row", r["status"] == "promoted" and r["new"] == len(reg.df))

print("\n== 2. Same file again (duplicate) ==")
r = P.ingest_file(engine, os.path.join(folder, FILES[0][0]), datetime(2026, 11, 5, 12, 0))
check("identical file is ignored", r["status"] == "duplicate", r["message"])

print("\n== 3. Newer Sea Export run: what changed ==")
oe_old = P.current_import_id(engine, "NG", "OE")
r = P.ingest_file(engine, os.path.join(folder, NEWER_OE[0]), NEWER_OE[1])
newer_id = r["import_id"]
check("newer run promoted", r["status"] == "promoted", f"new={r.get('new')} changed={r.get('changed')} no longer present={r.get('ended')}")
d = P.diff(engine, "NG", "OE", oe_old, r["import_id"])
print(f"  New shipments ({len(d['new'])}):", ", ".join(d["new"]["shipment_no"].tolist()[:10]))
print(f"  No longer present ({len(d['gone'])}):", ", ".join(d["gone"]["shipment_no"].tolist()[:10]))
cols = Counter(c for v in d["changed_fields"].values() for c in v)
print(f"  Changed shipments: {len(d['changed_keys'])}. Columns that changed most:", cols.most_common(8))

print("\n== 4. Older report arriving late (stale) ==")
reg = P.read_register(os.path.join(folder, FILES[2][0]))
r = P.process_register(engine, reg, "late_copy.xlsx", "test-sha-stale", datetime(2026, 11, 5, 11, 0))
check("older report does not replace newer data", r["status"] == "stale", r["message"])

print("\n== 5. Bad reports ==")
reg = P.read_register(os.path.join(folder, NEWER_OE[0]))
bad = P.Register(reg.company, reg.report_type, reg.df.drop(columns=["Customer"]), reg.title)
r = P.process_register(engine, bad, "no_customer.xlsx", "test-sha-1", datetime(2026, 11, 6, 9, 0))
check("missing column is rejected", r["status"] == "failed", r["message"])
dupk = P.Register(reg.company, reg.report_type, __import__("pandas").concat([reg.df, reg.df.head(3)]), reg.title)
r = P.process_register(engine, dupk, "dup_keys.xlsx", "test-sha-2", datetime(2026, 11, 6, 9, 0))
check("repeated shipment key is rejected", r["status"] == "failed", r["message"])
part = P.Register(reg.company, reg.report_type, reg.df.head(int(len(reg.df) * 0.7)), reg.title)
r = P.process_register(engine, part, "partial.xlsx", "test-sha-3", datetime(2026, 11, 6, 9, 0))
check("report with 30% fewer rows is held for review", r["status"] == "needs_review", r["message"])
check("current data untouched by the bad reports", P.current_import_id(engine, "NG", "OE") == newer_id)
snap = P.snapshot(engine, "NG", "OE")
check("current Sea Export still has all rows", len(snap) == len(reg.df), f"{len(snap)} rows")

print("\n== 6. A shipment that disappears is 'not present', never 'completed' ==")
smaller = P.Register(reg.company, reg.report_type, reg.df.iloc[1:], reg.title)    # drop one shipment
r = P.process_register(engine, smaller, "one_less.xlsx", "test-sha-4", datetime(2026, 11, 6, 9, 0))
check("one missing shipment is applied", r["status"] == "promoted" and r["ended"] == 1, f"ended={r.get('ended')}")
import sqlalchemy as sa
from app.db import shipments
with engine.connect() as c:
    reasons = c.execute(sa.select(shipments.c.ended_reason, sa.func.count()).where(shipments.c.ended_reason.isnot(None)).group_by(shipments.c.ended_reason)).all()
print("  Reasons recorded:", dict(reasons))
check("an old snapshot can still be rebuilt", len(P.snapshot(engine, "NG", "OE", oe_old)) == 3175)

print("\n== Imports log ==")
import pandas as pd
pd.set_option("display.width", 200, "display.max_colwidth", 60)
print(pd.read_sql("select id, company c, report_type t, status, row_count rows, new_rows new, changed_rows chg, ended_rows gone from imports", engine).to_string(index=False))
print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
