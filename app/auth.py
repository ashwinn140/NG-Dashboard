"""Sign-in: one-time email link (with a 6-digit code as fallback) and user ID + password. Sessions, roles and lockouts."""
import hashlib, hmac, os, re, secrets
from datetime import datetime, timedelta
from sqlalchemy import select, update, insert, delete, func
from .db import users, sessions, login_tokens

LINK_MINUTES = 15            # a link or code works for this long, once
LINK_REQUESTS_PER_HOUR = 10  # per email address
CODE_ATTEMPTS = 5
SESSION_HOURS = 12
PW_FAILS = 5                 # wrong passwords before a 15-minute lock
LOCK_MINUTES = 15
ROLES = ("admin", "management", "operations", "finance")
LOB_CODES = ("AE", "AI", "OE", "OI")
COMPANIES = ("NG", "NCS")


def _pepper() -> bytes:
    return (os.environ.get("SECRET_KEY") or "dev-only-secret-change-me").encode()


def h(value: str) -> str:
    return hmac.new(_pepper(), value.encode(), hashlib.sha256).hexdigest()


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$%s$%s" % (salt.hex(), dk.hex())


def check_password(pw: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        hashlib.scrypt(b"x", salt=b"0" * 16, n=2 ** 14, r=8, p=1, dklen=32)      # same cost whether or not the user exists
        return False
    _, salt, dk = stored.split("$")
    cand = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1, dklen=32)
    return hmac.compare_digest(cand.hex(), dk)


def password_problem(pw: str) -> str | None:
    if len(pw) < 10: return "Use at least 10 characters."
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw): return "Use letters and at least one number."
    return None


def _split(v): return [x for x in (v or "").split(",") if x]


def user_dict(r) -> dict:
    return dict(id=r.id, email=r.email, user_id=r.user_id, name=r.name or r.email, role=r.role, companies=_split(r.companies), lobs=_split(r.lobs), finance=bool(r.finance), active=bool(r.active),
                has_password=bool(r.pw_hash), last_login=r.last_login.isoformat() if r.last_login else None)


def finance_default(role: str) -> int:
    return 1 if role in ("admin", "management", "finance") else 0


def create_user(engine, email: str, role: str = "operations", name: str = "", user_id: str | None = None, companies=None, lobs=None, finance: bool | None = None, password: str | None = None) -> dict:
    email = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email): raise ValueError("That does not look like an email address.")
    if role not in ROLES: raise ValueError("Role must be one of: " + ", ".join(ROLES))
    companies = [c for c in (companies or []) if c in COMPANIES]; lobs = [l for l in (lobs or []) if l in LOB_CODES]
    if password:
        p = password_problem(password)
        if p: raise ValueError(p)
    with engine.begin() as conn:
        if conn.execute(select(users.c.id).where(users.c.email == email)).first(): raise ValueError("A user with this email already exists.")
        if user_id and conn.execute(select(users.c.id).where(users.c.user_id == user_id.strip().lower())).first(): raise ValueError("That user ID is taken.")
        conn.execute(insert(users).values(email=email, user_id=(user_id or "").strip().lower() or None, name=name or email.split("@")[0], role=role, companies=",".join(companies), lobs=",".join(lobs),
                                          finance=finance_default(role) if finance is None else int(bool(finance)), active=1, pw_hash=hash_password(password) if password else None,
                                          pw_set_at=datetime.utcnow() if password else None, fail_count=0, created_at=datetime.utcnow()))
        r = conn.execute(select(users).where(users.c.email == email)).one()
    return user_dict(r)


def update_user(engine, uid: int, **f) -> dict:
    vals = {}
    if "role" in f and f["role"] is not None:
        if f["role"] not in ROLES: raise ValueError("Role must be one of: " + ", ".join(ROLES))
        vals["role"] = f["role"]
    if "name" in f and f["name"] is not None: vals["name"] = f["name"]
    if "companies" in f and f["companies"] is not None: vals["companies"] = ",".join(c for c in f["companies"] if c in COMPANIES)
    if "lobs" in f and f["lobs"] is not None: vals["lobs"] = ",".join(l for l in f["lobs"] if l in LOB_CODES)
    if "finance" in f and f["finance"] is not None: vals["finance"] = int(bool(f["finance"]))
    if "active" in f and f["active"] is not None: vals["active"] = int(bool(f["active"]))
    if "user_id" in f and f["user_id"] is not None: vals["user_id"] = f["user_id"].strip().lower() or None
    with engine.begin() as conn:
        if "role" in vals and "finance" not in vals and f.get("reset_finance"): vals["finance"] = finance_default(vals["role"])
        if vals: conn.execute(update(users).where(users.c.id == uid).values(**vals))
        if vals.get("active") == 0: conn.execute(delete(sessions).where(sessions.c.user_id == uid))
        r = conn.execute(select(users).where(users.c.id == uid)).first()
    if not r: raise ValueError("No such user.")
    return user_dict(r)


def set_password(engine, uid: int, pw: str) -> None:
    p = password_problem(pw)
    if p: raise ValueError(p)
    with engine.begin() as conn:
        conn.execute(update(users).where(users.c.id == uid).values(pw_hash=hash_password(pw), pw_set_at=datetime.utcnow(), fail_count=0, locked_until=None))
        conn.execute(delete(sessions).where(sessions.c.user_id == uid))


# ------------------------------------------------------------------ email link and code
def request_link(engine, email: str, now: datetime | None = None):
    """Returns (token, code, user) when a link should be mailed, or None. The caller shows the same message either way."""
    now = now or datetime.utcnow(); email = email.strip().lower()
    with engine.begin() as conn:
        recent = conn.execute(select(func.count()).select_from(login_tokens).where(login_tokens.c.email == email, login_tokens.c.created_at > now - timedelta(hours=1))).scalar()
        u = conn.execute(select(users).where(users.c.email == email, users.c.active == 1)).first()
        if recent >= LINK_REQUESTS_PER_HOUR or not u:
            if not u: conn.execute(insert(login_tokens).values(email=email, token_hash="-", code_hash="-", created_at=now, expires_at=now, used=1, attempts=0))     # counts toward the limit, so unknown addresses cannot be probed for free
            return None
        token = secrets.token_urlsafe(32); code = "%06d" % secrets.randbelow(10 ** 6)
        conn.execute(insert(login_tokens).values(email=email, token_hash=h("t:" + token), code_hash=h("c:%s:%s" % (email, code)), created_at=now, expires_at=now + timedelta(minutes=LINK_MINUTES), used=0, attempts=0))
    return token, code, user_dict(u)


def use_token(engine, token: str, now: datetime | None = None):
    now = now or datetime.utcnow(); th = h("t:" + token)
    with engine.begin() as conn:
        t = conn.execute(select(login_tokens).where(login_tokens.c.token_hash == th)).first()
        if not t or t.used or t.expires_at < now: return None
        conn.execute(update(login_tokens).where(login_tokens.c.id == t.id).values(used=1))
        u = conn.execute(select(users).where(users.c.email == t.email, users.c.active == 1)).first()
    return user_dict(u) if u else None


def use_code(engine, email: str, code: str, now: datetime | None = None):
    now = now or datetime.utcnow(); email = email.strip().lower()
    with engine.begin() as conn:
        t = conn.execute(select(login_tokens).where(login_tokens.c.email == email, login_tokens.c.used == 0, login_tokens.c.expires_at > now).order_by(login_tokens.c.id.desc())).first()
        if not t: return None
        if t.attempts >= CODE_ATTEMPTS:
            conn.execute(update(login_tokens).where(login_tokens.c.id == t.id).values(used=1)); return None
        if not hmac.compare_digest(t.code_hash, h("c:%s:%s" % (email, code.strip()))):
            conn.execute(update(login_tokens).where(login_tokens.c.id == t.id).values(attempts=t.attempts + 1, used=1 if t.attempts + 1 >= CODE_ATTEMPTS else 0)); return None
        conn.execute(update(login_tokens).where(login_tokens.c.id == t.id).values(used=1))
        u = conn.execute(select(users).where(users.c.email == email, users.c.active == 1)).first()
    return user_dict(u) if u else None


def password_login(engine, login: str, pw: str, now: datetime | None = None):
    """Returns (user, message). Wrong ID and wrong password look the same; five wrong passwords lock the account for 15 minutes."""
    now = now or datetime.utcnow(); login = login.strip().lower()
    with engine.begin() as conn:
        u = conn.execute(select(users).where((users.c.email == login) | (users.c.user_id == login))).first()
        if u and u.locked_until and u.locked_until > now: return None, "Too many wrong attempts. Try again in a few minutes."
        ok = check_password(pw, u.pw_hash if u else None) and u is not None and u.active == 1
        if ok:
            conn.execute(update(users).where(users.c.id == u.id).values(fail_count=0, locked_until=None)); return user_dict(u), ""
        if u:
            n = (u.fail_count or 0) + 1
            conn.execute(update(users).where(users.c.id == u.id).values(fail_count=0 if n >= PW_FAILS else n, locked_until=now + timedelta(minutes=LOCK_MINUTES) if n >= PW_FAILS else None))
    return None, "That ID or password is not right."


# ------------------------------------------------------------------ sessions
def create_session(engine, uid: int, method: str, now: datetime | None = None):
    now = now or datetime.utcnow(); raw = secrets.token_urlsafe(32); csrf = secrets.token_urlsafe(24)
    with engine.begin() as conn:
        conn.execute(delete(sessions).where(sessions.c.expires_at < now))
        conn.execute(insert(sessions).values(id=h("s:" + raw), user_id=uid, csrf=csrf, created_at=now, expires_at=now + timedelta(hours=SESSION_HOURS), method=method))
        conn.execute(update(users).where(users.c.id == uid).values(last_login=now))
    return raw, csrf


def session_user(engine, raw: str | None, now: datetime | None = None):
    if not raw: return None
    now = now or datetime.utcnow()
    with engine.connect() as conn:
        s = conn.execute(select(sessions).where(sessions.c.id == h("s:" + raw))).first()
        if not s or s.expires_at < now: return None
        u = conn.execute(select(users).where(users.c.id == s.user_id, users.c.active == 1)).first()
    if not u: return None
    d = user_dict(u); d["csrf"] = s.csrf; d["method"] = s.method; return d


def end_session(engine, raw: str | None) -> None:
    if raw:
        with engine.begin() as conn: conn.execute(delete(sessions).where(sessions.c.id == h("s:" + raw)))
