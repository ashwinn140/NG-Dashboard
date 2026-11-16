"""Organization master (agent details): read the ERP export and keep the latest copy in the database."""
import re
from datetime import datetime
import numpy as np, pandas as pd
from sqlalchemy import delete, insert
from .db import org_master

norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())


def _clean(v):
    t = "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v).strip()
    return "" if t in ("0", "0.0", "nan", "NaN") else t


def read_master(path: str) -> list[dict]:
    df = pd.read_excel(path)
    if "Organization" not in df.columns: raise ValueError("This does not look like the Organization master: there is no 'Organization' column.")
    rows, seen = [], set()
    for r in df.to_dict("records"):
        name = _clean(r.get("Organization"))
        if not name: continue
        k = norm(name)
        if not k or k in seen: continue
        seen.add(k); nets = []
        for j in range(1, 7):
            v = _clean(r.get(f"Network {j} (UDF)"))
            if v and v not in nets: nets.append(v)
        rows.append(dict(norm_key=k, name=name, country=_clean(r.get("CountryName")), sales=_clean(r.get("Salesperson")), network=", ".join(nets), conf=_clean(r.get("Conference Attended by")),
                         contact=_clean(r.get("Contact Name") or r.get("Contact Person")), email=_clean(r.get("Email Address") or r.get("Email"))))
    return rows


def preview_master(path: str) -> dict:
    rows = read_master(path)
    return dict(rows=len(rows), with_contact=sum(1 for r in rows if r["contact"]), with_email=sum(1 for r in rows if r["email"]), with_network=sum(1 for r in rows if r["network"]), with_country=sum(1 for r in rows if r["country"]))


def load_master(engine, path: str, company: str) -> dict:
    """Replace this company's master with the file's contents."""
    rows = read_master(path)
    if not rows:
        raise ValueError("Organization master contains no valid Organization records; the existing master was not changed.")
    now = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(delete(org_master).where(org_master.c.company == company))
        for i in range(0, len(rows), 2000):
            conn.execute(insert(org_master), [dict(r, company=company, updated_at=now) for r in rows[i:i + 2000]])
    return dict(rows=len(rows), company=company)
