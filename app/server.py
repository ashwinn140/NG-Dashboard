"""The web app: sign-in, the dashboard data, the admin portal and the endpoint the Gmail script posts to."""
import gc, gzip, hashlib, io, json, logging, os, secrets, shutil, tempfile, threading, time
from collections import defaultdict, deque
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select, func, insert, delete, update
from . import auth, admin_ops as ops, dataset as DS, mailer, master as MST, processor as P, profit as J
from .db import get_engine, imports, uploads, users, prefs, admin_log, shipments, org_master

log = logging.getLogger("app")
WEB = Path(__file__).parent / "web"
MAX_UPLOAD = 80 * 1048576
PREF_NAMES = {"visuals", "views", "defs"}


def df_json(df: pd.DataFrame):
    return json.loads(df.to_json(orient="records", date_format="iso")) if len(df) else []


class Store:
    """Engine, the upload folder, the import worker and the cached dashboard data."""
    def __init__(self, engine, upload_dir: str, start_worker: bool = True):
        self.engine, self.upload_dir, self.upload_warning = engine, Path(upload_dir), ""
        try:
            self.upload_dir.mkdir(parents=True, exist_ok=True); probe = self.upload_dir / ".write-test"; probe.write_text("x"); probe.unlink()
        except OSError as e:                      # never crash on this: keep working, and say so in the admin portal
            self.upload_dir = Path(tempfile.gettempdir()) / "uploads"; self.upload_dir.mkdir(parents=True, exist_ok=True)
            self.upload_warning = f"The upload folder {upload_dir} cannot be written ({e}). Files are kept in a temporary folder and will be lost at the next restart. Attach a volume at /data."
            log.error(self.upload_warning)
        self.lock = threading.RLock(); self.full = None; self.version = int(ops.get_flag(engine, "data_version", "0") or 0); self.full_version = -1
        self.cache: dict = {}; self.wake = threading.Event(); self.idle = threading.Event(); self.idle.set(); self.stop = False; self.building = False
        with engine.begin() as c: c.execute(update(uploads).where(uploads.c.status == "processing").values(status="queued"))          # a crash mid-load: try again
        if start_worker:
            self.thread = threading.Thread(target=self._worker, daemon=True, name="importer"); self.thread.start()
        self.wake.set()

    # ---- dataset
    def dataset_for(self, user: dict) -> bytes:
        with self.lock:
            with self.engine.connect() as c:
                has = c.execute(select(func.count()).select_from(shipments).where(shipments.c.to_import.is_(None)).limit(1)).scalar()
            if not has:                         # nothing loaded yet: say so instead of failing
                return gzip.compress(json.dumps({"empty": True, "user": {"finance": bool(user["finance"]), "companies": user["companies"], "lobs": user["lobs"]}}).encode(), 6)
            if self.full is None or self.full_version != self.version:
                self.full = DS.build_full(self.engine); self.full_version = self.version; self.cache.clear()
            sig = (self.version, tuple(sorted(user["companies"])), tuple(sorted(user["lobs"])), bool(user["finance"]))
            if sig not in self.cache:
                D = DS.restrict(self.full, dict(companies=user["companies"], lobs=user["lobs"], finance=user["finance"]))
                if len(self.cache) > 20: self.cache.clear()
                self.cache[sig] = gzip.compress(json.dumps(D, separators=(",", ":"), ensure_ascii=False).encode(), 6)
            return self.cache[sig]

    def warm(self):
        """Builds the dashboard data ahead of time, so the first person after a load does not wait."""
        try:
            with self.lock:
                with self.engine.connect() as c:
                    if not c.execute(select(func.count()).select_from(shipments).where(shipments.c.to_import.is_(None)).limit(1)).scalar():
                        return                      # nothing loaded yet: nothing to prepare (and no error to log)
                if self.full is None or self.full_version != self.version:
                    self.full = DS.build_full(self.engine); self.full_version = self.version; self.cache.clear()
        except Exception:
            log.exception("could not prepare the dashboard data")

    def bump(self):
        with self.lock:
            self.version += 1; ops.set_flag(self.engine, "data_version", str(self.version))

    # ---- worker
    def enqueue(self, **v) -> int:
        with self.engine.begin() as c:
            iid = c.execute(insert(uploads).values(status="queued", received_at=datetime.utcnow(), **v)).inserted_primary_key[0]
        self.idle.clear(); self.wake.set(); return iid

    def _next(self):
        with self.engine.begin() as c:
            r = c.execute(select(uploads).where(uploads.c.status == "queued").order_by(uploads.c.id).limit(1)).first()
            if r: c.execute(update(uploads).where(uploads.c.id == r.id).values(status="processing"))
        return r

    def _worker(self):
        while not self.stop:
            if os.environ.get("IMPORTS_PAUSED") == "1":
                self.wake.wait(2); self.wake.clear(); continue
            r = self._next()
            if not r:
                self.warm()  # build once after a batch, never alongside the import worker
                self.idle.set(); self.wake.wait(2); self.wake.clear(); continue
            self.idle.clear(); changed = False
            try:
                # Do not retain/build a second dashboard dataset alongside a large workbook.
                with self.lock:
                    self.full = None; self.full_version = -1; self.cache.clear()
                    gc.collect()
                    res = P.ingest_file(self.engine, r.path, r.report_time or datetime.utcnow(), r.gmail_id or "", bool(r.approve), r.source or "email", r.uploaded_by or "", r.uploaded_by if r.approve else "", r.reason or "", r.subject or "")
                status = "done"; changed = res.get("status") == "promoted"
            except Exception as e:                      # one bad file must not stop the queue
                log.exception("import failed"); status = "failed"
                msg = "The file could not be read as an Excel workbook." if type(e).__name__ in ("BadZipFile", "InvalidFileException", "KeyError") else f"{type(e).__name__}: {e}"
                with self.engine.begin() as c:
                    iid = P._record(c, None, None, report_time=r.report_time, file_name=r.file_name, file_sha256=hashlib.sha256(Path(r.path).read_bytes()).hexdigest() if r.path and Path(r.path).exists() else "", source_ref=r.gmail_id or "",
                                    status="failed", message=msg, file_path=r.path, source=r.source or "email", uploaded_by=r.uploaded_by or "", subject=r.subject or "")
                res = dict(import_id=iid, status="failed", message=msg)
            with self.engine.begin() as c: c.execute(update(uploads).where(uploads.c.id == r.id).values(status=status, result=json.loads(json.dumps(res, default=str))))
            if changed: self.bump()
            if res.get("status") in ("failed", "needs_review"): self._alert(r, res)

    def _alert(self, r, res):
        to = ops.get_settings(self.engine).get("alert_email") or os.environ.get("ALERT_EMAIL", "")
        if to: mailer.send(to, f"Dashboard: {r.file_name} was {res.get('status')}", f"{r.file_name}\n{res.get('status')}: {res.get('message', '')}\n\nOpen the admin portal > Imports to approve it, retry it or upload a corrected file.")

    def wait_idle(self, timeout: float = 120) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            with self.engine.connect() as c:
                n = c.execute(select(func.count()).select_from(uploads).where(uploads.c.status.in_(["queued", "processing"]))).scalar()
            if n == 0: return True
            time.sleep(0.2)
        return False


def create_app(engine=None, upload_dir: str | None = None, start_worker: bool = True) -> FastAPI:
    engine = engine or get_engine()
    store = Store(engine, upload_dir or os.environ.get("UPLOAD_DIR", "data/uploads"), start_worker)
    if os.environ.get("RAILWAY_ENVIRONMENT") and not os.environ.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY is not set. In Railway open the service > Variables and add SECRET_KEY (a long random text), then redeploy.")
    explicit = os.environ.get("BASE_URL", "").strip().rstrip("/"); rdom = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
    base_url = explicit or (f"https://{rdom}" if rdom else "http://localhost:8000")
    secure = base_url.startswith("https") or bool(os.environ.get("RAILWAY_ENVIRONMENT"))
    def public_base(request: Request) -> str:                  # the address people actually used; BASE_URL only overrides it
        if explicit: return explicit
        proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
        return f"{proto}://{request.headers.get('host', 'localhost')}"
    app = FastAPI(title="Performance dashboard", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store; app.state.engine = engine
    hits: dict = defaultdict(deque); app.state.hits = hits

    # bootstrap the first administrator (a bad value is reported, never allowed to stop the app from starting)
    first = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    if first:
        with engine.connect() as c: have = c.execute(select(func.count()).select_from(users)).scalar()
        if not have:
            try: auth.create_user(engine, first, "admin", os.environ.get("ADMIN_NAME", "Administrator"), password=os.environ.get("ADMIN_PASSWORD") or None)
            except ValueError as e:
                log.error("ADMIN_PASSWORD or ADMIN_EMAIL was not accepted (%s). Creating the administrator without a password: sign in by email link, or set a password in the admin portal.", e)
                try: auth.create_user(engine, first, "admin", os.environ.get("ADMIN_NAME", "Administrator"))
                except ValueError as e2: log.error("The administrator could not be created: %s", e2)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin", "Cache-Control": resp.headers.get("Cache-Control", "no-store"),
                             "Permissions-Policy": "geolocation=(), camera=(), microphone=()"})
        if secure: resp.headers["Strict-Transport-Security"] = "max-age=31536000"
        return resp

    def limit(request: Request, n: int = 30):
        ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?")); q = hits[ip]; now = time.time()
        while q and q[0] < now - 60: q.popleft()
        if len(q) >= n: raise HTTPException(429, "Too many requests. Please wait a minute.")
        q.append(now)

    def same_origin(request: Request):                          # a browser's Origin must be this very site
        o = request.headers.get("origin")
        if not o: return
        if urlparse(o).netloc == request.headers.get("host", "") or o.rstrip("/") == base_url: return
        raise HTTPException(403, "Request from another site was refused.")

    def me(request: Request) -> dict:
        u = auth.session_user(engine, request.cookies.get("ng_session"))
        if not u: raise HTTPException(401, "Please sign in.")
        return u

    def unsafe(request: Request, user: dict = Depends(me)) -> dict:        # state-changing calls: signed in + CSRF token + same site
        same_origin(request)
        if request.headers.get("x-csrf-token") != user["csrf"]: raise HTTPException(403, "The page is out of date. Reload it and try again.")
        return user

    def admin(user: dict = Depends(me)) -> dict:
        if user["role"] != "admin": raise HTTPException(403, "Administrators only.")
        return user

    def admin_unsafe(user: dict = Depends(unsafe)) -> dict:
        if user["role"] != "admin": raise HTTPException(403, "Administrators only.")
        return user

    def start_session(u: dict, method: str, resp: Response):
        raw, csrf = auth.create_session(engine, u["id"], method)
        resp.set_cookie("ng_session", raw, max_age=auth.SESSION_HOURS * 3600, httponly=True, samesite="lax", secure=secure, path="/")

    product = os.environ.get("PRODUCT_NAME", "Performance Dashboard")
    page = lambda name: HTMLResponse((WEB / name).read_text(encoding="utf-8").replace("{{PRODUCT}}", product))

    # ------------------------------------------------------------------ pages
    @app.get("/healthz")
    def healthz(): return {"ok": True}

    @app.get("/auth/options")
    def auth_options(): return {"email": mailer.configured(), "password": True}

    @app.get("/login", response_class=HTMLResponse)
    def login_page(): return page("login.html")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        if not auth.session_user(engine, request.cookies.get("ng_session")): return RedirectResponse("/login", 303)
        return page("dashboard.html")

    @app.get("/admin", response_class=HTMLResponse)
    def admin_page(request: Request):
        u = auth.session_user(engine, request.cookies.get("ng_session"))
        if not u: return RedirectResponse("/login", 303)
        if u["role"] != "admin": return RedirectResponse("/", 303)
        return page("admin.html")

    # ------------------------------------------------------------------ sign-in
    @app.post("/auth/request")
    async def request_link(request: Request):
        limit(request); same_origin(request); body = await request.json(); email = str(body.get("email", "")).strip().lower()
        r = auth.request_link(engine, email)
        if r:
            token, code, u = r
            link = f"{public_base(request)}/auth/verify?t={token}"
            mailer.send(email, f"Your {product} sign-in link", f"Hello {u['name']},\n\nOpen this link to sign in (it works once, for {auth.LINK_MINUTES} minutes):\n{link}\n\nOr type this code on the sign-in page: {code}\n\nIf you did not ask for this, ignore this email.")
        return {"ok": True, "message": "If that address is registered, a sign-in link and a 6-digit code are on their way."}

    @app.get("/auth/verify", response_class=HTMLResponse)
    def verify_page(t: str = ""):       # a mail scanner opening the link only sees this page; the link is used up by the button
        safe = "".join(ch for ch in t if ch.isalnum() or ch in "-_")
        return HTMLResponse(f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Continue</title>
<body style="font:16px system-ui;max-width:26rem;margin:15vh auto;padding:1rem;text-align:center"><h1 style="font-size:1.3rem">Sign in to the dashboard</h1><p>Press the button to finish signing in.</p>
<form method=post action="/auth/verify"><input type=hidden name=t value="{safe}"><button style="font:inherit;padding:.8rem 2rem;border-radius:8px;border:0;background:#2f5d9b;color:#fff;cursor:pointer">Continue</button></form></body>""")

    @app.post("/auth/verify")
    async def verify_do(request: Request):
        limit(request); form = await request.form(); u = auth.use_token(engine, str(form.get("t", "")))
        if not u: return HTMLResponse("<meta charset=utf-8><body style='font:16px system-ui;max-width:26rem;margin:15vh auto;padding:1rem'><p>This link has expired or was already used.</p><p><a href='/login'>Get a new one</a></p>", 400)
        resp = RedirectResponse("/", 303); start_session(u, "link", resp); return resp

    @app.post("/auth/code")
    async def code_do(request: Request):
        limit(request); same_origin(request); b = await request.json(); u = auth.use_code(engine, str(b.get("email", "")), str(b.get("code", "")))
        if not u: raise HTTPException(400, "That code is not right or has expired.")
        resp = JSONResponse({"ok": True}); start_session(u, "code", resp); return resp

    @app.post("/auth/login")
    async def password_do(request: Request):
        limit(request, 20); same_origin(request); b = await request.json(); u, msg = auth.password_login(engine, str(b.get("login", "")), str(b.get("password", "")))
        if not u: raise HTTPException(400, msg)
        resp = JSONResponse({"ok": True}); start_session(u, "password", resp); return resp

    @app.post("/auth/logout")
    def logout(request: Request):
        same_origin(request); auth.end_session(engine, request.cookies.get("ng_session")); resp = JSONResponse({"ok": True}); resp.delete_cookie("ng_session", path="/"); return resp

    @app.get("/api/me")
    def api_me(user: dict = Depends(me)):
        meta = ops.get_flag(engine, "data_version", "0")
        return {k: user[k] for k in ("id", "email", "name", "role", "companies", "lobs", "finance", "csrf")} | {"data_version": meta}

    @app.post("/api/me/password")
    async def change_password(request: Request, user: dict = Depends(unsafe)):
        b = await request.json(); u, _ = auth.password_login(engine, user["email"], str(b.get("current", "")))
        if not u and auth.session_user(engine, request.cookies.get("ng_session"))["method"] != "link": raise HTTPException(400, "Your current password is not right.")
        try: auth.set_password(engine, user["id"], str(b.get("new", "")))
        except ValueError as e: raise HTTPException(400, str(e))
        resp = JSONResponse({"ok": True}); u2 = auth.user_dict(engine.connect().execute(select(users).where(users.c.id == user["id"])).first()); start_session(u2, "password", resp); return resp

    # ------------------------------------------------------------------ the data and the user's own saved things
    @app.get("/api/dataset")
    def api_dataset(user: dict = Depends(me)):
        return Response(store.dataset_for(user), media_type="application/json", headers={"Content-Encoding": "gzip", "Cache-Control": "private, no-store"})

    @app.get("/api/prefs")
    def prefs_get(user: dict = Depends(me)):
        with engine.connect() as c: rows = c.execute(select(prefs.c.name, prefs.c.value).where(prefs.c.user_id == user["id"])).all()
        return {n: v for n, v in rows}

    @app.put("/api/prefs/{name}")
    async def prefs_put(name: str, request: Request, user: dict = Depends(unsafe)):
        if name not in PREF_NAMES: raise HTTPException(404, "Unknown item.")
        raw = await request.body()
        if len(raw) > 1_000_000: raise HTTPException(413, "That is too large to save.")
        try: val = json.loads(raw)
        except ValueError: raise HTTPException(400, "Not valid data.")
        with engine.begin() as c:
            c.execute(delete(prefs).where(prefs.c.user_id == user["id"], prefs.c.name == name)); c.execute(insert(prefs).values(user_id=user["id"], name=name, value=val, updated_at=datetime.utcnow()))
        return {"ok": True}

    # ------------------------------------------------------------------ the Gmail script
    @app.post("/api/ingest")
    async def ingest(request: Request, file: UploadFile = File(...), file_name: str = Form(""), source: str = Form("email"), gmail_message_id: str = Form(""), gmail_date: str = Form(""),
                     subject: str = Form(""), sender: str = Form("")):
        want = os.environ.get("INGEST_SECRET", "")
        got = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not want or not secrets.compare_digest(got, want): raise HTTPException(401, "Wrong or missing password.")
        data = await file.read()
        if len(data) > MAX_UPLOAD: raise HTTPException(413, "File too large.")
        name = Path(file_name or file.filename or "report.xlsx").name
        if not name.lower().endswith(".xlsx"): return JSONResponse({"status": "rejected", "message": "Only .xlsx files are accepted."}, 200)
        try: rt = datetime.fromisoformat(gmail_date.replace("Z", "+00:00")).replace(tzinfo=None) if gmail_date else datetime.utcnow()
        except ValueError: rt = datetime.utcnow()
        path, sha = save_file(store, data, name)
        with engine.connect() as c:
            dup = c.execute(select(imports.c.id).where(imports.c.file_sha256 == sha, imports.c.status == "promoted")).first() or c.execute(select(uploads.c.id).where(uploads.c.gmail_id == gmail_message_id, uploads.c.file_name == name, uploads.c.status.in_(["queued", "processing", "done"])).limit(1)).first() if gmail_message_id else None
        if dup: return {"status": "duplicate", "message": "This file was already received."}
        uid = store.enqueue(file_name=name, path=path, source=source or "email", subject=subject[:300], sender=sender[:200], gmail_id=gmail_message_id[:100], report_time=rt, uploaded_by="")
        return {"status": "queued", "upload_id": uid, "message": "Received. It will be loaded in a moment."}

    # ------------------------------------------------------------------ admin portal
    def setup_checks() -> list:
        with engine.connect() as c:
            n_ship = c.execute(select(func.count()).select_from(shipments).where(shipments.c.to_import.is_(None))).scalar()
            n_master = c.execute(select(func.count()).select_from(org_master)).scalar(); n_users = c.execute(select(func.count()).select_from(users).where(users.c.active == 1)).scalar()
            n_mail = c.execute(select(func.count()).select_from(uploads).where(uploads.c.source == "email", uploads.c.status == "done")).scalar()
        on_rail = bool(os.environ.get("RAILWAY_ENVIRONMENT")); items = [
            ("secret", bool(os.environ.get("SECRET_KEY")), "SECRET_KEY is set", "Add SECRET_KEY (a long random text) under Variables, then redeploy. Until then sign-in is not secure."),
            ("ingest", bool(os.environ.get("INGEST_SECRET")), "INGEST_SECRET is set (the Gmail script's password)", "Add INGEST_SECRET under Variables and put the same value in the Gmail script."),
            ("db", engine.dialect.name != "sqlite" or not on_rail, "The database is PostgreSQL", "Add PostgreSQL to the Railway project and set DATABASE_URL to its reference."),
            ("uploads", not store.upload_warning, "Original files are kept on a volume", store.upload_warning or ""),
            ("smtp", mailer.configured(), "Email sign-in links can be sent", "For Resend, add MAIL_PROVIDER=resend, RESEND_API_KEY and RESEND_FROM_EMAIL under Railway Variables. Use a verified sender domain for other users. Until email is tested, keep password sign-in available."),
            ("pw", not os.environ.get("ADMIN_PASSWORD"), "The first-sign-in password variable has been removed", "Once you can sign in (and email works), delete the ADMIN_PASSWORD variable."),
            ("reports", n_ship > 0, "Reports are loaded", "Open Upload a report (or Previous reports) and load the ERP files."),
            ("master", n_master > 0, "The Organization master is loaded", "Open Organization master and load the export for each company."),
            ("users", n_users > 1, "Other people have been added", "Open Users and add the people who should see the dashboard."),
            ("gmail", n_mail > 0, "The Gmail script has delivered a report", "Set the Apps Script properties APP_URL and INGEST_SECRET and run installTrigger (see gmail/ERP_Mail_Collector.gs).")]
        return [dict(key=k, ok=bool(ok), title=t, fix=f) for k, ok, t, f in items]

    @app.get("/api/admin/overview")
    def a_overview(user: dict = Depends(admin)):
        s = ops.get_settings(engine); yrs, fy = int(s["history_years"]), int(s["fy_start_month"])
        with engine.connect() as c:
            q = c.execute(select(func.count()).select_from(uploads).where(uploads.c.status.in_(["queued", "processing"]))).scalar()
            nu = c.execute(select(func.count()).select_from(users).where(users.c.active == 1)).scalar()
            held = c.execute(select(func.count()).select_from(imports).where(imports.c.status.in_(["needs_review", "failed"]))).scalar()
        return {"queue": q, "users": nu, "needs_attention": held, "health": P.health(engine, date.today(), datetime.utcnow(), float(s["max_age_hours"])), "coverage": df_json(P.coverage(engine, date.today(), yrs, fy)),
                "profit_coverage": df_json(J.profit_coverage(engine, date.today(), yrs, fy)), "settings": s, "mail_configured": mailer.configured(), "data_version": store.version, "setup": setup_checks()}

    @app.get("/api/admin/imports")
    def a_imports(status: str = "", user: dict = Depends(admin)):
        return df_json(P.list_imports(engine, status or None, 300))

    @app.get("/api/admin/uploads")
    def a_uploads(user: dict = Depends(admin)):
        with engine.connect() as c: rows = c.execute(select(uploads.c.id, uploads.c.file_name, uploads.c.source, uploads.c.status, uploads.c.result, uploads.c.received_at, uploads.c.uploaded_by).order_by(uploads.c.id.desc()).limit(100)).mappings().all()
        return json.loads(json.dumps([dict(r) for r in rows], default=str))

    @app.post("/api/admin/imports/{iid}/approve")
    async def a_approve(iid: int, request: Request, user: dict = Depends(admin_unsafe)):
        b = await request.json(); reason = str(b.get("reason", "")).strip()
        if not reason: raise HTTPException(400, "A reason is required.")
        res = P.approve_import(engine, iid, user["email"], reason)
        if res.get("status") == "promoted": store.bump()
        ops.log(engine, user["email"], "approve_import", f"{iid}: {reason}"); return res

    @app.post("/api/admin/imports/{iid}/retry")
    def a_retry(iid: int, user: dict = Depends(admin_unsafe)):
        res = P.retry_import(engine, iid)
        if res.get("status") == "promoted": store.bump()
        ops.log(engine, user["email"], "retry_import", iid); return res

    @app.post("/api/admin/imports/{iid}/undo")
    async def a_undo(iid: int, request: Request, user: dict = Depends(admin_unsafe)):
        b = await request.json()
        try: res = ops.undo_last_import(engine, iid, user["email"], str(b.get("reason", "")))
        except ValueError as e: raise HTTPException(400, str(e))
        store.bump(); return res

    async def _save_many(files: list[UploadFile]):
        out = []
        for f in files:
            data = await f.read()
            if len(data) > MAX_UPLOAD: raise HTTPException(413, f"{f.filename} is too large.")
            name = Path(f.filename or "report.xlsx").name
            if not name.lower().endswith(".xlsx"): raise HTTPException(400, f"{name} is not an .xlsx file.")
            out.append((name,) + save_file(store, data, name))
        return out

    @app.post("/api/admin/upload/preview")
    async def a_preview(files: list[UploadFile] = File(...), user: dict = Depends(admin_unsafe)):
        res = []
        for name, path, sha in await _save_many(files):
            try: p = ops.preview_any(engine, path)
            except Exception as e: p = dict(verdict="rejected", message=f"{type(e).__name__}: {e}")
            res.append(dict(file=name, sha=sha, **json.loads(json.dumps(p, default=str))))
        return res

    @app.post("/api/admin/upload")
    async def a_upload(files: list[UploadFile] = File(...), kind: str = Form("manual"), approve: int = Form(0), reason: str = Form(""), user: dict = Depends(admin_unsafe)):
        if approve and not reason.strip(): raise HTTPException(400, "A reason is required to load a report that would normally be held.")
        ids = []
        saved = await _save_many(files)
        order = []
        for name, path, sha in saved:        # earlier years first, so history loads in order
            try: p = ops.preview_any(engine, path); order.append((str(p.get("covers_from") or ""), name, path))
            except Exception: order.append(("", name, path))
        for _, name, path in sorted(order):
            ids.append(store.enqueue(file_name=name, path=path, source="history" if kind == "history" else "manual", report_time=datetime.utcnow(), uploaded_by=user["email"], approve=int(bool(approve)), reason=reason))
        ops.log(engine, user["email"], "upload_" + kind, f"{len(ids)} file(s)"); return {"queued": ids}

    @app.post("/api/admin/master/preview")
    async def a_master_preview(file: UploadFile = File(...), user: dict = Depends(admin_unsafe)):
        (name, path, sha), = await _save_many([file])
        try: return MST.preview_master(path)
        except Exception as e: raise HTTPException(400, str(e))

    @app.post("/api/admin/master")
    async def a_master(file: UploadFile = File(...), company: str = Form(...), user: dict = Depends(admin_unsafe)):
        if company not in ("NG", "NCS"): raise HTTPException(400, "Choose New Globe or Neutral Consolidation.")
        (name, path, sha), = await _save_many([file])
        try: res = MST.load_master(engine, path, company)
        except Exception as e: raise HTTPException(400, str(e))
        store.bump(); ops.log(engine, user["email"], "load_master", f"{company}: {res['rows']} organisations"); return res

    @app.get("/api/admin/users")
    def a_users(user: dict = Depends(admin)):
        with engine.connect() as c: rows = c.execute(select(users).order_by(users.c.email)).all()
        return [auth.user_dict(r) for r in rows]

    @app.post("/api/admin/users")
    async def a_user_new(request: Request, user: dict = Depends(admin_unsafe)):
        b = await request.json()
        try: u = auth.create_user(engine, b.get("email", ""), b.get("role", "operations"), b.get("name", ""), b.get("user_id") or None, b.get("companies"), b.get("lobs"), b.get("finance"), b.get("password") or None)
        except ValueError as e: raise HTTPException(400, str(e))
        ops.log(engine, user["email"], "create_user", u["email"]); return u

    @app.patch("/api/admin/users/{uid}")
    async def a_user_edit(uid: int, request: Request, user: dict = Depends(admin_unsafe)):
        b = await request.json()
        if uid == user["id"] and (b.get("active") is False or (b.get("role") and b["role"] != "admin")): raise HTTPException(400, "You cannot remove your own administrator access.")
        try: u = auth.update_user(engine, uid, **{k: b.get(k) for k in ("role", "name", "companies", "lobs", "finance", "active", "user_id")}, reset_finance=bool(b.get("reset_finance")))
        except ValueError as e: raise HTTPException(400, str(e))
        ops.log(engine, user["email"], "edit_user", f"{u['email']}: {sorted(b)}"); return u

    @app.post("/api/admin/users/{uid}/password")
    async def a_user_pw(uid: int, request: Request, user: dict = Depends(admin_unsafe)):
        b = await request.json()
        try: auth.set_password(engine, uid, str(b.get("password", "")))
        except ValueError as e: raise HTTPException(400, str(e))
        ops.log(engine, user["email"], "set_password", uid); return {"ok": True}

    @app.post("/api/admin/users/{uid}/send-link")
    def a_user_link(uid: int, request: Request, user: dict = Depends(admin_unsafe)):
        with engine.connect() as c: u = c.execute(select(users).where(users.c.id == uid)).first()
        if not u: raise HTTPException(404, "No such user.")
        r = auth.request_link(engine, u.email)
        if not r: raise HTTPException(429, "Too many links requested for this address. Try again in an hour.")
        token, code, ud = r; sent = mailer.send(u.email, f"Your {product} sign-in link", f"Open this link to sign in (works once, {auth.LINK_MINUTES} minutes):\n{public_base(request)}/auth/verify?t={token}\n\nOr use the code {code} on the sign-in page.")
        return {"sent": sent, "message": "Link sent." if sent else "Email could not be sent. Check email provider settings and delivery logs; password sign-in is still available."}

    @app.get("/api/admin/settings")
    def a_settings(user: dict = Depends(admin)): return ops.get_settings(engine)

    @app.put("/api/admin/settings")
    async def a_settings_put(request: Request, user: dict = Depends(admin_unsafe)):
        try: return ops.put_settings(engine, await request.json(), user["email"])
        except ValueError as e: raise HTTPException(400, str(e))

    @app.get("/api/admin/retention")
    def a_ret(user: dict = Depends(admin)):
        s = ops.get_settings(engine); return json.loads(json.dumps(P.retention_preview(engine, date.today(), int(s["history_years"]), int(s["fy_start_month"])), default=str))

    @app.post("/api/admin/retention")
    async def a_ret_apply(request: Request, user: dict = Depends(admin_unsafe)):
        b = await request.json(); s = ops.get_settings(engine)
        if not str(b.get("reason", "")).strip(): raise HTTPException(400, "A reason is required.")
        with store.lock:
            store.full = None; store.full_version = -1; store.cache.clear(); gc.collect()
            res = P.apply_retention(engine, user["email"], str(b["reason"]), date.today(), int(s["history_years"]), int(s["fy_start_month"])); store.bump()
        return json.loads(json.dumps(res, default=str))

    @app.get("/api/admin/audit")
    def a_audit(user: dict = Depends(admin)):
        with engine.connect() as c: rows = c.execute(select(admin_log).order_by(admin_log.c.id.desc()).limit(200)).mappings().all()
        return json.loads(json.dumps([dict(r) for r in rows], default=str))

    try: bad = [c for c in setup_checks() if not c["ok"] and c["key"] in ("secret", "ingest", "db", "uploads", "smtp")]
    except Exception: bad = []
    log.warning("Started. Address: %s | database: %s | still to set up: %s", base_url if (explicit or rdom) else "taken from the browser (BASE_URL is not needed)", engine.dialect.name, ", ".join(c["key"] for c in bad) or "nothing")
    return app


def save_file(store: Store, data: bytes, name: str):
    sha = hashlib.sha256(data).hexdigest(); d = store.upload_dir / datetime.utcnow().strftime("%Y/%m"); d.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)[:120]; p = d / f"{sha}_{safe}"
    try:
        with p.open("xb") as f: f.write(data)
    except FileExistsError:
        pass  # repeated deliveries reuse the exact same archived workbook
    return str(p), sha


def app_factory():
    """For `uvicorn app.server:app_factory --factory`."""
    return create_app()
