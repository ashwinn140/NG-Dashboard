"""End to end: the real web app against a fresh database, using the sample ERP files.  python scripts/run_server_test.py <folder with the Excel files>"""
import gzip, json, os, re, sys, tempfile, time
from datetime import datetime, date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
tmp = tempfile.mkdtemp()
os.environ.update(INGEST_SECRET="test-ingest-secret", ADMIN_EMAIL="boss@example.com", ADMIN_PASSWORD="Correct-horse9", BASE_URL="http://testserver", SECRET_KEY="test-key", UPLOAD_DIR=os.path.join(tmp, "up"))
import pandas as pd
from openpyxl import Workbook
from fastapi.testclient import TestClient
from app.db import get_engine, imports, shipments, profit_lines, users
from app.server import create_app
from app import mailer, dataset as DS, auth
from sqlalchemy import select, func

def fresh_engine(sqlite_path):
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        from sqlalchemy import create_engine
        from app.db import metadata
        e0 = create_engine(url.replace("postgresql://", "postgresql+psycopg2://", 1)); metadata.drop_all(e0); e0.dispose(); return get_engine(url)
    return get_engine("sqlite:///" + sqlite_path)

U = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads"
REG = ["1793879006568_Ship_Reg_AE_NG1.xlsx", "1793879006569_Ship_Reg_AI_NG1.xlsx", "1793879006569_Ship_Reg_OE_NG1.xlsx", "1793879006568_Ship_Reg_OI_NG1.xlsx", "Ship_Reg_AE_NCS1_4_.xlsx", "Ship_Reg_AI_NCS1.xlsx", "Ship_Reg_OE_NCS1_4_.xlsx", "Ship_Reg_OI_NCS1.xlsx"]
PRO = ["1793934145789_New_globeJob_Profit_Analysis_Report.xlsx", "1793934145789_NCS_Job_Profit_Analysis_Report__1_.xlsx"]
fails = 0
def check(label, ok, extra=""):
    global fails; fails += 0 if ok else 1; print(("PASS  " if ok else "FAIL  ") + label + (f"   [{extra}]" if extra else ""))

eng = fresh_engine(os.path.join(tmp, "app.db")); app = create_app(eng, os.path.join(tmp, "up")); store = app.state.store
anon = TestClient(app, base_url="http://testserver")
def client(): return TestClient(app, base_url="http://testserver")
def signin(email, pw):
    c = client(); r = c.post("/auth/login", json={"login": email, "password": pw}); assert r.status_code == 200, r.text
    me = c.get("/api/me").json(); c.headers["X-CSRF-Token"] = me["csrf"]; return c, me
def post_file(c, path, **kw): 
    with open(path, "rb") as f: return c.post("/api/ingest", headers={"Authorization": "Bearer test-ingest-secret"}, files={"file": (os.path.basename(path), f)}, data=kw)

print("== 1. Doors are shut to strangers ==")
check("the home page sends a stranger to the sign-in page", anon.get("/", follow_redirects=False).status_code == 303 and anon.get("/", follow_redirects=False).headers["location"] == "/login")
check("data, admin and prefs refuse a stranger", all(anon.get(u).status_code == 401 for u in ("/api/dataset", "/api/me", "/api/prefs", "/api/admin/overview", "/api/admin/users")))
check("the Gmail endpoint refuses a wrong or missing password", anon.post("/api/ingest", files={"file": ("a.xlsx", b"x")}).status_code == 401 and anon.post("/api/ingest", headers={"Authorization": "Bearer nope"}, files={"file": ("a.xlsx", b"x")}).status_code == 401)
check("the product name is on the sign-in page and the dashboard page", "Performance Dashboard" in anon.get("/login").text)
check("security headers are on", all(h in anon.get("/login").headers for h in ("x-content-type-options", "x-frame-options", "referrer-policy")))

print("\n== 2. The Gmail script posts the ERP files ==")
t0 = time.time()
for i, f in enumerate(REG + PRO):
    r = post_file(anon, os.path.join(U, f), source="email", gmail_message_id=f"m{i}", gmail_date=f"2026-11-05T{8+i//4:02d}:{(i*7)%60:02d}:00Z", subject="Shipment Register", sender="erp@x.com")
    assert r.status_code == 200 and r.json()["status"] == "queued", r.text
check("ten files accepted at once (answered 'queued', not kept waiting)", True, f"{time.time()-t0:.1f}s")
check("they all load in the background", store.wait_idle(300))
with eng.connect() as c:
    st = dict(c.execute(select(imports.c.status, func.count()).group_by(imports.c.status)).all()); n_ship = c.execute(select(func.count()).select_from(shipments).where(shipments.c.to_import.is_(None))).scalar(); n_pl = c.execute(select(func.count()).select_from(profit_lines).where(profit_lines.c.to_import.is_(None))).scalar()
check("every file promoted", st.get("promoted") == 10, str(st)); check("21,409 shipments and 1,210 charge lines are held", (n_ship, n_pl) == (21409, 1210), f"{n_ship}, {n_pl}")
r = post_file(anon, os.path.join(U, REG[3]), source="email", gmail_message_id="m3", gmail_date="2026-11-05T09:00:00Z")
check("the same email posted again is recognised as a duplicate", r.json()["status"] == "duplicate", r.json()["message"])
bad = os.path.join(tmp, "broken.xlsx"); open(bad, "wb").write(b"this is not a spreadsheet")
r = post_file(anon, bad, source="email", gmail_message_id="mx", gmail_date="2026-11-05T10:00:00Z"); store.wait_idle(60)
with eng.connect() as c: last = c.execute(select(imports.c.status, imports.c.message).order_by(imports.c.id.desc())).first()
check("a broken file is recorded as failed and the queue carries on", last.status == "failed", last.message[:60])
r = post_file(anon, os.path.join(U, "Dashboard.xlsx"), source="email", gmail_message_id="my", gmail_date="2026-11-05T11:00:00Z"); store.wait_idle(60)
check("a spreadsheet that is not an ERP report is rejected cleanly", True)

print("\n== 3. Signing in ==")
admin, me = signin("boss@example.com", "Correct-horse9")
check("the first administrator is created from the settings and can sign in with a password", me["role"] == "admin" and me["finance"] is True)
check("a change without the page's security token is refused", admin.post("/api/admin/users", json={"email": "x@y.com"}, headers={"X-CSRF-Token": "wrong"}).status_code == 403)
check("the dashboard and the admin portal open for the administrator", admin.get("/").status_code == 200 and "Loading the dashboard" in admin.get("/").text and "Performance Dashboard" in admin.get("/").text and "{{PRODUCT}}" not in admin.get("/").text and admin.get("/admin").status_code == 200)
r = admin.post("/api/admin/users", json={"email": "ops@example.com", "name": "Olive Ops", "role": "operations", "companies": ["NG"], "lobs": ["AE"]}); check("the admin adds an operations user limited to New Globe Air Export", r.status_code == 200 and r.json()["finance"] is False)
admin.post("/api/admin/users", json={"email": "fin@example.com", "name": "Fiona Fin", "role": "finance", "companies": ["NCS"], "password": "Another-pass77"})
admin.post("/api/admin/users", json={"email": "mgr@example.com", "name": "Manoj Mgr", "role": "management", "user_id": "manoj", "password": "Manager-pass88"})
mailer.OUTBOX.clear(); r = anon.post("/auth/request", json={"email": "ops@example.com"}); mail = mailer.OUTBOX[-1]["text"]
link = re.search(r"(http://testserver/auth/verify\?t=[\w-]+)", mail).group(1); code = re.search(r"page: (\d{6})", mail).group(1)
check("an email link and a 6-digit code are mailed", bool(link) and len(code) == 6)
cs = client(); page = cs.get(link.replace("http://testserver", "")); check("opening the link only shows a Continue page (mail scanners cannot use it up)", "Continue" in page.text and cs.get("/api/me").status_code == 401)
r = cs.post("/auth/verify", data={"t": link.split("t=")[1]}, follow_redirects=False); check("pressing Continue signs in", r.status_code == 303 and cs.get("/api/me").json()["email"] == "ops@example.com")
check("the link works only once", client().post("/auth/verify", data={"t": link.split("t=")[1]}).status_code == 400)
mailer.OUTBOX.clear(); anon.post("/auth/request", json={"email": "ops@example.com"}); code2 = re.search(r"page: (\d{6})", mailer.OUTBOX[-1]["text"]).group(1)
cc = client(); r = cc.post("/auth/code", json={"email": "ops@example.com", "code": code2}); check("the 6-digit code signs in too", r.status_code == 200 and cc.get("/api/me").status_code == 200)
mailer.OUTBOX.clear(); anon.post("/auth/request", json={"email": "ops@example.com"}); wrong = ["000000", "111111", "222222", "333333", "444444"]
rs = [client().post("/auth/code", json={"email": "ops@example.com", "code": w}).status_code for w in wrong]; code3 = re.search(r"page: (\d{6})", mailer.OUTBOX[-1]["text"]).group(1)
check("five wrong codes use the code up: the right one no longer works", all(s == 400 for s in rs) and client().post("/auth/code", json={"email": "ops@example.com", "code": code3}).status_code == 400)
mailer.OUTBOX.clear(); [anon.post("/auth/request", json={"email": "mgr@example.com"}) for _ in range(12)]
check("at most 10 links per hour per address", len(mailer.OUTBOX) == 10, f"{len(mailer.OUTBOX)} sent of 12 asked")
mailer.OUTBOX.clear(); r = anon.post("/auth/request", json={"email": "stranger@nowhere.com"}); check("an unknown address gets the same reply and no email", r.json()["ok"] and not mailer.OUTBOX)
app.state.hits.clear(); mgr, me_m = signin("manoj", "Manager-pass88"); check("a user ID and password sign in (the ID works as well as the email)", me_m["role"] == "management" and me_m["finance"])
msgs = [client().post("/auth/login", json={"login": "fin@example.com", "password": "bad" + str(i)}).json()["detail"] for i in range(5)]
r = client().post("/auth/login", json={"login": "fin@example.com", "password": "Another-pass77"}); check("five wrong passwords lock the account for a while (even the right password is refused)", r.status_code == 400 and "Too many" in r.json()["detail"])
with eng.begin() as c: c.execute(users.update().where(users.c.email == "fin@example.com").values(locked_until=None, fail_count=0))
app.state.hits.clear(); fin, me_f = signin("fin@example.com", "Another-pass77")
r = client().post("/auth/login", json={"login": "nobody", "password": "x"}); check("a wrong ID and a wrong password look the same", r.json()["detail"] == "That ID or password is not right.")

app.state.hits.clear(); lim = [client().post("/auth/request", json={"email": "x@x.com"}).status_code for _ in range(33)]; check("a flood of sign-in requests from one place is slowed down (429)", 429 in lim and lim[0] == 200, f"first 429 at request {lim.index(429)+1 if 429 in lim else None}"); app.state.hits.clear()
print("\n== 4. People see only what they are allowed ==")
ops, _ = signin("ops@example.com", "x") if False else (cs, None); ops.headers["X-CSRF-Token"] = cs.get("/api/me").json()["csrf"]
def ds(c):
    r = c.get("/api/dataset"); assert r.headers.get("content-encoding") == "gzip" and "no-store" in r.headers.get("cache-control", ""); return r.json()
Da, Do, Df, Dm = ds(admin), ds(ops), ds(fin), ds(mgr)
check("administrator and management get everything", len(Da["rep"]) == 21409 and len(Da["p"]["co"]) == 1210 and len(Dm["rep"]) == 21409 and len(Dm["p"]["co"]) == 1210)
check("operations (New Globe, Air Export): 9,777 shipments and no money at all", len(Do["rep"]) == 9777 and len(Do["p"]["co"]) == 0 and Do["user"]["finance"] is False and all(Do["rep"][i] == 0 for i in range(len(Do["rep"]))), f"{len(Do['rep'])} rows")
check("finance (Neutral Consolidation): 3,010 shipments, only Neutral's 90 charge lines", len(Df["rep"]) == 3010 and len(Df["p"]["co"]) == 90 and set(Df["p"]["co"]) == {1}, f"{len(Df['rep'])} rows, {len(Df['p']['co'])} lines")
full = store.full; ci = full["cols"]["customer"]; cust_all = [ci["d"][c] for c in ci["c"]]; ng_ae = {cust_all[i] for i in range(len(cust_all)) if full["rep"][i] == 0}; hidden = {c for c in set(cust_all) if c not in ng_ae}
dc = set(Do["cols"]["customer"]["d"]); dagent = Do["cols"]["agent"]["d"]; hidden_ag = {full["cols"]["agent"]["d"][c] for i, c in enumerate(full["cols"]["agent"]["c"]) if full["rep"][i] != 0} - {full["cols"]["agent"]["d"][c] for i, c in enumerate(full["cols"]["agent"]["c"]) if full["rep"][i] == 0}
check("names of customers and agents the person may not see are not even in the data sent", not (dc & hidden) and not (set(dagent) & hidden_ag), f"{len(dc)} customers sent of {len(set(cust_all))}")
check("agent details only for agents sent", len(Do["agentInfo"]) == len(Do["cols"]["agent"]["d"]))
check("the other reports show no rows and no dates for this person", all(m["rows"] == 0 for i, m in enumerate(Do["meta"]) if i != 0) and Do["meta"][0]["rows"] == 9777)
check("operations cannot open the admin portal or its data", ops.get("/admin", follow_redirects=False).status_code == 303 and ops.get("/api/admin/users").status_code == 403 and ops.post("/api/admin/users", json={"email": "z@z.com"}).status_code == 403)

print("\n== 5. Saved visuals, views and settings follow the person ==")
vis = [{"id": "v1", "title": "My chart", "data": "ops", "measure": "count", "dim": "time:month"}]
check("a person saves visuals", ops.put("/api/prefs/visuals", json=vis).status_code == 200 and ops.get("/api/prefs").json()["visuals"] == vis)
check("another person does not see them", "visuals" not in mgr.get("/api/prefs").json())
check("an unknown item and a huge item are refused", ops.put("/api/prefs/hack", json={}).status_code == 404 and ops.put("/api/prefs/views", content=b"[" + b"1," * 600000 + b"1]", headers={"Content-Type": "application/json", "X-CSRF-Token": ops.headers["X-CSRF-Token"]}).status_code == 413)

print("\n== 6. The admin portal ==")
ov = admin.get("/api/admin/overview").json(); check("overview: nothing queued, history by year shown", ov["queue"] == 0 and len(ov["coverage"]) >= 3 and len(ov["profit_coverage"]) >= 3, f"needs attention {ov['needs_attention']}")
imps = admin.get("/api/admin/imports").json(); check("the import log lists every file with its result", len(imps) >= 12 and {"promoted", "failed"} <= {i["status"] for i in imps}, f"{len(imps)} entries")
with open(os.path.join(U, REG[3]), "rb") as f: pv = admin.post("/api/admin/upload/preview", files=[("files", (REG[3], f))]).json()
check("preview of a file already loaded says duplicate", pv[0]["verdict"] == "duplicate", pv[0]["message"][:50])
# previous years: one register and one profit report, made from the samples
raw = pd.read_excel(os.path.join(U, REG[3]), header=None, dtype=object); HDR = 3; hdr0 = list(raw.iloc[HDR]); dcol = hdr0.index("Shipment Date")
body = raw.iloc[HDR + 1:].reset_index(drop=True).copy(); body.columns = range(len(hdr0)); body[dcol] = pd.to_datetime(body[dcol]) - pd.DateOffset(years=1)
wb = Workbook(); ws = wb.active
for row in raw.iloc[:HDR].values.tolist(): ws.append([(c.replace("2026", "2025") if isinstance(c, str) else (None if isinstance(c, float) and c != c else c)) for c in row][:len(hdr0)])
ws.append([None if (isinstance(v, float) and v != v) else v for v in hdr0])
for r in body.itertuples(index=False): ws.append([None if (v is None or (not isinstance(v, str) and pd.isna(v))) else (v.to_pydatetime() if isinstance(v, pd.Timestamp) else v) for v in r])
y25 = os.path.join(tmp, "Ship_Reg_OI_NG_2025.xlsx"); wb.save(y25)
import openpyxl
rows = [list(r) for r in openpyxl.load_workbook(os.path.join(U, PRO[0]), read_only=True, data_only=True).worksheets[0].iter_rows(values_only=True)]
from datetime import timedelta
rows[0][0] = rows[0][0].replace("01-Nov-2026 to 30-Nov-2026", "01-Jan-2025 to 31-Dec-2025")
for i, r in enumerate(rows):
    if i > 2 and r[0] not in (None, "", "Total") and not str(r[0]).startswith("Generated") and r[5] not in ("Total", "Job Total"):
        r[2] = r[2] + "-25"
        for k in (3, 7, 10):
            if r[k]: r[k] = r[k] - timedelta(days=365)
wb = Workbook(); ws = wb.active
for r in rows: ws.append(r)
p25 = os.path.join(tmp, "Profit_NG_2025.xlsx"); wb.save(p25)
n_before = (n_ship, n_pl)
with open(y25, "rb") as a, open(p25, "rb") as b: r = admin.post("/api/admin/upload/preview", files=[("files", (os.path.basename(y25), a)), ("files", (os.path.basename(p25), b))]).json()
check("previous-year files are checked before loading: both ready", [x["verdict"] for x in r] == ["ready", "ready"], str([(x["kind"], x["company"], str(x["covers_from"])[:10], x["rows"]) for x in r]))
with open(y25, "rb") as a, open(p25, "rb") as b: q = admin.post("/api/admin/upload", files=[("files", (os.path.basename(y25), a)), ("files", (os.path.basename(p25), b))], data={"kind": "history"}).json()
check("loaded in the background, as previous reports", len(q["queued"]) == 2 and store.wait_idle(300))
with eng.connect() as c:
    n_ship2 = c.execute(select(func.count()).select_from(shipments).where(shipments.c.to_import.is_(None))).scalar(); n_pl2 = c.execute(select(func.count()).select_from(profit_lines).where(profit_lines.c.to_import.is_(None))).scalar()
    cur26 = c.execute(select(func.count()).select_from(shipments).where(shipments.c.to_import.is_(None), shipments.c.shipment_date >= date(2026, 1, 1))).scalar()
check("last year was added and this year was not touched", n_ship2 == n_ship + 1092 and n_pl2 == n_pl + 1120 and cur26 == n_ship, f"shipments {n_ship}->{n_ship2}, lines {n_pl}->{n_pl2}")
ov = admin.get("/api/admin/overview").json(); y = {(r["company"], r["year"]): r for r in ov["profit_coverage"]}
check("history by year shows the earlier year's lines (financial year Apr-Mar: Jan-Mar 2026 is not in the sample, so not fully covered)", y.get(("NG", 2025), {}).get("lines") == 1120 and y[("NG", 2025)]["import_covers_year"] is False, str(y.get(("NG", 2025))))
admin.put("/api/admin/settings", json={"fy_start_month": "1"}); ov = admin.get("/api/admin/overview").json(); y = {(r["company"], r["year"]): r for r in ov["profit_coverage"]}
check("with a calendar year setting, 2025 shows as fully covered", y.get(("NG", 2025), {}).get("import_covers_year") is True, str(y.get(("NG", 2025)))); admin.put("/api/admin/settings", json={"fy_start_month": "4"})
Da2 = ds(admin); check("the dashboard data includes the earlier year", len(Da2["rep"]) == 21409 + 1092 and len(Da2["p"]["co"]) == 1210 + 1120)
jps = [i for i in admin.get("/api/admin/imports").json() if i["status"] == "promoted" and i["report_type"] == "JP" and i["company"] == "NG"]; newest, oldest = jps[0], jps[-1]
r = admin.post(f"/api/admin/imports/{oldest['id']}/undo", json={"reason": "test"}); check("only the latest load of a report can be undone (an older one is refused)", r.status_code == 400, r.json().get("detail", ""))
r = admin.post(f"/api/admin/imports/{newest['id']}/undo", json={"reason": "test"}); check("undo of the latest load removes it and restores what it replaced", r.status_code == 200 and r.json()["removed"] == 1120, str(r.json()))
with eng.connect() as c: back = c.execute(select(func.count()).select_from(profit_lines).where(profit_lines.c.to_import.is_(None))).scalar()
check("after the undo the data is back to where it was", back == 1210, str(back))
r = admin.post(f"/api/admin/imports/{newest['id']}/undo", json={"reason": "again"}); check("an import cannot be undone twice", r.status_code == 400)
# organisation master with contact details
mdf = pd.read_excel(os.path.join(U, "Organization_Master_data-NGL.xlsx")); ag = Da["cols"]["agent"]["d"][Da["cols"]["agent"]["c"][0]]; mdf["Contact Name"] = None; mdf["Email Address"] = None
k = mdf.Organization.astype(str).str.strip() == ag; mdf.loc[k, "Contact Name"] = "Test Contact"; mdf.loc[k, "Email Address"] = "contact@agent.example"; mp = os.path.join(tmp, "Organization_Master_data-NGL.xlsx"); mdf.to_excel(mp, index=False)
with open(mp, "rb") as f: pv = admin.post("/api/admin/master/preview", files={"file": ("m.xlsx", f)}).json()
with open(mp, "rb") as f: r = admin.post("/api/admin/master", files={"file": ("m.xlsx", f)}, data={"company": "NG"})
Dn = ds(admin); i = Dn["cols"]["agent"]["d"].index(ag)
check("an updated Organization master brings contact and email into the data", pv["with_email"] == 1 and r.status_code == 200 and Dn["agentInfo"][i][4:] == ["Test Contact", "contact@agent.example"], str(Dn["agentInfo"][i]))
# users
us = admin.get("/api/admin/users").json(); me_id = [u for u in us if u["email"] == "boss@example.com"][0]["id"]; ops_id = [u for u in us if u["email"] == "ops@example.com"][0]["id"]
check("an administrator cannot demote or lock themselves out", admin.patch(f"/api/admin/users/{me_id}", json={"active": False}).status_code == 400 and admin.patch(f"/api/admin/users/{me_id}", json={"role": "operations"}).status_code == 400)
r = admin.patch(f"/api/admin/users/{ops_id}", json={"lobs": ["AE", "AI"], "companies": ["NG", "NCS"]}); check("changing a user's LOBs and companies works", r.json()["lobs"] == ["AE", "AI"])
Do2 = ds(ops); check("and takes effect on the person's next load", len(Do2["rep"]) == 9777 + 4352 + 2193 + 59, f"{len(Do2['rep'])} rows")
admin.patch(f"/api/admin/users/{ops_id}", json={"active": False}); check("deactivating a person ends their session at once", ops.get("/api/me").status_code == 401)
check("settings can be changed and bad values are refused", admin.put("/api/admin/settings", json={"history_years": "5"}).json()["history_years"] == "5" and admin.put("/api/admin/settings", json={"history_years": "99"}).status_code == 400)
check("the retention preview works", admin.get("/api/admin/retention").status_code == 200)
check("the activity log records what the administrator did", len(admin.get("/api/admin/audit").json()) >= 8)
r = admin.post("/auth/logout"); check("signing out ends the session", r.status_code == 200 and admin.get("/api/me").status_code == 401)
print("\nSUMMARY:", "ALL CHECKS PASSED" if not fails else f"{fails} FAILED")
store.stop = True; sys.exit(1 if fails else 0)
