"""The web app: sign-in, the dashboard data, the admin portal and the endpoint the Gmail script posts to."""
import gc, gzip, hashlib, io, json, logging, os, secrets, shutil, tempfile, threading, time
from collections import defaultdict, deque
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select, func, insert, delete, update, and_, or_
from sqlalchemy.exc import IntegrityError
from . import auth, admin_ops as ops, dataset as DS, mailer, master as MST, processor as P, profit as J, metric_definitions as MD, metric_execution as MX, report_scheduler as RS, report_scheduler_service as RSS
from .db import get_engine, imports, uploads, users, prefs, admin_log, shipments, profit_lines, org_master

log = logging.getLogger("app")
WEB = Path(__file__).parent / "web"
MAX_UPLOAD = 80 * 1048576
PREF_NAMES = {"visuals", "views", "defs", "partner360"}


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
            self.thread = threading.Thread(target=self._supervise_worker, daemon=True, name="importer"); self.thread.start()
        self.wake.set()
        self.scheduler_worker = None
        if start_worker and str(os.environ.get("REPORT_SCHEDULER_ENABLED", "false")).strip().lower() in ("1", "true", "yes", "on"):
            self.scheduler_worker = RSS.SchedulerWorker(engine, self)
            self.scheduler_worker.start()

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
                D["data_version"] = self.version
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

    def _supervise_worker(self):
        """Keep queue consumption alive if a database or worker error escapes _worker."""
        while not self.stop:
            try:
                self._worker()
                if not self.stop:
                    log.error("import worker exited unexpectedly; restarting")
            except Exception:
                log.exception("import worker crashed; restarting after backoff")
            if self.stop:
                break
            # A worker crash can leave the claimed upload in processing forever.
            # Requeue it so the next worker iteration can retry it.
            try:
                with self.engine.begin() as c:
                    c.execute(update(uploads).where(uploads.c.status == "processing").values(status="queued"))
            except Exception:
                log.exception("could not recover interrupted imports")
            time.sleep(5)

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
    @app.get("/customer360", response_class=HTMLResponse)
    def customer360_page(request: Request):
        if not auth.session_user(engine, request.cookies.get("ng_session")): return RedirectResponse("/login", 303)
        return page("customer360.html")

    @app.get("/help", response_class=HTMLResponse)
    def help_page(user: dict = Depends(me)):
        """Authenticated, permission-aware in-app help and metric dictionary."""
        return page("help.html")

    @app.get("/api/metrics/definitions")
    def api_metric_definitions(user: dict = Depends(me)):
        """Source-backed explanation metadata, without exposing restricted financial data."""
        return {"metrics": [m for m in MD.all_metrics() if user["finance"] or not m["finance_required"]], "source": "code_verified",
                "note": "Source headers must also be checked against actual uploaded reports."}

    @app.get("/api/metrics/definitions/{metric_id}")
    def api_metric_definition(metric_id: str, user: dict = Depends(me)):
        if not user["finance"] and (metric_id.startswith("profit.") or metric_id.startswith("ops.rate_")):
            raise HTTPException(403, "Financial metric definitions require finance access.")
        metric = MD.get_metric(metric_id)
        if metric is None:
            raise HTTPException(404, "Unknown metric.")
        return metric.public_dict()

    async def metric_evidence(request, user, include_operations_links=True):
        raw = await request.body()
        if len(raw) > 8_000_000: raise HTTPException(413, "Selection too large.")
        try:
            body = json.loads(raw)
            if not isinstance(body, dict): raise ValueError("Invalid metric request.")
            def execute_metric():
                data = json.loads(gzip.decompress(store.dataset_for(user)))
                return MX.execute(data, body, MD, include_operations_links=include_operations_links)
            return await run_in_threadpool(execute_metric)
        except PermissionError as e: raise HTTPException(403, str(e))
        except (ValueError, TypeError, KeyError) as e: raise HTTPException(400, str(e))

    @app.post("/api/metrics/evidence")
    async def metric_evidence_api(request: Request, user: dict = Depends(unsafe)):
        return await metric_evidence(request, user)

    @app.post("/api/metrics/activity")
    async def metric_activity_api(request: Request, user: dict = Depends(unsafe)):
        request_started = time.perf_counter()
        evidence_started = request_started
        evidence = await metric_evidence(request, user, include_operations_links=False)
        evidence_ms = (time.perf_counter() - evidence_started) * 1000
        if evidence["metric"]["id"] != "ops.shipments":
            raise HTTPException(400, "Activity requires operational shipment evidence.")
        from .phase2_metrics import cross_lob_customer_activity
        from .customer_history import build_recent_jobs, normalize_customer_sql, is_named_customer

        try:
            as_of = date.fromisoformat(evidence["context"]["as_of"])
        except (ValueError, KeyError, TypeError):
            raise HTTPException(400, "A valid activity as-of date is required.")

        lob_order = ("AE", "AI", "OE", "OI")
        visible_lobs = list(user["lobs"]) if user["lobs"] else list(lob_order)
        visible_lobs = [lob for lob in lob_order if lob in visible_lobs]
        allowed_companies = list(user["companies"]) if user["companies"] else ["NG", "NCS"]
        context = evidence.get("context") or {}
        selected_lobs = set(lob_order)
        mode = str(context.get("mode") or "").strip().casefold()
        direction = str(context.get("direction") or "").strip().casefold()
        if mode == "air":
            selected_lobs &= {"AE", "AI"}
        elif mode in ("ocean", "sea"):
            selected_lobs &= {"OE", "OI"}
        if direction == "export":
            selected_lobs &= {"AE", "OE"}
        elif direction == "import":
            selected_lobs &= {"AI", "OI"}
        requested_lobs = (context.get("relationships") or {}).get("lob") or []
        if isinstance(requested_lobs, (str, bytes)):
            requested_lobs = [requested_lobs]
        if requested_lobs:
            def matches_lob(value, code):
                value = str(value or "").casefold()
                return {
                    "AE": ("air" in value and "export" in value),
                    "AI": ("air" in value and "import" in value),
                    "OE": (("ocean" in value or "sea" in value) and "export" in value),
                    "OI": (("ocean" in value or "sea" in value) and "import" in value),
                }[code]
            filtered_lobs = {lob for lob in lob_order if any(matches_lob(value, lob) for value in requested_lobs)}
            if filtered_lobs:
                selected_lobs &= filtered_lobs
        selected_lobs &= set(visible_lobs)
        if not selected_lobs:
            selected_lobs = set(visible_lobs)

        normalize_customer = lambda value: " ".join(str(value or "").split()).lower()
        groups = {}
        for row in evidence["records"]:
            customer = " ".join(str(row.get("customer") or "").split())
            company = str(row.get("company") or "").strip().upper()
            if not is_named_customer(customer) or company not in allowed_companies or not row.get("date"):
                continue
            try:
                shipment_day = date.fromisoformat(row["date"])
            except (ValueError, TypeError):
                continue
            if shipment_day > as_of:
                continue
            key = (company, normalize_customer(customer))
            group = groups.setdefault(key, {
                "company": company, "customer": customer, "indices": [],
                "selected_lobs": set(selected_lobs),
            })
            group["indices"].append(row["source_index"])

        grouping_ms = (time.perf_counter() - evidence_started) * 1000 - evidence_ms
        if not groups:
            log.info(
                "customer360_activity_profile evidence_ms=%.1f grouping_ms=%.1f "
                "customers=0 total_ms=%.1f",
                evidence_ms, grouping_ms, (time.perf_counter() - request_started) * 1000,
            )
            return {
                "as_of": as_of.isoformat(), "customers": [],
                "snapshot": evidence["snapshot"], "coverage": [],
                "method": "No customers match the selected, permission-scoped relationship filters.",
            }

        companies = sorted({company for company, _ in groups})
        customer_keys = set(groups)
        normalized_names = sorted({customer for _, customer in groups})
        def fetch_customer_history():
            activity_dates = {key: {lob: [] for lob in visible_lobs} for key in groups}
            latest_jobs = {key: [] for key in groups}
            promoted = set()
            register_started = time.perf_counter()
            register_row_count = 0
            register_ms = 0.0
            import_ms = 0.0
            jpr_ms = 0.0
            jpr_row_count = 0
            batch_size = 500
            with engine.connect() as conn:
                normalized_register_customer = normalize_customer_sql(shipments.c.customer)
                for offset in range(0, len(normalized_names), batch_size):
                    name_batch = normalized_names[offset:offset + batch_size]
                    register_rows = conn.execute(select(
                        shipments.c.company, shipments.c.report_type, shipments.c.customer,
                        shipments.c.shipment_date
                    ).where(
                        shipments.c.company.in_(companies),
                        normalized_register_customer.in_(name_batch),
                        shipments.c.report_type.in_(visible_lobs),
                        shipments.c.to_import.is_(None),
                        shipments.c.shipment_date.is_not(None),
                        shipments.c.shipment_date <= as_of,
                    )).mappings().all()
                    for row in register_rows:
                        key = (row["company"], normalize_customer(row["customer"]))
                        lob = row["report_type"]
                        if key in activity_dates and lob in activity_dates[key] and row["shipment_date"]:
                            register_row_count += 1
                            activity_dates[key][lob].append(row["shipment_date"])

                register_ms = (time.perf_counter() - register_started) * 1000
                import_started = time.perf_counter()
                import_rows = conn.execute(select(
                    imports.c.company, imports.c.report_type, imports.c.status, imports.c.id
                ).where(
                    imports.c.company.in_(companies),
                    imports.c.report_type.in_(lob_order),
                ).order_by(imports.c.id.desc())).mappings().all()
                latest_import_status = {}
                for row in import_rows:
                    key = (row["company"], row["report_type"])
                    if key not in latest_import_status:
                        latest_import_status[key] = row["status"]
                promoted.update(key for key, status in latest_import_status.items() if status == "promoted")
                import_ms = (time.perf_counter() - import_started) * 1000

                jpr_started = time.perf_counter()
                normalized_jpr_customer = normalize_customer_sql(profit_lines.c.customer)
                for offset in range(0, len(normalized_names), batch_size):
                    name_batch = normalized_names[offset:offset + batch_size]
                    jpr_rows = conn.execute(select(
                        profit_lines.c.company, profit_lines.c.job_no, profit_lines.c.job_date,
                        profit_lines.c.lob, profit_lines.c.customer, profit_lines.c.extra
                    ).where(
                        profit_lines.c.company.in_(companies),
                        normalized_jpr_customer.in_(name_batch),
                        *J.current_jobs(),
                    ).order_by(profit_lines.c.job_date.desc(), profit_lines.c.id.desc())).mappings().all()
                    for row in jpr_rows:
                        key = (row["company"], normalize_customer(row["customer"]))
                        if key in latest_jobs:
                            jpr_row_count += 1
                            latest_jobs[key].append(dict(row))
                jpr_ms = (time.perf_counter() - jpr_started) * 1000
            return (activity_dates, latest_jobs, promoted, register_ms, register_row_count,
                    import_ms, jpr_ms, jpr_row_count)

        (activity_dates, latest_jobs, promoted, register_ms, register_row_count,
         import_ms, jpr_ms, jpr_row_count) = await run_in_threadpool(fetch_customer_history)

        result = []
        coverage = {}
        for key, group in groups.items():
            company = group["company"]
            source_complete = all((company, lob) in promoted for lob in lob_order)
            coverage[company] = {
                "company": company,
                "visible_lobs": visible_lobs,
                "promoted_sources": sorted(lob for lob in visible_lobs if (company, lob) in promoted),
                "complete_company_scope": source_complete and set(visible_lobs) == set(lob_order),
            }
            signal = cross_lob_customer_activity(
                activity_dates[key], as_of,
                sorted(group["selected_lobs"]), visible_lobs, source_complete,
            )
            jobs = build_recent_jobs(latest_jobs[key], lobs=visible_lobs, limit=5)
            result.append({
                "company": company,
                "customer": group["customer"],
                "indices": sorted(set(group["indices"])),
                "selected_lob_activity": signal,
                "last_five_jobs": jobs,
                "identity_basis": "exact source customer name, case/whitespace normalized",
            })

        result.sort(key=lambda row: (
            row["selected_lob_activity"]["classification"] in
            ("active_in_selected_scope", "insufficient_history"),
            -(row["selected_lob_activity"]["company_wide_activity"].get("days_since_last") or 0),
            row["company"], row["customer"].casefold(),
        ))
        total_ms = (time.perf_counter() - request_started) * 1000
        log.info(
            "customer360_activity_profile evidence_ms=%.1f grouping_ms=%.1f "
            "register_ms=%.1f register_rows=%d import_ms=%.1f jpr_ms=%.1f "
            "jpr_rows=%d customers=%d total_ms=%.1f",
            evidence_ms, grouping_ms, register_ms, register_row_count, import_ms,
            jpr_ms, jpr_row_count, len(result), total_ms,
        )
        if total_ms >= 5000:
            log.warning(
                "customer360_activity_slow evidence_ms=%.1f grouping_ms=%.1f "
                "register_ms=%.1f import_ms=%.1f jpr_ms=%.1f customers=%d total_ms=%.1f",
                evidence_ms, grouping_ms, register_ms, import_ms, jpr_ms, len(result), total_ms,
            )
        return {
            "as_of": as_of.isoformat(), "customers": result,
            "snapshot": evidence["snapshot"], "coverage": list(coverage.values()),
            "method": (
                "Adaptive cadence uses the median interval between distinct shipment dates: "
                "<=14 days => 30-day threshold; <=30 => 60; otherwise 90 days. "
                "At risk after the threshold; inactive after 1.5x the threshold; at least "
                "three distinct dates are required. Activity is checked across all LOBs "
                "visible to the signed-in user, independently of the selected dashboard "
                "date start. Company-wide inactivity is asserted only when all four LOBs "
                "are authorized and each has a promoted source snapshot. It describes "
                "loaded snapshot history, not an all-time guarantee. Customer matching "
                "uses exact source names with case/whitespace normalization because a "
                "verified customer-code key is not yet available across all current reports. "
                "Job-owner history uses current JPR records only; missing/conflicting owners "
                "are never guessed."
            ),
        }

    @app.post("/api/metrics/export")
    async def metric_export_api(request: Request, user: dict = Depends(unsafe)):
        result = await metric_evidence(request, user)
        return Response(MX.workbook(result), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="metric_reconciliation.xlsx"', "Cache-Control": "private, no-store"})

    @app.get("/assets/metric_trace.js")
    def metric_trace_script(user: dict = Depends(me)):
        return Response((WEB / "metric_trace.js").read_text(), media_type="application/javascript", headers={"Cache-Control": "private, no-store"})

    @app.get("/api/dataset")
    def api_dataset(user: dict = Depends(me)):
        return Response(store.dataset_for(user), media_type="application/json", headers={"Content-Encoding": "gzip", "Cache-Control": "private, no-store"})

    # ------------------------------------------------------------------ scheduled email reports
    @app.get("/reports/scheduled", response_class=HTMLResponse)
    def scheduled_reports_page(user: dict = Depends(me)):
        return page("report_scheduler.html")

    @app.get("/api/report-schedules/catalog")
    def report_schedule_catalog(user: dict = Depends(me)):
        catalog = []
        for report_id, report in RS.REPORT_CATALOG.items():
            if report.get("permission") == "finance" and not user["finance"]:
                continue
            catalog.append({
                "id": report_id, "title": report["title"], "permission": report["permission"],
                "date_basis": report["date_basis"], "filters": list(report["filters"]),
                "detail_columns": [col for col in report["columns"] if user["finance"] or col not in ("buy_rate", "sell_rate")],
                "summary_columns": list(report["summary_columns"]),
                "summary_only": report_id == "customer_performance",
            })
        return {"reports": catalog, "companies": user["companies"] or ["NG", "NCS"],
                "lobs": user["lobs"] or ["AE", "AI", "OE", "OI"],
                "finance": bool(user["finance"]), "worker_enabled": RSS._worker_enabled()}

    @app.get("/api/report-schedules")
    def report_schedule_list(user: dict = Depends(me)):
        return {"schedules": RSS.list_schedules(engine, user["id"]),
                "worker_enabled": RSS._worker_enabled()}

    @app.post("/api/report-schedules")
    async def report_schedule_create(request: Request, user: dict = Depends(unsafe)):
        try:
            body = await request.json()
            return RSS.create_schedule(engine, user, body)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    @app.patch("/api/report-schedules/{schedule_id}")
    async def report_schedule_update(schedule_id: int, request: Request, user: dict = Depends(unsafe)):
        try:
            return RSS.update_schedule(engine, user, schedule_id, await request.json())
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    @app.delete("/api/report-schedules/{schedule_id}")
    def report_schedule_delete(schedule_id: int, user: dict = Depends(unsafe)):
        try:
            return RSS.delete_schedule(engine, user, schedule_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @app.get("/api/report-schedules/{schedule_id}/runs")
    def report_schedule_runs(schedule_id: int, user: dict = Depends(me)):
        try:
            return {"runs": RSS.list_runs(engine, user["id"], schedule_id)}
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @app.post("/api/report-schedules/{schedule_id}/run-now")
    def report_schedule_run_now(schedule_id: int, user: dict = Depends(unsafe)):
        try:
            return RSS.queue_manual_run(engine, user, schedule_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except IntegrityError:
            raise HTTPException(409, "A report run is already queued for this schedule.")

    @app.post("/api/report-schedules/preview")
    async def report_schedule_preview(request: Request, user: dict = Depends(unsafe)):
        try:
            prepared = RSS.preview_workbook(engine, store, user, await request.json())
            workbook = prepared["workbook"]
            filename = workbook["filename"].replace('"', "")
            return Response(
                workbook["content"], media_type=RSS.XLSX_MIME,
                headers={"Content-Disposition": f'attachment; filename="{filename}"',
                         "Cache-Control": "private, no-store"},
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/report-schedules/{schedule_id}/preview")
    def report_schedule_saved_preview(schedule_id: int, user: dict = Depends(unsafe)):
        try:
            schedule = RSS.get_schedule(engine, user["id"], schedule_id)
            prepared = RSS.prepare_workbook(engine, store, user, schedule["definition"])
            workbook = prepared["workbook"]
            filename = workbook["filename"].replace('"', "")
            return Response(
                workbook["content"], media_type=RSS.XLSX_MIME,
                headers={"Content-Disposition": f'attachment; filename="{filename}"',
                         "Cache-Control": "private, no-store"},
            )
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/customers/recent-jobs")
    async def customer_recent_jobs(request: Request, user: dict = Depends(unsafe)):
        """Return the latest five distinct JPR jobs for visible Operations customer rows.

        Owner/job identity only; no income, expense or profit values. Company
        and LOB scope are checked again on the server for every request.
        """
        from .customer_history import build_recent_jobs, build_last_shipment_owners, visible_report_types_for_scopes, normalize_customer_sql, is_named_customer
        raw = await request.body()
        if len(raw) > 1_000_000: raise HTTPException(413, "Selection too large.")
        try:
            body = json.loads(raw)
            if not isinstance(body, dict) or not isinstance(body.get("customers"), list):
                raise ValueError("A customer selection is required.")
            requests = body["customers"]
            if len(requests) > 500: raise ValueError("Please export customer history in smaller batches.")
            allowed_companies = set(user["companies"] or ["NG", "NCS"])
            allowed_lobs = set(user["lobs"]) if user["lobs"] else None
            normalized = []
            all_companies, all_names = set(), set()
            for item in requests:
                if not isinstance(item, dict): raise ValueError("Invalid customer selection.")
                name = " ".join(str(item.get("customer") or "").split())
                companies = item.get("companies") or sorted(allowed_companies)
                requested_lobs = item.get("lobs")
                lobs = set(requested_lobs or (allowed_lobs or []))
                last_shipment_date = str(item.get("last_shipment_date") or "").strip()[:10]
                if last_shipment_date:
                    try: date.fromisoformat(last_shipment_date)
                    except ValueError: raise ValueError("Invalid last shipment date.")
                if not is_named_customer(name) or len(name) > 300: raise ValueError("Invalid customer name.")
                if not isinstance(companies, list) or not companies or not set(companies).issubset(allowed_companies):
                    raise PermissionError("The selected company is outside your access scope.")
                if not isinstance(requested_lobs or [], list) or (allowed_lobs is not None and not lobs.issubset(allowed_lobs)):
                    raise PermissionError("The selected line of business is outside your access scope.")
                normalized.append((name, set(companies), lobs, last_shipment_date))
                all_companies.update(companies)
                all_names.add(name.strip().lower())
            if not normalized:
                return {"histories": []}
            def build_history_batch():
                with engine.connect() as conn:
                    # A caller may request only customers already present in the
                    # current operational register within their authorized scope.
                    visible_report_types = visible_report_types_for_scopes(lobs for _, _, lobs, _ in normalized)
                    visible_rows = conn.execute(select(
                        shipments.c.company, shipments.c.customer
                    ).where(
                        shipments.c.company.in_(sorted(all_companies)),
                        shipments.c.report_type.in_(visible_report_types),
                        shipments.c.to_import.is_(None),
                        normalize_customer_sql(shipments.c.customer).in_(sorted(all_names))
                    )).all()
                    visible = {
                        (company, " ".join(str(customer or "").split()).lower())
                        for company, customer in visible_rows
                    }
                    for name, companies, _, _ in normalized:
                        if any((company, name.lower()) not in visible for company in companies):
                            raise PermissionError("The customer is outside your visible operational scope for one or more selected companies.")
                    shipment_rows = conn.execute(select(
                        shipments.c.company, shipments.c.report_type, shipments.c.shipment_no,
                        shipments.c.shipment_date, shipments.c.customer
                    ).where(
                        shipments.c.company.in_(sorted(all_companies)),
                        shipments.c.report_type.in_(visible_report_types),
                        shipments.c.to_import.is_(None),
                        normalize_customer_sql(shipments.c.customer).in_(sorted(all_names))
                    ).order_by(shipments.c.shipment_date.desc(), shipments.c.id.desc())).mappings().all()
                    source_rows = conn.execute(select(
                        profit_lines.c.id, profit_lines.c.company, profit_lines.c.job_no,
                        profit_lines.c.job_date, profit_lines.c.lob, profit_lines.c.customer,
                        profit_lines.c.extra
                    ).where(
                        profit_lines.c.company.in_(sorted(all_companies)),
                        normalize_customer_sql(profit_lines.c.customer).in_(sorted(all_names)),
                        *J.current_jobs()
                    ).order_by(profit_lines.c.job_date.desc(), profit_lines.c.id.desc())).mappings().all()
                by_customer = {}
                for row in source_rows:
                    key = " ".join(str(row["customer"] or "").split()).lower()
                    by_customer.setdefault(key, []).append(dict(row))
                shipments_by_customer = {}
                for row in shipment_rows:
                    key = " ".join(str(row["customer"] or "").split()).lower()
                    shipments_by_customer.setdefault(key, []).append(dict(row))
                histories = []
                for name, companies, lobs, last_shipment_date in normalized:
                    key = name.strip().lower()
                    rows = [row for row in by_customer.get(key, []) if row["company"] in companies]
                    visible_shipments = [row for row in shipments_by_customer.get(key, []) if row["company"] in companies]
                    jobs = build_recent_jobs(rows, lobs=lobs, limit=5)
                    last_owner = build_last_shipment_owners(visible_shipments, rows, lobs=lobs, target_date=last_shipment_date).get(key)
                    histories.append({
                        "customer": name,
                        "jobs": jobs,
                        "job_count_returned": len(jobs),
                        "last_shipment_job_owner": last_owner["last_shipment_job_owner"] if last_owner else "No shipment record",
                        "last_shipment_owner_status": last_owner["last_shipment_owner_status"] if last_owner else "no_shipment",
                        "last_shipment_date": last_owner["last_shipment_date"] if last_owner else None,
                        "last_shipment_numbers": last_owner["last_shipment_numbers"] if last_owner else [],
                    })
                return {"histories": histories, "basis": "Job Date", "source": "Current Job Profit Analysis Report"}
            return await run_in_threadpool(build_history_batch)
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except (ValueError, TypeError, KeyError) as e:
            raise HTTPException(400, str(e))

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

    @app.get("/api/admin/data-freshness")
    def a_data_freshness(user: dict = Depends(admin)):
        """Read-only LOB/year inventory with import provenance; never modifies reporting data."""
        from .db import profit_lines
        from sqlalchemy import extract
        kinds = {"AE": "Air Export", "AI": "Air Import", "OE": "Ocean Export",
                 "OI": "Ocean Import", "JP": "Job Profit"}
        with engine.connect() as c:
            ship_counts = c.execute(
                select(shipments.c.company, shipments.c.report_type,
                       extract("year", shipments.c.shipment_date).label("yr"),
                       func.count().label("qty"))
                .where(shipments.c.to_import.is_(None), shipments.c.shipment_date.is_not(None))
                .group_by(shipments.c.company, shipments.c.report_type,
                          extract("year", shipments.c.shipment_date))).all()
            profit_counts = c.execute(
                select(profit_lines.c.company,
                       extract("year", profit_lines.c.job_date).label("yr"),
                       func.count().label("qty"))
                .where(*J.current_jobs(), profit_lines.c.job_date.is_not(None))
                .group_by(profit_lines.c.company, extract("year", profit_lines.c.job_date))).all()
            audit = c.execute(
                select(imports.c.id, imports.c.company, imports.c.report_type,
                       imports.c.status, imports.c.received_at, imports.c.report_time,
                       imports.c.range_from, imports.c.range_to, imports.c.file_name,
                       imports.c.source, imports.c.new_rows, imports.c.changed_rows,
                       imports.c.ended_rows, imports.c.message)
                .where(imports.c.company.in_(["NG", "NCS"]),
                       imports.c.report_type.in_(list(kinds)),
                       (imports.c.report_type != "JP") |
                       (imports.c.columns.like('%"Job Date"%') &
                        imports.c.columns.not_like('%"Charge"%')))
                .order_by(imports.c.id.desc())).mappings().all()
        counts = {}
        for company, kind, yr, qty in ship_counts:
            if yr is not None and kind in kinds:
                key = (company, kind, int(yr))
                counts[key] = counts.get(key, 0) + int(qty)
        for company, yr, qty in profit_counts:
            if yr is not None:
                key = (company, "JP", int(yr))
                counts[key] = counts.get(key, 0) + int(qty)
        years = sorted({k[2] for k in counts} | {date.today().year, date.today().year - 1}, reverse=True)
        def overlaps(item, yr):
            start, end = item["range_from"], item["range_to"]
            return (start is None or start.year <= yr) and (end is None or end.year >= yr)
        result = []
        for company in ("NG", "NCS"):
            for yr in years:
                for kind, label in kinds.items():
                    matches = [a for a in audit if a["company"] == company and
                               a["report_type"] == kind and overlaps(a, yr)]
                    success = next((a for a in matches if a["status"] == "promoted"), None)
                    latest = matches[0] if matches else None
                    count = counts.get((company, kind, yr), 0)
                    if not count and not matches:
                        status = "not_loaded"
                    elif latest and latest["status"] in ("failed", "needs_review"):
                        status = "attention"
                    elif success:
                        status = "loaded"
                    else:
                        status = "unverified"
                    result.append({
                        "company": company, "year": yr, "report_type": kind, "lob": label,
                        "rows": count, "status": status,
                        "last_success": success["received_at"].isoformat() + "Z" if success and success["received_at"] else None,
                        "last_report_time": success["report_time"].isoformat() + "Z" if success and success["report_time"] else None,
                        "last_attempt": latest["received_at"].isoformat() + "Z" if latest and latest["received_at"] else None,
                        "last_attempt_status": latest["status"] if latest else None,
                        "file_name": success["file_name"] if success else None,
                        "source": success["source"] if success else None,
                        "range_from": success["range_from"].isoformat() if success and success["range_from"] else None,
                        "range_to": success["range_to"].isoformat() if success and success["range_to"] else None,
                        "new_rows": success["new_rows"] if success else None,
                        "changed_rows": success["changed_rows"] if success else None,
                        "removed_rows": success["ended_rows"] if success else None,
                        "last_error": latest["message"] if status == "attention" else None
                    })
        return {"rows": result, "timestamp_note": "Last successful import uses the recorded import receipt timestamp (UTC), not a separately tracked commit timestamp.",
                "count_note": "Counts are current open shipment/job rows by their own dates; not cumulative import-file row counts."}

    @app.get("/api/admin/reconciliation")
    def a_reconciliation(user: dict = Depends(admin)):
        """Temporary read-only import diagnostics; administrator session required."""
        from datetime import timedelta
        from .processor import year_slots
        s = ops.get_settings(engine)
        yrs, fy = int(s["history_years"]), int(s["fy_start_month"])
        today = date.today()
        slots = year_slots(today, yrs, fy)
        with engine.connect() as c:
            pending = c.execute(select(uploads.c.id, uploads.c.file_name, uploads.c.status,
                uploads.c.received_at, uploads.c.result).where(
                uploads.c.status.in_(["queued", "processing"])).order_by(uploads.c.id)).mappings().all()
            reviews = c.execute(select(imports.c.id, imports.c.company, imports.c.report_type,
                imports.c.file_name, imports.c.status, imports.c.message, imports.c.range_from,
                imports.c.range_to).where(imports.c.status.in_(["needs_review", "failed"])).order_by(imports.c.id.desc())).mappings().all()
            accepted = c.execute(select(imports.c.company, imports.c.report_type,
                imports.c.range_from, imports.c.range_to).where(
                imports.c.status == "promoted", imports.c.range_from.is_not(None),
                imports.c.range_to.is_not(None), (imports.c.report_type != "JP") | imports.c.columns.not_like('%"Charge"%'))).all()
        def missing(ranges, start, end):
            cursor = start
            gaps = []
            for a, b in sorted(ranges):
                if b < cursor or a > end:
                    continue
                if a > cursor:
                    gaps.append([cursor.isoformat(), (a-timedelta(days=1)).isoformat()])
                cursor = max(cursor, b+timedelta(days=1))
                if cursor > end:
                    break
            if cursor <= end:
                gaps.append([cursor.isoformat(), end.isoformat()])
            return gaps
        groups = sorted(set((x.company, x.report_type) for x in accepted))
        gaps = []
        for company, kind in groups:
            ranges = [(x.range_from, x.range_to) for x in accepted if x.company == company and x.report_type == kind]
            for sl in slots:
                end = min(sl["end"], today)
                if sl["start"] <= end:
                    absent = missing(ranges, sl["start"], end)
                    if absent:
                        gaps.append(dict(company=company, report=kind, period=sl["label"], missing=absent))
        return {"generated_at": datetime.utcnow().isoformat(), "pending_count": len(pending),
                "pending": [dict(x) for x in pending],
                "review_count": len(reviews), "reviews": [dict(x) for x in reviews],
                "missing_coverage": gaps, "note": "Date coverage only; no financial reconciliation performed."}

    @app.get("/api/admin/phase2/source-readiness")
    def phase2_source_readiness(user: dict = Depends(admin)):
        """Read-only Phase 2 field and aggregate data-quality diagnostics."""
        from .phase2_coverage import report_field_coverage, job_history_field_coverage, job_history_data_quality
        with engine.connect() as c:
            rows = c.execute(select(imports.c.id, imports.c.company,
                imports.c.report_type, imports.c.columns).where(
                imports.c.status == "promoted")).mappings().all()
            register_rows = c.execute(select(
                shipments.c.company, shipments.c.report_type, shipments.c.shipment_no,
                shipments.c.shipment_date, shipments.c.job_owner
            ).where(
                shipments.c.to_import.is_(None),
                shipments.c.report_type.in_(("AE", "AI", "OE", "OI"))
            )).mappings().yield_per(5000)
            job_rows = c.execute(select(
                profit_lines.c.company, profit_lines.c.job_no, profit_lines.c.job_date,
                profit_lines.c.lob, profit_lines.c.extra
            ).where(*J.current_jobs())).mappings().yield_per(5000)
            # Consume the large row streams while the connection is open. The
            # quality helper keeps only compact match indexes and job identities.
            quality = job_history_data_quality(register_rows, job_rows)
        return {
            "report_fields": report_field_coverage(rows),
            "job_history_fields": job_history_field_coverage(rows),
            "job_history_quality": quality,
            "note": "Read-only header and aggregate quality checks. No job, customer or owner names are returned. Header presence and nonblank owner coverage do not prove customer identity or complete all-time history."
        }

    @app.get("/phase2/intelligence", response_class=HTMLResponse)
    def phase2_intelligence_page(user: dict = Depends(me)):
        raise HTTPException(410, "Business Intelligence has been removed. Use the main dashboard.")

    @app.get("/phase2/opportunities", response_class=HTMLResponse)
    def phase2_opportunities_page(user: dict = Depends(admin)):
        return page("opportunities.html")

    @app.get("/api/admin/phase2/opportunities")
    def phase2_opportunities(user: dict = Depends(admin)):
        """Read-only customer whitespace candidates from the existing shipment register.

        Administrator-only until salesperson-level assignment and permission
        checks are validated. Incomplete company/LOB imports yield no candidates.
        """
        from datetime import timedelta
        from .phase2_opportunity import find_opportunities
        # The latest promoted register rows are authoritative. Do not require
        # current_import entries: historical imports can be promoted without
        # having all four pointers populated.
        output, coverage = [], []
        with engine.connect() as c:
            for company in ("NG", "NCS"):
                if user["companies"] and company not in user["companies"]:
                    continue
                allowed_lobs = set(user["lobs"]) if user["lobs"] else {"AE", "AI", "OE", "OI"}
                if allowed_lobs != {"AE", "AI", "OE", "OI"}:
                    coverage.append({"company": company, "status": "restricted_lob_access",
                                     "available_lobs": sorted(allowed_lobs)})
                    continue
                available = set(c.execute(select(shipments.c.report_type).distinct().where(
                    shipments.c.company == company,
                    shipments.c.report_type.in_(["AE", "AI", "OE", "OI"]),
                    shipments.c.to_import.is_(None))).scalars().all())
                if not {"AE", "AI", "OE", "OI"}.issubset(available):
                    coverage.append({"company": company, "status": "missing_lob_source",
                                     "available_lobs": sorted(available),
                                     "missing_lobs": sorted({"AE", "AI", "OE", "OI"} - available)})
                    continue
                latest = c.execute(select(func.max(shipments.c.shipment_date)).where(
                    shipments.c.company == company,
                    shipments.c.report_type.in_(["AE", "AI", "OE", "OI"]),
                    shipments.c.to_import.is_(None))).scalar()
                if not latest:
                    coverage.append({"company": company, "status": "no_shipment_dates"})
                    continue
                as_of = min(latest, date.today())
                cutoff = as_of - timedelta(days=179)
                records = c.execute(select(shipments.c.company, shipments.c.report_type,
                    shipments.c.customer, shipments.c.shipment_no, shipments.c.shipment_date, shipments.c.extra["Sales Person"].as_string().label("erp_salesperson")).where(
                    shipments.c.company == company,
                    shipments.c.report_type.in_(["AE", "AI", "OE", "OI"]),
                    shipments.c.to_import.is_(None),
                    shipments.c.shipment_date >= cutoff,
                    shipments.c.shipment_date <= as_of)).mappings().all()
                rows = [{"company": r["company"], "lob": r["report_type"],
                         "customer": r["customer"], "shipment_id": r["shipment_no"],
                         "shipment_date": r["shipment_date"], "salesperson": r["erp_salesperson"]} for r in records]
                candidates = find_opportunities(rows, as_of, complete_lob_coverage=True)
                output.extend(candidates)
                coverage.append({"company": company, "status": "ready",
                                 "available_lobs": sorted(available), "as_of": as_of.isoformat(),
                                 "window_rows": len(rows), "candidate_count": len(candidates)})
        output.sort(key=lambda r: (-r["shipment_count"], r["company"], r["customer"]))
        return {"viewer_id": user["id"], "window_days": 180, "candidates": output,
                "total_candidates": len(output), "coverage": coverage,
                "note": "Potential cross-service whitespace, not verified demand. Company-scoped, latest available 180-day shipment window. Only companies with all four LOBs loaded qualify."}

    @app.post("/api/admin/phase2/opportunities/export")
    def phase2_opportunities_export(user: dict = Depends(unsafe)):
        if user['role'] != 'admin': raise HTTPException(403, "Administrator access required.")
        data = phase2_opportunities(user)
        rows = [{"company": r['company'], "customer": r['customer'], "shipments": r['shipment_count'], "active_lobs": json.dumps(r['active_lobs']), "candidate_lobs": ', '.join(r['candidate_lobs']), "erp_salespersons": json.dumps(r.get('salespersons',{})), "confidence": r['confidence'], "reason": r['reason']} for r in data['candidates']]
        definition = dict(id='ops.opportunities', title='Potential cross-service opportunities', formula='Count customer/company groups with at least 3 distinct recent shipments and at least one absent LOB in the latest 180-day window; all four source LOBs must be available.', explanation=data['note'], source='Shipment Register', source_headers=['Shipment No','Shipment Date','Customer','Sales Person'], date_basis='Shipment Date', limitations='Name-based customer identity where ERP codes are unavailable. No forecast GP or confirmed customer demand.')
        result = dict(metric=definition, snapshot=str(store.version), version='1', current=dict(value=len(rows),numerator=None,denominator=None), previous=dict(value=None,numerator=None,denominator=None), difference=None, percentage=None, reconciliation=dict(displayed_value=data['total_candidates'],recalculated_value=len(rows),difference=data['total_candidates']-len(rows),status='match'), records=rows, comparison_records=[], context=dict(window_days=180,scope='All authorized qualified opportunities, independent of the table text search'), lineage=dict(coverage=data['coverage']))
        return Response(MX.workbook(result), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition':'attachment; filename="opportunity_reconciliation.xlsx"','Cache-Control':'private, no-store'})

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

