"""The things that went wrong on the first real deployment must not be able to happen again.  python scripts/run_resilience_test.py <folder with the Excel files>"""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
tmp = tempfile.mkdtemp(); U = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads"; fails = 0
def check(label, ok, extra=""):
    global fails; fails += 0 if ok else 1; print(("PASS  " if ok else "FAIL  ") + label + (f"   [{extra}]" if extra else ""))
def env(**kw):
    for k in ("BASE_URL", "RAILWAY_ENVIRONMENT", "RAILWAY_PUBLIC_DOMAIN", "ADMIN_EMAIL", "ADMIN_PASSWORD", "SECRET_KEY", "INGEST_SECRET", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "UPLOAD_DIR"): os.environ.pop(k, None)
    os.environ.update(kw)
from fastapi.testclient import TestClient
from app.db import get_engine
from app.server import create_app
from app import mailer, processor as P, dataset as DS

print("== 1. A password that is too short no longer stops the app (it did, on the first deployment) ==")
env(ADMIN_EMAIL="boss@example.com", ADMIN_PASSWORD="short", SECRET_KEY="k", UPLOAD_DIR=tmp + "/up1")
app = create_app(get_engine("sqlite:///" + tmp + "/a.db"), tmp + "/up1"); c = TestClient(app)
r = c.post("/auth/login", json={"login": "boss@example.com", "password": "short"})
check("the app starts, the administrator exists without a password, and the short password is refused politely", r.status_code == 400 and "not right" in r.json()["detail"])

print("\n== 2. A volume the app cannot write to no longer crashes it (it did, after the volume was added) ==")
open(tmp + "/afile", "w").write("x"); env(ADMIN_EMAIL="boss@example.com", ADMIN_PASSWORD="Correct-horse9", SECRET_KEY="k", UPLOAD_DIR=tmp + "/afile/uploads")
app = create_app(get_engine("sqlite:///" + tmp + "/b.db"), tmp + "/afile/uploads"); c = TestClient(app); c.post("/auth/login", json={"login": "boss@example.com", "password": "Correct-horse9"}); c.headers["X-CSRF-Token"] = c.get("/api/me").json()["csrf"]
ov = c.get("/api/admin/overview").json(); chk = {x["key"]: x for x in ov["setup"]}
check("the app starts anyway and the admin portal says so, with how to fix it", chk["uploads"]["ok"] is False and "volume" in chk["uploads"]["fix"].lower(), chk["uploads"]["fix"][:80])

print("\n== 3. No more guessing at the web address (BASE_URL was missing, and sign-in was refused) ==")
env(ADMIN_EMAIL="boss@example.com", ADMIN_PASSWORD="Correct-horse9", SECRET_KEY="k", UPLOAD_DIR=tmp + "/up3")
app = create_app(get_engine("sqlite:///" + tmp + "/c.db"), tmp + "/up3"); c = TestClient(app, base_url="https://dash.example.org")
r = c.post("/auth/login", json={"login": "boss@example.com", "password": "Correct-horse9"}, headers={"Origin": "https://dash.example.org"})
check("with no BASE_URL at all, a sign-in from the site's own address works", r.status_code == 200)
r = TestClient(app, base_url="https://dash.example.org").post("/auth/login", json={"login": "boss@example.com", "password": "Correct-horse9"}, headers={"Origin": "https://evil.example"})
check("a request that claims to come from another site is still refused", r.status_code == 403)
c2 = TestClient(app, base_url="https://dash.example.org"); c2.post("/auth/login", json={"login": "boss@example.com", "password": "Correct-horse9"}, headers={"Origin": "https://dash.example.org"}); c2.headers["X-CSRF-Token"] = c2.get("/api/me").json()["csrf"]
c2.post("/api/admin/users", json={"email": "x@y.com", "role": "operations"}, headers={"Origin": "https://dash.example.org"}); mailer.OUTBOX.clear()
mailer.send  # sign-in email links carry the address the person used
r = c2.post("/auth/request", json={"email": "x@y.com"}, headers={"Origin": "https://dash.example.org"}); mail = mailer.OUTBOX[-1]["text"] if mailer.OUTBOX else ""
check("sign-in links in emails use the address people really open", "https://dash.example.org/auth/verify?t=" in mail, mail[mail.find("http"):mail.find("http") + 40])
check("the sign-in page learns whether email sign-in is available", c2.get("/auth/options").json() == {"email": False, "password": True})

print("\n== 4. A missing SECRET_KEY is named at once on Railway, instead of a silent weak default ==")
env(RAILWAY_ENVIRONMENT="production")
try: create_app(get_engine("sqlite:///" + tmp + "/d.db"), tmp + "/up4"); ok = False; msg = ""
except RuntimeError as e: ok = True; msg = str(e)
check("the app refuses to start and says exactly what to add", ok and "SECRET_KEY" in msg, msg[:70])

print("\n== 4b. Starting on an empty database logs no error (the first live start showed a traceback) ==")
import logging, io, time as _t
buf = io.StringIO(); h = logging.StreamHandler(buf); logging.getLogger("app").addHandler(h)
env(ADMIN_EMAIL="boss@example.com", ADMIN_PASSWORD="Correct-horse9", SECRET_KEY="k", UPLOAD_DIR=tmp + "/up4b")
app4 = create_app(get_engine("sqlite:///" + tmp + "/f.db"), tmp + "/up4b"); _t.sleep(3); logging.getLogger("app").removeHandler(h)
check("no 'could not prepare the dashboard data' error at start", "could not prepare" not in buf.getvalue(), buf.getvalue()[:80].replace("\n", " ")); app4.state.store.stop = True
print("\n== 5. A system with only some reports loaded still works (people load them one by one) ==")
env(ADMIN_EMAIL="boss@example.com", ADMIN_PASSWORD="Correct-horse9", SECRET_KEY="k", UPLOAD_DIR=tmp + "/up5")
eng = get_engine("sqlite:///" + tmp + "/e.db"); app = create_app(eng, tmp + "/up5", start_worker=False); c = TestClient(app); c.post("/auth/login", json={"login": "boss@example.com", "password": "Correct-horse9"})
check("an empty system answers with a clear 'nothing loaded yet'", c.get("/api/dataset").json().get("empty") is True)
from datetime import datetime
r = P.ingest_file(eng, os.path.join(U, "1793879006568_Ship_Reg_AE_NG1.xlsx"), datetime(2026, 11, 5, 8)); app.state.store.bump()
D = c.get("/api/dataset").json(); check("with a single register loaded the dashboard data builds (9,777 shipments, no profit)", len(D["rep"]) == 9777 and len(D["p"]["co"]) == 0 and not D.get("empty"), f"{len(D['rep'])} rows")
P.ingest_file(eng, os.path.join(U, "1793934145789_New_globeJob_Profit_Analysis_Report.xlsx"), datetime(2026, 11, 5, 9)); app.state.store.bump()
D = c.get("/api/dataset").json(); check("add one profit report and it joins", len(D["p"]["co"]) == 1120, f"{len(D['p']['co'])} lines")
print("\nSUMMARY:", "ALL CHECKS PASSED" if not fails else f"{fails} FAILED"); sys.exit(1 if fails else 0)
