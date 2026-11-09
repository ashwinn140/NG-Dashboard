"""Builds the dashboard's data (the same JSON the review file embeds) from the database, then trims it to what one user may see."""
import collections, json, re
from datetime import datetime
import numpy as np, pandas as pd
from sqlalchemy import select, func
from . import config as CFG, profit as J
from .db import imports, shipments, profit_lines, org_master

REPS = [("NG", "AE"), ("NG", "AI"), ("NG", "OE"), ("NG", "OI"), ("NCS", "AE"), ("NCS", "AI"), ("NCS", "OE"), ("NCS", "OI")]
EXTRAS = ["Sales Person", "Trade Lane Name", "Loading Country", "Discharge Country", "Collection Executive", "Business Dimension", "Inco Terms", "Freight Type", "Contract Type",
          "Commodity Type", "Co-Load Type", "Origin Agent", "Customer Branch", "Document Executive (UDF)", "Place Of Execution", "Container Types"]
DASHBOARD_COLUMNS = sorted(set(EXTRAS) | {c for cols in CFG.SOURCE_COLUMNS.values() for c in cols} |
                           {"Booking Thru", "Invoice No. & Date", "Billing Details", "Buy Rate (UDF)", "Sell Rate (UDF)", "Dest. Agent", "Destination Agent"})
norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
INV_RE = re.compile(r"([A-Za-z0-9/\-\.]+?)\s*dt\.?\s*(\d{1,2})[-/ ]([A-Za-z]{3})[A-Za-z]*[-/ ](\d{4})", re.I)
RATE_NUM = re.compile(r"\d[\d,]*\.?\d*")
EPOCH = pd.Timestamp("1970-01-01")


def _txt(v):
    return "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v).strip()


def _clean(v):
    t = _txt(v)
    return "" if t in ("0", "0.0", "nan", "NaN") else t


def _docs(v):
    t = _txt(v)
    if not re.search(r"\w", t): return set(), False
    out = set()
    for doc, d_, m_, y_ in INV_RE.findall(t):
        try: out.add((doc.strip(" ;,.-"), pd.Timestamp(f"{d_} {m_} {y_}")))
        except Exception: pass
    return out, True


def _inv(a, b):
    da, ta = _docs(a); db, tb = _docs(b); both = da | db
    if not (ta or tb): return (-1, 0)
    return ((min(d for _, d in both) - EPOCH).days if both else -1, max(1, min(len(both), 250)))


def _rate(v):
    t = _txt(v); mm = RATE_NUM.search(t)
    if not mm: return (0.0, 0)
    if re.search(r"usd|eur|aed|gbp|sgd|\$|€|£", t, re.I): return (0.0, 3)
    try: val = float(mm.group(0).replace(",", "").rstrip("."))
    except Exception: return (0.0, 0)
    return (val, 1 if re.fullmatch(r"[\d,]+(\.\d+)?", t) else 2)


def load_master(engine):
    with engine.connect() as c:
        rows = c.execute(select(org_master).order_by(org_master.c.company.desc(), org_master.c.norm_key)).mappings().all()   # NG first
    out = {}
    for r in rows: out.setdefault(r["norm_key"], dict(r))
    return out


def _open_frame(engine, company, rt):
    # Project only displayed columns. Sorting full JSON rows in PostgreSQL caused
    # temporary-disk exhaustion; sort the projected rows in memory instead.
    q = select(shipments.c.id, *(shipments.c.extra[col].as_string().label(col) for col in DASHBOARD_COLUMNS)).where(
        shipments.c.company == company, shipments.c.report_type == rt, shipments.c.to_import.is_(None))
    with engine.connect() as c:
        rows = [dict(r) for r in c.execution_options(stream_results=True).execute(q).mappings()]
    rows.sort(key=lambda r: r.pop("id"))
    return pd.DataFrame(rows)


def _changes(engine, company, rt):
    """What the latest load of this report changed: new, no longer present, changed (with the columns that differ)."""
    if CFG.replace_reports():
        return None
    with engine.connect() as c:
        ids = [r[0] for r in c.execute(select(imports.c.id).where(imports.c.company == company, imports.c.report_type == rt, imports.c.status == "promoted").order_by(imports.c.id.desc()).limit(2)).all()]
        if len(ids) < 2: return None
        cur = ids[0]
        newv = c.execute(select(shipments.c.id, shipments.c.key, shipments.c.shipment_no, shipments.c.shipment_date, shipments.c.customer, shipments.c.branch, shipments.c.status).where(
            shipments.c.company == company, shipments.c.report_type == rt, shipments.c.from_import == cur)).all()
        oldv = c.execute(select(shipments.c.id, shipments.c.key, shipments.c.shipment_no, shipments.c.shipment_date, shipments.c.customer, shipments.c.branch, shipments.c.status, shipments.c.ended_reason).where(
            shipments.c.company == company, shipments.c.report_type == rt, shipments.c.to_import == cur)).all()
        n_old = c.execute(select(func.count()).select_from(shipments).where(shipments.c.company == company, shipments.c.report_type == rt, shipments.c.from_import <= ids[1],
                          (shipments.c.to_import.is_(None)) | (shipments.c.to_import > ids[1]))).scalar()
        n_new = c.execute(select(func.count()).select_from(shipments).where(shipments.c.company == company, shipments.c.report_type == rt, shipments.c.to_import.is_(None))).scalar()
    brief = lambda r: [r.shipment_no, r.shipment_date.strftime("%Y-%m-%d"), r.customer, r.branch, r.status]
    oldmap = {r.key: r for r in oldv if r.ended_reason == "changed"}; gone = [r for r in oldv if r.ended_reason == "not_present"]
    new = [r for r in newv if r.key not in oldmap]; chg = [r for r in newv if r.key in oldmap]
    extras = {}
    detail_ids = [i for r in chg for i in (r.id, oldmap[r.key].id)]
    with engine.connect() as c:
        for start in range(0, len(detail_ids), 500):
            extras.update((r.id, r.extra) for r in c.execute(select(shipments.c.id, shipments.c.extra).where(shipments.c.id.in_(detail_ids[start:start + 500]))))
    def details(r):
        a, b = extras[oldmap[r.key].id], extras[r.id]
        cols = sorted(k for k in set(a) | set(b) if a.get(k, "") != b.get(k, ""))
        return [brief(r), [[k, str(a.get(k, ""))[:60], str(b.get(k, ""))[:60]] for k in cols]]
    return {"new": [brief(r) for r in new], "gone": [brief(r) for r in gone], "changed": [details(r) for r in chg], "old_rows": int(n_old), "new_rows": int(n_new)}


def build_full(engine) -> dict:
    """Everything, for every company and report. Per-user trimming happens in restrict()."""
    frames, ranges, rep_meta = [], [], []
    with engine.connect() as c:
        runs = {(r[0], r[1]): r[2] for r in c.execute(select(imports.c.company, imports.c.report_type, func.count()).where(imports.c.status == "promoted").group_by(imports.c.company, imports.c.report_type)).all()}
        rng = {}
        for r in c.execute(select(imports.c.company, imports.c.report_type, imports.c.id, imports.c.range_from, imports.c.range_to).where(imports.c.status == "promoted").order_by(imports.c.id)).all(): rng[(r[0], r[1])] = (r[3], r[4])
    for ri, (co, rt) in enumerate(REPS):
        df = _open_frame(engine, co, rt)
        if df.empty: df = pd.DataFrame({"Shipment No": [], "Shipment Date": []})
        df["_rep"] = ri
        df["_carrier"] = df["Airline"] if "Airline" in df.columns and rt in ("AE", "AI") else df.get("Shipping Line")
        frames.append(df); ranges.append(rng.get((co, rt), (None, None)))
    A = pd.concat(frames, ignore_index=True)
    del frames, df
    N = len(A)
    if N == 0: raise ValueError("No shipments are loaded yet, so there is no dashboard data to build.")
    S = lambda col: A[col].fillna("").astype(str).str.strip().str.replace(r"\s+", " ", regex=True) if col in A.columns else pd.Series([""] * N)

    def canon(series):
        # Preserve ERP identity text. Punctuation/Unicode normalization belongs
        # in search, not in destructive replacement of source organization names.
        return series.fillna("").astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

    def port(series):
        code = series.str.extract(r"^\(([A-Za-z0-9]{5})\)")[0]
        name = (series.str.replace(r"^\([A-Za-z0-9]{5}\)\s*", "", regex=True).str.replace(r",\s*[A-Za-z .']+$", "", regex=True).str.replace(r"\s*\(ex .*?\)", "", regex=True).str.strip().str.title())
        canon_by = pd.DataFrame({"c": code, "n": name}).dropna(subset=["c"]).groupby("c")["n"].agg(lambda x: collections.Counter(x).most_common(1)[0][0]).to_dict()
        return pd.Series([canon_by.get(c, n) if isinstance(c, str) else n for c, n in zip(code, name)])

    carrier = A["_carrier"].fillna("").astype(str).str.strip().str.replace(r"\s+", " ", regex=True) if "_carrier" in A.columns else pd.Series([""] * N)
    cats = {"branch": ("Branch", S("Branch")), "customer": ("Customer", canon(S("Customer"))), "shipper": ("Shipper", canon(S("Shipper"))), "consignee": ("Consignee", canon(S("Consignee"))),
            "job_owner": ("Job owner", S("Job Owner")), "carrier": ("Airline / shipping line", canon(carrier)), "origin": ("Origin port", port(S("Loading Port"))), "destination": ("Destination port", port(S("Discharge Port"))),
            "nomination": ("Nomination", S("Self/Agent Nomination (UDF)")), "consol": ("Consol type", S("Consol Type")), "cargo": ("Cargo type", S("Cargo Type")), "status": ("Status", S("Status"))}
    MASTER = load_master(engine)
    _bt = S("Booking Thru"); _cu = cats["customer"][1].fillna("").astype(str)
    _ag = pd.Series(np.where((_bt.str.lower() == "self") | (_bt == ""), _cu, _bt)).map(lambda n: MASTER[norm(n)]["name"] if norm(n) in MASTER else n)
    cats["agent"] = ("Agent", canon(_ag))
    cats["origin_agent"] = ("Origin agent", S("Origin Agent"))
    cats["destination_agent"] = ("Destination agent", S("Dest. Agent").where(S("Dest. Agent") != "", S("Destination Agent")))
    sd = pd.to_datetime(A["Shipment Date"]) if N else pd.Series([], dtype="datetime64[ns]")
    ops = pd.to_datetime(A["Operations Locked On"], errors="coerce") if "Operations Locked On" in A.columns else pd.Series([pd.NaT] * N)
    fin = pd.to_datetime(A["Financials Locked On"], errors="coerce") if "Financials Locked On" in A.columns else pd.Series([pd.NaT] * N)
    _iv = [_inv(a, b) for a, b in zip(A.get("Invoice No. & Date", pd.Series([None] * N)), A.get("Billing Details", pd.Series([None] * N)))]
    INV1 = [a for a, b in _iv]; INVN = [b for a, b in _iv]
    _rb = [_rate(v) for v in A.get("Buy Rate (UDF)", pd.Series([None] * N))]; _rs = [_rate(v) for v in A.get("Sell Rate (UDF)", pd.Series([None] * N))]
    RBUY = [round(a, 3) for a, b in _rb]; RBF = [b for a, b in _rb]; RSELL = [round(a, 3) for a, b in _rs]; RSF = [b for a, b in _rs]
    days = lambda s: ((s - EPOCH).dt.days).fillna(-1).astype(int)
    stage = np.where(ops.isna(), "Pending ops lock", np.where(fin.isna(), "Financials open", "Closed"))
    cats["stage"] = ("Stage", pd.Series(stage))
    for x in EXTRAS: cats["x_" + norm(x)] = (x, S(x))

    def enc(series):
        s = series.replace("", "(blank)"); vc = s.value_counts()
        d = list(vc.index); idx = {v: i for i, v in enumerate(d)}
        return {"d": d, "c": s.map(idx).astype(int).tolist()}

    # ---- job profit lines joined to the registers
    with engine.connect() as c:
        fields = ["id", "company", "job_date", "job_no", "lob", "customer", "party", "branch", "charge", "income", "expense", "trans_date", "trade_lane", "extra"]
        pl_rows = list(c.execute(select(*(profit_lines.c[k] for k in fields)).where(*J.current_jobs())).mappings())
        pl_rows.sort(key=lambda r: r["id"])
        jp = J.summary_imports(c.execute(select(imports.c.company, imports.c.range_from, imports.c.range_to, imports.c.file_name, imports.c.columns).where(imports.c.report_type == "JP", imports.c.status == "promoted").order_by(imports.c.id)).all())
    reg_co = np.where(A["_rep"] < 4, "NG", "NCS") if N else np.array([]); reg_no = A["Shipment No"].astype(str).str.strip().values if N else []; reg_date = sd.dt.strftime("%Y-%m-%d").values if N else []
    reg_rt = [REPS[int(ri)][1] for ri in A["_rep"]]
    by_key, by_no = collections.defaultdict(list), collections.defaultdict(list)
    for i in range(N):
        by_key[(reg_co[i], reg_no[i], reg_date[i])].append(i); by_no[(reg_co[i], reg_no[i])].append(i)
    ICN = {norm(n): cc for n, cc in CFG.COMPANIES.items()}
    pl, pmeta_acc = [], {}
    for r in pl_rows:
        co = r["company"]; jd = r["job_date"].strftime("%Y-%m-%d") if r["job_date"] else ""
        mode, direction, kind = J._mode(r["lob"]); other = "NCS" if co == "NG" else "NG"
        # Match within the known LOB, using a unique exact date first. Never
        # attribute finance to an arbitrary first shipment with a reused number.
        expected_rt = {("Air", "Export"): "AE", ("Air", "Import"): "AI",
                       ("Sea", "Export"): "OE", ("Sea", "Import"): "OI"}.get((mode, direction))
        candidates = by_key.get((co, r["job_no"], jd), [])
        if not candidates:
            candidates = by_no.get((co, r["job_no"]), [])
        candidates = [i for i in candidates if expected_rt is None or reg_rt[i] == expected_rt]
        si = candidates[0] if kind != "Customs clearance" and len(candidates) == 1 and str(r["job_no"] or "").strip() else -1
        ic = "Intercompany" if (ICN.get(norm(r["customer"])) == other or ICN.get(norm(r["party"])) == other) else "External"
        rtc = {("Air", "Export"): 0, ("Air", "Import"): 1, ("Sea", "Export"): 2, ("Sea", "Import"): 3}.get((mode, direction), 4)
        pl.append(dict(co=0 if co == "NG" else 1, sidx=si, rt=rtc, branch=r["branch"], lob=r["lob"], mode=mode, direction=direction, kind=kind, job=r["job_no"], customer=r["customer"], charge=r["charge"], party=r["party"],
                       income=r["income"] or 0.0, expense=r["expense"] or 0.0, td=r["trans_date"], jd=r["job_date"], plane=r["trade_lane"], ic=ic))
        e = pmeta_acc.setdefault(co, dict(lines=0, income=0.0, expense=0.0, jobs={}))
        e["lines"] += 1; e["income"] += r["income"] or 0.0; e["expense"] += r["expense"] or 0.0; e["jobs"].setdefault((r["job_no"], jd, r["lob"]), (si, r["lob"]))
    pmeta = []
    for co in ("NG", "NCS"):
        if co not in pmeta_acc: continue
        e = pmeta_acc[co]; mine = [x for x in jp if x[0] == co]; unm = collections.Counter(l for (si, l) in e["jobs"].values() if si < 0)
        cols = json.loads(mine[-1][4]) if mine and mine[-1][4] else []
        pmeta.append(dict(co=co, file=mine[-1][3] if mine else "", title=f"{CFG.COMPANY_LABELS[co]} · Job Profit Analysis", range_from=str(min(x[1] for x in mine if x[1])) if mine else "", range_to=str(max(x[2] for x in mine if x[2])) if mine else "",
                          basis="Job Date", lines=e["lines"], income=round(e["income"], 2), expense=round(e["expense"], 2), grand_income=round(e["income"], 2), grand_expense=round(e["expense"], 2), columns=cols,
                          ranges=[[str(x[1]), str(x[2])] for x in mine if x[1] and x[2]], jobs=len(e["jobs"]), matched=sum(1 for (si, l) in e["jobs"].values() if si >= 0), unmatched_by_lob=dict(unm)))
    PD = pd.DataFrame(pl, columns=["co", "sidx", "rt", "branch", "lob", "mode", "direction", "kind", "job", "customer", "charge", "party", "income", "expense", "td", "jd", "plane", "ic"]); NP = len(PD)
    NOMATCH = "(no register match)"
    from_reg = lambda series, idx: pd.Series([series.iloc[i] if i >= 0 else NOMATCH for i in idx], dtype=object)
    source_map = {"branch": "Location", "customer": "Organization", "shipper": "Shipper", "consignee": "Consignee", "job_owner": "Job Owner", "carrier": "Carrier", "agent": "Overseas Agent", "origin_agent": "Origin Agent", "destination_agent": "Dest. Agent", "origin": "Loading Port", "destination": "Discharge Port", "x_salesperson": "Sales Person", "x_tradelanename": "Trade Lane", "x_dischargecountry": "Discharge Country", "x_loadingcountry": "Loading Country", "cargo": "Cargo Type", "consol": "Consol Type"}
    source_values = [x["extra"] or {} for x in pl_rows]
    # Source job attributes take priority, including explicit blanks. Register
    # attributes are only fallbacks for fields absent from the uploaded report.
    pser = {}
    for k, (label, ser) in cats.items():
        ps = from_reg(ser.reset_index(drop=True), PD.sidx.tolist())
        if k == "branch": ps = PD.branch.astype(str).str.strip()
        if k == "customer": ps = PD.customer.fillna("").astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
        if k == "x_tradelanename": ps = pd.Series([v if v != NOMATCH or not pl_ else (pl_ or NOMATCH) for v, pl_ in zip(ps, PD.plane.fillna("").astype(str))], dtype=object)
        field = source_map.get(k)
        if k == "destination_agent":
            source_values_for_field = [dict(extra, **{"Dest. Agent": extra["Destination Agent"]}) if "Dest. Agent" not in extra and "Destination Agent" in extra else extra for extra in source_values]
        else:
            source_values_for_field = source_values
        if field:
            ps = pd.Series([str(extra[field]).strip() if field in extra else ("" if si < 0 else val) for extra, si, val in zip(source_values_for_field, PD.sidx.tolist(), ps)], dtype=object)
        pser[k] = ps
    cust_all = pd.concat([cats["customer"][1].reset_index(drop=True), pser["customer"]], ignore_index=True); cust_c = canon(cust_all)
    cats["customer"] = (cats["customer"][0], cust_c.iloc[:N].reset_index(drop=True)); pser["customer"] = cust_c.iloc[N:].reset_index(drop=True)

    def enc_both(k):
        comb = pd.concat([cats[k][1].reset_index(drop=True), pser[k]], ignore_index=True); e = enc(comb); return {"l": cats[k][0], "d": e["d"], "c": e["c"][:N], "pc": e["c"][N:]}
    pcols = {k: enc_both(k) for k in cats}
    AGENTINFO = [[MASTER[norm(n)]["country"] or "", MASTER[norm(n)]["network"] or "", MASTER[norm(n)]["conf"] or "", MASTER[norm(n)]["sales"] or "", MASTER[norm(n)]["contact"] or "", MASTER[norm(n)]["email"] or ""]
                 if norm(n) in MASTER else ["", "", "", "", "", ""] for n in pcols["agent"]["d"]]
    for k, label in {"lob": "Line of business", "ic": "Intercompany", "job": "Job no.", "mode": "Mode (profit)", "direction": "Direction (profit)", "kind": "Service"}.items():
        e = enc(PD[k].fillna("").astype(str)); pcols["p_" + k] = {"l": label, "d": e["d"], "pc": e["c"]}
    excluded = set(source_map.values()) | set(CFG.PROFIT_REQUIRED) | {"_format", "Profit Margin %"}
    for name in sorted({key for extra in source_values for key in extra} - excluded):
        if not name or name.startswith("_"):
            continue
        key = "jp_" + norm(name)
        e = enc(pd.Series([str(extra.get(name, "")) for extra in source_values], dtype=object))
        pcols[key] = {"l": name, "d": e["d"], "pc": e["c"]}
    dayso = lambda s: pd.to_datetime(s, errors="coerce").map(lambda d: -1 if pd.isna(d) else (d - EPOCH).days)
    PROFIT = {"co": PD.co.tolist(), "sidx": PD.sidx.tolist(), "rt": PD.rt.tolist(), "income": PD.income.astype(float).round(2).tolist(), "expense": PD.expense.astype(float).round(2).tolist(), "td": dayso(PD.td).tolist(), "jd": dayso(PD.jd).tolist(), "meta": pmeta, "format": J.FORMAT}
    num = lambda col: pd.to_numeric(A[col], errors="coerce").fillna(0) if col in A.columns else pd.Series([0.0] * N)
    out = {"reps": [[c_, r_] for c_, r_ in REPS], "ckg": pd.to_numeric(A.get("Chargeable Wt", pd.Series([0] * N)), errors="coerce").fillna(0).tolist(), "rbuy": RBUY, "rbf": RBF, "rsell": RSELL, "rsf": RSF,
           "inv1": INV1, "invN": INVN, "rep": A["_rep"].tolist(), "no": A["Shipment No"].astype(str).tolist(), "date": days(sd).tolist(), "ops": days(ops).tolist(), "fin": days(fin).tolist(),
           "gross": (num("Gross Weight") / 1000).tolist(), "chg": (num("Chargeable Wt") / 1000).tolist(), "teus": num("TEUs").tolist(), "cbm": num("Volume").tolist(),
           "agentInfo": AGENTINFO, "cols": pcols, "p": PROFIT}
    meta = []
    for ri, (co, rt) in enumerate(REPS):
        m = (A["_rep"] == ri).values; d = sd[m]; rep_no = A.loc[m, "Shipment No"].astype(str)
        rf, rto = ranges[ri]
        meta.append({"co": co, "rep": rt, "rows": int(m.sum()), "from": d.min().strftime("%Y-%m-%d") if len(d) else "", "to": d.max().strftime("%Y-%m-%d") if len(d) else "", "repeated": int(rep_no.duplicated(keep=False).sum() // 2),
                     "runs": int(runs.get((co, rt), 0)), "pend": int((stage[m] == "Pending ops lock").sum()), "finopen": int((stage[m] == "Financials open").sum()),
                     "range_from": rf.strftime("%Y-%m-%d") if rf else "", "range_to": rto.strftime("%Y-%m-%d") if rto else ""})
    out["meta"] = meta
    ch = {}
    for ri, (co, rt) in enumerate(REPS):
        c_ = _changes(engine, co, rt)
        if c_: ch[str(ri)] = c_
    out["changes"] = ch
    out["storage_mode"] = "replace" if CFG.replace_reports() else "versioned"
    out["built_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    return out


# ------------------------------------------------------------------ per-user trimming
def _remap(codes, d, keep_idx):
    """Re-number a dictionary column so only values still used remain (nothing about hidden rows leaks)."""
    arr = np.asarray(codes, dtype=np.int64)
    used = np.unique(arr)
    new = {int(o): i for i, o in enumerate(used)}
    return [d[int(o)] for o in used], [new[int(x)] for x in arr]


def restrict(D: dict, user: dict) -> dict:
    """user: {companies:[...], lobs:[...], finance:bool}. Returns a copy holding only permitted rows and the dictionary values they use."""
    reps = D["reps"]
    allowed_rep = [i for i, (co, rt) in enumerate(reps) if (not user["companies"] or co in user["companies"]) and (not user["lobs"] or rt in user["lobs"])]
    rep = np.asarray(D["rep"], dtype=np.int64)
    keep = np.isin(rep, allowed_rep)
    idx = np.nonzero(keep)[0]
    pk = np.zeros(len(D["p"]["co"]), dtype=bool)
    if user["finance"]:
        pco = np.asarray(D["p"]["co"], dtype=np.int64); prt = np.asarray(D["p"]["rt"], dtype=np.int64)
        comp_ok = [i for i, c in enumerate(["NG", "NCS"]) if not user["companies"] or c in user["companies"]]
        lob_ix = {"AE": 0, "AI": 1, "OE": 2, "OI": 3}
        rt_ok = [lob_ix[l] for l in user["lobs"]] if user["lobs"] else [0, 1, 2, 3, 4]      # road and general jobs only for people with every LOB
        pk = np.isin(pco, comp_ok) & np.isin(prt, rt_ok)
    pidx = np.nonzero(pk)[0]
    # register rows: new index of each kept row, for the profit join
    newpos = -np.ones(len(rep), dtype=np.int64); newpos[idx] = np.arange(len(idx))
    take = lambda a: [a[i] for i in idx]
    out = {"reps": reps, "rep": take(D["rep"]), "no": take(D["no"])}
    for k in ("date", "ops", "fin", "gross", "chg", "teus", "cbm", "ckg", "rbuy", "rbf", "rsell", "rsf", "inv1", "invN"): out[k] = take(D[k])
    if not user["finance"]:
        for k in ("rbuy", "rbf", "rsell", "rsf"):
            out[k] = [0] * len(idx)
    sidx = np.asarray(D["p"]["sidx"], dtype=np.int64)[pidx] if len(pidx) else np.array([], dtype=np.int64)
    sidx_new = np.full(len(sidx), -1, dtype=np.int64)
    matched = (sidx >= 0) & (sidx < len(newpos))
    sidx_new[matched] = newpos[sidx[matched]]  # hidden shipments remain unmatched, including empty registers
    out["p"] = {"co": [D["p"]["co"][i] for i in pidx], "sidx": sidx_new.tolist(), "rt": [D["p"]["rt"][i] for i in pidx], "income": [D["p"]["income"][i] for i in pidx], "expense": [D["p"]["expense"][i] for i in pidx],
                "format": J.FORMAT, "td": [D["p"]["td"][i] for i in pidx], "jd": [D["p"]["jd"][i] for i in pidx], "meta": [m for m in D["p"]["meta"] if user["finance"] and not user["lobs"] and (not user["companies"] or m["co"] in user["companies"])]}
    cols = {}
    for k, c in D["cols"].items():
        entry = {"l": c["l"]}
        regc = [c["c"][i] for i in idx] if "c" in c else None
        profc = [c["pc"][i] for i in pidx] if "pc" in c else []
        both = (regc or []) + profc
        if both:
            arr = np.asarray(both, dtype=np.int64); used = np.unique(arr); mp = {int(o): i for i, o in enumerate(used)}
            entry["d"] = [c["d"][int(o)] for o in used]
            if regc is not None: entry["c"] = [mp[int(x)] for x in regc]
            entry["pc"] = [mp[int(x)] for x in profc]
        else:
            entry["d"] = []; entry["pc"] = []
            if regc is not None: entry["c"] = []
        cols[k] = entry
    out["cols"] = cols
    # agent details only for agents still present
    ag_old = D["cols"]["agent"]["d"]; ag_new = cols["agent"]["d"]; pos = {n: i for i, n in enumerate(ag_old)}
    out["agentInfo"] = [D["agentInfo"][pos[n]] for n in ag_new]
    blank = {"rows": 0, "from": "", "to": "", "pend": 0, "finopen": 0, "repeated": 0, "runs": 0}
    out["meta"] = [m if i in allowed_rep else dict(m, **blank) for i, m in enumerate(D["meta"])]
    out["changes"] = {k: v for k, v in D["changes"].items() if int(k) in allowed_rep}
    out["built_at"] = D.get("built_at")
    out["storage_mode"] = D.get("storage_mode", "versioned")
    out["user"] = {"finance": bool(user["finance"]), "companies": user["companies"], "lobs": user["lobs"]}
    return out

