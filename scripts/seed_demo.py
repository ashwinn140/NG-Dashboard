"""Loads the sample ERP files and creates demo users, so the whole app can be tried locally.
   DATABASE_URL=sqlite:///data/demo.db python scripts/seed_demo.py <folder with the Excel files>"""
import os, sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db import get_engine
from app import processor as P, master as M, auth
folder = sys.argv[1] if len(sys.argv) > 1 else "."
FILES = ["1793879006568_Ship_Reg_AE_NG1.xlsx", "1793879006569_Ship_Reg_AI_NG1.xlsx", "1793879006569_Ship_Reg_OE_NG1.xlsx", "1793879006568_Ship_Reg_OI_NG1.xlsx", "Ship_Reg_AE_NCS1_4_.xlsx", "Ship_Reg_AI_NCS1.xlsx",
         "Ship_Reg_OE_NCS1_4_.xlsx", "Ship_Reg_OI_NCS1.xlsx", "1793934145789_New_globeJob_Profit_Analysis_Report.xlsx", "1793934145789_NCS_Job_Profit_Analysis_Report__1_.xlsx"]
eng = get_engine(); t0 = datetime(2026, 11, 5, 8)
for i, f in enumerate(FILES):
    r = P.ingest_file(eng, os.path.join(folder, f), t0 + timedelta(minutes=i), source="manual", uploaded_by="seed"); print(f[:40].ljust(42), r["status"])
for co, f in (("NG", "Organization_Master_data-NGL.xlsx"), ("NCS", "Organization_Master_data-_NCS.xlsx")):
    if os.path.exists(os.path.join(folder, f)): print("master", co, M.load_master(eng, os.path.join(folder, f), co)["rows"])
for email, role, name, pw, kw in [("admin@demo.test", "admin", "Demo Admin", "Demo-admin-1234", {}), ("ops@demo.test", "operations", "Demo Operations (New Globe, Air Export)", "Demo-ops-12345", {"companies": ["NG"], "lobs": ["AE"]}), ("fin@demo.test", "finance", "Demo Finance", "Demo-fin-12345", {})]:
    try: auth.create_user(eng, email, role, name, password=pw, **kw); print("user", email, "/", pw)
    except ValueError as e: print("user", email, e)
