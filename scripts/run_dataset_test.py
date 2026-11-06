"""Loads the sample ERP files into a fresh database, rebuilds the dashboard data from it and checks it equals the data the review file was built from."""
import sys, os, gzip, base64, json, tempfile, time
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from app.db import get_engine
from app import processor as P, master as M, dataset as DS
def fresh_engine(sqlite_path):
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        from sqlalchemy import create_engine
        from app.db import metadata
        e0 = create_engine(url.replace("postgresql://", "postgresql+psycopg2://", 1)); metadata.drop_all(e0); e0.dispose(); return get_engine(url)
    return get_engine("sqlite:///" + sqlite_path)

U = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads"
REF = sys.argv[2] if len(sys.argv) > 2 else "/home/claude/review/data.b64"
FILES = ["1793879006568_Ship_Reg_AE_NG1.xlsx", "1793879006569_Ship_Reg_AI_NG1.xlsx", "1793879006569_Ship_Reg_OE_NG1.xlsx", "1793879006568_Ship_Reg_OI_NG1.xlsx",
         "Ship_Reg_AE_NCS1_4_.xlsx", "Ship_Reg_AI_NCS1.xlsx", "Ship_Reg_OE_NCS1_4_.xlsx", "Ship_Reg_OI_NCS1.xlsx", "1793934145789_New_globeJob_Profit_Analysis_Report.xlsx", "1793934145789_NCS_Job_Profit_Analysis_Report__1_.xlsx"]
fails = 0
def check(label, ok, extra=""):
    global fails; fails += 0 if ok else 1; print(("PASS  " if ok else "FAIL  ") + label + (f"   [{extra}]" if extra else ""))
tmp = tempfile.mkdtemp(); eng = fresh_engine(os.path.join(tmp, "t.db")); t0 = datetime(2026, 11, 5, 8)
for i, f in enumerate(FILES): r = P.ingest_file(eng, os.path.join(U, f), t0 + timedelta(minutes=i)); assert r["status"] == "promoted", (f, r)
print("loaded", len(FILES), "files")
M.load_master(eng, os.path.join(U, "Organization_Master_data-NGL.xlsx"), "NG"); M.load_master(eng, os.path.join(U, "Organization_Master_data-_NCS.xlsx"), "NCS")
t = time.time(); D = DS.build_full(eng); print(f"built in {time.time()-t:.1f}s")
R = json.loads(gzip.decompress(base64.b64decode(open(REF).read())))
for k in ["rep", "no", "date", "ops", "fin", "chg", "gross", "teus", "cbm", "ckg", "rbuy", "rbf", "rsell", "rsf", "inv1", "invN"]:
    check(f"column '{k}' identical to the review data", D[k] == R[k] or (np.allclose(D[k], R[k], equal_nan=True) if k not in ("no",) else False), f"{len(D[k])} rows")
check("every dictionary and every code identical (30 columns)", all(D["cols"][k]["d"] == R["cols"][k]["d"] and D["cols"][k].get("c") == R["cols"][k].get("c") and D["cols"][k]["pc"] == R["cols"][k]["pc"] for k in R["cols"]), f"{len(R['cols'])} columns")
check("agent details identical", D["agentInfo"] == R["agentInfo"], f"{len(D['agentInfo'])} agents")
for k in ["co", "sidx", "rt", "income", "expense", "td", "jd"]: check(f"profit '{k}' identical", D["p"][k] == R["p"][k], f"{len(D['p'][k])} lines")
check("report meta (rows, dates, pending, financials open) identical", all(all(D["meta"][i][f] == R["meta"][i][f] for f in ("co", "rep", "rows", "from", "to", "repeated", "pend", "finopen", "range_from", "range_to")) for i in range(8)))
check("profit meta: lines, income, expense, jobs, matched", all(a["lines"] == b["lines"] and abs(a["income"] - b["income"]) < 0.01 and a["jobs"] == b["jobs"] and a["matched"] == b["matched"] and a["unmatched_by_lob"] == b["unmatched_by_lob"] for a, b in zip(D["p"]["meta"], R["p"]["meta"])))
print("\nSUMMARY:", "ALL CHECKS PASSED" if not fails else f"{fails} FAILED")
json.dump(D, open(os.path.join(tmp, "full.json"), "w")); print("dataset kept at", os.path.join(tmp, "full.json"), "| db", os.path.join(tmp, "t.db"))
