(function () {
'use strict';
// ---------------------------------------------------------------- decode data
const D = window.__D;
const SERVER = !!window.__ME, FIN = !SERVER || !!(D.user && D.user.finance);
function srvPut(name, val) { if (!SERVER) return; try { fetch('/api/prefs/' + name, {method: 'PUT', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': window.__ME.csrf}, body: JSON.stringify(val)}).catch(() => {}); } catch (e) { /* offline */ } }
const N = D.rep.length;
const REPN = ['Air Export', 'Air Import', 'Sea Export', 'Sea Import'], COMP = ['New Globe', 'Neutral Consolidation'];
const REPCOL = ['#4c78a8', '#f58518', '#54a24b', '#b279a2'];
const fInt = d3.format(','), f1 = d3.format(',.1f'), fP0 = d3.format('.0%'), fP1 = d3.format('.1%');
const DMS = 864e5, dDate = (d) => new Date(d * DMS), isoD = (s) => Math.round(Date.parse(s) / DMS);
const fIso = d3.utcFormat('%Y-%m-%d'), fDay = (d) => d3.utcFormat('%-d %b %Y')(dDate(d)), fMon = (d) => d3.utcFormat('%b %Y')(dDate(d)), fDM = (d) => d3.utcFormat('%-d %b')(dDate(d));

// Demo history: earlier years simulated from this year's rows so year-on-year can be previewed. They are only ever
// visible on the Compare page when the demo switch is on. Real rows are 0..N-1; demo rows follow them.
const hash01 = (a, b) => { let x = (Math.imul(a + 1, 2654435761) ^ Math.imul(b + 7, 40503)) >>> 0; x = Math.imul(x ^ (x >>> 15), 2246822519) >>> 0; x = Math.imul(x ^ (x >>> 13), 3266489917) >>> 0; return ((x ^ (x >>> 16)) >>> 0) / 4294967296; };
const DEMO_KEEP = [0, 0.86, 0.72], demoSrc = [], demoK = [];
const NA = N + demoSrc.length, ext = (T, a) => { const x = new T(NA); x.set(a); return x; };
const rep = ext(Uint8Array, D.rep), comp = new Uint8Array(NA), rtype = new Uint8Array(NA), mode = new Uint8Array(NA), demo = new Uint8Array(NA);
const date = ext(Int32Array, D.date), opsD = ext(Int32Array, D.ops), finD = ext(Int32Array, D.fin), inv1 = ext(Int32Array, D.inv1), invN = ext(Uint8Array, D.invN);
const chg = ext(Float64Array, D.chg), teus = ext(Float64Array, D.teus), gross = ext(Float64Array, D.gross), cbm = ext(Float64Array, D.cbm);
for (let t = 0; t < demoSrc.length; t++) { const i = N + t, s0 = demoSrc[t], k = demoK[t], f = 0.7 + 0.6 * hash01(s0, 10 + k); rep[i] = rep[s0]; date[i] = date[s0] - 365 * k; inv1[i] = inv1[s0] > 0 ? inv1[s0] - 365 * k : inv1[s0]; invN[i] = invN[s0]; chg[i] = chg[s0] * f; teus[i] = Math.round(teus[s0] * f); gross[i] = gross[s0] * f; cbm[i] = cbm[s0] * f; demo[i] = 1; opsD[i] = -1; finD[i] = -1; }
for (let i = 0; i < NA; i++) { comp[i] = rep[i] < 4 ? 0 : 1; rtype[i] = rep[i] % 4; mode[i] = rtype[i] < 2 ? 0 : 1; }
const VOL = new Float64Array(NA); for (let i = 0; i < NA; i++) VOL[i] = mode[i] === 0 ? chg[i] : teus[i];
const mStart = new Int32Array(NA); { const cache = new Map(); for (let i = 0; i < NA; i++) { let v = cache.get(date[i]); if (v === undefined) { v = Math.round(+d3.utcMonth.floor(dDate(date[i])) / DMS); cache.set(date[i], v); } mStart[i] = v; } }
const COLS = {company: {l: 'Company', d: COMP, c: comp}, report: {l: 'Report', d: REPN, c: rtype}};
for (const k in D.cols) { const dc = D.cols[k], c = dc.c ? ext(Uint32Array, dc.c) : new Uint32Array(NA); if (dc.c) for (let t = 0; t < demoSrc.length; t++) c[N + t] = c[demoSrc[t]]; COLS[k] = {l: dc.l, d: dc.d, c, own: !!dc.c}; }
// ---- job profit lines, joined to the shipment registers by job number (the "VLOOKUP"); they share the same dictionaries, so every filter applies to both
const PD_ = D.p, NP = PD_.co.length, PSH = [7, 31, 365], pdemoSrc = [], pdemoK = [];
const NPA = NP + pdemoSrc.length, pext = (T, a) => { const x = new T(NPA); x.set(a); return x; };
const pco = pext(Uint8Array, PD_.co), prt = pext(Uint8Array, PD_.rt), pinc = pext(Float64Array, PD_.income), pexp = pext(Float64Array, PD_.expense), ptd = pext(Int32Array, PD_.td), pjd = pext(Int32Array, PD_.jd), psidx = pext(Int32Array, PD_.sidx);
const pdemo = new Uint8Array(NPA), pjob = new Int32Array(NPA);
for (let t = 0; t < pdemoSrc.length; t++) { const i = NP + t, s0 = pdemoSrc[t], f = 0.7 + 0.6 * hash01(s0, 90 + pdemoK[t]); pco[i] = pco[s0]; prt[i] = prt[s0]; pinc[i] = pinc[s0] * f; pexp[i] = pexp[s0] * f; ptd[i] = ptd[s0] - PSH[pdemoK[t]]; pjd[i] = pjd[s0] - PSH[pdemoK[t]]; psidx[i] = psidx[s0]; pdemo[i] = 1; }
for (const k in D.cols) { const pc = pext(Uint32Array, D.cols[k].pc); for (let t = 0; t < pdemoSrc.length; t++) pc[NP + t] = pc[pdemoSrc[t]]; COLS[k].pc = pc; }
COLS.company.pc = pco; COLS.company.own = true; COLS.report.own = true; COLS.report.pc = prt; COLS.report.d = REPN.concat(['Other (road, general)']);
COLS.jobstatus = {l: 'Job status', d: ['No flagged condition', 'Cost not booked', 'Costs booked, no income recorded', 'Loss-making', 'Low margin'], c: null, pc: new Uint8Array(NPA), own: false};
COLS.band = {l: 'Job margin band', d: ['Loss (below 0%)', '0 to 10%', '10 to 30%', '30 to 60%', '60 to 99%', '100% (no cost booked)', 'No income'], c: null, pc: new Uint8Array(NPA), own: false};
{ const jm = new Map(), jc = COLS.p_job.pc; for (let i = 0; i < NPA; i++) { const k = pco[i] + ':' + jc[i] + ':' + pjd[i] + ':' + COLS.p_lob.pc[i]; let j = jm.get(k); if (j === undefined) { j = jm.size; jm.set(k, j); } pjob[i] = j; } var NJ = jm.size; }
const pjInc = new Float64Array(NJ), pjExp = new Float64Array(NJ), pjFirst = new Int32Array(NJ).fill(-1);
for (let i = 0; i < NP; i++) { const j = pjob[i]; pjInc[j] += pinc[i]; pjExp[j] += pexp[i]; if (pjFirst[j] < 0) pjFirst[j] = i; }
for (let t = 0; t < pdemoSrc.length; t++) if (pjFirst[pjob[NP + t]] < 0) pjFirst[pjob[NP + t]] = pdemoSrc[t];
let pdate = pjd, PMIN = 0, PMAX = 0;
function setPBasis(b) { pdate = pjd; PMIN = 1e9; PMAX = -1e9; for (let i = 0; i < NP; i++) if (pdate[i] > 0) { if (pdate[i] < PMIN) PMIN = pdate[i]; if (pdate[i] > PMAX) PMAX = pdate[i]; } }
setPBasis('job');
const PMAIN = ['p_lob', 'jobstatus', 'band', 'p_ic'], PEXTRA = ['p_job', 'p_mode', 'p_direction', 'p_kind'];

{ const lm = new Map(), names = [], codes = new Uint32Array(NA), oc = COLS.origin.c, dc = COLS.destination.c; for (let i = 0; i < NA; i++) { const key = oc[i] + ':' + dc[i]; let j = lm.get(key); if (j === undefined) { j = names.length; lm.set(key, j); names.push(COLS.origin.d[oc[i]] + ' → ' + COLS.destination.d[dc[i]]); } codes[i] = j; } const lpc = new Uint32Array(NPA), poc = COLS.origin.pc, pdc = COLS.destination.pc; for (let i = 0; i < NPA; i++) { const key = poc[i] + ':' + pdc[i]; let j = lm.get(key); if (j === undefined) { j = names.length; lm.set(key, j); names.push(COLS.origin.d[poc[i]] + ' → ' + COLS.destination.d[pdc[i]]); } lpc[i] = j; } COLS.lane = {l: 'Lane', d: names, c: codes, pc: lpc, own: true}; }
const MAIN = ['company', 'report', 'branch', 'customer', 'agent', 'x_salesperson', 'shipper', 'consignee', 'job_owner', 'carrier', 'origin', 'destination', 'x_tradelanename', 'x_dischargecountry', 'nomination', 'consol', 'cargo', 'status', 'stage'];
const EXTRA = Object.keys(COLS).filter((k) => (k.startsWith('x_') || k.startsWith('jp_')) && !MAIN.includes(k)).sort((a, b) => COLS[a].l.localeCompare(COLS[b].l));
let MINDATE = 1e9, MAXDATE = -1e9; for (let i = 0; i < N; i++) { if (date[i] < MINDATE) MINDATE = date[i]; if (date[i] > MAXDATE) MAXDATE = date[i]; }
const OPS_MIN = MINDATE, OPS_MAX = MAXDATE;
const STAGE_PEND = COLS.stage.d.indexOf('Pending ops lock'), STAGE_FIN = COLS.stage.d.indexOf('Financials open');

// ---------------------------------------------------------------- state
const S = {page: 's_owner', group: 'summary', rank: 'profit', pdemo: false, exp: null, jobs: {q: '', sort: 'profit', dir: -1}, pcust: {sort: 'profit', dir: -1}, pcmp: {unit: 'month', against: 'prev', basis: 'todate', anchor: null, custom: false, A: {from: null, to: null}, B: {from: null, to: null}, dim: 'branch', measure: 'profit', show: 'all', tsort: {sort: 'adelta', dir: -1}}, from: null, to: null, rel: null, sel: {}, extra: [], qm: new Set(), qd: new Set(), measure: 'count', compare: true,
  cust: {sort: 'cnt', dir: -1}, ship: {q: '', page: 0, sort: 'date', dir: -1}, wl: {q: '', stage: '', sort: 'age', dir: -1}, ch: null};
let R = {};
const DEFAULTS = {topN: 25, heatN: 15, tableRows: 50, pageSize: 100, wlRows: 300, oldDays: 90, buckets: '30,60,90,180', activeMin: 1, grain: 'auto', autoDays: 62, compare: 'prev', fyStart: 4, weekStart: 1, relEnd: 'data', yearBasis: 'fy', historyYears: 3, moneyUnit: 'auto', lapsedMonths: 2, declinePct: 30, rateMode: 'text', rateMax: 5000, unbilledDays: 30, ownerConc: 25, unassignedShare: 20, unassignedNames: 'Administrator', lowMargin: 10, costCoverage: 80, jobRows: 300, pBasis: 'job', flatPct: 1, varMinPct: 0, varMinBase: 0, varMinAbs: 0};
S.def = Object.assign({}, DEFAULTS);
try { const st = JSON.parse(localStorage.getItem('ngDefs') || '{}'); for (const k in DEFAULTS) if (st[k] !== undefined && typeof st[k] === typeof DEFAULTS[k]) S.def[k] = st[k]; } catch (e) { /* storage not available: defaults are used */ }
S.def.pBasis = 'job';
function saveDefs() { try { localStorage.setItem('ngDefs', JSON.stringify(S.def)); } catch (e) { /* ignore */ } srvPut('defs', S.def); }
function bucketList() { const u = [...new Set(String(S.def.buckets).split(',').map((x) => parseInt(x, 10)).filter((x) => x > 0))].sort((x, y) => x - y); return u.length ? u : [30, 60, 90, 180]; }
function cmpLabel() { const w=R.w; return 'current '+fRange({from:w.from,to:w.to})+' vs '+fRange({from:w.pfrom,to:w.pto})+(S.def.compare==='yoy'?' (year-on-year)':' ('+w.n+' days each)'); }
function grainOf(w) { const g = S.def.grain; return g === 'auto' ? (w.n > S.def.autoDays ? 'month' : 'day') : g; }
function asOfDay() { return S.def.relEnd === 'today' ? Math.floor(Date.now() / DMS) : MAXDATE; }
function dayClamped(y, m, d) { const last = new Date(Date.UTC(y, m + 1, 0)).getUTCDate(); return dayOf(y, m, Math.min(d, last)); }
function resolveRel(r) {
  const a = asOfDay();
  if (r.kind === 'month') return {from: pStart('month', a), to: a};
  if (r.kind === 'lastmonth') { const s0 = pStart('month', a); return {from: addMonths(s0, -1), to: s0 - 1}; }
  if (r.kind === 'ytd') return {from: pStart('year', a), to: a};
  if (r.kind === 'lastyear') { const s0 = pStart('year', a); return {from: addMonths(s0, -12), to: s0 - 1}; }
  if (r.kind === 'year') { const b = yearBounds(r.y); return {from: b.from, to: Math.max(b.from, Math.min(b.to, a))}; }
  const n = Math.max(1, r.n | 0), [y, m, d] = ymd(a);
  if (r.unit === 'weeks') return {from: a - 7 * n + 1, to: a};
  if (r.unit === 'months') return {from: dayClamped(y, m - n, d) + 1, to: a};
  if (r.unit === 'years') return {from: dayClamped(y - n, m, d) + 1, to: a};
  if (r.unit === 'cweeks') { const e = wkStart(a) - 1; return {from: e - 7 * n + 1, to: e}; }
  if (r.unit === 'cmonths') { const s0 = pStart('month', a); return {from: addMonths(s0, -n), to: s0 - 1}; }
  return {from: a - n + 1, to: a};
}
const FYB = () => S.def.yearBasis === 'fy' && S.def.fyStart !== 1;
const fyLabel = (y) => 'FY ' + y + '–' + String((y + 1) % 100).padStart(2, '0');
function yearBounds(y) { const fm = FYB() ? S.def.fyStart - 1 : 0, s0 = dayOf(y, fm, 1); return {from: s0, to: dayOf(y + 1, fm, 1) - 1}; }
function yearOfDay(d) { const [y, m] = ymd(d), fm = FYB() ? S.def.fyStart - 1 : 0; return m >= fm ? y : y - 1; }
const yearName = (y) => (FYB() ? fyLabel(y) : String(y));
function relLabel(r) {
  if (r.kind === 'month') return 'This month so far'; if (r.kind === 'lastmonth') return 'Last month'; if (r.kind === 'ytd') return FYB() ? 'Financial year to date' : 'Year to date';
  if (r.kind === 'lastyear') return FYB() ? 'Last financial year' : 'Last year'; if (r.kind === 'year') return yearName(r.y);
  const pl = {days: 'days', weeks: 'weeks', months: 'months', years: 'years', cweeks: 'complete weeks', cmonths: 'complete months'}[r.unit];
  return 'Last ' + (r.n === 1 ? pl.replace(/s$/, '') : r.n + ' ' + pl);
}
const wkStart = (d) => (S.def.weekStart === 0 ? d - ((d + 4) % 7) : d - ((d + 3) % 7));
const MENU = {key: null, q: ''};

function h(tag, props, ...kids) {
  const e = document.createElement(tag);
  if (props) for (const k in props) { const v = props[k];
    if (k === 'class') e.className = v; else if (k === 'style') e.style.cssText = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (v === true) e.setAttribute(k, ''); else if (v !== false && v != null) e.setAttribute(k, v); }
  for (const c of kids.flat(Infinity)) { if (c == null || c === false) continue; e.append(c.nodeType ? c : document.createTextNode(String(c))); }
  return e;
}
const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- filtering
function win() { let from, to; if (S.rel) { const r = resolveRel(S.rel); from = r.from; to = r.to; } else { from = S.from == null ? MINDATE : S.from; to = S.to == null ? MAXDATE : S.to; } const n = Math.max(1, to - from + 1); return S.def.compare === 'yoy' ? {from, to, n, pfrom: dayClamped(...ymd(from).map((v,i)=>i===0?v-1:v)), pto: dayClamped(...ymd(to).map((v,i)=>i===0?v-1:v))} : {from, to, n, pfrom: from - n, pto: from - 1}; }
function mask(opt) {
  opt = opt || {}; const skip = new Set([].concat(opt.skip || [])), NN = N, m = new Uint8Array(NA); m.fill(1, 0, NN);
  for (const k in S.sel) { if (skip.has(k) || !COLS[k].own) continue; const set = S.sel[k]; if (!set || !set.size) continue;
    const L = new Uint8Array(COLS[k].d.length); set.forEach((v) => { L[v] = 1; }); const c = COLS[k].c; for (let i = 0; i < NN; i++) if (!L[c[i]]) m[i] = 0; }
  if (opt.dates !== 'none') { const w = win(), lo = opt.dates === 'prev' ? w.pfrom : w.from, hi = opt.dates === 'prev' ? w.pto : w.to; for (let i = 0; i < NN; i++) if (date[i] < lo || date[i] > hi) m[i] = 0; }
  return m;
}
function syncBounds() { MINDATE = Math.min(OPS_MIN, PMIN); MAXDATE = Math.max(OPS_MAX, PMAX); }   // one date range for the whole dashboard, so switching views never changes it
function setGroup(g) { if (g === 'profit' && !FIN) return; S.group = g; S.page = g === 'ops' ? 'overview' : g === 'summary' ? 's_owner' : g === 'mine' ? 'v_mine' : 'p_overview'; syncBounds(); renderAll(); }
function compute() {
  syncBounds();
  if (S.group === 'summary' || S.group === 'mine') { const M = mask(), P = mask({dates: 'prev'}); let n = 0, np = 0; for (let i = 0; i < N; i++) { if (M[i]) n++; if (P[i]) np++; } recomputeJobsP(); const t = totalsP(maskP()), tp = totalsP(maskP({dates: 'prev'})); R = {w: win(), M, P, n, np, air: 0, sea: 0, mixed: false, useVol: false, t, tp}; return; }
  if (S.group === 'profit') { recomputeJobsP(); const M = maskP(), P = maskP({dates: 'prev'}), t = totalsP(M), tp = totalsP(P); R = {w: win(), M, P, t, tp, n: t.lines}; return; }
  const M = mask(), P = mask({dates: 'prev'}); let n = 0, air = 0, sea = 0, np = 0;
  for (let i = 0; i < N; i++) { if (M[i]) { n++; if (mode[i]) sea++; else air++; } if (P[i]) np++; }
  const mixed = air > 0 && sea > 0, useVol = S.measure === 'volume' && !mixed;
  R = {w: win(), M, P, n, np, air, sea, mixed, useVol};
}
const vi = (i) => (R.useVol ? VOL[i] : 1);
const fm = (x) => (R.useVol ? (R.air ? f1(x) + ' t' : fInt(Math.round(x)) + ' TEU') : fInt(x));
const pctChange = (a, b) => (Number.isFinite(a) && Number.isFinite(b) && b !== 0 ? (a - b) / Math.abs(b) : null);
const fDelta = (x) => (x == null ? '' : (x >= 0 ? '+' : '−') + fP1(Math.abs(x)));
function toggle(key, j) { if (key === 'report') { S.qm.clear(); S.qd.clear(); } const set = S.sel[key] || (S.sel[key] = new Set()); if (set.has(j)) set.delete(j); else set.add(j); if (!set.size) delete S.sel[key]; renderAll(); }
function setOnly(key, j) { if (key === 'report') { S.qm.clear(); S.qd.clear(); } S.sel[key] = new Set([j]); renderAll(); }

// ---------------------------------------------------------------- small components
function emptyNote() { return h('p', {class: 'empty'}, 'Nothing in this selection.'); }
function rankRows(items, total, onClick, ci) {
  if (!items.length) return emptyNote();
  const mx = Math.max(...items.map((d) => d.v), 1e-9);
  return h('div', {class: 'rank'}, items.map((d) => h('button', {type: 'button', class: 'row' + (d.sel ? ' on' : ''), onclick: () => onClick(d)},
    h('span', {class: 'lab', title: d.label}, d.label),
    h('span', {class: 'track'}, h('span', {class: 'fill', style: 'width:' + (d.v / mx * 100) + '%;background:' + (d.color || (window.CHART_COLORS || ['#4c78a8'])[ci || 0])})),
    h('span', {class: 'val'}, fm(d.v) + (total ? ' · ' + fS(d.v / total) : '')))));
}
const fS = (s) => (s >= 0.1 ? fP0(s) : fP1(s));
function rankedKey(key) {
  const limit = S.def.topN;
  const m = mask({skip: key}), c = COLS[key].c, a = new Float64Array(COLS[key].d.length); let tot = 0;
  for (let i = 0; i < N; i++) if (m[i]) { const v = vi(i); a[c[i]] += v; tot += v; }
  const sel = S.sel[key] || new Set(); let ids = []; for (let j = 0; j < a.length; j++) if (a[j] > 0 || sel.has(j)) ids.push(j);
  ids.sort((x, y) => a[y] - a[x]); const top = ids.slice(0, limit); sel.forEach((j) => { if (!top.includes(j)) top.push(j); });
  return h('div', null, rankRows(top.map((j) => ({k: j, label: COLS[key].d[j], v: a[j], sel: sel.has(j)})), tot, (d) => {const metric=R.useVol?(R.air?'ops.air_weight':'ops.teu'):'ops.shipments';toggle(key,d.k);window.MetricTrace?.openCategory(metric,key,d.k);}, CI[key] || 0),
    ids.length > top.length ? h('p', {class: 'more'}, 'Top ' + top.length + ' of ' + fInt(ids.length) + '. Use the ' + COLS[key].l + ' filter above to find others.') : null);
}
const CI = {customer: 0, branch: 1, carrier: 3, origin: 2, destination: 4, x_tradelanename: 5, x_dischargecountry: 6, shipper: 0, consignee: 1};
window.CHART_COLORS = ['#4c78a8', '#f58518', '#54a24b', '#b279a2', '#e45756', '#72b7b2', '#eeca3b', '#9d755d'];
// Explanations are attached to the shared renderers, not to individual pages,
// so newly added cards and KPIs also receive the reporting context.
function businessMeaning(label, note) {
  const name = String(label || '').trim();
  const lower = name.toLowerCase();
  const formula = /gross profit|\bgp\b/.test(lower)
    ? 'Gross profit = recorded income minus recorded expense for the selected jobs.'
    : /^(margin|profit margin|margin %)$/.test(lower) || /margin rate/.test(lower)
    ? 'Margin percentage = gross profit divided by income, multiplied by 100, where income is non-zero.'
    : /^(profit|actual profit)$/.test(lower)
    ? 'Profit = income minus booked expense across the selected job-summary records.'
    : /^(jobs)$/.test(lower)
    ? 'Number of jobs represented by the selected Job Profit Analysis Report records.'
    : /^(profit per job)$/.test(lower)
    ? 'Total profit divided by the number of selected jobs, when the job count is non-zero.'
    : /shipments|shipment count/.test(lower)
    ? 'Count of shipment records meeting the selected date, company, LOB and other filters.'
    : /teu/.test(lower)
    ? 'Sum of TEUs for selected sea shipment records.'
    : /chargeable weight/.test(lower)
    ? 'Sum of chargeable weight for selected air shipment records.'
    : /customer/.test(lower) && /active|distinct|unique/.test(lower)
    ? 'Count of distinct customers meeting the current filters and the configured activity threshold.'
    : /revenue|income|sales value/.test(lower)
    ? 'Sum of recorded income for the selected job-summary records.'
    : /cost|expense/.test(lower)
    ? 'Sum of recorded expenses for the selected job-summary records.'
    : /variance|change|growth|decline/.test(lower)
    ? 'Difference between the selected current and comparison periods; percentage change uses the previous value as the denominator when non-zero.'
    : '';
  // Financial imports are job-summary snapshots, not charge-level rows.
  // Never imply that a finance visual is sourced from charge-line data.
  const meaning = 'Shows ' + name.toLowerCase() + ' for the selected reporting scope.';
  const calculation = formula || (note ? 'This visual uses the source-data calculation described in its note. A metric-specific formula is not yet verified.' : 'Metric-specific formula not yet verified; refer to the displayed measure and source report before using this figure for decisions.');
  const reportingWindow = R && R.w ? R.w : null;
  return h('details', {class: 'business-explanation', style: 'margin-top:.55rem;font-size:.78rem'},
    h('summary', {style: 'cursor:pointer'}, 'Business meaning & calculation'),
    h('p', null, h('strong', null, 'What this means: '), meaning),
    h('p', null, h('strong', null, 'How it is calculated: '), calculation),
    reportingWindow ? h('p', {class: 'meta'}, 'Reporting dates: ' + fRange({from:reportingWindow.from,to:reportingWindow.to}) + (S.compare && reportingWindow.pfrom != null && reportingWindow.pto != null ? '; comparison: ' + fRange({from:reportingWindow.pfrom,to:reportingWindow.pto}) : '') + '. Filters apply.') : null);
}
function card(title, note, body, cls) { return h('article', {class: 'card ' + (cls || '')}, h('h2', {class: 'h'}, title), note ? h('p', {class: 'note'}, note) : null, body, businessMeaning(title, note)); }
function kpi(label, value, delta, note, tone, previousValue) {
  // Promoted ERP records are the reporting source of truth. A zero prior
  // value is a valid baseline, but a percentage cannot be calculated from it.
  const hasComparison = Boolean(S.compare);
  const hasPrevious = previousValue != null;
  const comparison = hasComparison
    ? (hasPrevious ? 'Current: ' + value + ' · Previous: ' + previousValue + ' · ' : '')
      + (delta == null ? (hasPrevious ? 'No percentage (zero or unavailable baseline)' : 'No comparable baseline') : fDelta(delta))
      + ' · ' + cmpLabel()
    : '';
  return h('div', {class: 'card kpi'}, h('div', {class: 'kl'}, label),
    h('div', {class: 'kv' + (tone ? ' ' + tone : '')}, value),
    hasComparison && (delta != null || hasPrevious)
      ? h('div', {class: 'delta ' + (delta != null && delta >= 0 ? 'ok' : delta != null ? 'bad' : '')}, comparison)
      : null,
    note ? h('div', {class: 'kn'}, note) : null,
    businessMeaning(label, note));
}
function activeCust(m) { const c = COLS.customer.c, a = new Uint32Array(COLS.customer.d.length); for (let i = 0; i < N; i++) if (m[i]) a[c[i]]++; let n = 0; for (let j = 0; j < a.length; j++) if (a[j] > 0 && a[j] >= S.def.activeMin) n++; return n; }
function sumWhere(m, f) { let s = 0; for (let i = 0; i < N; i++) if (m[i]) s += f(i); return s; }
function distinct(m, key) { const c = COLS[key].c, set = new Set(); for (let i = 0; i < N; i++) if (m[i]) set.add(c[i]); return set.size; }
function top10(m, useVol) { const c = COLS.customer.c, a = new Float64Array(COLS.customer.d.length); let t = 0; for (let i = 0; i < N; i++) if (m[i]) { const v = useVol ? VOL[i] : 1; a[c[i]] += v; t += v; }
  if (!t) return null; const s = Array.from(a).sort((x, y) => y - x); let u = 0; for (let k = 0; k < S.def.topN; k++) u += s[k] || 0; return u / t; }

// ---------------------------------------------------------------- trend chart
function trendChart() {
  const w = R.w, grain = grainOf(w), month = grain === 'month', M = R.M; const starts = [];
  if (month) d3.utcMonth.range(d3.utcMonth.floor(dDate(w.from)), dDate(w.to + 1)).forEach((d) => starts.push(Math.round(+d / DMS))); else if (grain === 'week') { for (let d = wkStart(w.from); d <= w.to; d += 7) starts.push(d); } else for (let d = w.from; d <= w.to; d++) starts.push(d);
  const idx = new Map(starts.map((s, i) => [s, i])), data = starts.map(() => [0, 0, 0, 0]);
  for (let i = 0; i < N; i++) if (M[i]) { const b = idx.get(month ? mStart[i] : grain === 'week' ? wkStart(date[i]) : date[i]); if (b !== undefined) data[b][rtype[i]] += vi(i); }
  const tot = data.map((a) => a[0] + a[1] + a[2] + a[3]), box = h('div', {class: 'trend'});
  if (!R.n) { box.append(emptyNote()); return box; }
  const W = Math.max(280, Math.round(($('page').clientWidth || 900) - 40)), H = 250, mt = 20, mb = 28;
  const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', '0 0 ' + W + ' ' + H).attr('role', 'img').attr('aria-label', 'Stacked bars by report over time');
  const ymax = d3.max(tot) || 1, y = d3.scaleLinear([0, ymax], [H - mb, mt]).nice(4), ticks = y.ticks(4), yf = y.domain()[1] >= 10 ? d3.format(',.0f') : d3.format(',.1f');
  const probe = svg.append('text').attr('class', 'tick').text(yf(d3.max(ticks))); const ml = Math.ceil(probe.node().getComputedTextLength()) + 12; probe.remove();
  const x = d3.scaleBand(starts, [ml, W - 8]).padding(0.25), bw = Math.min(x.bandwidth(), 40), off = (x.bandwidth() - bw) / 2;
  ticks.forEach((t) => { svg.append('line').attr('x1', ml).attr('x2', W - 8).attr('y1', y(t)).attr('y2', y(t)).style('stroke', 'var(--grid)'); svg.append('text').attr('class', 'tick').attr('x', ml - 6).attr('y', y(t)).attr('text-anchor', 'end').attr('dominant-baseline', 'middle').text(yf(t)); });
  const tip = h('div', {class: 'tip', hidden: true}); box.append(tip);
  starts.forEach((s, bi) => { let acc = 0;
    for (let r = 0; r < 4; r++) { const v = data[bi][r]; if (!v) continue; const y0 = y(acc + v), y1 = y(acc); acc += v;
      svg.append('rect').attr('x', x(s) + off).attr('y', y0).attr('width', bw).attr('height', Math.max(0, y1 - y0)).attr('fill', REPCOL[r]); }
    svg.append('rect').attr('class', 'hit').attr('x', x(s)).attr('y', mt).attr('width', x.bandwidth()).attr('height', H - mb - mt).attr('fill', 'transparent').style('cursor', 'pointer')
      .on('mousemove', (ev) => { const b = box.getBoundingClientRect(); tip.replaceChildren(h('div', {class: 'tip-h'}, month ? fMon(s) : (grain === 'week' ? 'Week of ' + fDay(s) : fDay(s))), h('div', null, 'Total: ' + fm(tot[bi])),
          ...[0, 1, 2, 3].filter((r) => data[bi][r]).map((r) => h('div', null, h('i', {class: 'sw', style: 'background:' + REPCOL[r]}), REPN[r] + ': ' + fm(data[bi][r])))); tip.hidden = false;
        const tw = tip.offsetWidth; let l = ev.clientX - b.left + 12; if (l + tw > b.width) l = ev.clientX - b.left - tw - 12; tip.style.left = Math.max(0, l) + 'px'; tip.style.top = Math.max(0, ev.clientY - b.top - 60) + 'px'; })
      .on('mouseleave', () => { tip.hidden = true; })
      .on('click', () => { if (month) { S.rel = null; S.from = Math.max(s, MINDATE); S.to = Math.min(Math.round(+d3.utcMonth.offset(dDate(s), 1) / DMS) - 1, MAXDATE); } else if (grain === 'week') { S.rel = null; S.from = Math.max(s, MINDATE); S.to = Math.min(s + 6, MAXDATE); } else { S.rel = null; S.from = s; S.to = s; } renderAll(); });
  });
  const step = Math.max(1, Math.ceil(56 / x.step()));
  starts.forEach((s, bi) => { if (bi % step === 0) svg.append('text').attr('class', 'tick').attr('x', x(s) + x.bandwidth() / 2).attr('y', H - 8).attr('text-anchor', 'middle').text(month ? d3.utcFormat('%b %y')(dDate(s)) : fDM(s)); });
  if (starts.length <= 14) starts.forEach((s, bi) => { if (tot[bi] > 0) svg.append('text').attr('class', 'lbl').attr('x', x(s) + x.bandwidth() / 2).attr('y', y(tot[bi]) - 5).attr('text-anchor', 'middle').text(yf(tot[bi])); });
  const present = [0, 1, 2, 3].filter((r) => data.some((a) => a[r] > 0));
  box.append(h('div', {class: 'legend'}, present.map((r) => h('button', {type: 'button', class: 'lg' + (S.sel.report && S.sel.report.has(r) ? ' on' : ''), onclick: () => toggle('report', r)}, h('i', {class: 'sw', style: 'background:' + REPCOL[r]}), REPN[r]))));
  return box;
}
function mixBlock(key, title) {
  const m = mask({skip: key}), c = COLS[key].c, a = new Float64Array(COLS[key].d.length); let t = 0; for (let i = 0; i < N; i++) if (m[i]) { a[c[i]]++; t++; }
  const ids = []; for (let j = 0; j < a.length; j++) if (a[j] > 0) ids.push(j); ids.sort((x, y) => a[y] - a[x]); const sel = S.sel[key] || new Set();
  return h('div', {class: 'mix'}, h('div', {class: 'mixh'}, title),
    h('div', {class: 'stack'}, ids.map((j, k) => h('span', {class: 'seg', style: 'width:' + (a[j] / t * 100) + '%;background:' + window.CHART_COLORS[k % 8]}))),
    h('div', {class: 'legend'}, ids.map((j, k) => h('button', {type: 'button', class: 'lg' + (sel.has(j) ? ' on' : ''), onclick: () => toggle(key, j)}, h('i', {class: 'sw', style: 'background:' + window.CHART_COLORS[k % 8]}), COLS[key].d[j] + ' ' + fS(a[j] / t)))));
}

// ---------------------------------------------------------------- pages
function pageOverview() {
  const kp = [];
  const dN = pctChange(R.n, R.np);
  kp.push(kpi('Shipments', fInt(R.n), S.compare ? dN : null, 'Dated within the selected range', '', fInt(R.np)));
  const sumAir = (m) => sumWhere(m, (i) => (mode[i] ? 0 : chg[i])), sumSea = (m) => sumWhere(m, (i) => (mode[i] ? teus[i] : 0));
  if (R.air) kp.push(kpi('Air chargeable weight (tonnes)', f1(sumAir(R.M)), S.compare ? pctChange(sumAir(R.M), sumAir(R.P)) : null, 'Air reports only', '', f1(sumAir(R.P))));
  if (R.sea) kp.push(kpi('Sea TEUs', fInt(Math.round(sumSea(R.M))), S.compare ? pctChange(sumSea(R.M), sumSea(R.P)) : null, 'TEUs recorded in ocean registers', '', fInt(Math.round(sumSea(R.P)))));
  kp.push(kpi('Active customers', fInt(activeCust(R.M)), S.compare ? pctChange(activeCust(R.M), activeCust(R.P)) : null, 'At least ' + S.def.activeMin + ' shipment' + (S.def.activeMin > 1 ? 's' : '') + ' in range', '', fInt(activeCust(R.P))));
  const t1 = top10(R.M, R.useVol), t0 = top10(R.P, R.useVol);
  kp.push(h('div', {class: 'card kpi'}, h('div', {class: 'kl'}, 'Top ' + S.def.topN + ' customers’ share'), h('div', {class: 'kv'}, t1 == null ? '—' : fP0(t1)),
    t1 != null && t0 != null && S.compare ? h('div', {class: 'delta flat'}, (t1 >= t0 ? '+' : '−') + f1(Math.abs(t1 - t0) * 100) + ' pts vs ' + cmpLabel()) : null,
    h('div', {class: 'kn'}, 'Share of ' + (R.useVol ? 'volume' : 'shipments') + '; higher means more concentrated'), businessMeaning('Top customer concentration', 'Top N customers divided by total selected shipments or volume')));
  const lanes = laneList();
  return h('div', null, h('div', {class: 'kpis'}, kp),
    h('div', {class: 'grid'},
      card('Trend', (R.useVol ? (R.air ? 'Chargeable weight (tonnes)' : 'TEUs') : 'Shipments') + ' per ' + grainOf(R.w) + ', stacked by report. Click a bar to zoom the date range; click a legend item to filter.', trendChart(), 'full'),
      card('Top ' + S.def.topN + ' customers', 'Click a customer to filter everything; click again to remove.', rankedKey('customer')),
      card('Top ' + S.def.topN + ' branches', 'Click a branch to filter everything.', rankedKey('branch')),
      card('Top ' + S.def.topN + ' lanes', 'Origin port to destination port. Click a lane to filter both ports.', lanes),
      card('Top ' + S.def.topN + ' airlines and shipping lines', 'Carrier on each shipment.', rankedKey('carrier')),
      card('Shipment mix', 'Share of shipments. Click an item to filter.', h('div', null, mixBlock('report', 'Report'), mixBlock('nomination', 'Nomination'), mixBlock('consol', 'Consol type'), mixBlock('cargo', 'Cargo type')))));
}
function laneAgg() {
  const m = mask({skip: ['origin', 'destination']}), o = COLS.origin.c, d = COLS.destination.c, c = COLS.carrier.c, map = new Map(); let tot = 0;
  for (let i = 0; i < N; i++) if (m[i]) { const k = o[i] * 1000 + d[i]; let e = map.get(k); if (!e) { e = {o: o[i], d: d[i], cnt: 0, v: 0, air: 0, sea: 0, car: new Set()}; map.set(k, e); } e.cnt++; const v = vi(i); e.v += v; tot += v; if (mode[i]) e.sea += teus[i]; else e.air += chg[i]; e.car.add(c[i]); }
  return {rows: [...map.values()], tot};
}
function laneSelected(e) { const so = S.sel.origin, sd = S.sel.destination; return !!(so && sd && so.size === 1 && sd.size === 1 && so.has(e.o) && sd.has(e.d)); }
function laneClick(e) { if (laneSelected(e)) { delete S.sel.origin; delete S.sel.destination; } else { S.sel.origin = new Set([e.o]); S.sel.destination = new Set([e.d]); } renderAll(); }
function laneList() {
  const limit = S.def.topN;
  const a = laneAgg(); a.rows.sort((x, y) => y.v - x.v); const items = a.rows.slice(0, limit).map((e) => ({k: e, label: COLS.origin.d[e.o] + ' → ' + COLS.destination.d[e.d], v: e.v, sel: laneSelected(e)}));
  return rankRows(items, a.tot, (d) => laneClick(d.k), 2);
}
function sortHead(cols, state, redraw) {
  return h('tr', null, cols.map((c) => h('th', {class: c.num ? 'n' : '', 'aria-sort': state.sort === c.k ? (state.dir > 0 ? 'ascending' : 'descending') : 'none'},
    c.sort === false ? c.t : h('button', {type: 'button', onclick: () => { state.dir = state.sort === c.k ? -state.dir : (c.num ? -1 : 1); state.sort = c.k; redraw(); }}, c.t + (state.sort === c.k ? (state.dir > 0 ? ' ▲' : ' ▼') : '')))));
}
function pageCustomers() {
  const key = 'customer', M2 = mask({skip: key}), P2 = mask({skip: key, dates: 'prev'}), c = COLS.customer.c, sz = COLS.customer.d.length;
  const cnt = new Float64Array(sz), pc = new Float64Array(sz), air = new Float64Array(sz), sea = new Float64Array(sz), last = new Int32Array(sz), vol = new Float64Array(sz); let totC = 0, totV = 0;
  for (let i = 0; i < N; i++) { if (M2[i]) { const j = c[i]; cnt[j]++; totC++; const v = vi(i); vol[j] += v; totV += v; if (mode[i]) sea[j] += teus[i]; else air[j] += chg[i]; if (date[i] > last[j]) last[j] = date[i]; } if (P2[i]) pc[c[i]]++; }
  const sel = S.sel[key] || new Set(), hasPrev = R.np > 0; const rows = []; for (let j = 0; j < sz; j++) if (cnt[j] > 0 || sel.has(j)) rows.push({j, cnt: cnt[j], air: air[j], sea: sea[j], share: totC ? cnt[j] / totC : 0, delta: hasPrev ? cnt[j] - pc[j] : 0, last: last[j], v: vol[j]});
  const exportCust = () => { const list = rows.slice().sort((a, b) => b.cnt - a.cnt), n = list.length + 1;
    downloadXlsx('customers_' + fIso(dDate(MAXDATE)) + '.xlsx', [{name: 'Customers', freeze: true, filter: true, cols: [42, 12, 18, 12, 18, 18, 16], rows: [['Customer', 'Shipments', 'Air chargeable weight (t)', 'Sea TEUs', 'Share of shipments', 'Change vs comparison (shipments)', 'Last shipment'].map(HDR)].concat(list.map((r, i) => [COLS.customer.d[r.j], {v: r.cnt, s: 3}, r.air ? {v: +r.air.toFixed(3), s: 4} : '', r.sea ? {v: Math.round(r.sea), s: 3} : '', {f: 'B' + (i + 2) + '/SUM(B$2:B$' + n + ')', s: 2}, hasPrev ? {v: r.delta, s: 3} : '', r.last > 0 ? {v: serial(r.last), s: 5} : '']))}, settingsSheet([[HDR('Range'), fDay(R.w.from) + ' to ' + fDay(R.w.to)]])]); };
  const tbody = h('tbody'), note = h('p', {class: 'note'});
  const cols = [{k: 'name', t: 'Customer'}, {k: 'cnt', t: 'Shipments', num: true}, {k: 'air', t: 'Air weight (t)', num: true}, {k: 'sea', t: 'Sea TEUs', num: true}, {k: 'share', t: 'Share', num: true}, {k: 'delta', t: 'Change vs previous', num: true}, {k: 'last', t: 'Last shipment', num: true}];
  const thead = h('thead'); const draw = () => {
    const s = S.cust, f = s.sort === 'name' ? (a, b) => COLS.customer.d[a.j].localeCompare(COLS.customer.d[b.j]) : (a, b) => a[s.sort] - b[s.sort]; rows.sort((a, b) => f(a, b) * s.dir);
    thead.replaceChildren(sortHead(cols, s, draw)); const shown = rows.slice(0, S.def.tableRows);
    tbody.replaceChildren(...shown.map((r) => h('tr', {class: 'click' + (sel.has(r.j) ? ' on' : ''), onclick: () => toggle(key, r.j)}, h('td', null, COLS.customer.d[r.j]), h('td', {class: 'n'}, fInt(r.cnt)), h('td', {class: 'n'}, r.air ? f1(r.air) : '–'), h('td', {class: 'n'}, r.sea ? fInt(Math.round(r.sea)) : '–'),
      h('td', {class: 'n'}, fS(r.share)), h('td', {class: 'n ' + (r.delta > 0 ? 'ok' : r.delta < 0 ? 'bad' : '')}, hasPrev ? (r.delta > 0 ? '+' : r.delta < 0 ? '−' : '') + fInt(Math.abs(r.delta)) : '–'), h('td', {class: 'n'}, r.last > 0 ? fDay(r.last) : '–'))));
    note.textContent = 'Showing ' + shown.length + ' of ' + fInt(rows.length) + ' customers. Click a header to sort, a row to filter. ' + (hasPrev ? 'Change = shipments minus the ' + cmpLabel() + '.' : 'No earlier period exists before this date range, so there is no change to show.'); };
  draw();
  // heatmap
  const topIds = rows.slice().sort((a, b) => b.v - a.v).slice(0, S.def.heatN).map((r) => r.j), months = d3.utcMonth.range(d3.utcMonth.floor(dDate(R.w.from)), dDate(R.w.to + 1)).map((d) => Math.round(+d / DMS)), mi = new Map(months.map((s, i) => [s, i]));
  const hm = new Map(topIds.map((j) => [j, new Float64Array(months.length)])); let hmax = 0;
  for (let i = 0; i < N; i++) if (M2[i]) { const a = hm.get(c[i]); if (a) { const b = mi.get(mStart[i]); if (b !== undefined) { a[b] += vi(i); if (a[b] > hmax) hmax = a[b]; } } }
  const heat = h('div', {class: 'scroll'}, h('table', {class: 'tbl heat'}, h('thead', null, h('tr', null, h('th', null, 'Customer'), months.map((s) => h('th', {class: 'n'}, d3.utcFormat('%b %y')(dDate(s)))))),
    h('tbody', null, topIds.map((j) => h('tr', null, h('td', {class: 'lab2'}, h('button', {type: 'button', class: 'link', onclick: () => toggle(key, j)}, COLS.customer.d[j])),
      [...hm.get(j)].map((v, bi) => h('td', {class: 'n hc', title: COLS.customer.d[j] + ' · ' + d3.utcFormat('%b %Y')(dDate(months[bi])) + ': ' + fm(v), style: v ? 'background:rgba(76,120,168,' + (0.12 + 0.75 * v / hmax) + ');color:' + (v / hmax > 0.55 ? '#fff' : 'inherit') : '', onclick: () => { S.sel.customer = new Set([j]); S.rel = null; S.from = Math.max(months[bi], MINDATE); S.to = Math.min(Math.round(+d3.utcMonth.offset(dDate(months[bi]), 1) / DMS) - 1, MAXDATE); renderAll(); }}, v ? (R.useVol ? (R.air ? f1(v) : fInt(Math.round(v))) : fInt(v)) : '')))))));
  const mov = hasPrev ? rows.filter((r) => r.delta !== 0) : [], gain = mov.filter((r) => r.delta > 0).sort((a, b) => b.delta - a.delta).slice(0, S.def.topN), lose = mov.filter((r) => r.delta < 0).sort((a, b) => a.delta - b.delta).slice(0, S.def.topN);
  const moverList = (arr, sign) => arr.length ? h('div', {class: 'rank'}, arr.map((r) => h('button', {type: 'button', class: 'row', onclick: () => toggle(key, r.j)}, h('span', {class: 'lab', title: COLS.customer.d[r.j]}, COLS.customer.d[r.j]), h('span', {class: 'track'}, h('span', {class: 'fill', style: 'width:' + Math.min(100, Math.abs(r.delta) / Math.abs(arr[0].delta) * 100) + '%;background:var(--' + (sign > 0 ? 'ok' : 'bad') + ')'})), h('span', {class: 'val'}, (sign > 0 ? '+' : '−') + fInt(Math.abs(r.delta)) + ' shipments')))) : (hasPrev ? emptyNote() : h('p', {class: 'empty'}, 'No earlier period to compare with. Choose a shorter date range, for example the last 30 days.'));
  return h('div', null, h('div', {class: 'grid'},
    card('Customers', null, h('div', null, h('div', {class: 'frow'}, dlButton('Download Excel', exportCust)), note, h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, thead, tbody))), 'full'),
    card('Customer by month', 'Top ' + S.def.heatN + ' customers by ' + (R.useVol ? 'volume' : 'shipments') + '. Click a cell to focus that customer and month.', heat, 'full'),
    card('Growing accounts', 'Biggest increase in shipments against the ' + cmpLabel() + '.', moverList(gain, 1)),
    card('Declining accounts', 'Biggest fall in shipments against the ' + cmpLabel() + '.', moverList(lose, -1))));
}
function pageLanes() {
  const a = laneAgg(); a.rows.sort((x, y) => y.cnt - x.cnt); const shown = a.rows.slice(0, S.def.tableRows);
  const exportLanes = () => { const list = a.rows.slice().sort((x, y) => y.cnt - x.cnt);
    downloadXlsx('lanes_' + fIso(dDate(MAXDATE)) + '.xlsx', [{name: 'Lanes', freeze: true, filter: true, cols: [46, 12, 18, 12, 12], rows: [['Lane', 'Shipments', 'Air chargeable weight (t)', 'Sea TEUs', 'Carriers'].map(HDR)].concat(list.map((e) => [COLS.origin.d[e.o] + ' → ' + COLS.destination.d[e.d], {v: e.cnt, s: 3}, e.air ? {v: +e.air.toFixed(3), s: 4} : '', e.sea ? {v: Math.round(e.sea), s: 3} : '', {v: e.car.size, s: 3}]))}, settingsSheet([[HDR('Range'), fDay(R.w.from) + ' to ' + fDay(R.w.to)]])]); };
  const tbl = h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, h('thead', null, h('tr', null, h('th', null, 'Lane'), h('th', {class: 'n'}, 'Shipments'), h('th', {class: 'n'}, 'Air weight (t)'), h('th', {class: 'n'}, 'Sea TEUs'), h('th', {class: 'n'}, 'Carriers'))),
    h('tbody', null, shown.map((e) => h('tr', {class: 'click' + (laneSelected(e) ? ' on' : ''), onclick: () => laneClick(e)}, h('td', null, COLS.origin.d[e.o] + ' → ' + COLS.destination.d[e.d]), h('td', {class: 'n'}, fInt(e.cnt)), h('td', {class: 'n'}, e.air ? f1(e.air) : '–'), h('td', {class: 'n'}, e.sea ? fInt(Math.round(e.sea)) : '–'), h('td', {class: 'n'}, fInt(e.car.size)))))));
  return h('div', {class: 'grid'}, card('Lanes', 'Top ' + shown.length + ' of ' + fInt(a.rows.length) + ' lanes by shipments. Click a row to filter both ports.', h('div', null, h('div', {class: 'frow'}, dlButton('Download Excel', exportLanes)), tbl), 'full'),
    card('Top ' + S.def.topN + ' origin ports', null, rankedKey('origin')), card('Top ' + S.def.topN + ' destination ports', null, rankedKey('destination')),
    card('Top ' + S.def.topN + ' airlines and shipping lines', null, rankedKey('carrier')), card('Top ' + S.def.topN + ' trade lanes', 'From the ERP’s Trade Lane Name column.', rankedKey('x_tradelanename')),
    card('Top ' + S.def.topN + ' destination countries', null, rankedKey('x_dischargecountry')), card('Top ' + S.def.topN + ' origin agents', null, rankedKey('x_originagent')));
}
function pageOps() {
  const M = mask({dates: 'none'}), st = COLS.stage.c, open = [];
  for (let i = 0; i < N; i++) if (M[i] && st[i] !== COLS.stage.d.indexOf('Closed')) open.push(i);
  const age = (i) => MAXDATE - date[i], pend = open.filter((i) => st[i] === STAGE_PEND).length, fin = open.filter((i) => st[i] === STAGE_FIN).length, old = open.filter((i) => age(i) > S.def.oldDays).length, oldest = open.reduce((m, i) => Math.max(m, age(i)), 0);
  const bl = bucketList(), buckets = []; { let lo = 0; bl.forEach((b) => { buckets.push([lo, b, lo + '–' + b + ' days']); lo = b + 1; }); buckets.push([lo, 1e9, 'Over ' + bl[bl.length - 1] + ' days']); }
  const bd = buckets.map(([lo, hi, l]) => { let p = 0, f = 0; open.forEach((i) => { const a = age(i); if (a >= lo && a <= hi) { if (st[i] === STAGE_PEND) p++; else f++; } }); return {l, p, f}; });
  const bmax = Math.max(...bd.map((d) => d.p + d.f), 1);
  const aging = h('div', null, bd.map((d) => h('div', {class: 'arow'}, h('span', {class: 'lab'}, d.l), h('span', {class: 'track'}, h('span', {class: 'aw', style: 'width:' + ((d.p + d.f) / bmax * 100) + '%'}, d.f ? h('span', {style: 'flex:' + d.f + ' 1 0;background:' + REPCOL[0]}) : null, d.p ? h('span', {style: 'flex:' + d.p + ' 1 0;background:' + REPCOL[1]}) : null)), h('span', {class: 'val'}, fInt(d.p + d.f)))),
    h('div', {class: 'legend'}, h('span', {class: 'lg static'}, h('i', {class: 'sw', style: 'background:' + REPCOL[0]}), 'Financials open'), h('span', {class: 'lg static'}, h('i', {class: 'sw', style: 'background:' + REPCOL[1]}), 'Waiting for ops lock')));
  // owners
  const oc = COLS.job_owner.c, om = new Map(); open.forEach((i) => { let e = om.get(oc[i]); if (!e) { e = {j: oc[i], p: 0, f: 0, o: 0}; om.set(oc[i], e); } if (st[i] === STAGE_PEND) e.p++; else e.f++; e.o = Math.max(e.o, age(i)); });
  const owners = [...om.values()].sort((a, b) => (b.p + b.f) - (a.p + a.f)).slice(0, S.def.tableRows), osel = S.sel.job_owner || new Set(), omax = Math.max(...owners.map((e) => e.p + e.f), 1);
  const otbl = h('div', {class: 'scroll'}, h('table', {class: 'tbl'}, h('thead', null, h('tr', null, h('th', null, 'Job owner'), h('th', null, 'Open'), h('th', {class: 'n'}, 'Ops lock'), h('th', {class: 'n'}, 'Financials'), h('th', {class: 'n'}, 'Oldest (days)'))),
    h('tbody', null, owners.map((e) => h('tr', {class: 'click' + (osel.has(e.j) ? ' on' : ''), onclick: () => toggle('job_owner', e.j)}, h('td', null, COLS.job_owner.d[e.j]), h('td', null, h('div', {class: 'ob'}, h('span', {class: 'track'}, h('span', {class: 'fill', style: 'width:' + ((e.p + e.f) / omax * 100) + '%;background:' + REPCOL[0]})), h('span', {class: 'val'}, fInt(e.p + e.f)))), h('td', {class: 'n'}, fInt(e.p)), h('td', {class: 'n'}, fInt(e.f)), h('td', {class: 'n'}, fInt(e.o)))))));
  // worklist
  const q = h('input', {type: 'search', class: 'q', placeholder: 'Search shipment, customer, owner…', 'aria-label': 'Search worklist', value: S.wl.q}), note = h('p', {class: 'note'}), tbody = h('tbody'), thead = h('thead');
  const stBtn = (v, t) => h('button', {type: 'button', class: 'btn' + (S.wl.stage === v ? ' on' : ''), onclick: () => { S.wl.stage = v; renderPage(); }}, t);
  const cols = [{k: 'rep', t: 'Report'}, {k: 'no', t: 'Shipment'}, {k: 'date', t: 'Date'}, {k: 'cust', t: 'Customer'}, {k: 'owner', t: 'Job owner'}, {k: 'branch', t: 'Branch'}, {k: 'stage', t: 'Stage'}, {k: 'status', t: 'Status'}, {k: 'age', t: 'Age (days)', num: true}];
  const KEY = {rep: (i) => rep[i], no: (i) => D.no[i], date: (i) => date[i], cust: (i) => COLS.customer.d[COLS.customer.c[i]], owner: (i) => COLS.job_owner.d[COLS.job_owner.c[i]], branch: (i) => COLS.branch.d[COLS.branch.c[i]], stage: (i) => st[i], status: (i) => COLS.status.d[COLS.status.c[i]], age: (i) => -date[i]};
  let lastWl = [];
  const exportWl = () => downloadXlsx('open_shipments_' + fIso(dDate(MAXDATE)) + '.xlsx', [{name: 'Open shipments', freeze: true, filter: true, cols: [24, 20, 14, 40, 22, 16, 22, 28, 12], rows: [['Report', 'Shipment', 'Date', 'Customer', 'Job owner', 'Branch', 'Stage', 'Status', 'Age (days)'].map(HDR)].concat(lastWl.map((i, k) => [COMP[comp[i]] + ' · ' + REPN[rtype[i]], D.no[i], {v: serial(date[i]), s: 5}, catv('customer', i), catv('job_owner', i), catv('branch', i), st[i] === STAGE_PEND ? 'Waiting for ops lock' : 'Financials open', catv('status', i), {f: 'Settings!$B$1-C' + (k + 2), s: 3}]))}, settingsSheet()]);
  const draw = () => { const s = S.wl, needle = s.q.trim().toLowerCase(); let rows = open.filter((i) => (!s.stage || COLS.stage.d[st[i]] === s.stage) && (!needle || (D.no[i] + ' ' + KEY.cust(i) + ' ' + KEY.owner(i) + ' ' + KEY.branch(i) + ' ' + KEY.status(i)).toLowerCase().includes(needle)));
    const kf = KEY[s.sort]; rows.sort((a, b) => { const x = kf(a), y = kf(b); return (typeof x === 'number' ? x - y : String(x).localeCompare(String(y))) * s.dir; });
    lastWl = rows; thead.replaceChildren(sortHead(cols, s, draw)); const shown = rows.slice(0, S.def.wlRows);
    tbody.replaceChildren(...shown.map((i) => h('tr', null, h('td', null, COMP[comp[i]].split(' ')[0] + ' · ' + REPN[rtype[i]]), h('td', null, D.no[i]), h('td', null, fDay(date[i])), h('td', null, KEY.cust(i)), h('td', null, KEY.owner(i)), h('td', null, KEY.branch(i)),
      h('td', null, h('span', {class: 'pill' + (st[i] === STAGE_PEND ? ' warn' : '')}, st[i] === STAGE_PEND ? 'Waiting for ops lock' : 'Financials open')), h('td', null, KEY.status(i)), h('td', {class: 'n'}, fInt(age(i))))));
    note.textContent = 'Showing ' + shown.length + ' of ' + fInt(rows.length) + ' open shipments' + (needle ? ' matching the search' : '') + '. Oldest first by default; click a header to sort.'; };
  q.addEventListener('input', () => { S.wl.q = q.value; draw(); }); draw();
  return h('div', null, h('p', {class: 'take'}, fInt(pend) + ' shipments still wait for an operations lock and ' + fInt(fin) + ' have operations locked but financials open; ' + fInt(old) + ' of these ' + fInt(pend + fin) + ' are more than ' + S.def.oldDays + ' days old.'),
    h('p', {class: 'meta'}, 'An open shipment has a blank operations lock or financials lock in the register. This page ignores the date range and follows every other filter. Age counts days from the shipment date to ' + fDay(MAXDATE) + '.'),
    h('div', {class: 'kpis'}, kpi('Waiting for operations lock', fInt(pend), null, 'Operations not locked yet'), kpi('Operations locked, financials open', fInt(fin), null, 'Financials not locked yet'), kpi('Open more than ' + S.def.oldDays + ' days', fInt(old), null, 'Either stage, from shipment date'), kpi('Oldest open shipment (days)', fInt(oldest), null, 'Days since shipment date'), kpi('Days from ops lock to financial lock', opsFacts(M).lag == null ? '–' : opsFacts(M).lag.toFixed(1), null, 'Average, where both are recorded')),
    h('div', {class: 'grid'}, card('How long shipments have been open', 'Open shipments by days since shipment date.', aging), card('Open shipments by job owner', 'Click an owner to filter everything below.', otbl),
      card('Worklist', null, h('div', null, h('div', {class: 'frow'}, q, h('div', {class: 'segs'}, stBtn('', 'All open'), stBtn('Pending ops lock', 'Waiting for ops lock'), stBtn('Financials open', 'Financials open')), dlButton('Download Excel', exportWl)), note, h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, thead, tbody))), 'full')));
}
const SHIP_COLS = [{k: 'rep', t: 'Report'}, {k: 'no', t: 'Shipment'}, {k: 'date', t: 'Date'}, {k: 'branch', t: 'Branch'}, {k: 'customer', t: 'Customer'}, {k: 'shipper', t: 'Shipper'}, {k: 'consignee', t: 'Consignee'}, {k: 'carrier', t: 'Carrier'}, {k: 'lane', t: 'Lane'}, {k: 'status', t: 'Status'}, {k: 'stage', t: 'Stage'}, {k: 'vol', t: 'Weight / TEU', num: true}];
const catv = (key, i) => COLS[key].d[COLS[key].c[i]];
function volText(i) { return mode[i] ? (teus[i] ? fInt(Math.round(teus[i])) + ' TEU' : (cbm[i] ? f1(cbm[i]) + ' CBM' : '–')) : (chg[i] ? f1(chg[i]) + ' t' : '–'); }
function shipTable(M) {
  const extra = EXTRA, head = ['Company', 'Report', 'Shipment No', 'Shipment Date', 'Branch', 'Customer', 'Shipper', 'Consignee', 'Job owner', 'Airline / shipping line', 'Origin port', 'Destination port', 'Status', 'Stage', 'Gross weight (t)', 'Chargeable weight (t)', 'TEUs', 'Volume (CBM)', 'Nomination', 'Consol type', 'Cargo type', 'Operations locked on', 'Financials locked on'].concat(extra.map((k) => COLS[k].l)), rows = [];
  for (let i = 0; i < N; i++) if (M[i]) rows.push([COMP[comp[i]], REPN[rtype[i]], D.no[i], fIso(dDate(date[i])), catv('branch', i), catv('customer', i), catv('shipper', i), catv('consignee', i), catv('job_owner', i), catv('carrier', i), catv('origin', i), catv('destination', i), catv('status', i), catv('stage', i), gross[i], chg[i], teus[i], cbm[i], catv('nomination', i), catv('consol', i), catv('cargo', i), opsD[i] > 0 ? fIso(dDate(opsD[i])) : '', finD[i] > 0 ? fIso(dDate(finD[i])) : ''].concat(extra.map((k) => catv(k, i))));
  return {head, rows};
}
function csvOf(M) {
  const t = shipTable(M), esc = (v) => { const raw=v;v = String(v == null ? '' : v);if(typeof raw==='string'&&/^[\s]*[=+@-]|^[\t\r]/.test(v))v="'"+v; return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
  return [t.head].concat(t.rows).map((r) => r.map(esc).join(',')).join('\n');
}
function pageShip() {
  const M = R.M, idx = []; for (let i = 0; i < N; i++) if (M[i]) idx.push(i);
  const S2 = S.ship, q = h('input', {type: 'search', class: 'q', placeholder: 'Search shipment, customer, shipper, consignee…', 'aria-label': 'Search shipments', value: S2.q}), note = h('p', {class: 'note'}), tbody = h('tbody'), thead = h('thead'), pager = h('div', {class: 'frow'});
  const KEY = {rep: (i) => rep[i], no: (i) => D.no[i], date: (i) => date[i], branch: (i) => catv('branch', i), customer: (i) => catv('customer', i), shipper: (i) => catv('shipper', i), consignee: (i) => catv('consignee', i), carrier: (i) => catv('carrier', i), lane: (i) => catv('origin', i) + catv('destination', i), status: (i) => catv('status', i), stage: (i) => catv('stage', i), vol: (i) => VOL[i]};
  const draw = () => { const needle = S2.q.trim().toLowerCase(); let rows = needle ? idx.filter((i) => (D.no[i] + ' ' + catv('customer', i) + ' ' + catv('shipper', i) + ' ' + catv('consignee', i)).toLowerCase().includes(needle)) : idx.slice();
    const kf = KEY[S2.sort]; rows.sort((a, b) => { const x = kf(a), y = kf(b); return (typeof x === 'number' ? x - y : String(x).localeCompare(String(y))) * S2.dir; });
    const pages = Math.max(1, Math.ceil(rows.length / S.def.pageSize)); S2.page = Math.min(S2.page, pages - 1); const shown = rows.slice(S2.page * S.def.pageSize, (S2.page + 1) * S.def.pageSize);
    thead.replaceChildren(sortHead(SHIP_COLS, S2, draw));
    tbody.replaceChildren(...shown.map((i) => h('tr', null, h('td', null, COMP[comp[i]].split(' ')[0] + ' · ' + REPN[rtype[i]]), h('td', null, D.no[i]), h('td', null, fDay(date[i])), h('td', null, catv('branch', i)), h('td', null, catv('customer', i)), h('td', null, catv('shipper', i)), h('td', null, catv('consignee', i)), h('td', null, catv('carrier', i)),
      h('td', null, catv('origin', i) + ' → ' + catv('destination', i)), h('td', null, catv('status', i)), h('td', null, catv('stage', i)), h('td', {class: 'n'}, volText(i)))));
    note.textContent = fInt(rows.length) + ' shipments' + (needle ? ' match the search' : ' in the current selection') + '. Page ' + (S2.page + 1) + ' of ' + pages + '.';
    pager.replaceChildren(h('button', {type: 'button', class: 'btn', disabled: S2.page === 0, onclick: () => { S2.page--; draw(); }}, 'Previous'), h('button', {type: 'button', class: 'btn', disabled: S2.page >= pages - 1, onclick: () => { S2.page++; draw(); }}, 'Next')); };
  q.addEventListener('input', () => { S2.q = q.value; S2.page = 0; draw(); }); draw();
  const dl = h('button', {type: 'button', class: 'btn on', onclick: () => { const blob = new Blob(['\ufeff' + csvOf(M)], {type: 'text/csv'}), a = h('a', {href: URL.createObjectURL(blob), download: 'shipments_' + fIso(dDate(MAXDATE)) + '.csv'}); document.body.append(a); a.click(); a.remove(); }}, 'Download CSV (' + fInt(idx.length) + ' rows, all columns)'), dx = dlButton('Download Excel (' + fInt(idx.length) + ' rows)', () => { const t = shipTable(M), isD = new Set([3, 21, 22]); downloadXlsx('shipments_' + fIso(dDate(MAXDATE)) + '.xlsx', [{name: 'Shipments', freeze: true, filter: true, cols: t.head.map((x, k) => (k === 5 || k === 6 || k === 7 ? 30 : 16)), rows: [t.head.map(HDR)].concat(t.rows.map((r) => r.map((v, k) => (isD.has(k) && v ? {v: serial(isoD(v)), s: 5} : (typeof v === 'number' ? v : v))))) }, settingsSheet()]); });
  return h('div', {class: 'grid'}, card('Shipments', 'Every shipment in the current selection. The CSV carries all filtered rows with the extra columns, and opens in Excel.', h('div', null, h('div', {class: 'frow'}, q, dx, dl), note, h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, thead, tbody)), pager), 'full'));
}
function pageChanges() {
  if (D.storage_mode === 'replace') return card('Daily report replacement', 'The latest data is kept for each reporting period.', h('p', {class: 'empty'}, 'Daily reports update the dates and branches they cover. Other periods stay available. Earlier versions of changed or removed records are not retained, so a before-and-after comparison is unavailable.'), 'full');
  const avail = Object.keys(D.changes).map(Number);
  if (!avail.length) return card('Changes since the last report', 'What each new load added, changed or removed.', h('p', {class: 'empty'}, 'Nothing to compare yet. A report needs to have been loaded at least twice; after the next daily load this page lists the new, changed and no-longer-present shipments.'), 'full');
  if (S.ch == null || !avail.includes(S.ch)) S.ch = avail[0]; const c = D.changes[String(S.ch)], m = D.meta[S.ch];
  const sel = h('div', {class: 'segs'}, avail.map((r) => h('button', {type: 'button', class: 'btn' + (S.ch === r ? ' on' : ''), onclick: () => { S.ch = r; renderPage(); }}, COMP[r < 4 ? 0 : 1] + ' · ' + REPN[r % 4])));
  const tb = (rows, cols) => rows.length ? h('div', {class: 'scroll'}, h('table', {class: 'tbl'}, h('thead', null, h('tr', null, cols.map((t) => h('th', null, t)))), h('tbody', null, rows))) : h('p', {class: 'empty'}, 'None.');
  const brief = (b) => [h('td', null, b[0]), h('td', null, b[1]), h('td', null, b[2]), h('td', null, b[3]), h('td', null, b[4])];
  return h('div', null, h('p', {class: 'meta'}, 'Compares the last two runs received of one report. Records are matched on shipment number plus date. A record missing from the newer run is “no longer present”, never “completed”. This page ignores the filters. In this review file the two runs are the two files received; the live system compares any two dates.'),
    h('div', {class: 'frow'}, sel), h('div', {class: 'kpis'}, kpi('Rows in earlier run', fInt(c.old_rows)), kpi('Rows in latest run', fInt(c.new_rows)), kpi('New shipments', fInt(c.new.length)), kpi('Changed shipments', fInt(c.changed.length)), kpi('No longer present', fInt(c.gone.length))),
    h('div', {class: 'grid'}, card('New shipments', null, tb(c.new.map((b) => h('tr', null, brief(b))), ['Shipment', 'Date', 'Customer', 'Branch', 'Status']), 'full'),
      card('Changed shipments', 'Each row shows the columns that changed, from earlier value to later value.', tb(c.changed.map(([b, ds]) => h('tr', null, brief(b), h('td', {class: 'chg'}, ds.slice(0, 5).map((d) => h('div', null, h('b', null, d[0] + ': '), (d[1] || '(blank)') + ' → ' + (d[2] || '(blank)'))), ds.length > 5 ? h('div', {class: 'more'}, '+' + (ds.length - 5) + ' more columns') : null))), ['Shipment', 'Date', 'Customer', 'Branch', 'Status', 'What changed']), 'full'),
      card('No longer present', null, tb(c.gone.map((b) => h('tr', null, brief(b))), ['Shipment', 'Date', 'Customer', 'Branch', 'Status']), 'full')));
}
function coverageCard() {
  const a = asOfDay(), Y = yearOfDay(a), hy = S.def.historyYears, years = []; for (let y = Y - hy + 1; y <= Y; y++) years.push(y);
  const cnt = new Map(); for (let i = 0; i < N; i++) { const k = rep[i] * 10000 + yearOfDay(date[i]); cnt.set(k, (cnt.get(k) || 0) + 1); }
  const warns = [], rows = D.meta.map((m, i) => {
    const expired = a > isoD(m.range_to);
    if (expired) warns.push(COMP[i < 4 ? 0 : 1] + ' ' + REPN[i % 4] + ' ends ' + fDay(isoD(m.range_to)));
    return h('tr', null, h('td', null, COMP[i < 4 ? 0 : 1]), h('td', null, REPN[i % 4]), years.map((y) => { const n = cnt.get(i * 10000 + y) || 0; return h('td', {class: 'n ' + (n ? '' : 'bad')}, n ? fInt(n) : 'missing'); }), h('td', {class: expired ? 'bad' : ''}, fDay(isoD(m.range_to)) + (expired ? ' (passed)' : '')));
  });
  return card('History by year', 'Years expected: ' + yearName(years[0]) + ' to ' + yearName(Y) + ', which is this ' + (FYB() ? 'financial year' : 'year') + ' and ' + (hy - 1) + ' before it. The window moves by itself each January, and an admin sets how many years to keep. A year shows “missing” until its reports are loaded.',
    h('div', null, warns.length ? h('p', {class: 'meta', style: 'color:var(--warn)'}, 'The ERP date range has run out for: ' + warns.join('; ') + '. Change the schedule’s date range in the ERP so new shipments keep arriving.') : null,
      h('div', {class: 'scroll'}, h('table', {class: 'tbl'}, h('thead', null, h('tr', null, ['Company', 'Report'].concat(years.map(yearName), ['ERP report covers up to']).map((t, k) => h('th', {class: k >= 2 && k < 2 + years.length ? 'n' : ''}, t)))), h('tbody', null, rows)))), 'full');
}
function pageStatus() {
  const rows = D.meta.map((m, i) => h('tr', null, h('td', null, COMP[m.co === 'NG' ? 0 : 1]), h('td', null, REPN[i % 4]), h('td', {class: 'n'}, fInt(m.rows)), h('td', null, m.from + ' to ' + m.to), h('td', {class: 'n'}, fInt(m.repeated)), h('td', {class: 'n'}, fInt(m.pend)), h('td', {class: 'n'}, fInt(m.finopen)), h('td', {class: 'n'}, m.runs), h('td', null, h('span', {class: 'pill ok'}, 'Current'))));
  return h('div', {class: 'grid'}, coverageCard(), card('Data status', 'What each report contains in this review file. In the live system this shows the last successful import time and any import errors per report.', h('div', {class: 'scroll'}, h('table', {class: 'tbl'},
    h('thead', null, h('tr', null, ['Company', 'Report', 'Rows', 'Shipment dates', 'Repeated numbers', 'Waiting ops lock', 'Financials open', 'Runs loaded', 'Status'].map((t, i) => h('th', {class: i > 1 && (i < 4 || i > 6) && i !== 3 && i !== 8 ? 'n' : ''}, t)))), h('tbody', null, rows))), 'full'),
    card('How the data is read', null, h('ul', {class: 'notes'},
      h('li', null, 'A shipment is identified by Shipment No plus Shipment Date together. Some shipment numbers were used twice in the ERP; both shipments are counted.'),
      h('li', null, 'Air volume is chargeable weight in tonnes. Sea volume is the TEUs recorded in the ocean registers, including any other cargo types where the source records TEUs. Air and sea are never added together.'),
      h('li', null, '“Financials open” means the Financials Locked On date is blank; “waiting for ops lock” means Operations Locked On is blank.'),
      h('li', null, 'Customer, shipper, consignee and carrier spellings are cleaned so variants count together. Port names are matched on the port code.'),
      h('li', null, 'History: each report covers the dates and branches stated in its title rows, and a shipment can only be marked not present inside them, so loading this year never touches earlier years. The plan keeps this year and the two years before it for year-on-year comparison.'),
      h('li', null, 'The comparison period, the top N, the age limit for open shipments, the age bands and the other definitions can all be changed under Definitions; the defaults are shown there.'),
      h('li', null, 'Profit comes from the uploaded job-level profit reports. Shipment counts and financial amounts use their respective date bases and the current filters.')), 'full'));
}
// ================================================================ Excel (.xlsx) writer: real formulas, no library needed beyond fflate
function xlsxBytes(sheets) {
  const esc = (v) => String(v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '');
  const colName = (n) => { let r = ''; n++; while (n > 0) { const k = (n - 1) % 26; r = String.fromCharCode(65 + k) + r; n = Math.floor((n - 1) / 26); } return r; };
  const sheetXml = (sh) => {
    const rows = sh.rows, last = Math.max(1, rows.length), width = Math.max(1, ...rows.map((r) => r.length));
    let x = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">';
    x += '<sheetViews><sheetView workbookViewId="0">' + (sh.freeze ? '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>' : '') + '</sheetView></sheetViews>';
    if (sh.cols) x += '<cols>' + sh.cols.map((w, i) => '<col min="' + (i + 1) + '" max="' + (i + 1) + '" width="' + w + '" customWidth="1"/>').join('') + '</cols>';
    x += '<sheetData>';
    rows.forEach((row, r) => {
      x += '<row r="' + (r + 1) + '">';
      row.forEach((cell, c) => {
        if (cell == null || cell === '') return;
        const o = typeof cell === 'object' ? cell : {v: cell}, ref = colName(c) + (r + 1), st = o.s ? ' s="' + o.s + '"' : '';
        if (o.f) x += '<c r="' + ref + '"' + st + '><f>' + esc(o.f) + '</f></c>';
        else if (typeof o.v === 'number' && isFinite(o.v)) x += '<c r="' + ref + '"' + st + '><v>' + o.v + '</v></c>';
        else x += '<c r="' + ref + '"' + st + ' t="inlineStr"><is><t xml:space="preserve">' + esc(o.v) + '</t></is></c>';
      });
      x += '</row>';
    });
    x += '</sheetData>' + (sh.filter ? '<autoFilter ref="A1:' + colName(width - 1) + last + '"/>' : '') + '</worksheet>';
    return x;
  };
  const files = {};
  files['[Content_Types].xml'] = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' + sheets.map((_, i) => '<Override PartName="/xl/worksheets/sheet' + (i + 1) + '.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>').join('') + '</Types>';
  files['_rels/.rels'] = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>';
  files['xl/workbook.xml'] = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + sheets.map((sh, i) => '<sheet name="' + esc(sh.name.replace(/[\\/?*[\]:]/g, ' ').slice(0, 31)) + '" sheetId="' + (i + 1) + '" r:id="rId' + (i + 1) + '"/>').join('') + '</sheets><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>';
  files['xl/_rels/workbook.xml.rels'] = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + sheets.map((_, i) => '<Relationship Id="rId' + (i + 1) + '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet' + (i + 1) + '.xml"/>').join('') + '<Relationship Id="rId' + (sheets.length + 1) + '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>';
  // style ids: 1 bold header, 2 percent 0.0%, 3 whole number, 4 one decimal, 5 date
  files['xl/styles.xml'] = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="3"><numFmt numFmtId="164" formatCode="0.0%"/><numFmt numFmtId="165" formatCode="#,##0.0"/><numFmt numFmtId="166" formatCode="dd-mmm-yyyy"/></numFmts><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="6"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>';
  sheets.forEach((sh, i) => { files['xl/worksheets/sheet' + (i + 1) + '.xml'] = sheetXml(sh); });
  const bin = {}; for (const k in files) bin[k] = fflate.strToU8(files[k]);
  return fflate.zipSync(bin, {level: 6});
}
function saveBytes(name, bytes, type) {
  const a = h('a', {href: URL.createObjectURL(new Blob([bytes], {type})), download: name}); document.body.append(a); a.click(); a.remove();
}
const XLSX_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
const serial = (d) => d + 25569;                       // days since 1970 -> Excel date serial
const HDR = (t) => ({v: t, s: 1});
function downloadXlsx(name, sheets) { saveBytes(name, xlsxBytes(sheets), XLSX_TYPE); }

/* Export every rendered report table and chart data currently exposed in the DOM. */
function exportVisibleVisuals(){
 const page=document.getElementById('page');if(!page)return;
 const title=(document.querySelector('#tabs [data-p="'+S.page+'"]')?.textContent||'Dashboard').trim();
 const sheets=[],seen=new Set();
 const tables=[...page.querySelectorAll('table')];
 tables.forEach((table,i)=>{
   const headers=[...table.querySelectorAll('thead tr')].flatMap(tr=>[...tr.cells].map(c=>c.innerText.trim()));
   const rows=[...table.querySelectorAll('tbody tr')].map(tr=>[...tr.cells].map(c=>{const t=c.innerText.trim();const n=Number(t.replace(/,/g,''));return t!==''&&/^[-+]?\d[\d,]*(?:\.\d+)?$/.test(t)?n:t}));
   if(!rows.length&&!headers.length)return;
   const width=Math.max(headers.length,...rows.map(r=>r.length),1);
   sheets.push({name:'Table '+(i+1),cols:Array(width).fill(20),rows:[headers.map(HDR),...rows]});
 });
 // Export D3-bound numerical chart series where available, never pixel positions.
 [...page.querySelectorAll('svg')].forEach((svg,i)=>{
   const items=[],unique=new Set();
   for(const el of svg.querySelectorAll('rect,path,circle,line,g')){
     const d=el.__data__;if(d==null)continue;
     let values=[];
     if(typeof d==='number')values=[['Value',d]];
     else if(Array.isArray(d))values=d.slice(0,12).map((v,j)=>[String(j),v]).filter(([,v])=>typeof v==='number'&&Number.isFinite(v));
     else if(typeof d==='object')values=Object.entries(d).filter(([,v])=>typeof v==='number'&&Number.isFinite(v)).slice(0,12);
     if(!values.length)continue;
     const label=el.getAttribute('aria-label')||el.querySelector('title')?.textContent||el.getAttribute('data-label')||'Series '+(items.length+1);
     const key=label+'|'+JSON.stringify(values);if(unique.has(key))continue;unique.add(key);
     for(const [field,value] of values)items.push([label,field,value]);
     if(items.length>=15000)break;
   }
   if(items.length)sheets.push({name:'Chart '+(i+1),cols:[52,24,22],rows:[[HDR('Series / mark'),HDR('Measure'),HDR('Value')],...items]});
 });
 if(!sheets.length){alert('This view has no exposed table or chart data to export. Use the report-specific Excel export where available.');return}
 sheets.push({name:'Export context',cols:[30,70],rows:[[HDR('Page'),title],[HDR('Current date range'),fRange({from:R.w.from,to:R.w.to})],[HDR('Comparison date range'),fRange({from:R.w.pfrom,to:R.w.pto})],[HDR('Filters'),filterSummary()],[HDR('Note'),'Visible table rows and D3-bound numeric chart series where available. Use report-specific Excel export for full underlying records.']]});
 downloadXlsx('NG_'+title.replace(/[^a-z0-9]+/gi,'_')+'_'+fIso(dDate(R.w.to))+'.xlsx',sheets);
}
function addUniversalExport(){
 const anchor=document.getElementById('printBtn')||document.getElementById('grpRow');if(!anchor)return;
 let b=document.getElementById('uxExportCurrent');if(!b){b=document.createElement('button');b.id='uxExportCurrent';b.type='button';b.className='btn';b.textContent='Export visible data · Excel';b.addEventListener('click',exportVisibleVisuals);anchor.insertAdjacentElement('afterend',b)}
}

function dlButton(label, build, disabledWhy) {
  return h('button', {type: 'button', class: 'btn on', disabled: !!disabledWhy, title: disabledWhy || '', onclick: build}, label);
}
const settingsSheet = (extraRows) => ({name: 'Settings', cols: [34, 60], rows: [[HDR('As-of date (latest shipment date)'), {v: serial(MAXDATE), s: 5}], [HDR('Exported'), new Date().toISOString().slice(0, 16).replace('T', ' ')], [HDR('Filters applied'), filterSummary()]].concat(extraRows || [])});
function filterSummary() {
  const bits = []; for (const k in S.sel) { const set = S.sel[k]; if (set && set.size) bits.push(COLS[k].l + ': ' + [...set].slice(0, 6).map((j) => COLS[k].d[j]).join(', ') + (set.size > 6 ? ' +' + (set.size - 6) : '')); }
  return bits.length ? bits.join(' | ') : 'None';
}

// ================================================================ Compare periods
S.cmp = {unit: 'month', against: 'prev', basis: 'todate', anchor: null, custom: false, A: {from: null, to: null}, B: {from: null, to: null}, dim: 'customer', show: 'all', tsort: {sort: 'adelta', dir: -1}};
S.demo = false; S.pdemo = false;
const UNITS = [['week', 'Week'], ['month', 'Month'], ['quarter', 'Quarter'], ['year', 'Year (follows the year setting above)']];
const ymd = (d) => { const x = dDate(d); return [x.getUTCFullYear(), x.getUTCMonth(), x.getUTCDate()]; };
const dayOf = (y, m, dd) => Math.round(Date.UTC(y, m, dd) / DMS);
const addMonths = (startDay, n) => { const [y, m] = ymd(startDay); return dayOf(y, m + n, 1); };
function pStart(unit, d) {
  const [y, m] = ymd(d), fm = FYB() ? S.def.fyStart - 1 : 0, rel = (m - fm + 12) % 12;      // months since the (financial) year began
  if (unit === 'week') return wkStart(d);
  if (unit === 'month') return dayOf(y, m, 1);
  if (unit === 'quarter') return dayOf(y, m - (rel % 3), 1);
  return dayOf(m >= fm ? y : y - 1, fm, 1);
}
const monthsIn = (unit) => (unit === 'month' ? 1 : unit === 'quarter' ? 3 : 12);
const pNext = (unit, start) => (unit === 'week' ? start + 7 : addMonths(start, monthsIn(unit)));
const pPrev = (unit, start) => (unit === 'week' ? start - 7 : addMonths(start, -monthsIn(unit)));
const nDays = (p) => p.to - p.from + 1;
const fRange = (p) => (p.from === p.to ? fDay(p.from) : fDay(p.from) + ' – ' + fDay(p.to));
function unitName(u) { return u === 'year' ? (FYB() ? 'financial year' : 'year') : {week: 'week', month: 'month', quarter: 'quarter'}[u]; }
function pName(unit, start) {
  const [y, m] = ymd(start), fm = FYB() ? S.def.fyStart - 1 : 0;
  if (unit === 'week') return 'Week of ' + fDay(start);
  if (unit === 'month') return d3.utcFormat('%b %Y')(dDate(start));
  const nm = yearName(m >= fm ? y : y - 1); return unit === 'year' ? nm : 'Q' + (Math.floor(((m - fm + 12) % 12) / 3) + 1) + ' ' + nm;
}
function periods(c0) {
  const c = c0 || S.cmp;
  if (c.custom) {
    if ([c.A.from, c.A.to, c.B.from, c.B.to].some((x) => x == null)) return {err: 'Pick both date ranges.'};
    const fix = (p) => ({from: Math.min(p.from, p.to), to: Math.max(p.from, p.to)});
    const cur = fix(c.A), prev = fix(c.B); return {cur, prev, unit: nDays(cur) <= 8 ? 'week' : nDays(cur) <= 62 ? 'month' : 'year', custom: true, title: 'Custom ranges'};
  }
  const unit = c.unit, anchor = c.anchor == null ? asOfDay() : c.anchor, cs = pStart(unit, anchor), ceFull = pNext(unit, cs) - 1;
  const cur = {from: cs, to: c.basis === 'todate' ? anchor : ceFull}, elapsed = anchor - cs;
  const ps = c.against === 'yoy' ? (unit === 'week' ? pStart('week', cs - 364) : addMonths(cs, -12)) : pPrev(unit, cs), peFull = pNext(unit, ps) - 1;
  let pe = c.basis === 'todate' ? ps + elapsed : peFull, clamped = false; if (pe > peFull) { pe = peFull; clamped = true; }
  const t = pName(unit, cs) + (c.basis === 'todate' ? ' so far' : '') + ' against ' + pName(unit, ps) + (c.basis === 'todate' ? ' (same number of days)' : '');
  return {cur, prev: {from: ps, to: pe}, unit, clamped, title: t, curName: pName(unit, cs), prevName: pName(unit, ps)};
}
const alignStart = (unit, p) => (unit === 'week' || unit === 'month' ? p.from : addMonths(pStart('month', p.from), 0));
function bucketIdx(unit, start, d) { if (unit === 'week') return d - start; if (unit === 'month') return Math.floor((d - start) / 7); const a = ymd(start), b = ymd(d); return (b[0] * 12 + b[1]) - (a[0] * 12 + a[1]); }
function bucketInfo(pr) {
  const unit = pr.unit, sc = alignStart(unit, pr.cur), sp = alignStart(unit, pr.prev);
  const n = unit === 'week' ? 7 : unit === 'month' ? Math.ceil(Math.max(nDays(pr.cur), nDays(pr.prev)) / 7) : Math.max(1, Math.min(60, Math.max(bucketIdx(unit, sc, pr.cur.to), bucketIdx(unit, sp, pr.prev.to)) + 1));
  const s0 = sc, labels = [];
  for (let k = 0; k < n; k++) labels.push(unit === 'week' ? d3.utcFormat('%a')(dDate(s0 + k)) : unit === 'month' ? (1 + 7 * k) + '–' + (7 * k + 7) : d3.utcFormat('%b')(dDate(addMonths(s0, k))));
  return {n, labels, sc, sp};
}

const cmpDims = () => ['customer', 'shipper', 'consignee', 'branch', 'carrier', 'lane', 'origin', 'destination', 'job_owner', 'nomination', 'consol', 'cargo', 'status', 'report', 'company'].concat(EXTRA);
function scanDim(m, key, pr, val) {
  const c = COLS[key].c, sz = COLS[key].d.length, curV = new Float64Array(sz), prevV = new Float64Array(sz), curC = new Float64Array(sz), prevC = new Float64Array(sz), NN = S.demo ? NA : N;
  const cf = pr.cur.from, ct = pr.cur.to, pf = pr.prev.from, pt = pr.prev.to;
  for (let i = 0; i < NN; i++) { if (!m[i]) continue; const d = date[i], inC = d >= cf && d <= ct, inP = d >= pf && d <= pt; if (!inC && !inP) continue; const j = c[i], v = val(i); if (inC) { curV[j] += v; curC[j]++; } if (inP) { prevV[j] += v; prevC[j]++; } }
  return {curV, prevV, curC, prevC, sz};
}
function scanTotals(m, pr) {
  const t = {nC: 0, nP: 0, airC: 0, airP: 0, seaC: 0, seaP: 0, hasAir: false, hasSea: false}, NN = S.demo ? NA : N;
  for (let i = 0; i < NN; i++) { if (!m[i]) continue; const d = date[i], inC = d >= pr.cur.from && d <= pr.cur.to, inP = d >= pr.prev.from && d <= pr.prev.to; if (!inC && !inP) continue;
    if (mode[i]) t.hasSea = true; else t.hasAir = true;
    if (inC) { t.nC++; if (mode[i]) t.seaC += teus[i]; else t.airC += chg[i]; } if (inP) { t.nP++; if (mode[i]) t.seaP += teus[i]; else t.airP += chg[i]; } }
  return t;
}
const sgn = (x) => (x > 0 ? '+' : x < 0 ? '−' : '');
const pctOf = (cur, prev) => (Number.isFinite(cur) && Number.isFinite(prev) && prev !== 0 ? (cur - prev) / Math.abs(prev) : null);
const fPctS = (p) => (p == null ? 'new' : sgn(p) + fP1(Math.abs(p)));
function statusOf(cur, prev) { if (prev === 0 && cur > 0) return 'New'; if (cur === 0 && prev > 0) return 'Lost'; const p = pctOf(cur, prev); if (p == null) return 'Flat'; return Math.abs(p) * 100 <= S.def.flatPct ? 'Flat' : p > 0 ? 'Up' : 'Down'; }

function cmpChartLine(el, tl, pr, info) {
  el.replaceChildren(); const W = Math.max(280, Math.round(($('page').clientWidth || 900) / (window.innerWidth > 900 ? 2 : 1) - 50)), H = 250, mt = 16, mb = 28;
  const L = tl.L, ymax = Math.max(d3.max(tl.cur.slice(0, tl.curN)) || 0, d3.max(tl.prev.slice(0, tl.prevN)) || 0, 1);
  const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', '0 0 ' + W + ' ' + H).attr('role', 'img').attr('aria-label', 'Cumulative current period against previous period');
  const y = d3.scaleLinear([0, ymax], [H - mb, mt]).nice(4), yf = y.domain()[1] >= 10 ? d3.format(',.0f') : d3.format(',.1f'), ticks = y.ticks(4);
  const probe = svg.append('text').attr('class', 'tick').text(yf(d3.max(ticks))); const ml = Math.ceil(probe.node().getComputedTextLength()) + 12; probe.remove();
  const x = d3.scaleLinear([0, Math.max(1, L - 1)], [ml, W - 10]);
  ticks.forEach((t) => { svg.append('line').attr('x1', ml).attr('x2', W - 10).attr('y1', y(t)).attr('y2', y(t)).style('stroke', 'var(--grid)'); svg.append('text').attr('class', 'tick').attr('x', ml - 6).attr('y', y(t)).attr('text-anchor', 'end').attr('dominant-baseline', 'middle').text(yf(t)); });
  const line = d3.line().x((d, i) => x(i)).y((d) => y(d));
  svg.append('path').attr('d', line(Array.from(tl.prev.slice(0, tl.prevN)))).attr('fill', 'none').attr('stroke', '#a39f95').attr('stroke-width', 2).attr('stroke-dasharray', '5 3');
  svg.append('path').attr('d', line(Array.from(tl.cur.slice(0, tl.curN)))).attr('fill', 'none').attr('stroke', '#4c78a8').attr('stroke-width', 2.5);
  const tickIdx = []; if (pr.unit === 'week') { for (let k = 0; k < Math.min(7, L); k++) tickIdx.push(k); } else if (pr.unit === 'month') { for (let k = 0; k < L; k += Math.max(1, Math.ceil(L / 8))) tickIdx.push(k); } else { for (let k = 0; ; k++) { const off = addMonths(pStart('month', pr.cur.from), k) - pr.cur.from; if (off >= L) break; if (off >= 0) tickIdx.push(off); } }
  const stepT = Math.max(1, Math.ceil(tickIdx.length / 8));
  tickIdx.forEach((k, n) => { if (n % stepT === 0) svg.append('text').attr('class', 'tick').attr('x', x(k)).attr('y', H - 8).attr('text-anchor', 'middle').text(pr.unit === 'week' ? d3.utcFormat('%a')(dDate(pr.cur.from + k)) : pr.unit === 'month' ? String(ymd(pr.cur.from + k)[2]) : d3.utcFormat('%b')(dDate(pr.cur.from + k))); });
  const curEnd = tl.cur[tl.curN - 1] || 0, prevEnd = tl.prev[tl.prevN - 1] || 0;
  svg.append('circle').attr('cx', x(tl.curN - 1)).attr('cy', y(curEnd)).attr('r', 4).attr('fill', '#4c78a8');
  svg.append('circle').attr('cx', x(tl.prevN - 1)).attr('cy', y(prevEnd)).attr('r', 4).attr('fill', '#a39f95');
  const tip = h('div', {class: 'tip', hidden: true}); el.append(tip);
  svg.append('rect').attr('x', ml).attr('y', mt).attr('width', W - ml - 10).attr('height', H - mt - mb).attr('fill', 'transparent')
    .on('mousemove', (ev) => { const b = el.getBoundingClientRect(), k = Math.max(0, Math.min(L - 1, Math.round(x.invert((ev.clientX - b.left) * W / b.width)))), cv = tl.cur[Math.min(k, tl.curN - 1)], pv = tl.prev[Math.min(k, tl.prevN - 1)];
      tip.replaceChildren(h('div', {class: 'tip-h'}, 'Day ' + (k + 1) + ' of the period'), h('div', null, h('i', {class: 'sw', style: 'background:#4c78a8'}), 'Current: ' + info.f(cv)), h('div', null, h('i', {class: 'sw', style: 'background:#a39f95'}), 'Previous: ' + info.f(pv)), h('div', null, 'Change: ' + sgn(cv - pv) + info.f(Math.abs(cv - pv)) + ' (' + fPctS(pctOf(cv, pv)) + ')')); tip.hidden = false;
      const tw = tip.offsetWidth; let l = ev.clientX - b.left + 12; if (l + tw > b.width) l = ev.clientX - b.left - tw - 12; tip.style.left = Math.max(0, l) + 'px'; tip.style.top = Math.max(0, ev.clientY - b.top - 70) + 'px'; })
    .on('mouseleave', () => { tip.hidden = true; });
  el.append(h('div', {class: 'legend'}, h('span', {class: 'lg static'}, h('i', {class: 'sw', style: 'background:#4c78a8'}), 'Current ' + fRange(pr.cur)), h('span', {class: 'lg static'}, h('i', {class: 'sw', style: 'background:#a39f95'}), 'Previous ' + fRange(pr.prev))));
}
function cmpChartBars(el, bk, info) {
  el.replaceChildren(); const W = Math.max(280, Math.round(($('page').clientWidth || 900) / (window.innerWidth > 900 ? 2 : 1) - 50)), H = 250, mt = 22, mb = 28, n = bk.n;
  const ymax = Math.max(1, d3.max(bk.cur) || 0, d3.max(bk.prev) || 0), y = d3.scaleLinear([0, ymax], [H - mb, mt]).nice(4), yf = y.domain()[1] >= 10 ? d3.format(',.0f') : d3.format(',.1f'), ticks = y.ticks(4);
  const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', '0 0 ' + W + ' ' + H).attr('role', 'img').attr('aria-label', 'Current against previous by period');
  const probe = svg.append('text').attr('class', 'tick').text(yf(d3.max(ticks))); const ml = Math.ceil(probe.node().getComputedTextLength()) + 12; probe.remove();
  const x = d3.scaleBand(d3.range(n), [ml, W - 8]).padding(0.2), bw = x.bandwidth() / 2;
  ticks.forEach((t) => { svg.append('line').attr('x1', ml).attr('x2', W - 8).attr('y1', y(t)).attr('y2', y(t)).style('stroke', 'var(--grid)'); svg.append('text').attr('class', 'tick').attr('x', ml - 6).attr('y', y(t)).attr('text-anchor', 'end').attr('dominant-baseline', 'middle').text(yf(t)); });
  const tip = h('div', {class: 'tip', hidden: true}); el.append(tip);
  for (let k = 0; k < n; k++) {
    svg.append('rect').attr('x', x(k)).attr('y', y(bk.prev[k])).attr('width', bw).attr('height', Math.max(0, H - mb - y(bk.prev[k]))).attr('fill', '#a39f95').attr('rx', 2);
    svg.append('rect').attr('x', x(k) + bw).attr('y', y(bk.cur[k])).attr('width', bw).attr('height', Math.max(0, H - mb - y(bk.cur[k]))).attr('fill', '#4c78a8').attr('rx', 2);
    svg.append('text').attr('class', 'tick').attr('x', x(k) + x.bandwidth() / 2).attr('y', H - 8).attr('text-anchor', 'middle').text(bk.labels[k]);
    const p = pctOf(bk.cur[k], bk.prev[k]); if (n <= 12 && (bk.cur[k] || bk.prev[k])) svg.append('text').attr('class', 'lbl').attr('x', x(k) + x.bandwidth() / 2).attr('y', y(Math.max(bk.cur[k], bk.prev[k])) - 5).attr('text-anchor', 'middle').style('fill', p == null ? 'var(--muted)' : p >= 0 ? 'var(--ok)' : 'var(--bad)').text(p == null ? 'new' : (p >= 0 ? '+' : '−') + d3.format('.0%')(Math.abs(p)));
    svg.append('rect').attr('x', x(k)).attr('y', mt).attr('width', x.bandwidth()).attr('height', H - mt - mb).attr('fill', 'transparent')
      .on('mousemove', (ev) => { const b = el.getBoundingClientRect(); tip.replaceChildren(h('div', {class: 'tip-h'}, bk.labels[k]), h('div', null, h('i', {class: 'sw', style: 'background:#4c78a8'}), 'Current: ' + info.f(bk.cur[k])), h('div', null, h('i', {class: 'sw', style: 'background:#a39f95'}), 'Previous: ' + info.f(bk.prev[k])), h('div', null, 'Change: ' + sgn(bk.cur[k] - bk.prev[k]) + info.f(Math.abs(bk.cur[k] - bk.prev[k])) + ' (' + fPctS(pctOf(bk.cur[k], bk.prev[k])) + ')')); tip.hidden = false;
        const tw = tip.offsetWidth; let l = ev.clientX - b.left + 12; if (l + tw > b.width) l = ev.clientX - b.left - tw - 12; tip.style.left = Math.max(0, l) + 'px'; tip.style.top = Math.max(0, ev.clientY - b.top - 70) + 'px'; })
      .on('mouseleave', () => { tip.hidden = true; });
  }
  el.append(h('div', {class: 'legend'}, h('span', {class: 'lg static'}, h('i', {class: 'sw', style: 'background:#4c78a8'}), 'Current'), h('span', {class: 'lg static'}, h('i', {class: 'sw', style: 'background:#a39f95'}), 'Previous')));
}
function deltaRows(items, onClick, info) {
  if (!items.length) return h('p', {class: 'empty'}, 'Nothing here for these periods and filters.');
  const mx = Math.max(...items.map((d) => Math.abs(d.delta)), 1e-9);
  return h('div', {class: 'rank'}, items.map((d) => h('button', {type: 'button', class: 'row' + (d.sel ? ' on' : ''), onclick: () => onClick(d)}, h('span', {class: 'lab', title: d.label}, d.label),
    h('span', {class: 'track'}, h('span', {class: 'fill', style: 'width:' + (Math.abs(d.delta) / mx * 100) + '%;background:var(--' + (d.delta >= 0 ? 'ok' : 'bad') + ')'})),
    h('span', {class: 'val'}, sgn(d.delta) + info.f(Math.abs(d.delta)) + (d.prev > 0 ? ' (' + fPctS(pctOf(d.cur, d.prev)) + ')' : ' (new)')))));
}
function pageCompare() {
  const c = S.cmp, pr = periods(), root = h('div');
  const controls = h('div', {class: 'card', style: 'margin-bottom:.9rem'});
  const sel = (opts, val, on) => { const e = h('select', null, opts.map((o) => h('option', {value: o[0], selected: String(o[0]) === String(val)}, o[1]))); e.value = String(val); e.addEventListener('change', () => on(e.value)); return e; };
  const dateIn = (val, on) => { const e = h('input', {type: 'date', value: val == null ? '' : fIso(dDate(val)), min: '2000-01-01', max: '2099-12-31'}); e.addEventListener('change', () => { if (e.value) { on(isoD(e.value)); renderAll(); } }); return e; };
  const preset = (label, f) => h('button', {type: 'button', class: 'btn', onclick: () => { Object.assign(c, {custom: false}, f); renderAll(); }}, label);
  const prefill = () => { const keep = c.custom; c.custom = false; const p = periods(); c.custom = keep; if (!p.err) { c.A = Object.assign({}, p.cur); c.B = Object.assign({}, p.prev); } };
  controls.append(h('h2', {class: 'h'}, 'Compare periods'), h('p', {class: 'note'}, 'Pick what to compare. Everything below follows the filters above (company, report, customer and so on) and ignores the date range.'),
    h('div', {class: 'frow'}, h('span', {class: 'lbl2'}, 'Quick picks'), preset(FYB() ? 'This financial year vs last' : 'Year vs last year', {unit: 'year', against: 'prev'}), preset('Quarter vs last quarter', {unit: 'quarter', against: 'prev'}), preset('Month vs last month', {unit: 'month', against: 'prev'}), preset('Week vs last week', {unit: 'week', against: 'prev'}), preset('Month vs same month last year', {unit: 'month', against: 'yoy'})),
    h('div', {class: 'frow'}, h('label', {class: 'f'}, h('span', null, 'Period'), sel(UNITS, c.unit, (v) => { c.unit = v; c.custom = false; renderAll(); })), h('label', {class: 'f'}, h('span', null, 'Against'), sel([['prev', 'The period just before'], ['yoy', 'Same period last year']], c.against, (v) => { c.against = v; c.custom = false; renderAll(); })),
      h('label', {class: 'f'}, h('span', null, 'Basis'), sel([['todate', 'To date (like for like)'], ['full', 'Full period']], c.basis, (v) => { c.basis = v; renderAll(); })), h('label', {class: 'f'}, h('span', null, 'As at'), dateIn(c.anchor == null ? asOfDay() : c.anchor, (v) => { c.anchor = v; c.custom = false; })),
      h('button', {type: 'button', class: 'btn', onclick: () => { c.anchor = null; renderAll(); }}, 'Reset to as-of date'), h('label', {class: 'f'}, h('input', {type: 'checkbox', checked: c.custom, onchange: (e) => { c.custom = e.target.checked; if (c.custom) prefill(); renderAll(); }}), 'Custom date ranges')));
  if (c.custom) controls.append(h('div', {class: 'frow'}, h('span', {class: 'lbl2'}, 'Current'), dateIn(c.A.from, (v) => { c.A.from = v; }), dateIn(c.A.to, (v) => { c.A.to = v; }), h('span', {class: 'lbl2'}, 'compared with'), dateIn(c.B.from, (v) => { c.B.from = v; }), dateIn(c.B.to, (v) => { c.B.to = v; })));
  root.append(controls);
  if (pr.err) { root.append(h('div', {class: 'card'}, h('p', {class: 'empty'}, pr.err))); return root; }

  const m = mask({dates: 'none', demo: true}), tot = scanTotals(m, pr), mixed = tot.hasAir && tot.hasSea, useVol = S.measure === 'volume' && !mixed;
  const val = (i) => (useVol ? VOL[i] : 1), unitTxt = useVol ? (tot.hasAir ? 't' : 'TEU') : '';
  const info = {f: (x) => (useVol ? (tot.hasAir ? f1(x) + ' t' : fInt(Math.round(x)) + ' TEU') : fInt(Math.round(x)))};
  root.append(h('div', {class: 'card', style: 'margin-bottom:.9rem'}, h('p', {class: 'take', style: 'margin:0 0 .3rem'}, pr.title + '.'),
    h('p', {class: 'meta', style: 'margin:0'}, 'Current: ' + (pr.curName ? pr.curName + ', ' : '') + fRange(pr.cur) + ' (' + nDays(pr.cur) + ' days)   |   Previous: ' + (pr.prevName ? pr.prevName + ', ' : '') + fRange(pr.prev) + ' (' + nDays(pr.prev) + ' days)' + (nDays(pr.cur) !== nDays(pr.prev) ? '   |   The two periods have a different number of days.' : '') + (pr.clamped ? '   |   The previous period is shorter than the days elapsed in the current one, so it stops at its last day.' : '')),
    mixed && S.measure === 'volume' ? h('p', {class: 'meta', style: 'margin:.3rem 0 0'}, 'Air and sea are never added together, so the figures below count shipments. Select only air or only sea reports to compare volume.') : null,
    tot.nP === 0 ? h('p', {class: 'meta', style: 'margin:.4rem 0 0;color:var(--warn)'}, 'There is no data in the comparison period. ' + (c.against === 'yoy' || pr.prev.to < MINDATE ? 'The uploaded records contain no activity for that comparison period. Upload earlier reports if needed.' : 'Choose a different period.')) : null));

  // KPI cards
  const cu = scanDim(m, 'customer', pr, () => 1); let aC = 0, aP = 0, nw = 0, ls = 0;
  for (let j = 0; j < cu.sz; j++) { const a = cu.curC[j] >= S.def.activeMin && cu.curC[j] > 0, b = cu.prevC[j] >= S.def.activeMin && cu.prevC[j] > 0; if (a) aC++; if (b) aP++; if (a && cu.prevC[j] === 0) nw++; if (b && cu.curC[j] === 0) ls++; }
  const vk = (label, cur, prev, f, note) => { const d = cur - prev, p = pctOf(cur, prev); return h('div', {class: 'card kpi'}, h('div', {class: 'kl'}, label), h('div', {class: 'kv'}, f(cur)), h('div', {class: 'kn'}, 'Previous ' + f(prev)), h('div', {class: 'delta ' + (d > 0 ? 'ok' : d < 0 ? 'bad' : 'flat')}, sgn(d) + f(Math.abs(d)) + ' (' + fPctS(p) + ')'), note ? h('div', {class: 'kn'}, note) : null); };
  const kp = [vk('Shipments', tot.nC, tot.nP, fInt)];
  if (tot.hasAir) kp.push(vk('Air chargeable weight (tonnes)', tot.airC, tot.airP, f1));
  if (tot.hasSea) kp.push(vk('Sea TEUs', tot.seaC, tot.seaP, (x) => fInt(Math.round(x)), 'Recorded ocean TEUs'));
  kp.push(vk('Active customers', aC, aP, fInt), h('div', {class: 'card kpi'}, h('div', {class: 'kl'}, 'Customers only in current period'), h('div', {class: 'kv'}, fInt(nw)), h('div', {class: 'kn'}, 'Meets activity minimum now; no previous-period shipments. Not necessarily a new customer.'), businessMeaning('Customers only in current period', 'Customers meeting activity threshold now and absent in the comparison period')), h('div', {class: 'card kpi'}, h('div', {class: 'kl'}, 'Customers only in comparison period'), h('div', {class: 'kv'}, fInt(ls)), h('div', {class: 'kn'}, 'Meets activity minimum before; no current-period shipments. Not confirmed lost business.'), businessMeaning('Customers only in comparison period', 'Customers meeting the comparison activity threshold but absent from current-period shipments')));
  root.append(h('div', {class: 'kpis'}, kp));

  // charts
  const L = Math.max(nDays(pr.cur), nDays(pr.prev)), cum = new Float64Array(L), cumP = new Float64Array(L), bk = bucketInfo(pr), bc = new Float64Array(bk.n), bpv = new Float64Array(bk.n), NN = S.demo ? NA : N;
  for (let i = 0; i < NN; i++) { if (!m[i]) continue; const d = date[i], v = val(i);
    if (d >= pr.cur.from && d <= pr.cur.to) { cum[d - pr.cur.from] += v; const b = bucketIdx(pr.unit, bk.sc, d); if (b >= 0 && b < bk.n) bc[b] += v; }
    if (d >= pr.prev.from && d <= pr.prev.to) { cumP[d - pr.prev.from] += v; const b = bucketIdx(pr.unit, bk.sp, d); if (b >= 0 && b < bk.n) bpv[b] += v; } }
  for (let k = 1; k < L; k++) { cum[k] += cum[k - 1]; cumP[k] += cumP[k - 1]; }
  const lineBox = h('div', {class: 'trend'}), barBox = h('div', {class: 'trend'});
  const mTxt = useVol ? (tot.hasAir ? 'Chargeable weight (tonnes)' : 'TEUs') : 'Shipments';
  root.append(h('div', {class: 'grid', style: 'margin-bottom:.9rem'}, card('Running total', mTxt + ', adding up day by day from the start of each period. The gap between the lines is the change.', lineBox), card('Period by period', mTxt + ' in each part of the period, with the percentage change above each pair.', barBox)));
  cmpChartLine(lineBox, {cur: cum, prev: cumP, L, curN: nDays(pr.cur), prevN: nDays(pr.prev)}, pr, info); cmpChartBars(barBox, {n: bk.n, labels: bk.labels, cur: bc, prev: bpv}, info);

  // dimension table
  const key = cmpDims().includes(c.dim) ? c.dim : 'customer', dm = mask({dates: 'none', demo: true, skip: key}), sc = scanDim(dm, key, pr, val), selSet = S.sel[key] || new Set();
  let totC = 0, totP = 0; for (let j = 0; j < sc.sz; j++) { totC += sc.curV[j]; totP += sc.prevV[j]; }
  const all = []; for (let j = 0; j < sc.sz; j++) { const cur = sc.curV[j], prev = sc.prevV[j]; if (cur === 0 && prev === 0 && !selSet.has(j)) continue; const delta = cur - prev; all.push({j, label: COLS[key].d[j], cur, prev, delta, adelta: Math.abs(delta), pct: pctOf(cur, prev), contrib: totP > 0 ? delta / totP : null, status: statusOf(cur, prev), sel: selSet.has(j)}); }
  const passes = (r) => { if (c.show === 'up' && !(r.delta > 0)) return false; if (c.show === 'down' && !(r.delta < 0)) return false; if (c.show === 'new' && r.status !== 'New') return false; if (c.show === 'lost' && r.status !== 'Lost') return false;
    if (S.def.varMinBase > 0 && r.prev < S.def.varMinBase) return false; if (S.def.varMinAbs > 0 && r.adelta < S.def.varMinAbs) return false;
    if (S.def.varMinPct > 0 && r.pct != null && Math.abs(r.pct) * 100 < S.def.varMinPct) return false; return true; };
  const rowsF = all.filter(passes), onPick = (d) => toggle(key, d.j);
  const gain = all.filter((r) => r.delta > 0).sort((a, b) => b.delta - a.delta).slice(0, S.def.topN), lose = all.filter((r) => r.delta < 0).sort((a, b) => a.delta - b.delta).slice(0, S.def.topN);
  root.append(h('div', {class: 'grid', style: 'margin-bottom:.9rem'}, card('Biggest increases by ' + COLS[key].l.toLowerCase(), 'What added most to the total. Click to filter everything.', deltaRows(gain, onPick, info)), card('Biggest decreases by ' + COLS[key].l.toLowerCase(), 'What took most away from the total. Click to filter everything.', deltaRows(lose, onPick, info))));

  const dimSel = sel(cmpDims().map((k) => [k, COLS[k].l]), key, (v) => { c.dim = v; renderAll(); });
  const showSel = sel([['all', 'All changes'], ['up', 'Increases only'], ['down', 'Decreases only'], ['new', 'New only'], ['lost', 'Lost only']], c.show, (v) => { c.show = v; renderAll(); });
  const num = (k, label, hint) => { const e = h('input', {type: 'number', min: 0, value: S.def[k], 'aria-label': label}); e.addEventListener('change', () => { const v = Math.max(0, parseFloat(e.value) || 0); S.def[k] = v; saveDefs(); renderDefs(); renderAll(); }); return h('label', {class: 'f', title: hint}, h('span', null, label), e); };
  const cols = [{k: 'label', t: COLS[key].l}, {k: 'cur', t: 'Current', num: true}, {k: 'prev', t: 'Previous', num: true}, {k: 'delta', t: 'Change', num: true}, {k: 'pct', t: 'Change %', num: true}, {k: 'contrib', t: 'Share of total change', num: true}, {k: 'status', t: 'Trend'}];
  const thead = h('thead'), tbody = h('tbody'), note = h('p', {class: 'note'});
  const draw = () => { const ts = c.tsort, f = ts.sort === 'label' || ts.sort === 'status' ? (a, b) => String(a[ts.sort]).localeCompare(String(b[ts.sort])) : (a, b) => (a[ts.sort] == null ? -1e18 : a[ts.sort]) - (b[ts.sort] == null ? -1e18 : b[ts.sort]);
    const rows = rowsF.slice().sort((a, b) => f(a, b) * ts.dir); thead.replaceChildren(sortHead(cols, ts, draw)); const shown = rows.slice(0, S.def.tableRows);
    tbody.replaceChildren(...shown.map((r) => h('tr', {class: 'click' + (r.sel ? ' on' : ''), onclick: () => onPick(r)}, h('td', null, r.label), h('td', {class: 'n'}, info.f(r.cur)), h('td', {class: 'n'}, info.f(r.prev)), h('td', {class: 'n ' + (r.delta > 0 ? 'ok' : r.delta < 0 ? 'bad' : '')}, sgn(r.delta) + info.f(r.adelta)),
      h('td', {class: 'n ' + (r.delta > 0 ? 'ok' : r.delta < 0 ? 'bad' : '')}, r.pct == null ? (r.cur > 0 ? 'new' : '–') : fPctS(r.pct)), h('td', {class: 'n'}, r.contrib == null ? '–' : sgn(r.contrib) + f1(Math.abs(r.contrib) * 100) + ' pts'), h('td', null, h('span', {class: 'pill ' + (r.status === 'Up' || r.status === 'New' ? 'ok' : r.status === 'Down' || r.status === 'Lost' ? 'bad' : '')}, r.status)))));
    tbody.append(h('tr', {class: 'totrow'}, h('td', null, 'Total of all ' + COLS[key].l.toLowerCase() + ' values'), h('td', {class: 'n'}, info.f(totC)), h('td', {class: 'n'}, info.f(totP)), h('td', {class: 'n'}, sgn(totC - totP) + info.f(Math.abs(totC - totP))), h('td', {class: 'n'}, fPctS(pctOf(totC, totP))), h('td'), h('td')));
    note.textContent = 'Showing ' + shown.length + ' of ' + fInt(rows.length) + ' rows' + (rows.length < all.length ? ' (' + (all.length - rows.length) + ' hidden by the filters)' : '') + '. Click a header to sort, a row to filter everything. Share of total change = the row’s change divided by the previous total.'; };
  draw();
  const why = S.demo ? 'Switched off while demo history is on' : '';
  const exportXlsx = () => { const rows = rowsF.slice().sort((a, b) => b.adelta - a.adelta), n = rows.length, tr = n + 2;
    const sheet = {name: 'Variance', freeze: true, filter: true, cols: [38, 14, 14, 14, 12, 18, 10], rows: [[HDR(COLS[key].l), HDR('Current'), HDR('Previous'), HDR('Change'), HDR('Change %'), HDR('Share of total change'), HDR('Trend')]]
      .concat(rows.map((r, i) => { const x = i + 2; return [r.label, {v: +r.cur.toFixed(3), s: useVol && tot.hasAir ? 4 : 3}, {v: +r.prev.toFixed(3), s: useVol && tot.hasAir ? 4 : 3}, {f: 'B' + x + '-C' + x, s: useVol && tot.hasAir ? 4 : 3}, {f: 'IF(C' + x + '=0,"",D' + x + '/C' + x + ')', s: 2}, {f: 'IF($C$' + tr + '=0,"",D' + x + '/$C$' + tr + ')', s: 2}, {f: 'IF(AND(C' + x + '=0,B' + x + '>0),"New",IF(AND(B' + x + '=0,C' + x + '>0),"Lost",IF(C' + x + '=0,"Flat",IF(ABS(D' + x + '/C' + x + ')<=Settings!$B$7/100,"Flat",IF(D' + x + '>0,"Up","Down")))))'}]; }))};
    sheet.rows.push([HDR('Total of rows listed'), {f: 'SUM(B2:B' + (n + 1) + ')', s: 3}, {f: 'SUM(C2:C' + (n + 1) + ')', s: 3}, {f: 'B' + tr + '-C' + tr, s: 3}, {f: 'IF(C' + tr + '=0,"",D' + tr + '/C' + tr + ')', s: 2}]);
    downloadXlsx('variance_' + fIso(dDate(MAXDATE)) + '.xlsx', [sheet, settingsSheet([[HDR('Comparison'), pr.title], [HDR('Current period'), fRange(pr.cur)], [HDR('Previous period'), fRange(pr.prev)], [HDR('Flat when change within (%)'), S.def.flatPct], [HDR('Measure'), mTxt], [HDR('Rows by'), COLS[key].l]])]); };
  // Settings sheet rows: 1 as-of, 2 exported, 3 filters, 4 comparison, 5 current, 6 previous, 7 flat percent (read by the Trend formula)
  root.append(card('Variance by ' + COLS[key].l.toLowerCase(), 'Current against previous, in value and in percent.', h('div', null,
    h('div', {class: 'frow'}, h('label', {class: 'f'}, h('span', null, 'Rows by'), dimSel), h('label', {class: 'f'}, h('span', null, 'Show'), showSel), num('varMinPct', 'Change at least (%)', 'Hide rows whose percentage change is smaller than this. 0 shows all.'), num('varMinAbs', 'Change at least (value)', 'Hide rows whose change in value is smaller than this.'), num('varMinBase', 'Previous at least', 'Hide rows whose previous value is below this, so tiny bases do not give huge percentages.'), dlButton('Download Excel', exportXlsx, why)),
    note, h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, thead, tbody))), 'full'));
  root.append(h('p', {class: 'ng-foot', style: 'font-size:.78rem;color:var(--muted)'}, 'Percent change is the change divided by the previous value. Items with nothing in the previous period are shown as New, and items with nothing now as Lost, instead of an infinite percentage. Like for like (to date) compares the same number of elapsed days in each period.'));
  return root;
}

// ---------------------------------------------------------------- profit helpers
const inrFmt = new Intl.NumberFormat('en-IN', {maximumFractionDigits: 0});
function money(x) {
  const a = Math.abs(x), s = x < 0 ? '−' : '', u = S.def.moneyUnit;
  if (u === 'cr' || (u === 'auto' && a >= 1e7)) return s + '₹' + (a / 1e7).toFixed(2) + ' Cr';
  if (u === 'lakh' || (u === 'auto' && a >= 1e5)) return s + '₹' + (a / 1e5).toFixed(2) + ' L';
  if (u === 'k') return s + '₹' + (a / 1e3).toFixed(1) + ' K';
  return s + '₹' + inrFmt.format(a);
}
const marginOf = (inc, exp) => (inc > 0 ? (inc - exp) / inc : null);
const fMargin = (m) => (m == null ? '–' : (m * 100).toFixed(1) + '%');
function recomputeJobsP() {
  const st = new Uint8Array(NJ), bd = new Uint8Array(NJ), low = S.def.lowMargin / 100;
  for (let j = 0; j < NJ; j++) { const inc = pjInc[j], exp = pjExp[j], p = inc - exp, m = marginOf(inc, exp); st[j] = exp === 0 && inc > 0 ? 1 : inc <= 0 && exp > 0 ? 2 : p < -1 ? 3 : (m != null && m < low ? 4 : 0); bd[j] = inc <= 0 ? 6 : p < -1 ? 0 : exp === 0 ? 5 : m < 0.1 ? 1 : m < 0.3 ? 2 : m < 0.6 ? 3 : 4; }   // a shortfall of under one rupee is rounding, not a loss
  for (let i = 0; i < NPA; i++) { COLS.jobstatus.pc[i] = st[pjob[i]]; COLS.band.pc[i] = bd[pjob[i]]; }
}
function groupByP(keyOrFn, m, size, labelFn) {
  const isKey = typeof keyOrFn === 'string', c = isKey ? COLS[keyOrFn].pc : null, kf = isKey ? (i) => c[i] : keyOrFn, n = isKey ? COLS[keyOrFn].d.length : size;
  const inc = new Float64Array(n), exp = new Float64Array(n), lines = new Int32Array(n), airT = new Float64Array(n), seaT = new Float64Array(n), airP = new Float64Array(n), seaP = new Float64Array(n), jobs = new Array(n).fill(null), booked = new Array(n).fill(null), vj = new Array(n).fill(null);
  for (let i = 0; i < NP; i++) {
    if (!m[i]) continue; const g = kf(i), j = pjob[i]; inc[g] += pinc[i]; exp[g] += pexp[i]; lines[g]++; (jobs[g] || (jobs[g] = new Set())).add(j); if (pexp[i] > 0) (booked[g] || (booked[g] = new Set())).add(j);
    const s = psidx[i]; if (s >= 0) { const air = mode[s] === 0; if (air) airP[g] += pinc[i] - pexp[i]; else seaP[g] += pinc[i] - pexp[i]; const sj = vj[g] || (vj[g] = new Set()); if (!sj.has(j)) { sj.add(j); if (air) airT[g] += chg[s]; else seaT[g] += teus[s]; } }
  }
  const out = []; for (let g = 0; g < n; g++) if (lines[g]) out.push({g, label: labelFn ? labelFn(g) : COLS[keyOrFn].d[g], inc: inc[g], exp: exp[g], profit: inc[g] - exp[g], margin: marginOf(inc[g], exp[g]), jobs: jobs[g].size, lines: lines[g], booked: booked[g] ? booked[g].size : 0, airT: airT[g], seaT: seaT[g], airP: airP[g], seaP: seaP[g]});
  return out;
}
function totalsP(m, from, to) {
  let inc = 0, exp = 0, lines = 0, neg = 0; const jobs = new Set(), booked = new Set();
  for (let i = 0; i < NP; i++) { if (!m[i]) continue; if (from != null && (pdate[i] < from || pdate[i] > to)) continue; inc += pinc[i]; exp += pexp[i]; lines++; jobs.add(pjob[i]); if (pexp[i] > 0) booked.add(pjob[i]); if (pinc[i] < 0) neg++; }
  return {inc, exp, profit: inc - exp, margin: marginOf(inc, exp), jobs: jobs.size, booked: booked.size, lines, neg};
}
function maskP(opt) {
  opt = opt || {}; const skip = new Set([].concat(opt.skip || [])), NN = NP, m = new Uint8Array(NPA); m.fill(1, 0, NN);
  for (const k in S.sel) { if (skip.has(k)) continue; const set = S.sel[k]; if (!set || !set.size) continue; const L = new Uint8Array(COLS[k].d.length); set.forEach((v) => { L[v] = 1; }); const c = COLS[k].pc; for (let i = 0; i < NN; i++) if (!L[c[i]]) m[i] = 0; }
  if (opt.dates !== 'none') { const w = win(), lo = opt.dates === 'prev' ? w.pfrom : w.from, hi = opt.dates === 'prev' ? w.pto : w.to; for (let i = 0; i < NN; i++) if (pdate[i] < lo || pdate[i] > hi) m[i] = 0; }
  return m;
}
const rankVal = (r) => (S.rank === 'income' ? r.inc : S.rank === 'expense' ? r.exp : r.profit);
function setMany(o) { for (const k in o) S.sel[k] = new Set([o[k]]); renderAll(); }
const pcatv = (key, i) => COLS[key].d[COLS[key].pc[i]];
function prankList(rows, onClick, selFn, opt) {
  opt = opt || {}; if (!rows.length) return emptyNote();
  const sorted = rows.slice().sort((a, b) => rankVal(b) - rankVal(a)), lim = opt.limit || S.def.topN; const top = sorted.slice(0, lim); sorted.forEach((r) => { if (selFn(r) && !top.includes(r)) top.push(r); });
  const mx = Math.max(...top.map((r) => Math.abs(rankVal(r))), 1), tot = d3.sum(rows, (r) => rankVal(r));
  return h('div', null, h('div', {class: 'rank'}, top.map((r) => h('button', {type: 'button', class: 'row' + (selFn(r) ? ' on' : ''), onclick: () => onClick(r)}, h('span', {class: 'lab', title: r.label}, r.label),
    h('span', {class: 'track'}, h('span', {class: 'fill', style: 'width:' + (Math.abs(rankVal(r)) / mx * 100) + '%;background:' + (rankVal(r) < 0 ? 'var(--bad)' : (opt.color || '#4c78a8'))})),
    h('span', {class: 'val'}, money(rankVal(r)) + (S.rank === 'profit' ? ' · ' + fMargin(r.margin) : '') + (tot > 0 && rankVal(r) > 0 ? ' · ' + fS(rankVal(r) / tot) : ''))))),
    sorted.length > top.length ? h('p', {class: 'more'}, 'Top ' + top.length + ' of ' + fInt(sorted.length) + '. Use the filters above to find others.') : null);
}
const pkeyRank = (key, opt) => { const m = maskP({skip: key}), sel = S.sel[key] || new Set(); return prankList(groupByP(key, m), (r) => {toggle(key,r.g);window.MetricTrace?.openCategory(S.rank==='income'?'profit.income':S.rank==='expense'?'profit.expense':'profit.gp',key,r.g);}, (r) => sel.has(r.g), opt); };

// ================================================================ pages
const colour = (v, mx) => (v >= 0 ? 'rgba(26,127,75,' : 'rgba(194,54,43,') + (0.1 + 0.7 * Math.min(1, Math.abs(v) / (mx || 1))) + ')';
function pbyJob(m) {
  const mp = new Map();
  for (let i = 0; i < NP; i++) { if (!m[i]) continue; const j = pjob[i]; let e = mp.get(j); if (!e) { e = {j, i0: i, inc: 0, exp: 0, lines: 0}; mp.set(j, e); } e.inc += pinc[i]; e.exp += pexp[i]; e.lines++; }
  return [...mp.values()].map((e) => Object.assign(e, {profit: e.inc - e.exp, margin: marginOf(e.inc, e.exp), status: COLS.jobstatus.pc[e.i0], job: pcatv('p_job', e.i0), branch: pcatv('branch', e.i0), lob: pcatv('p_lob', e.i0), customer: pcatv('customer', e.i0), company: pco[e.i0], jdate: pjd[e.i0]}));
}
function bridgeChart(items) {
  const W = Math.max(280, Math.round(($('page').clientWidth || 900) / (window.innerWidth > 900 ? 2 : 1) - 50)), H = 230, mt = 18, mb = 44, box = h('div', {class: 'trend'});
  const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', '0 0 ' + W + ' ' + H).attr('role', 'img').attr('aria-label', 'Income to profit bridge');
  let run = 0; const bars = items.map((it) => { if (it.total) { const b = {...it, a: 0, b: it.v}; run = it.v; return b; } const b = {...it, a: run, b: run + it.v}; run += it.v; return b; });
  const hi = Math.max(1, d3.max(bars, (b) => Math.max(b.a, b.b))), lo = Math.min(0, d3.min(bars, (b) => Math.min(b.a, b.b))), y = d3.scaleLinear([lo, hi], [H - mb, mt]), x = d3.scaleBand(d3.range(bars.length), [8, W - 8]).padding(0.3);
  svg.append('line').attr('x1', 8).attr('x2', W - 8).attr('y1', y(0)).attr('y2', y(0)).style('stroke', 'var(--axis)');
  bars.forEach((b, k) => { const y0 = y(Math.max(b.a, b.b)), y1 = y(Math.min(b.a, b.b));
    svg.append('rect').attr('x', x(k)).attr('y', y0).attr('width', x.bandwidth()).attr('height', Math.max(1, y1 - y0)).attr('fill', b.color).attr('opacity', b.est ? 0.55 : 1).attr('rx', 3);
    svg.append('text').attr('class', 'lbl').attr('x', x(k) + x.bandwidth() / 2).attr('y', y0 - 5).attr('text-anchor', 'middle').text(money(b.v));
    svg.append('text').attr('class', 'tick').attr('x', x(k) + x.bandwidth() / 2).attr('y', H - 26).attr('text-anchor', 'middle').text(b.l1); svg.append('text').attr('class', 'tick').attr('x', x(k) + x.bandwidth() / 2).attr('y', H - 12).attr('text-anchor', 'middle').text(b.l2 || ''); });
  return box;
}
function weekChart(m) {
  const mp = new Map(); for (let i = 0; i < NP; i++) { if (!m[i] || pdate[i] <= 0) continue; const w = wkStart(pdate[i]); const e = mp.get(w) || {w, inc: 0, exp: 0}; e.inc += pinc[i]; e.exp += pexp[i]; mp.set(w, e); }
  const data = [...mp.values()].sort((a, b) => a.w - b.w), box = h('div', {class: 'trend'}); if (!data.length) { box.append(emptyNote()); return box; }
  const W = Math.max(280, Math.round(($('page').clientWidth || 900) - 40)), H = 240, mt = 20, mb = 28, ymax = d3.max(data, (d) => Math.max(d.inc, d.exp)) || 1;
  const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', '0 0 ' + W + ' ' + H).attr('role', 'img').attr('aria-label', 'Income and expense by week');
  const y = d3.scaleLinear([0, ymax], [H - mb, mt]).nice(4), ticks = y.ticks(4); const probe = svg.append('text').attr('class', 'tick').text(money(d3.max(ticks))); const ml = Math.ceil(probe.node().getComputedTextLength()) + 12; probe.remove();
  const x = d3.scaleBand(data.map((d) => d.w), [ml, W - 8]).padding(0.25), bw = x.bandwidth() / 2, tip = h('div', {class: 'tip', hidden: true}); box.append(tip);
  ticks.forEach((t) => { svg.append('line').attr('x1', ml).attr('x2', W - 8).attr('y1', y(t)).attr('y2', y(t)).style('stroke', 'var(--grid)'); svg.append('text').attr('class', 'tick').attr('x', ml - 6).attr('y', y(t)).attr('text-anchor', 'end').attr('dominant-baseline', 'middle').text(money(t)); });
  data.forEach((d) => {
    svg.append('rect').attr('x', x(d.w)).attr('y', y(d.inc)).attr('width', bw).attr('height', Math.max(0, H - mb - y(d.inc))).attr('fill', '#4c78a8').attr('rx', 2);
    svg.append('rect').attr('x', x(d.w) + bw).attr('y', y(d.exp)).attr('width', bw).attr('height', Math.max(0, H - mb - y(d.exp))).attr('fill', '#f58518').attr('rx', 2);
    svg.append('text').attr('class', 'tick').attr('x', x(d.w) + x.bandwidth() / 2).attr('y', H - 8).attr('text-anchor', 'middle').text(fDM(d.w));
    svg.append('rect').attr('x', x(d.w)).attr('y', mt).attr('width', x.bandwidth()).attr('height', H - mt - mb).attr('fill', 'transparent')
      .on('mousemove', (ev) => { const b = box.getBoundingClientRect(); tip.replaceChildren(h('div', {class: 'tip-h'}, 'Week of ' + fDay(d.w)), h('div', null, 'Income: ' + money(d.inc)), h('div', null, 'Expense: ' + money(d.exp)), h('div', null, 'Profit: ' + money(d.inc - d.exp) + ' · ' + fMargin(marginOf(d.inc, d.exp)))); tip.hidden = false;
        const tw = tip.offsetWidth; let l = ev.clientX - b.left + 12; if (l + tw > b.width) l = ev.clientX - b.left - tw - 12; tip.style.left = Math.max(0, l) + 'px'; tip.style.top = Math.max(0, ev.clientY - b.top - 70) + 'px'; })
      .on('mouseleave', () => { tip.hidden = true; }).on('click', () => { S.rel = null; S.from = d.w; S.to = d.w + 6; renderAll(); }).style('cursor', 'pointer');
  });
  box.append(h('div', {class: 'legend'}, h('span', {class: 'lg static'}, h('i', {class: 'sw', style: 'background:#4c78a8'}), 'Income'), h('span', {class: 'lg static'}, h('i', {class: 'sw', style: 'background:#f58518'}), 'Expense')));
  return box;
}
function pExpectedByLob(m) {
  const seenJ = new Set(), ratio = new Map(); let ti = 0, te = 0;
  for (let i = 0; i < NP; i++) { const j = pjob[i]; if (!seenJ.has(j)) { seenJ.add(j); if (pjExp[j] > 0 && pjInc[j] > 0) { const l = COLS.p_lob.pc[i], r = ratio.get(l) || [0, 0]; r[0] += pjInc[j]; r[1] += pjExp[j]; ratio.set(l, r); ti += pjInc[j]; te += pjExp[j]; } } }
  const all = ti ? te / ti : 0, rows = new Map(), done = new Set();
  for (const e of pbyJob(m)) { if (COLS.jobstatus.pc[e.i0] !== 1 || done.has(e.j)) continue; done.add(e.j); const l = COLS.p_lob.pc[e.i0], r = ratio.get(l), rt = r && r[0] > 0 ? r[1] / r[0] : all, o = rows.get(l) || {lob: COLS.p_lob.d[l], ratio: rt, jobs: 0, inc: 0, est: 0}; o.jobs++; o.inc += e.inc; o.est += e.inc * rt; rows.set(l, o); }
  const list = [...rows.values()].sort((a, b) => b.inc - a.inc); return {rows: list, est: d3.sum(list, (r) => r.est), inc: d3.sum(list, (r) => r.inc), jobs: d3.sum(list, (r) => r.jobs), overall: all};
}

function ppOverview() {
  const t = R.t, tp = R.tp, on = S.compare, dd = (a, b) => (on ? pctChange(a, b) : null), ex = pExpectedByLob(R.M), cov = t.jobs ? t.booked / t.jobs : 1;
  const stat = groupByP('jobstatus', maskP({skip: 'jobstatus'})), st = (n) => stat.find((r) => r.label === n) || {jobs: 0, inc: 0, exp: 0, profit: 0};
  const ptsDelta = t.margin != null && tp.margin != null && on ? (t.margin >= tp.margin ? '+' : '−') + ((Math.abs(t.margin - tp.margin)) * 100).toFixed(1) + ' pts vs ' + cmpLabel() : null;
  const kp = [kpi('Income', money(t.inc), dd(t.inc, tp.inc), 'Income recorded in Job Profit Analysis Report', '', money(tp.inc)), kpi('Expense', money(t.exp), dd(t.exp, tp.exp), 'Costs booked so far', '', money(tp.exp)), kpi('Profit', money(t.profit), dd(t.profit, tp.profit), 'Income minus expense', t.profit < 0 ? 'bad' : '', money(tp.profit)),
    h('div', {class: 'card kpi'}, h('div', {class: 'kl'}, 'Margin'), h('div', {class: 'kv'}, fMargin(t.margin)), ptsDelta ? h('div', {class: 'delta flat'}, ptsDelta) : null, h('div', {class: 'kn'}, 'Profit as a share of income'), businessMeaning('Margin', 'Profit divided by income for the selected job summaries')),
    kpi('Jobs', fInt(t.jobs), dd(t.jobs, tp.jobs), 'With at least one line', '', fInt(tp.jobs)), kpi('Profit per job', t.jobs ? money(t.profit / t.jobs) : '–', null, 'Average over these jobs'),
    kpi('Jobs with cost booked', t.jobs ? fP0(cov) : '–', null, t.booked + ' of ' + t.jobs + ' jobs', cov * 100 < S.def.costCoverage ? 'warn' : ''),
    kpi('Profit after expected costs', money(t.profit - ex.est), null, 'Estimate: unbooked jobs get the cost ratio of booked jobs', 'warn')];
  const banner = t.jobs && cov * 100 < S.def.costCoverage ? h('div', {class: 'card warnbar'}, h('b', null, 'Margins are probably too high. '), 'Costs are booked on only ' + t.booked + ' of ' + t.jobs + ' jobs (' + fP0(cov) + '), so ' + fInt(ex.jobs) + ' jobs worth ' + money(ex.inc) + ' of income show no cost at all. If they cost what similar booked jobs cost, profit would be about ' + money(t.profit - ex.est) + ', not ' + money(t.profit) + '. ',
    h('button', {type: 'button', class: 'btn', onclick: () => setOnly('jobstatus', 1)}, 'Show those jobs')) : null;
  const comp = groupByP('company', maskP({skip: 'company'})).sort((a, b) => b.profit - a.profit), cs = S.sel.company || new Set();
  const compTbl = h('div', {class: 'scroll'}, h('table', {class: 'tbl'}, h('thead', null, h('tr', null, ['Company', 'Income', 'Expense', 'Profit', 'Margin', 'Jobs'].map((x, k) => h('th', {class: k ? 'n' : ''}, x)))),
    h('tbody', null, comp.map((r) => h('tr', {class: 'click' + (cs.has(r.g) ? ' on' : ''), onclick: () => toggle('company', r.g)}, h('td', null, r.label), h('td', {class: 'n'}, money(r.inc)), h('td', {class: 'n'}, money(r.exp)), h('td', {class: 'n ' + (r.profit < 0 ? 'bad' : '')}, money(r.profit)), h('td', {class: 'n'}, fMargin(r.margin)), h('td', {class: 'n'}, fInt(r.jobs)))))));
  const bandRows = groupByP('band', maskP({skip: 'band'})), bs = S.sel.band || new Set(), bmx = Math.max(...bandRows.map((r) => r.jobs), 1);
  const bands = bandRows.length ? h('div', {class: 'rank'}, COLS.band.d.map((n, g) => bandRows.find((r) => r.g === g)).filter(Boolean).map((r) => h('button', {type: 'button', class: 'row' + (bs.has(r.g) ? ' on' : ''), onclick: () => toggle('band', r.g)}, h('span', {class: 'lab'}, r.label),
    h('span', {class: 'track'}, h('span', {class: 'fill', style: 'width:' + (r.jobs / bmx * 100) + '%;background:' + (r.g === 0 ? 'var(--bad)' : r.g >= 5 ? 'var(--warn)' : '#4c78a8')})), h('span', {class: 'val'}, fInt(r.jobs) + ' jobs · ' + money(r.profit))))) : emptyNote();
  const bridge = bridgeChart([{l1: 'Income', v: t.inc, total: true, color: '#4c78a8'}, {l1: 'Expense', l2: 'booked', v: -t.exp, color: '#f58518'}, {l1: 'Profit', l2: 'as booked', v: t.profit, total: true, color: '#1a7f4b'}, {l1: 'Expected', l2: 'unbooked cost', v: -ex.est, color: '#f58518', est: true}, {l1: 'Estimated', l2: 'profit', v: t.profit - ex.est, total: true, color: '#1a7f4b', est: true}]);
  return h('div', null, banner, h('div', {class: 'kpis'}, kp), h('div', {class: 'grid'},
    card('From income to profit', 'The pale bars are an estimate of costs still to be booked.', bridge), card('By company', 'Click a company to filter everything.', compTbl),
    card('Income and expense by week', 'By ' + 'job date' + '. Click a week to zoom in.', weekChart(R.M), 'full'),
    card('Top ' + S.def.topN + ' branches', 'Ranked by ' + S.rank + '. Click to filter.', pkeyRank('branch', {color: '#4c78a8'})), card('Top ' + S.def.topN + ' lines of business', 'Click to filter.', pkeyRank('p_lob', {color: '#54a24b'})),
    card('Top ' + S.def.topN + ' customers', 'Click to filter.', pkeyRank('customer', {color: '#b279a2'})), card('Top ' + S.def.topN + ' sales people', 'Profit by the ERP Sales Person. Job report values take priority; a unique register match is a fallback for omitted columns. Click to filter.', pkeyRank('x_salesperson', {color: '#72b7b2'})), card('Top ' + S.def.topN + ' trade lanes', 'From the register. Click to filter.', pkeyRank('x_tradelanename', {color: '#e45756'})), card('How healthy are the jobs?', 'Jobs by margin band. Click a band to filter.', bands)));
}
function ppBranches() {
  const m = maskP({skip: ['company', 'branch']}), NB = COLS.branch.d.length, rows = groupByP((i) => pco[i] * NB + COLS.branch.pc[i], m, 2 * NB, (g) => COLS.branch.d[g % NB]).map((r) => Object.assign(r, {co: Math.floor(r.g / NB), br: r.g % NB}));
  const totalP = d3.sum(rows, (r) => r.profit), selB = S.sel.branch || new Set(), selC = S.sel.company || new Set(), isSel = (r) => selB.has(r.br) && selC.has(r.co) && selB.size === 1 && selC.size === 1;
  const booked = new Map(); for (let i = 0; i < NP; i++) if (m[i] && pexp[i] > 0) { const k = pco[i] * NB + COLS.branch.pc[i]; (booked.get(k) || booked.set(k, new Set()).get(k)).add(pjob[i]); }
  rows.forEach((r) => { r.booked = booked.has(r.g) ? booked.get(r.g).size : 0; });
  const pick = (r) => { if (isSel(r)) { delete S.sel.branch; delete S.sel.company; renderAll(); } else setMany({company: r.co, branch: r.br}); };
  const order = [0, 1].map((c) => ({c, rows: rows.filter((r) => r.co === c).sort((a, b) => b.profit - a.profit), p: d3.sum(rows.filter((r) => r.co === c), (r) => r.profit)})).sort((a, b) => b.p - a.p).filter((o) => o.rows.length);
  const trs = []; order.forEach((o) => { const T = {inc: d3.sum(o.rows, (r) => r.inc), exp: d3.sum(o.rows, (r) => r.exp), jobs: d3.sum(o.rows, (r) => r.jobs), bk: d3.sum(o.rows, (r) => r.booked)};
    trs.push(h('tr', {class: 'totrow'}, h('td', null, COMP[o.c] + ' (all branches)'), h('td', {class: 'n'}, money(T.inc)), h('td', {class: 'n'}, money(T.exp)), h('td', {class: 'n'}, money(T.inc - T.exp)), h('td', {class: 'n'}, fMargin(marginOf(T.inc, T.exp))), h('td', {class: 'n'}, fInt(T.jobs)), h('td', {class: 'n'}, T.jobs ? money((T.inc - T.exp) / T.jobs) : '–'), h('td', {class: 'n'}, totalP ? fS((T.inc - T.exp) / totalP) : '–'), h('td', {class: 'n'}, T.jobs ? fP0(T.bk / T.jobs) : '–')));
    o.rows.forEach((r) => trs.push(h('tr', {class: 'click' + (isSel(r) ? ' on' : ''), onclick: () => pick(r)}, h('td', {style: 'padding-left:1.4rem'}, r.label), h('td', {class: 'n'}, money(r.inc)), h('td', {class: 'n'}, money(r.exp)), h('td', {class: 'n ' + (r.profit < 0 ? 'bad' : '')}, money(r.profit)), h('td', {class: 'n'}, fMargin(r.margin)), h('td', {class: 'n'}, fInt(r.jobs)), h('td', {class: 'n'}, r.jobs ? money(r.profit / r.jobs) : '–'), h('td', {class: 'n'}, totalP ? fS(r.profit / totalP) : '–'), h('td', {class: 'n ' + (r.jobs && r.booked / r.jobs * 100 < S.def.costCoverage ? 'warnt' : '')}, r.jobs ? fP0(r.booked / r.jobs) : '–')))); });
  const exportB = () => { const list = order.flatMap((o) => o.rows), n = list.length + 1;
    downloadXlsx('branch_profit_' + fIso(dDate(MAXDATE)) + '.xlsx', [{name: 'Branch profit', freeze: true, filter: true, cols: [24, 22, 16, 16, 16, 12, 10, 16, 14, 16], rows: [['Company', 'Branch', 'Income', 'Expense', 'Profit', 'Margin', 'Jobs', 'Profit per job', 'Share of total profit', 'Jobs with cost booked'].map(HDR)]
      .concat(list.map((r, i) => { const x = i + 2; return [COMP[r.co], r.label, {v: +r.inc.toFixed(2), s: 3}, {v: +r.exp.toFixed(2), s: 3}, {f: 'C' + x + '-D' + x, s: 3}, {f: 'IF(C' + x + '<=0,"",E' + x + '/C' + x + ')', s: 2}, {v: r.jobs, s: 3}, {f: 'IF(G' + x + '=0,"",E' + x + '/G' + x + ')', s: 3}, {f: 'IF(SUM(E$2:E$' + n + ')=0,"",E' + x + '/SUM(E$2:E$' + n + '))', s: 2}, {v: r.booked, s: 3}]; }))
      .concat([[HDR('Total'), '', {f: 'SUM(C2:C' + n + ')', s: 3}, {f: 'SUM(D2:D' + n + ')', s: 3}, {f: 'SUM(E2:E' + n + ')', s: 3}, {f: 'IF(C' + (n + 1) + '<=0,"",E' + (n + 1) + '/C' + (n + 1) + ')', s: 2}, {f: 'SUM(G2:G' + n + ')', s: 3}]])}, settingsSheet()]); };
  // grouped bars: profit by branch, one bar per company
  const brs = [...new Set(rows.map((r) => r.br))].map((b) => ({b, ng: (rows.find((r) => r.br === b && r.co === 0) || {profit: 0}).profit, ncs: (rows.find((r) => r.br === b && r.co === 1) || {profit: 0}).profit})).sort((a, c) => (c.ng + c.ncs) - (a.ng + a.ncs));
  const chart = h('div', {class: 'trend'}); if (!brs.length) chart.append(emptyNote()); else {
    const W = Math.max(280, Math.round(($('page').clientWidth || 900) / (window.innerWidth > 900 ? 2 : 1) - 50)), H = 260, mt = 18, mb = 54, ymax = Math.max(1, d3.max(brs, (d) => Math.max(d.ng, d.ncs))), ymin = Math.min(0, d3.min(brs, (d) => Math.min(d.ng, d.ncs)));
    const svg = d3.select(chart).append('svg').attr('width', '100%').attr('viewBox', '0 0 ' + W + ' ' + H).attr('role', 'img').attr('aria-label', 'Profit by branch, New Globe against Neutral Consolidation');
    const y = d3.scaleLinear([ymin, ymax], [H - mb, mt]).nice(4), ticks = y.ticks(4); const probe = svg.append('text').attr('class', 'tick').text(money(d3.max(ticks))); const ml = Math.ceil(probe.node().getComputedTextLength()) + 12; probe.remove();
    const x = d3.scaleBand(brs.map((d) => d.b), [ml, W - 8]).padding(0.2), bw = x.bandwidth() / 2;
    ticks.forEach((t) => { svg.append('line').attr('x1', ml).attr('x2', W - 8).attr('y1', y(t)).attr('y2', y(t)).style('stroke', 'var(--grid)'); svg.append('text').attr('class', 'tick').attr('x', ml - 6).attr('y', y(t)).attr('text-anchor', 'end').attr('dominant-baseline', 'middle').text(money(t)); });
    brs.forEach((d) => { [[d.ng, 0, '#4c78a8'], [d.ncs, 1, '#f58518']].forEach(([v, c, col]) => { if (!v && !rows.find((r) => r.br === d.b && r.co === c)) return; const r0 = rows.find((r) => r.br === d.b && r.co === c);
        svg.append('rect').attr('x', x(d.b) + c * bw).attr('y', Math.min(y(v), y(0))).attr('width', bw).attr('height', Math.abs(y(v) - y(0))).attr('fill', col).attr('rx', 2).style('cursor', 'pointer').on('click', () => {if(r0){pick(r0);window.MetricTrace?.open('profit.gp','Selected company and branch');}}).append('title').text(COMP[c] + ' · ' + COLS.branch.d[d.b] + ': ' + money(v)); });
      const lab = COLS.branch.d[d.b]; svg.append('text').attr('class', 'tick').attr('x', x(d.b) + x.bandwidth() / 2).attr('y', H - 34).attr('text-anchor', 'middle').text(lab.length > 11 ? lab.slice(0, 10) + '…' : lab); });
    chart.append(h('div', {class: 'legend'}, h('span', {class: 'lg static'}, h('i', {class: 'sw', style: 'background:#4c78a8'}), 'New Globe'), h('span', {class: 'lg static'}, h('i', {class: 'sw', style: 'background:#f58518'}), 'Neutral Consolidation'))); }
  // branch x line of business heat grid
  const NL = COLS.p_lob.d.length, hm = groupByP((i) => COLS.branch.pc[i] * NL + COLS.p_lob.pc[i], maskP({skip: ['branch', 'p_lob']}), NB * NL, () => ''), hmx = Math.max(...hm.map((r) => Math.abs(r.profit)), 1);
  const bUse = [...new Set(hm.map((r) => Math.floor(r.g / NL)))].sort((a, b) => d3.sum(hm.filter((r) => Math.floor(r.g / NL) === b), (r) => r.profit) - d3.sum(hm.filter((r) => Math.floor(r.g / NL) === a), (r) => r.profit)), lUse = [...new Set(hm.map((r) => r.g % NL))].sort((a, b) => d3.sum(hm.filter((r) => r.g % NL === b), (r) => r.profit) - d3.sum(hm.filter((r) => r.g % NL === a), (r) => r.profit));
  const heat = h('div', {class: 'scroll'}, h('table', {class: 'tbl heat'}, h('thead', null, h('tr', null, h('th', null, 'Branch'), lUse.map((l) => h('th', {class: 'n'}, COLS.p_lob.d[l].replace('FFWD ', 'F ').replace('CCL ', 'C '))))),
    h('tbody', null, bUse.map((b) => h('tr', null, h('td', null, COLS.branch.d[b]), lUse.map((l) => { const r = hm.find((x) => x.g === b * NL + l); return h('td', {class: 'n hc', title: r ? COLS.branch.d[b] + ' · ' + COLS.p_lob.d[l] + ': profit ' + money(r.profit) + ', margin ' + fMargin(r.margin) : '', style: r ? 'background:' + colour(r.profit, hmx) : '', onclick: () => {if(r){setMany({branch:b,p_lob:l});window.MetricTrace?.open('profit.gp','Selected branch and LOB');}}}, r ? money(r.profit) : ''); }))))));
  return h('div', null, h('div', {class: 'grid'}, card('Profit by branch', 'Every branch of both companies. Profit is income minus the costs booked so far; the last column shows how many jobs have a cost booked (a low figure means the margin is flattering). Click a row or bar to filter.', h('div', null, h('div', {class: 'frow'}, dlButton('Download Excel', exportB)),
      h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, h('thead', null, h('tr', null, ['Branch', 'Income', 'Expense', 'Profit', 'Margin', 'Jobs', 'Profit per job', 'Share of profit', 'Jobs with cost booked'].map((x, k) => h('th', {class: k ? 'n' : ''}, x)))), h('tbody', null, trs)))), 'full'),
    card('New Globe against Neutral Consolidation', 'Profit by branch. Click a bar to filter to that company and branch.', chart), card('Branch by line of business', 'Profit in each combination. Click a cell to filter.', heat)));
}
function ppCustomers() {
  const m = maskP({skip: 'customer'}), rows = groupByP('customer', m), sel = S.sel.customer || new Set(), tot = d3.sum(rows, (r) => r.profit), st = S.pcust;
  const sorted = rows.slice().sort((a, b) => b.profit - a.profit); let cum = 0, n80 = 0; const pos = d3.sum(rows.filter((r) => r.profit > 0), (r) => r.profit);
  sorted.forEach((r) => { if (r.profit > 0 && cum < 0.8 * pos) { cum += r.profit; n80++; } });
  const top1 = sorted[0], cols = [{k: 'label', t: 'Customer'}, {k: 'inc', t: 'Income', num: true}, {k: 'exp', t: 'Expense', num: true}, {k: 'profit', t: 'Profit', num: true}, {k: 'margin', t: 'Margin', num: true}, {k: 'jobs', t: 'Jobs', num: true}, {k: 'share', t: 'Share of profit', num: true}];
  rows.forEach((r) => { r.share = tot > 0 ? r.profit / tot : null; });
  const thead = h('thead'), tbody = h('tbody'), note = h('p', {class: 'note'}), draw = () => { const f = st.sort === 'label' ? (a, b) => a.label.localeCompare(b.label) : (a, b) => (a[st.sort] == null ? -1e18 : a[st.sort]) - (b[st.sort] == null ? -1e18 : b[st.sort]); const list = rows.slice().sort((a, b) => f(a, b) * st.dir), shown = list.slice(0, S.def.tableRows);
    thead.replaceChildren(sortHead(cols, st, draw)); tbody.replaceChildren(...shown.map((r) => h('tr', {class: 'click' + (sel.has(r.g) ? ' on' : ''), onclick: () => toggle('customer', r.g)}, h('td', null, r.label), h('td', {class: 'n'}, money(r.inc)), h('td', {class: 'n'}, money(r.exp)), h('td', {class: 'n ' + (r.profit < 0 ? 'bad' : '')}, money(r.profit)), h('td', {class: 'n'}, fMargin(r.margin)), h('td', {class: 'n'}, fInt(r.jobs)), h('td', {class: 'n'}, r.share == null ? '–' : fS(r.share)))));
    note.textContent = 'Showing ' + shown.length + ' of ' + fInt(list.length) + ' customers. Click a header to sort, a row to filter.'; }; draw();
  const exportC = () => { const list = rows.slice().sort((a, b) => b.profit - a.profit), n = list.length + 1;
    downloadXlsx('customer_profit_' + fIso(dDate(MAXDATE)) + '.xlsx', [{name: 'Customer profit', freeze: true, filter: true, cols: [46, 16, 16, 16, 12, 10, 16], rows: [['Customer', 'Income', 'Expense', 'Profit', 'Margin', 'Jobs', 'Share of total profit'].map(HDR)].concat(list.map((r, i) => { const x = i + 2; return [r.label, {v: +r.inc.toFixed(2), s: 3}, {v: +r.exp.toFixed(2), s: 3}, {f: 'B' + x + '-C' + x, s: 3}, {f: 'IF(B' + x + '<=0,"",D' + x + '/B' + x + ')', s: 2}, {v: r.jobs, s: 3}, {f: 'IF(SUM(D$2:D$' + n + ')=0,"",D' + x + '/SUM(D$2:D$' + n + '))', s: 2}]; }))}, settingsSheet()]); };
  // income against margin, bubble = profit
  const sc = h('div', {class: 'trend'}), pts = rows.slice().sort((a, b) => b.inc - a.inc).slice(0, 60).filter((r) => r.margin != null);
  if (!pts.length) sc.append(emptyNote()); else { const W = Math.max(280, Math.round(($('page').clientWidth || 900) / (window.innerWidth > 900 ? 2 : 1) - 50)), H = 280, ml = 46, mr = 12, mt = 14, mb = 34, svg = d3.select(sc).append('svg').attr('width', '100%').attr('viewBox', '0 0 ' + W + ' ' + H).attr('role', 'img').attr('aria-label', 'Customers by income and margin');
    const x = d3.scaleLinear([0, d3.max(pts, (r) => r.inc) || 1], [ml, W - mr]).nice(), y = d3.scaleLinear([Math.min(0, d3.min(pts, (r) => r.margin)), 1], [H - mb, mt]).nice(), rad = d3.scaleSqrt([0, d3.max(pts, (r) => Math.abs(r.profit)) || 1], [3, 16]);
    x.ticks(4).forEach((t) => { svg.append('text').attr('class', 'tick').attr('x', x(t)).attr('y', H - 16).attr('text-anchor', 'middle').text(money(t)); }); y.ticks(5).forEach((t) => { svg.append('line').attr('x1', ml).attr('x2', W - mr).attr('y1', y(t)).attr('y2', y(t)).style('stroke', 'var(--grid)'); svg.append('text').attr('class', 'tick').attr('x', ml - 6).attr('y', y(t)).attr('text-anchor', 'end').attr('dominant-baseline', 'middle').text(Math.round(t * 100) + '%'); });
    svg.append('text').attr('class', 'tick').attr('x', W / 2).attr('y', H - 2).attr('text-anchor', 'middle').text('Income'); svg.append('text').attr('class', 'tick').attr('transform', 'rotate(-90)').attr('x', -H / 2).attr('y', 11).attr('text-anchor', 'middle').text('Margin');
    pts.forEach((r) => svg.append('circle').attr('cx', x(r.inc)).attr('cy', y(r.margin)).attr('r', rad(Math.abs(r.profit))).attr('fill', r.profit < 0 ? '#c2362b' : '#4c78a8').attr('opacity', sel.size && !sel.has(r.g) ? 0.25 : 0.65).style('cursor', 'pointer').on('click', () => {toggle('customer',r.g);window.MetricTrace?.openCategory('profit.gp','customer',r.g);}).append('title').text(r.label + ': income ' + money(r.inc) + ', profit ' + money(r.profit) + ', margin ' + fMargin(r.margin))); }
  return h('div', null, h('div', {class: 'kpis'}, kpi('Customers', fInt(rows.length), null, 'With at least one line'), kpi('Customers making 80% of profit', fInt(n80), null, 'Of those with a positive profit'), kpi('Biggest customer', top1 ? fS(top1.profit / (tot || 1)) : '–', null, top1 ? top1.label : ''), kpi('Loss-making customers', fInt(rows.filter((r) => r.profit < 0).length), null, 'Profit below zero in this selection', 'bad')),
    h('div', {class: 'grid', style: 'margin-top:.9rem'}, card('Customers', null, h('div', null, h('div', {class: 'frow'}, dlButton('Download Excel', exportC)), note, h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, thead, tbody))), 'full'),
      card('Income against margin', 'Each bubble is a customer (largest 60 by income); size is profit, red is a loss. Customers high on the right and low on the chart earn little on big volumes. Click to filter.', sc, 'full')));
}
function ppJobs() {
  const jobs = pbyJob(R.M), st = S.jobs, q = h('input', {type: 'search', class: 'q', placeholder: 'Search job, customer, branch…', 'aria-label': 'Search jobs', value: st.q}), note = h('p', {class: 'note'}), thead = h('thead'), tbody = h('tbody'), sels = S.sel.jobstatus || new Set();
  const cols = [{k: 'company', t: 'Company'}, {k: 'branch', t: 'Branch'}, {k: 'p_lob', t: 'Line'}, {k: 'p_job', t: 'Job'}, {k: 'customer', t: 'Customer'}, {k: 'inc', t: 'Income', num: true}, {k: 'exp', t: 'Expense', num: true}, {k: 'profit', t: 'Profit', num: true}, {k: 'margin', t: 'Margin', num: true}, {k: 'lines', t: 'Lines', num: true}, {k: 'status', t: 'Status'}];
  let last = []; const draw = () => { const needle = st.q.trim().toLowerCase(), list = jobs.filter((e) => !needle || (e.job + ' ' + e.customer + ' ' + e.branch + ' ' + e.lob).toLowerCase().includes(needle));
    const f = ['company', 'branch', 'p_lob', 'p_job', 'customer'].includes(st.sort) ? (a, b) => String(a[st.sort] === a.company ? COMP[a.company] : a[st.sort]).localeCompare(String(b[st.sort] === b.company ? COMP[b.company] : b[st.sort])) : st.sort === 'status' ? (a, b) => a.status - b.status : (a, b) => (a[st.sort] == null ? -1e18 : a[st.sort]) - (b[st.sort] == null ? -1e18 : b[st.sort]);
    list.sort((a, b) => f(a, b) * st.dir); last = list; thead.replaceChildren(sortHead(cols, st, draw)); const shown = list.slice(0, S.def.jobRows);
    tbody.replaceChildren(...shown.map((e) => h('tr', {class: 'click', onclick: () => setOnly('p_job', COLS.p_job.pc[e.i0])}, h('td', null, COMP[e.company]), h('td', null, e.branch), h('td', null, e.lob), h('td', null, e.job), h('td', null, e.customer), h('td', {class: 'n'}, money(e.inc)), h('td', {class: 'n'}, money(e.exp)), h('td', {class: 'n ' + (e.profit < 0 ? 'bad' : '')}, money(e.profit)), h('td', {class: 'n'}, fMargin(e.margin)), h('td', {class: 'n'}, fInt(e.lines)), h('td', null, h('span', {class: 'pill ' + (e.status === 3 ? 'bad' : e.status ? 'warn' : 'ok')}, COLS.jobstatus.d[e.status])))));
    note.textContent = 'Showing ' + shown.length + ' of ' + fInt(list.length) + ' jobs. Click a header to sort; click a job to filter everything to it.'; };
  q.addEventListener('input', () => { st.q = q.value; draw(); }); draw();
  const exportJ = () => downloadXlsx('jobs_' + fIso(dDate(MAXDATE)) + '.xlsx', [{name: 'Jobs', freeze: true, filter: true, cols: [24, 18, 16, 16, 44, 16, 16, 16, 12, 8, 18], rows: [['Company', 'Branch', 'Line', 'Job', 'Customer', 'Income', 'Expense', 'Profit', 'Margin', 'Lines', 'Status'].map(HDR)].concat(last.map((e, i) => { const x = i + 2; return [COMP[e.company], e.branch, e.lob, e.job, e.customer, {v: +e.inc.toFixed(2), s: 3}, {v: +e.exp.toFixed(2), s: 3}, {f: 'F' + x + '-G' + x, s: 3}, {f: 'IF(F' + x + '<=0,"",H' + x + '/F' + x + ')', s: 2}, {v: e.lines, s: 3}, COLS.jobstatus.d[e.status]]; }))}, settingsSheet()]);
  const fb = (g, t) => h('button', {type: 'button', class: 'btn' + (g === 'all' ? (sels.size === 0 ? ' on' : '') : sels.size === 1 && sels.has(g) ? ' on' : ''), onclick: () => { if (g === 'all') delete S.sel.jobstatus; else S.sel.jobstatus = new Set([g]); renderAll(); }}, t);
  return h('div', {class: 'grid'}, card('Jobs', 'One row per job in the current selection. Profit is income minus the costs booked so far.', h('div', null, h('div', {class: 'frow'}, q, h('div', {class: 'segs'}, fb('all', 'All jobs'), fb(3, 'Loss-making'), fb(1, 'Cost not booked'), fb(2, 'Costs booked, no income recorded'), fb(4, 'Low margin')), dlButton('Download Excel', exportJ)), note, h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, thead, tbody))), 'full'));
}
function ppQuality() {
  const m = maskP({skip: 'jobstatus'}), stat = groupByP('jobstatus', m), g = (n) => stat.find((r) => r.label === n) || {jobs: 0, inc: 0, exp: 0, profit: 0}, total = totalsP(m), jobs = pbyJob(m), ex = pExpectedByLob(m);
  const neg = []; for (let i = 0; i < NP; i++) if (m[i] && pinc[i] < 0) neg.push(i);
  const cardS = (n, idx, text, tone) => h('button', {type: 'button', class: 'card kpi clickable', onclick: () => {setOnly('jobstatus',idx);const metric={1:'profit.cost_not_booked_proxy',2:'profit.billing_pending_proxy',3:'profit.loss_making',4:'profit.low_margin'}[idx];window.MetricTrace?.open(metric,n);}}, h('div', {class: 'kl'}, n), h('div', {class: 'kv ' + (tone || '')}, fInt(g(n).jobs) + ' jobs'), h('div', {class: 'kn'}, text(g(n))));
  const list = (arr, label, val) => arr.length ? h('div', {class: 'rank'}, arr.slice(0, S.def.topN).map((e) => h('button', {type: 'button', class: 'row', onclick: () => setOnly('p_job', COLS.p_job.pc[e.i0])}, h('span', {class: 'lab', title: e.job + ' · ' + e.customer}, e.job + ' · ' + e.customer), h('span', {class: 'track'}, h('span', {class: 'fill', style: 'width:' + Math.min(100, Math.abs(val(e)) / (Math.abs(val(arr[0])) || 1) * 100) + '%;background:' + (val(e) < 0 ? 'var(--bad)' : 'var(--warn)')})), h('span', {class: 'val'}, money(val(e)))))) : h('p', {class: 'empty'}, 'None in this selection.');
  const ic = groupByP('p_ic', maskP({skip: 'p_ic'})).find((r) => r.label === 'Intercompany');
  const lobTbl = h('div', {class: 'scroll'}, h('table', {class: 'tbl'}, h('thead', null, h('tr', null, ['Line of business', 'Jobs without cost', 'Their income', 'Cost ratio on booked jobs', 'Expected cost'].map((x, k) => h('th', {class: k ? 'n' : ''}, x)))), h('tbody', null, ex.rows.map((r) => h('tr', null, h('td', null, r.lob), h('td', {class: 'n'}, fInt(r.jobs)), h('td', {class: 'n'}, money(r.inc)), h('td', {class: 'n'}, fP0(r.ratio)), h('td', {class: 'n'}, money(r.est)))), h('tr', {class: 'totrow'}, h('td', null, 'Total'), h('td', {class: 'n'}, fInt(ex.jobs)), h('td', {class: 'n'}, money(ex.inc)), h('td', {class: 'n'}, fP0(ex.overall)), h('td', {class: 'n'}, money(ex.est))))));
  return h('div', null, h('p', {class: 'meta'}, 'Profit is only as good as the costs booked. Click a card to filter every page to those jobs. The job rules (and the low-margin limit) are set under Definitions.'),
    h('div', {class: 'kpis'}, cardS('Cost not booked', 1, (r) => money(r.inc) + ' of income with no cost yet', 'warn'), cardS('Costs booked, no income recorded', 2, (r) => money(r.exp) + ' of cost with no income yet', 'warn'), cardS('Loss-making', 3, (r) => money(r.profit) + ' in total', 'bad'), cardS('Low margin', 4, (r) => 'Below ' + S.def.lowMargin + '% margin, ' + money(r.profit) + ' profit'),
      h('div', {class: 'card kpi'}, h('div', {class: 'kl'}, 'Negative income rows'), h('div', {class: 'kv'}, fInt(neg.length) + ' lines'), h('div', {class: 'kn'}, 'Income lines below zero: ' + money(d3.sum(neg, (i) => pinc[i]))), businessMeaning('Negative income rows', 'Count of selected finance rows with negative recorded income')),
      h('div', {class: 'card kpi'}, h('div', {class: 'kl'}, 'Company-name matched jobs'), h('div', {class: 'kv'}, ic ? fInt(ic.jobs) + ' jobs' : '0 jobs'), h('div', {class: 'kn'}, ic ? 'Income ' + money(ic.inc) + ', expense ' + money(ic.exp) + '. Name-based flag; group totals do not eliminate intercompany entries.' : 'None in this selection'), businessMeaning('Company-name matched jobs', 'Job count flagged by company-name matching; not an intercompany elimination'))),
    h('div', {class: 'grid', style: 'margin-top:.9rem'}, card('Expected costs on jobs with none booked', 'Each job without a cost gets the cost ratio of booked jobs in the same line of business. An estimate, to show how far the margin may fall.', lobTbl, 'full'),
      costGapCard(), card('Biggest losses', 'Jobs with the lowest profit. Click to filter.', list(jobs.filter((e) => e.profit < 0).sort((a, b) => a.profit - b.profit), 'loss', (e) => e.profit)), card('Biggest jobs with no cost booked', 'Largest income first. Click to filter.', list(jobs.filter((e) => COLS.jobstatus.pc[e.i0] === 1).sort((a, b) => b.inc - a.inc), 'income', (e) => e.inc))));
}

// ---------------------------------------------------------------- compare periods (profit)
const CMP_DIMS = ['branch', 'customer', 'x_salesperson', 'x_tradelanename', 'destination', 'origin', 'carrier', 'lane', 'job_owner', 'p_lob', 'company', 'p_mode', 'p_direction', 'p_kind', 'jobstatus'];
function scanP(m, key, pr) {
  const c = COLS[key].pc, sz = COLS[key].d.length, o = {ci: new Float64Array(sz), ce: new Float64Array(sz), pi: new Float64Array(sz), pe: new Float64Array(sz), cl: new Float64Array(sz), pl: new Float64Array(sz)}, NN = S.pdemo ? NPA : NP;
  for (let i = 0; i < NN; i++) { if (!m[i]) continue; const d = pdate[i], inC = d >= pr.cur.from && d <= pr.cur.to, inP = d >= pr.prev.from && d <= pr.prev.to; if (!inC && !inP) continue; const j = c[i]; if (inC) { o.ci[j] += pinc[i]; o.ce[j] += pexp[i]; o.cl[j]++; } if (inP) { o.pi[j] += pinc[i]; o.pe[j] += pexp[i]; o.pl[j]++; } }
  return o;
}
function ppCompare() {
  const c = S.pcmp, pr = periods(S.pcmp), root = h('div'), controls = h('div', {class: 'card', style: 'margin-bottom:.9rem'});
  const sel = (opts, val, on) => { const e = h('select', null, opts.map((o) => h('option', {value: o[0], selected: String(o[0]) === String(val)}, o[1]))); e.value = String(val); e.addEventListener('change', () => on(e.value)); return e; };
  const dateIn = (val, on) => { const e = h('input', {type: 'date', value: val == null ? '' : fIso(dDate(val)), min: '2000-01-01', max: '2099-12-31'}); e.addEventListener('change', () => { if (e.value) { on(isoD(e.value)); renderAll(); } }); return e; };
  const preset = (label, f) => h('button', {type: 'button', class: 'btn', onclick: () => { Object.assign(c, {custom: false}, f); renderAll(); }}, label);
  const prefill = () => { const keep = c.custom; c.custom = false; const p = periods(S.pcmp); c.custom = keep; if (!p.err) { c.A = Object.assign({}, p.cur); c.B = Object.assign({}, p.prev); } };
  controls.append(h('h2', {class: 'h'}, 'Variance: change in value and percentage'), h('p', {class: 'note'}, 'Profit against an earlier period, by ' + 'job date' + '. Everything follows the filters above and ignores the date range.'), h('p', {class: 'meta'}, 'Money history loaded so far: ' + D.p.meta.map((mm) => COMP[mm.co === 'NG' ? 0 : 1] + ' job dates ' + mm.range_from + ' to ' + mm.range_to).join('; ') + '. Earlier months and years appear here as soon as they are loaded. Invoice history comes separately from the shipment registers: ', h('button', {type: 'button', class: 'btn', onclick: () => goto('profit', 'p_billing')}, 'Open billing health')),
    h('div', {class: 'frow'}, h('span', {class: 'lbl2'}, 'Quick picks'), preset(FYB() ? 'This financial year vs last' : 'Year vs last year', {unit: 'year', against: 'prev'}), preset('Quarter vs last quarter', {unit: 'quarter', against: 'prev'}), preset('Month vs last month', {unit: 'month', against: 'prev'}), preset('Week vs last week', {unit: 'week', against: 'prev'}), preset('Month vs same month last year', {unit: 'month', against: 'yoy'})),
    h('div', {class: 'frow'}, h('label', {class: 'f'}, h('span', null, 'Period'), sel(UNITS, c.unit, (v) => { c.unit = v; c.custom = false; renderAll(); })), h('label', {class: 'f'}, h('span', null, 'Against'), sel([['prev', 'The period just before'], ['yoy', 'Same period last year']], c.against, (v) => { c.against = v; c.custom = false; renderAll(); })),
      h('label', {class: 'f'}, h('span', null, 'Basis'), sel([['todate', 'To date (like for like)'], ['full', 'Full period']], c.basis, (v) => { c.basis = v; renderAll(); })), h('label', {class: 'f'}, h('span', null, 'As at'), dateIn(c.anchor == null ? asOfDay() : c.anchor, (v) => { c.anchor = v; c.custom = false; })),
      h('button', {type: 'button', class: 'btn', onclick: () => { c.anchor = null; renderAll(); }}, 'Reset to as-of date'), h('label', {class: 'f'}, h('input', {type: 'checkbox', checked: c.custom, onchange: (e) => { c.custom = e.target.checked; if (c.custom) prefill(); renderAll(); }}), 'Custom date ranges')));
  if (c.custom) controls.append(h('div', {class: 'frow'}, h('span', {class: 'lbl2'}, 'Current'), dateIn(c.A.from, (v) => { c.A.from = v; }), dateIn(c.A.to, (v) => { c.A.to = v; }), h('span', {class: 'lbl2'}, 'compared with'), dateIn(c.B.from, (v) => { c.B.from = v; }), dateIn(c.B.to, (v) => { c.B.to = v; })));
  root.append(controls);
  if (pr.err) { root.append(h('div', {class: 'card'}, h('p', {class: 'empty'}, pr.err))); return root; }
  const m = maskP({dates: 'none', demo: true}), NN = S.pdemo ? NPA : NP; let ci = 0, ce = 0, pi = 0, pe = 0; const cj = new Set(), pj = new Set();
  for (let i = 0; i < NN; i++) { if (!m[i]) continue; const d = pdate[i]; if (d >= pr.cur.from && d <= pr.cur.to) { ci += pinc[i]; ce += pexp[i]; cj.add(pjob[i]); } if (d >= pr.prev.from && d <= pr.prev.to) { pi += pinc[i]; pe += pexp[i]; pj.add(pjob[i]); } }
  const meas = c.measure, mv = (a, b) => (meas === 'income' ? a : meas === 'expense' ? b : a - b), mLabel = meas === 'income' ? 'Income' : meas === 'expense' ? 'Expense' : 'Profit';
  root.append(h('div', {class: 'card', style: 'margin-bottom:.9rem'}, h('p', {class: 'take', style: 'margin:0 0 .3rem'}, pr.title + '.'), h('p', {class: 'meta', style: 'margin:0'}, 'Current: ' + (pr.curName ? pr.curName + ', ' : '') + fRange(pr.cur) + ' (' + nDays(pr.cur) + ' days)   |   Previous: ' + (pr.prevName ? pr.prevName + ', ' : '') + fRange(pr.prev) + ' (' + nDays(pr.prev) + ' days)' + (nDays(pr.cur) !== nDays(pr.prev) ? '   |   The two periods have a different number of days.' : '')),
    pj.size === 0 ? h('p', {class: 'meta', style: 'margin:.4rem 0 0;color:var(--warn)'}, 'There is no data in the comparison period. The reports loaded so far cover ' + fDay(MINDATE) + ' to ' + fDay(MAXDATE) + '. No activity is present in the uploaded comparison-period records. Upload earlier reports if needed.') : null));
  const vk = (label, cur, prev, f) => { const d = cur - prev, p = pctOf(cur, prev); return h('div', {class: 'card kpi'}, h('div', {class: 'kl'}, label), h('div', {class: 'kv'}, f(cur)), h('div', {class: 'kn'}, 'Previous ' + f(prev)), h('div', {class: 'delta ' + (d > 0 ? 'ok' : d < 0 ? 'bad' : 'flat')}, sgn(d) + f(Math.abs(d)) + ' (' + fPctS(p) + ')')); };
  const mC = marginOf(ci, ce), mP = marginOf(pi, pe), mpts = mC != null && mP != null ? (mC - mP) * 100 : null;
  root.append(h('div', {class: 'kpis'}, vk('Income', ci, pi, money), vk('Expense', ce, pe, money), vk('Profit', ci - ce, pi - pe, money), h('div', {class: 'card kpi'}, h('div', {class: 'kl'}, 'Margin'), h('div', {class: 'kv'}, fMargin(mC)), h('div', {class: 'kn'}, 'Previous ' + fMargin(mP)), mpts == null ? null : h('div', {class: 'delta ' + (mpts > 0 ? 'ok' : mpts < 0 ? 'bad' : 'flat')}, sgn(mpts) + Math.abs(mpts).toFixed(1) + ' pts'), businessMeaning('Margin', 'Current and previous period profit divided by income')), vk('Jobs', cj.size, pj.size, fInt)));
  const bk = bucketInfo(pr), bc = new Float64Array(bk.n), bp = new Float64Array(bk.n);
  for (let i = 0; i < NN; i++) { if (!m[i]) continue; const d = pdate[i], v = meas === 'income' ? pinc[i] : meas === 'expense' ? pexp[i] : pinc[i] - pexp[i]; if (d >= pr.cur.from && d <= pr.cur.to) { const b = bucketIdx(pr.unit, bk.sc, d); if (b >= 0 && b < bk.n) bc[b] += v; } if (d >= pr.prev.from && d <= pr.prev.to) { const b = bucketIdx(pr.unit, bk.sp, d); if (b >= 0 && b < bk.n) bp[b] += v; } }
  const barBox = h('div', {class: 'trend'}), info = {f: money};
  const measSel = sel([['profit', 'Profit'], ['income', 'Income'], ['expense', 'Expense']], meas, (v) => { c.measure = v; renderAll(); });
  root.append(card('Period by period: ' + mLabel.toLowerCase(), 'Each part of the period against the same part of the earlier one, with the percentage change above each pair.', barBox)); cmpChartBars(barBox, {n: bk.n, labels: bk.labels, cur: bc, prev: bp}, info);
  const key = CMP_DIMS.includes(c.dim) ? c.dim : 'branch', dm = maskP({dates: 'none', demo: true, skip: key}), sc = scanP(dm, key, pr), selSet = S.sel[key] || new Set();
  let totC = 0, totP = 0; for (let j = 0; j < sc.ci.length; j++) { totC += mv(sc.ci[j], sc.ce[j]); totP += mv(sc.pi[j], sc.pe[j]); }
  const all = []; for (let j = 0; j < sc.ci.length; j++) { if (!sc.cl[j] && !sc.pl[j] && !selSet.has(j)) continue; const cur = mv(sc.ci[j], sc.ce[j]), prev = mv(sc.pi[j], sc.pe[j]), delta = cur - prev;
    all.push({j, label: COLS[key].d[j], cur, prev, delta, adelta: Math.abs(delta), pct: prev > 0 || prev < 0 ? (cur - prev) / Math.abs(prev) : null, mcur: marginOf(sc.ci[j], sc.ce[j]), mprev: marginOf(sc.pi[j], sc.pe[j]), contrib: totP !== 0 ? delta / Math.abs(totP) : null, status: prev === 0 && cur !== 0 ? 'New' : cur === 0 && prev !== 0 ? 'Lost' : (prev !== 0 && Math.abs((cur - prev) / Math.abs(prev)) * 100 <= S.def.flatPct ? 'Flat' : delta > 0 ? 'Up' : delta < 0 ? 'Down' : 'Flat'), sel: selSet.has(j)}); }
  const show = c.show, passes = (r) => { if (show === 'up' && !(r.delta > 0)) return false; if (show === 'down' && !(r.delta < 0)) return false; if (show === 'new' && r.status !== 'New') return false; if (show === 'lost' && r.status !== 'Lost') return false;
    if (S.def.varMinBase > 0 && Math.abs(r.prev) < S.def.varMinBase) return false; if (S.def.varMinAbs > 0 && r.adelta < S.def.varMinAbs) return false; if (S.def.varMinPct > 0 && r.pct != null && Math.abs(r.pct) * 100 < S.def.varMinPct) return false; return true; };
  const rowsF = all.filter(passes), onPick = (d) => toggle(key, d.j);
  const gain = all.filter((r) => r.delta > 0).sort((a, b) => b.delta - a.delta).slice(0, S.def.topN), lose = all.filter((r) => r.delta < 0).sort((a, b) => a.delta - b.delta).slice(0, S.def.topN);
  root.append(h('div', {class: 'grid', style: 'margin:.9rem 0'}, card('Biggest increases by ' + COLS[key].l.toLowerCase(), mLabel + '. Click to filter everything.', deltaRows(gain, onPick, info)), card('Biggest decreases by ' + COLS[key].l.toLowerCase(), mLabel + '. Click to filter everything.', deltaRows(lose, onPick, info))));
  const num = (k, label, hint) => { const e = h('input', {type: 'number', min: 0, value: S.def[k], 'aria-label': label}); e.addEventListener('change', () => { S.def[k] = Math.max(0, parseFloat(e.value) || 0); saveDefs(); renderDefs(); renderAll(); }); return h('label', {class: 'f', title: hint}, h('span', null, label), e); };
  const cols = [{k: 'label', t: COLS[key].l}, {k: 'cur', t: 'Current', num: true}, {k: 'prev', t: 'Previous', num: true}, {k: 'delta', t: 'Change', num: true}, {k: 'pct', t: 'Change %', num: true}, {k: 'mcur', t: 'Margin now', num: true}, {k: 'mprev', t: 'Margin before', num: true}, {k: 'contrib', t: 'Share of total change', num: true}, {k: 'status', t: 'Trend'}];
  const thead = h('thead'), tbody = h('tbody'), note = h('p', {class: 'note'}); const draw = () => { const ts = c.tsort, f = ts.sort === 'label' || ts.sort === 'status' ? (a, b) => String(a[ts.sort]).localeCompare(String(b[ts.sort])) : (a, b) => (a[ts.sort] == null ? -1e18 : a[ts.sort]) - (b[ts.sort] == null ? -1e18 : b[ts.sort]);
    const rows = rowsF.slice().sort((a, b) => f(a, b) * ts.dir); thead.replaceChildren(sortHead(cols, ts, draw)); const shown = rows.slice(0, S.def.tableRows);
    tbody.replaceChildren(...shown.map((r) => h('tr', {class: 'click' + (r.sel ? ' on' : ''), onclick: () => onPick(r)}, h('td', null, r.label), h('td', {class: 'n'}, money(r.cur)), h('td', {class: 'n'}, money(r.prev)), h('td', {class: 'n ' + (r.delta > 0 ? 'ok' : r.delta < 0 ? 'bad' : '')}, sgn(r.delta) + money(r.adelta)), h('td', {class: 'n ' + (r.delta > 0 ? 'ok' : r.delta < 0 ? 'bad' : '')}, r.pct == null ? (r.cur ? 'new' : '–') : fPctS(r.pct)),
      h('td', {class: 'n'}, fMargin(r.mcur)), h('td', {class: 'n'}, fMargin(r.mprev)), h('td', {class: 'n'}, r.contrib == null ? '–' : sgn(r.contrib) + (Math.abs(r.contrib) * 100).toFixed(1) + ' pts'), h('td', null, h('span', {class: 'pill ' + (r.status === 'Up' || r.status === 'New' ? 'ok' : r.status === 'Down' || r.status === 'Lost' ? 'bad' : '')}, r.status)))));
    tbody.append(h('tr', {class: 'totrow'}, h('td', null, 'Total'), h('td', {class: 'n'}, money(totC)), h('td', {class: 'n'}, money(totP)), h('td', {class: 'n'}, sgn(totC - totP) + money(Math.abs(totC - totP))), h('td', {class: 'n'}, fPctS(totP !== 0 ? (totC - totP) / Math.abs(totP) : null)), h('td'), h('td'), h('td'), h('td')));
    note.textContent = 'Showing ' + shown.length + ' of ' + fInt(rows.length) + ' rows' + (rows.length < all.length ? ' (' + (all.length - rows.length) + ' hidden by the filters)' : '') + '. Click a header to sort, a row to filter everything.'; }; draw();
  const why = S.pdemo ? 'Switched off while demo history is on' : '';
  const exportXlsx = () => { const rows = rowsF.slice().sort((a, b) => b.adelta - a.adelta), n = rows.length, tr = n + 2;
    const sheet = {name: 'Variance', freeze: true, filter: true, cols: [38, 16, 16, 16, 12, 16], rows: [[HDR(COLS[key].l), HDR('Current'), HDR('Previous'), HDR('Change'), HDR('Change %'), HDR('Trend')]].concat(rows.map((r, i) => { const x = i + 2; return [r.label, {v: +r.cur.toFixed(2), s: 3}, {v: +r.prev.toFixed(2), s: 3}, {f: 'B' + x + '-C' + x, s: 3}, {f: 'IF(C' + x + '=0,"",D' + x + '/ABS(C' + x + '))', s: 2}, {f: 'IF(AND(C' + x + '=0,B' + x + '<>0),"New",IF(AND(B' + x + '=0,C' + x + '<>0),"Lost",IF(C' + x + '=0,"Flat",IF(ABS(D' + x + '/C' + x + ')<=Settings!$B$7/100,"Flat",IF(D' + x + '>0,"Up","Down")))))'}]; }))};
    sheet.rows.push([HDR('Total of rows listed'), {f: 'SUM(B2:B' + (n + 1) + ')', s: 3}, {f: 'SUM(C2:C' + (n + 1) + ')', s: 3}, {f: 'B' + tr + '-C' + tr, s: 3}, {f: 'IF(C' + tr + '=0,"",D' + tr + '/ABS(C' + tr + '))', s: 2}]);
    downloadXlsx('profit_variance_' + fIso(dDate(MAXDATE)) + '.xlsx', [sheet, settingsSheet([[HDR('Comparison'), pr.title], [HDR('Current period'), fRange(pr.cur)], [HDR('Previous period'), fRange(pr.prev)], [HDR('Flat when change within (%)'), S.def.flatPct], [HDR('Measure'), mLabel], [HDR('Rows by'), COLS[key].l]])]); };
  root.append(card('Variance by ' + COLS[key].l.toLowerCase(), 'Current against previous, in rupees and in percent.', h('div', null, h('div', {class: 'frow'}, h('label', {class: 'f'}, h('span', null, 'Measure'), measSel), h('label', {class: 'f'}, h('span', null, 'Rows by'), sel(CMP_DIMS.map((k) => [k, COLS[k].l]), key, (v) => { c.dim = v; renderAll(); })),
      h('label', {class: 'f'}, h('span', null, 'Show'), sel([['all', 'All changes'], ['up', 'Increases only'], ['down', 'Decreases only'], ['new', 'New only'], ['lost', 'Lost only']], c.show, (v) => { c.show = v; renderAll(); })), num('varMinPct', 'Change at least (%)', 'Hide rows whose percentage change is smaller than this. 0 shows all.'), num('varMinAbs', 'Change at least (₹)', 'Hide rows whose change in rupees is smaller than this.'), num('varMinBase', 'Previous at least (₹)', 'Hide rows whose previous value is below this.'), dlButton('Download Excel', exportXlsx, why)),
    note, h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, thead, tbody))), 'full'));
  return root;
}

// ================================================================ profitability explorer: every KRA by any dimension (uses the register join)
const EXP_DIMS = [
  {k: 'customer', l: 'Customer'}, {k: 'x_salesperson', l: 'Sales person'}, {k: 'branch', l: 'Branch'}, {k: 'x_tradelanename', l: 'Trade lane'}, {k: 'destination', l: 'Destination port'}, {k: 'origin', l: 'Origin port'},
  {k: 'carrier', l: 'Airline', mode: 0}, {k: 'carrier', l: 'Shipping line', mode: 1}, {k: 'lane', l: 'Lane (origin to destination)'}, {k: 'x_dischargecountry', l: 'Destination country'}, {k: 'x_loadingcountry', l: 'Origin country'},
  {k: 'job_owner', l: 'Job owner'}, {k: 'shipper', l: 'Shipper'}, {k: 'consignee', l: 'Consignee'}, {k: 'p_lob', l: 'Line of business'}, 
  {k: 'x_originagent', l: 'Origin agent'}, {k: 'consol', l: 'Consol type'}, {k: 'nomination', l: 'Nomination'}, {k: 'x_businessdimension', l: 'Business dimension'}];
S.exp = {dim: 0, sort: {sort: 'profit', dir: -1}};
function ppExplorer() {
  const ex = S.exp, d = EXP_DIMS[ex.dim] || EXP_DIMS[0], key = d.k, root = h('div');
  const m = maskP({skip: key}); if (d.mode != null) for (let i = 0; i < NP; i++) if (m[i] && !(psidx[i] >= 0 && mode[psidx[i]] === d.mode)) m[i] = 0;
  const rows = groupByP(key, m).map((r) => Object.assign(r, {ppj: r.jobs ? r.profit / r.jobs : null, ppt: r.airT > 0 ? r.airP / r.airT : null, ppe: r.seaT > 0 ? r.seaP / r.seaT : null, bk: r.jobs ? r.booked / r.jobs : null}));
  const tot = totalsP(m), totalP = d3.sum(rows, (r) => r.profit); rows.forEach((r) => { r.share = totalP > 0 ? r.profit / totalP : null; });
  const sel = S.sel[key] || new Set(), noMatch = COLS[key].d.indexOf('(no register match)');
  const quick = h('div', {class: 'segs'}, EXP_DIMS.slice(0, 9).map((q, i) => h('button', {type: 'button', class: 'btn' + (ex.dim === i ? ' on' : ''), onclick: () => { ex.dim = i; ex.sort = {sort: 'profit', dir: -1}; renderAll(); }}, q.l)));
  const more = h('select', {'aria-label': 'More dimensions'}, h('option', {value: ''}, 'More…'), EXP_DIMS.map((q, i) => (i >= 9 ? h('option', {value: i, selected: ex.dim === i}, q.l) : null)));
  more.addEventListener('change', () => { if (more.value !== '') { ex.dim = parseInt(more.value, 10); ex.sort = {sort: 'profit', dir: -1}; renderAll(); } });
  const best = rows.filter((r) => r.profit > 0).sort((a, b) => b.profit - a.profit)[0], matchedJobs = (() => { const s = new Set(), t = new Set(); for (let i = 0; i < NP; i++) if (m[i]) { t.add(pjob[i]); if (psidx[i] >= 0) s.add(pjob[i]); } return [s.size, t.size]; })();
  const airP = d3.sum(rows, (r) => r.airP), airT = d3.sum(rows, (r) => r.airT), seaP = d3.sum(rows, (r) => r.seaP), seaT = d3.sum(rows, (r) => r.seaT);
  root.append(h('div', {class: 'card', style: 'margin-bottom:.9rem'}, h('h2', {class: 'h'}, 'Profitability by ' + d.l.toLowerCase()), h('p', {class: 'note'}, 'Income, cost and profit for any angle. Job report attributes take priority. Omitted fields can use a unique company, LOB, job and date register match. Operational weight and TEU denominators use matched registers.'), h('div', {class: 'frow'}, quick, more), tot.jobs && tot.booked / tot.jobs * 100 < S.def.costCoverage ? h('p', {class: 'meta', style: 'color:var(--warn);margin:.5rem 0 0'}, 'Costs are not booked yet on many of these jobs, so margins and the per-tonne and per-TEU figures are higher than they will end up. See Profit quality.') : null));
  root.append(h('div', {class: 'kpis'}, kpi('Profit', money(tot.profit), null, 'Of the ' + fInt(rows.length) + ' ' + d.l.toLowerCase() + ' values shown'), kpi('Margin', fMargin(tot.margin), null, 'Profit over income'), kpi('Best ' + d.l.toLowerCase(), best ? money(best.profit) : '–', null, best ? best.label : ''),
    kpi('Air: profit per tonne', airT > 0 ? money(airP / airT) : '–', null, fInt(Math.round(airT)) + ' chargeable tonnes on matched air jobs'), kpi('Sea: profit per TEU', seaT > 0 ? money(seaP / seaT) : '–', null, fInt(Math.round(seaT)) + ' recorded TEUs on matched ocean jobs'), kpi('Jobs matched to the register', matchedJobs[1] ? fP0(matchedJobs[0] / matchedJobs[1]) : '–', null, matchedJobs[0] + ' of ' + matchedJobs[1] + ' jobs; customs-clearance and road jobs have no register entry')));
  const cols = [{k: 'label', t: d.l}, {k: 'inc', t: 'Income', num: true}, {k: 'exp', t: 'Expense', num: true}, {k: 'profit', t: 'Profit', num: true}, {k: 'margin', t: 'Margin', num: true}, {k: 'jobs', t: 'Jobs', num: true}, {k: 'ppj', t: 'Profit per job', num: true}, {k: 'share', t: 'Share of profit', num: true}, {k: 'ppt', t: 'Profit per air tonne', num: true}, {k: 'ppe', t: 'Profit per sea TEU', num: true}, {k: 'bk', t: 'Jobs with cost booked', num: true}];
  const thead = h('thead'), tbody = h('tbody'), note = h('p', {class: 'note'}); let last = [];
  const draw = () => { const st = ex.sort, f = st.sort === 'label' ? (a, b) => a.label.localeCompare(b.label) : (a, b) => (a[st.sort] == null ? -1e18 : a[st.sort]) - (b[st.sort] == null ? -1e18 : b[st.sort]); const list = rows.slice().sort((a, b) => f(a, b) * st.dir); last = list; const shown = list.slice(0, S.def.tableRows);
    thead.replaceChildren(sortHead(cols, st, draw));
    tbody.replaceChildren(...shown.map((r) => h('tr', {class: 'click' + (sel.has(r.g) ? ' on' : ''), onclick: () => toggle(key, r.g)}, h('td', null, r.label), h('td', {class: 'n'}, money(r.inc)), h('td', {class: 'n'}, money(r.exp)), h('td', {class: 'n ' + (r.profit < 0 ? 'bad' : '')}, money(r.profit)), h('td', {class: 'n'}, fMargin(r.margin)), h('td', {class: 'n'}, fInt(r.jobs)),
      h('td', {class: 'n'}, r.ppj == null ? '–' : money(r.ppj)), h('td', {class: 'n'}, r.share == null ? '–' : fS(r.share)), h('td', {class: 'n'}, r.ppt == null ? '–' : money(r.ppt)), h('td', {class: 'n'}, r.ppe == null ? '–' : money(r.ppe)), h('td', {class: 'n ' + (r.bk != null && r.bk * 100 < S.def.costCoverage ? 'warnt' : '')}, r.bk == null ? '–' : fP0(r.bk)))));
    note.textContent = 'Showing ' + shown.length + ' of ' + fInt(list.length) + ' rows' + (noMatch >= 0 && rows.some((r) => r.g === noMatch) ? '. “(no register match)” holds jobs with no shipment in the register (customs clearance, road and general jobs)' : '') + '. Click a header to sort, a row to filter everything.'; };
  draw();
  const exportE = () => { const list = last, n = list.length + 1, tr = n + 1;
    downloadXlsx('profitability_by_' + d.l.toLowerCase().replace(/[^a-z]+/g, '_') + '_' + fIso(dDate(MAXDATE)) + '.xlsx', [{name: 'Profitability', freeze: true, filter: true, cols: [42, 16, 16, 16, 12, 10, 16, 14, 14, 14, 16], rows: [[d.l, 'Income', 'Expense', 'Profit', 'Margin', 'Jobs', 'Profit per job', 'Share of profit', 'Air tonnes', 'Air profit', 'Profit per air tonne', 'Sea TEUs', 'Sea profit', 'Profit per sea TEU'].map(HDR)]
      .concat(list.map((r, i) => { const x = i + 2; return [r.label, {v: +r.inc.toFixed(2), s: 3}, {v: +r.exp.toFixed(2), s: 3}, {f: 'B' + x + '-C' + x, s: 3}, {f: 'IF(B' + x + '<=0,"",D' + x + '/B' + x + ')', s: 2}, {v: r.jobs, s: 3}, {f: 'IF(F' + x + '=0,"",D' + x + '/F' + x + ')', s: 3}, {f: 'IF(SUM(D$2:D$' + n + ')=0,"",D' + x + '/SUM(D$2:D$' + n + '))', s: 2}, {v: +r.airT.toFixed(3), s: 4}, {v: +r.airP.toFixed(2), s: 3}, {f: 'IF(I' + x + '=0,"",J' + x + '/I' + x + ')', s: 3}, {v: Math.round(r.seaT), s: 3}, {v: +r.seaP.toFixed(2), s: 3}, {f: 'IF(L' + x + '=0,"",M' + x + '/L' + x + ')', s: 3}]; }))
      .concat([[HDR('Total'), {f: 'SUM(B2:B' + n + ')', s: 3}, {f: 'SUM(C2:C' + n + ')', s: 3}, {f: 'SUM(D2:D' + n + ')', s: 3}, {f: 'IF(B' + tr + '<=0,"",D' + tr + '/B' + tr + ')', s: 2}, {f: 'SUM(F2:F' + n + ')', s: 3}]])}, settingsSheet([[HDR('Rows by'), d.l]])]); };
  root.append(h('div', {class: 'grid'}, card('Top ' + S.def.topN + ' by ' + S.rank, 'Ranked by ' + S.rank + '. Click a bar to filter everything.', prankList(rows, (r) => toggle(key, r.g), (r) => sel.has(r.g), {color: '#4c78a8'})),
    card('All rows', 'Profit per air tonne and per sea TEU use only jobs matched to the register: air by chargeable tonnes, sea by TEUs (full-container loads).', h('div', null, h('div', {class: 'frow'}, dlButton('Download Excel', exportE)), note, h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, thead, tbody))), 'full')));
  return root;
}
// ================================================================ profit data status (with the register join)
function ppStatus() {
  const M_ = D.p.meta; const rows = M_.map(mm => h('tr', null, h('td',null,COMP[mm.co === 'NG' ? 0 : 1]), h('td',null,mm.range_from + ' to ' + mm.range_to), h('td',null,'Job Date'), h('td',{class:'n'},fInt(mm.jobs)), h('td',{class:'n'},money(mm.income)), h('td',{class:'n'},money(mm.expense)), h('td',null,'Source totals validated at import')));
  const join = M_.map((mm) => h('tr', null, h('td', null, COMP[mm.co === 'NG' ? 0 : 1]), h('td', {class: 'n'}, fInt(mm.jobs)), h('td', {class: 'n'}, fInt(mm.matched)), h('td', {class: 'n'}, fP0(mm.matched / mm.jobs)), h('td', null, Object.entries(mm.unmatched_by_lob).map(([k, v]) => k + ': ' + v).join(' · ') || 'none')));
  const cols = h('div', {class: 'scroll'}, h('table', {class: 'tbl'}, h('thead', null, h('tr', null, h('th', null, 'Company'), h('th', null, 'Columns found in the report (any order)'))), h('tbody', null, M_.map((mm) => h('tr', null, h('td', null, COMP[mm.co === 'NG' ? 0 : 1]), h('td', null, mm.columns.join(' · ')))))));
  return h('div', {class: 'grid'}, card('Profit data status', 'Each report states its own grand total. The job records must add up to it, otherwise the file is rejected. In the live system this page also shows the last successful import time and any errors.', h('div', {class: 'scroll'}, h('table', {class: 'tbl'}, h('thead', null, h('tr', null, ['Company', 'Report covers', 'Basis', 'Jobs', 'Income', 'Expense', 'Import validation'].map((x, k) => h('th', {class: k > 2 && k < 8 ? 'n' : ''}, x)))), h('tbody', null, rows))), 'full'),
    card('Matched to the shipment register', 'Job-report attributes are used directly. A unique register match supplies missing attributes and register weights; unmatched and customs jobs retain their finance totals.', h('div', {class: 'scroll'}, h('table', {class: 'tbl'}, h('thead', null, h('tr', null, ['Company', 'Jobs', 'Matched', 'Share matched', 'Not matched, by line of business'].map((x, k) => h('th', {class: k > 0 && k < 4 ? 'n' : ''}, x)))), h('tbody', null, join))), 'full'),
    card('How the numbers are worked out', null, h('ul', {class: 'notes'},
      h('li', null, 'Each record contains the total income and expense of one job. Profit is income minus expense; margin is profit divided by income.'),
      h('li', null, 'The report contains one row per job. All finance filters and comparisons use Job Date. It includes the income and expense booked against those jobs, regardless of invoice date.'),
      h('li', null, 'Cost not booked: the job has income but no expense line yet. Costs booked, no income recorded: cost but no income. Loss-making: expense above income. Low margin: below the limit under Definitions (default 10%).'),
      h('li', null, 'Profit after expected costs is an estimate: jobs with no cost booked get the cost ratio of booked jobs in the same line of business.'),
      h('li', null, 'Profit per air tonne uses chargeable weight and profit per sea TEU uses TEUs, both from the register, for matched jobs only. Each matched job’s weight is counted once.'),
      h('li', null, 'A job is marked intercompany when its customer is the other group company; vendor-level intercompany checks are unavailable in this format. In a group view with both companies selected, such income and cost belong to both.'),
      h('li', null, 'In the live system the profit report arrives every day covering the whole year at job level, and earlier years use the same format. Each daily file replaces the lines for its dates; earlier years are never touched.'),
      h('li', null, 'Comparisons use the uploaded ERP records. A zero prior value is shown explicitly; percentage change is unavailable when the prior value is zero.')), 'full'),
    card('Columns', 'Column order does not matter, and extra columns added to the ERP report are kept and can be used as filters.', cols, 'full'));
}

// ================================================================ owner's summary and scorecard: operations and accounting side by side
const SC_DIMS = [{k: 'customer', l: 'Customer'}, {k: 'agent', l: 'Agent'}, {k: 'x_salesperson', l: 'Sales person'}, {k: 'branch', l: 'Branch'}, {k: 'x_tradelanename', l: 'Trade lane'}, {k: 'destination', l: 'Destination port'}, {k: 'origin', l: 'Origin port'},
  {k: 'carrier', l: 'Airline or shipping line'}, {k: 'lane', l: 'Lane (origin to destination)'}, {k: 'x_dischargecountry', l: 'Destination country'}, {k: 'x_loadingcountry', l: 'Origin country'}, {k: 'job_owner', l: 'Job owner'},
  {k: 'shipper', l: 'Shipper'}, {k: 'consignee', l: 'Consignee'}, {k: 'nomination', l: 'Nomination'}, {k: 'consol', l: 'Consol type'}, {k: 'x_originagent', l: 'Origin agent'}, {k: 'x_businessdimension', l: 'Business dimension'}];
S.sc = {dim: 0, sort: {sort: 'profit', dir: -1}};
function goto(group, page, extra) { if (extra) for (const k in extra) S.sel[k] = new Set([].concat(extra[k])); S.group = group; S.page = page; syncBounds(); renderAll(); window.scrollTo(0, 0); }
function opsFacts(m) {
  let n = 0, air = 0, sea = 0, openFin = 0, old = 0, lagSum = 0, lagN = 0; const cust = new Set(), age0 = OPS_MAX;
  for (let i = 0; i < N; i++) { if (!m[i]) continue; n++; if (mode[i]) sea += teus[i]; else air += chg[i]; cust.add(COLS.customer.c[i]); if (COLS.stage.c[i] === STAGE_FIN) { openFin++; if (age0 - date[i] > S.def.oldDays) old++; } if (opsD[i] > 0 && finD[i] > 0) { lagSum += finD[i] - opsD[i]; lagN++; } }
  return {n, air, sea, openFin, old, lag: lagN ? lagSum / lagN : null, cust: cust.size};
}
function monthBars(m) {
  const mp = new Map(); for (let i = 0; i < N; i++) if (m[i]) mp.set(mStart[i], (mp.get(mStart[i]) || 0) + 1);
  const data = [...mp.entries()].sort((a, b) => a[0] - b[0]), box = h('div', {class: 'trend'}); if (!data.length) { box.append(emptyNote()); return box; }
  const W = Math.max(280, Math.round(($('page').clientWidth || 900) / (window.innerWidth > 900 ? 2 : 1) - 50)), H = 230, mt = 20, mb = 28, ymax = d3.max(data, (d) => d[1]) || 1;
  const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', '0 0 ' + W + ' ' + H).attr('role', 'img').attr('aria-label', 'Shipments by month');
  const y = d3.scaleLinear([0, ymax], [H - mb, mt]).nice(4), ticks = y.ticks(4), ml = 46, x = d3.scaleBand(data.map((d) => d[0]), [ml, W - 8]).padding(0.25);
  ticks.forEach((t) => { svg.append('line').attr('x1', ml).attr('x2', W - 8).attr('y1', y(t)).attr('y2', y(t)).style('stroke', 'var(--grid)'); svg.append('text').attr('class', 'tick').attr('x', ml - 6).attr('y', y(t)).attr('text-anchor', 'end').attr('dominant-baseline', 'middle').text(fInt(t)); });
  data.forEach((d) => { svg.append('rect').attr('x', x(d[0])).attr('y', y(d[1])).attr('width', x.bandwidth()).attr('height', Math.max(0, H - mb - y(d[1]))).attr('fill', '#4c78a8').attr('rx', 3).style('cursor', 'pointer').on('click', () => { S.rel = null; S.from = Math.max(d[0], OPS_MIN); S.to = Math.min(Math.round(+d3.utcMonth.offset(dDate(d[0]), 1) / DMS) - 1, OPS_MAX); renderAll(); }).append('title').text(fMon(d[0]) + ': ' + fInt(d[1]) + ' shipments');
    svg.append('text').attr('class', 'tick').attr('x', x(d[0]) + x.bandwidth() / 2).attr('y', H - 8).attr('text-anchor', 'middle').text(d3.utcFormat('%b')(dDate(d[0]))); if (data.length <= 14) svg.append('text').attr('class', 'lbl').attr('x', x(d[0]) + x.bandwidth() / 2).attr('y', y(d[1]) - 5).attr('text-anchor', 'middle').text(fInt(d[1])); });
  return box;
}
function sOwner() {
  const M = mask(), P = mask({dates: 'prev'}), pm = maskP(), on = S.compare, dd = (a, b) => (on ? pctChange(a, b) : null), o = opsFacts(M), op = opsFacts(P), mo = opsFacts(mask({dates: 'none'})), t = R.t, tp = R.tp;
  const ex = pExpectedByLob(pm), cov = t.jobs ? t.booked / t.jobs : 1, stat = groupByP('jobstatus', maskP({skip: 'jobstatus'})), st = (n) => stat.find((r) => r.label === n) || {jobs: 0, inc: 0, exp: 0, profit: 0};
  const ptsDelta = t.margin != null && tp.margin != null && on ? (t.margin >= tp.margin ? '+' : '−') + (Math.abs(t.margin - tp.margin) * 100).toFixed(1) + ' pts vs ' + cmpLabel() : null;
  const opsK = [kpi('Shipments', fInt(o.n), dd(o.n, op.n), 'By shipment date', '', fInt(op.n)), kpi('Air chargeable weight', f1(o.air) + ' t', dd(o.air, op.air), 'Air shipments', '', f1(op.air) + ' t'), kpi('Sea TEUs', fInt(Math.round(o.sea)), dd(o.sea, op.sea), 'Recorded ocean TEUs', '', fInt(Math.round(op.sea))), kpi('Active customers', fInt(o.cust), dd(o.cust, op.cust), 'With a shipment in range', '', fInt(op.cust)),
    kpi('Financials still open', fInt(mo.openFin), null, fInt(mo.old) + ' older than ' + S.def.oldDays + ' days (ignores the date range)', mo.old ? 'warn' : ''), kpi('Days from ops lock to financial lock', mo.lag == null ? '–' : mo.lag.toFixed(1), null, 'Average, where both are recorded')];
  const accK = [kpi('Income', money(t.inc), dd(t.inc, tp.inc), 'By job date', '', money(tp.inc)), kpi('Profit', money(t.profit), dd(t.profit, tp.profit), 'Income minus booked cost', t.profit < 0 ? 'bad' : '', money(tp.profit)), h('div', {class: 'card kpi'}, h('div', {class: 'kl'}, 'Margin'), h('div', {class: 'kv'}, fMargin(t.margin)), ptsDelta ? h('div', {class: 'delta flat'}, ptsDelta) : null, h('div', {class: 'kn'}, 'Profit over income'), businessMeaning('Margin', 'Profit divided by income for selected jobs')),
    kpi('Jobs', fInt(t.jobs), dd(t.jobs, tp.jobs), 'In the profit report', '', fInt(tp.jobs)), kpi('Jobs with cost booked', t.jobs ? fP0(cov) : '–', null, t.booked + ' of ' + t.jobs, cov * 100 < S.def.costCoverage ? 'warn' : ''), kpi('Profit after expected costs', money(t.profit - ex.est), null, 'Estimate for jobs with no cost yet', 'warn')];
  // what needs attention
  const al = [], money0 = money, un = S.def.unassignedNames.split(',').map((x) => x.trim().toLowerCase()).filter(Boolean);
  if (st('Cost not booked').jobs) al.push({sev: cov * 100 < S.def.costCoverage ? 'bad' : 'warn', text: fInt(st('Cost not booked').jobs) + ' jobs worth ' + money(st('Cost not booked').inc) + ' of income have no cost booked, so profit is overstated by about ' + money(ex.est), go: () => goto('profit', 'p_quality', {jobstatus: 1}), label: 'See the jobs'});
  if (FIN) { const Mb = mask({dates: 'none'}); let late = 0; for (let i = 0; i < N; i++) if (Mb[i] && opsD[i] > 0 && invN[i] === 0 && OPS_MAX - opsD[i] > S.def.unbilledDays) late++; if (late) al.push({sev: 'warn', text: fInt(late) + ' shipments have operations locked but no invoice or billing document in the register for more than ' + S.def.unbilledDays + ' days: revenue that may still be waiting to be billed', go: () => goto('profit', 'p_billing'), label: 'See billing health'}); }
  if (FIN) { let neg = 0, give = 0; for (let i = 0; i < N; i++) if (M[i] && rtype[i] === 0 && rateOK(i) && rsell[i] < rbuy[i]) { neg++; give += rmargin(i); } if (neg) al.push({sev: 'warn', text: fInt(neg) + ' air export shipments were sold below their buy rate, giving away ' + money(Math.abs(give)), go: () => goto('profit', 'p_rates'), label: 'See rate margin'}); }
  if (mo.old) al.push({sev: 'warn', text: fInt(mo.old) + ' shipments have operations locked but financials still open after more than ' + S.def.oldDays + ' days: billing is slow', go: () => goto('ops', 'ops', {stage: STAGE_FIN}), label: 'See the worklist'});
  if (st('Loss-making').jobs) al.push({sev: 'bad', text: fInt(st('Loss-making').jobs) + ' loss-making job' + (st('Loss-making').jobs > 1 ? 's' : '') + ' costing ' + money(Math.abs(st('Loss-making').profit)), go: () => goto('profit', 'p_quality', {jobstatus: 3}), label: 'See the jobs'});
  const cu = groupByP('customer', maskP({skip: 'customer'})).sort((a, b) => b.profit - a.profit), tp1 = cu[0], totPos = d3.sum(cu.filter((r) => r.profit > 0), (r) => r.profit);
  if (tp1 && totPos > 0 && tp1.profit / totPos * 100 > S.def.ownerConc) al.push({sev: 'warn', text: tp1.label + ' alone brings ' + fP0(tp1.profit / totPos) + ' of profit (limit ' + S.def.ownerConc + '%): a risk if they leave', go: () => goto('profit', 'p_customers'), label: 'See customers'});
  const sp = groupByP('x_salesperson', maskP({skip: 'x_salesperson'})), spT = d3.sum(sp, (r) => r.profit), spU = d3.sum(sp.filter((r) => un.includes(r.label.toLowerCase()) || r.label === '(blank)'), (r) => r.profit);
  if (spT > 0 && spU / spT * 100 > S.def.unassignedShare) al.push({sev: 'warn', text: fP0(spU / spT) + ' of profit (' + money(spU) + ') is credited to “' + S.def.unassignedNames + '” or no sales person, so sales people cannot be judged', go: () => goto('profit', 'p_explorer'), label: 'See sales people'});
  const tlb = groupByP('x_tradelanename', maskP({skip: 'x_tradelanename'})), tlT = d3.sum(tlb, (r) => r.profit), tlU = d3.sum(tlb.filter((r) => r.label === '(blank)' || r.label === '(no register match)'), (r) => r.profit);
  if (tlT > 0 && tlU / tlT * 100 > S.def.unassignedShare) al.push({sev: 'info', text: fP0(tlU / tlT) + ' of profit has no trade lane recorded, which weakens lane analysis', go: () => goto('profit', 'p_explorer'), label: 'See trade lanes'});
  const dec = (() => { const a = new Float64Array(COLS.customer.d.length), b = new Float64Array(COLS.customer.d.length), mm = mask({skip: 'customer'}), pp = mask({skip: 'customer', dates: 'prev'}); for (let i = 0; i < N; i++) { if (mm[i]) a[COLS.customer.c[i]]++; if (pp[i]) b[COLS.customer.c[i]]++; } let w = null; for (let j = 0; j < a.length; j++) { const dlt = a[j] - b[j]; if (b[j] >= 10 && (!w || dlt < w.d)) w = {j, d: dlt, b: b[j], a: a[j]}; } return w; })();
  if (dec && dec.d < 0 && R.np > 0) al.push({sev: 'warn', text: COLS.customer.d[dec.j] + ' shipped ' + fInt(dec.a) + ' against ' + fInt(dec.b) + ' in the ' + cmpLabel() + ': the biggest fall among regular customers', go: () => goto('ops', 'customers'), label: 'See customers'});
  const asDay = asOfDay(), lateRanges = [...D.meta.map((mm, i) => ({n: COMP[i < 4 ? 0 : 1] + ' ' + REPN[i % 4], end: isoD(mm.range_to)})), ...D.p.meta.map((mm) => ({n: COMP[mm.co === 'NG' ? 0 : 1] + ' profit', end: isoD(mm.range_to)}))].filter((r) => asDay > r.end);
  if (lateRanges.length) al.push({sev: 'bad', text: 'The ERP date range has run out for ' + lateRanges.length + ' report' + (lateRanges.length > 1 ? 's' : '') + ' (' + lateRanges.slice(0, 3).map((r) => r.n).join(', ') + '): new shipments will stop arriving until the schedule is changed', go: () => goto('ops', 'status'), label: 'See data status'});
  const age = Math.floor(Date.now() / DMS) - OPS_MAX; if (age > 2) al.push({sev: 'info', text: 'The latest data is ' + age + ' days old (' + fDay(OPS_MAX) + ')', go: null});
  const sevIcon = {bad: '●', warn: '●', info: '●'}, alertsCard = card('What needs your attention', 'Checked against the filters above. Click “See” to jump to the detail with the right filter on. The limits are under Definitions.', al.length ? h('div', {class: 'alerts'}, al.map((a) => h('div', {class: 'alert ' + a.sev}, h('span', {class: 'dot'}, sevIcon[a.sev]), h('span', {class: 'atext'}, a.text), a.go ? h('button', {type: 'button', class: 'btn', onclick: a.go}, a.label) : null))) : h('p', {class: 'empty'}, 'Nothing needs attention in this selection.'), 'full');
  // the two companies side by side
  const cops = [0, 1].map((c) => { const mm = mask({skip: 'company'}); for (let i = 0; i < N; i++) if (comp[i] !== c) mm[i] = 0; return opsFacts(mm); }), cacc = groupByP('company', maskP({skip: 'company'}));
  const cmpTbl = h('div', {class: 'scroll'}, h('table', {class: 'tbl'}, h('thead', null, h('tr', null, ['Company', 'Shipments', 'Air tonnes', 'Sea TEUs', 'Income', 'Profit', 'Margin', 'Jobs with cost booked'].map((x, k) => h('th', {class: k ? 'n' : ''}, x)))), h('tbody', null, [0, 1].map((c) => { const a = cacc.find((r) => r.g === c) || {inc: 0, profit: 0, margin: null, jobs: 0, booked: 0}, cs = S.sel.company || new Set();
    return h('tr', {class: 'click' + (cs.size === 1 && cs.has(c) ? ' on' : ''), onclick: () => toggle('company', c)}, h('td', null, COMP[c]), h('td', {class: 'n'}, fInt(cops[c].n)), h('td', {class: 'n'}, f1(cops[c].air)), h('td', {class: 'n'}, fInt(Math.round(cops[c].sea))), h('td', {class: 'n'}, money(a.inc)), h('td', {class: 'n ' + (a.profit < 0 ? 'bad' : '')}, money(a.profit)), h('td', {class: 'n'}, fMargin(a.margin)), h('td', {class: 'n'}, a.jobs ? fP0(a.booked / a.jobs) : '–')); }))));
  if (!FIN) cmpTbl.querySelectorAll('tr').forEach(row => Array.from(row.children).slice(4).forEach(cell => cell.remove()));
  return h('div', null, h('p', {class: 'meta'}, 'Operations and accounting together, for the filters above. Shipments are counted by shipment date and profit by job date, within the same date range.'),
    h('h2', {class: 'h', style: 'margin:.4rem 0'}, 'Operations'), h('div', {class: 'kpis'}, opsK), FIN ? h('h2', {class: 'h', style: 'margin:.9rem 0 .4rem'}, 'Accounting') : null, FIN ? h('div', {class: 'kpis'}, accK) : null,
    h('div', {class: 'grid', style: 'margin-top:.9rem'}, sVariance(), alertsCard, card('The two companies', 'Click a company to filter everything.', cmpTbl), card('Shipments by month', 'Click a month to zoom in.', monthBars(M)), FIN ? card('Profit by week', 'Job date. Click a week to zoom in.', weekChart(pm)) : null,
      FIN ? card('Top ' + S.def.topN + ' customers by profit', 'Click to filter.', pkeyRank('customer', {color: '#b279a2'})) : null, FIN ? card('Top ' + S.def.topN + ' sales people by profit', 'Click to filter.', pkeyRank('x_salesperson', {color: '#72b7b2'})) : null, FIN ? card('Top ' + S.def.topN + ' branches by profit', 'Click to filter.', pkeyRank('branch', {color: '#4c78a8'})) : null));
}
function sScore() {
  const sc = S.sc, d = SC_DIMS[sc.dim] || SC_DIMS[0], key = d.k, root = h('div'), m = mask({skip: key}), n = COLS[key].d.length, c = COLS[key].c;
  const ship = new Float64Array(n), airT = new Float64Array(n), seaT = new Float64Array(n), openF = new Float64Array(n), lagS = new Float64Array(n), lagN = new Float64Array(n);
  for (let i = 0; i < N; i++) { if (!m[i]) continue; const g = c[i]; ship[g]++; if (mode[i]) seaT[g] += teus[i]; else airT[g] += chg[i]; if (COLS.stage.c[i] === STAGE_FIN) openF[g]++; if (opsD[i] > 0 && finD[i] > 0) { lagS[g] += finD[i] - opsD[i]; lagN[g]++; } }
  const pr = new Map(groupByP(key, maskP({skip: key})).map((r) => [r.g, r])), rows = [];
  for (let g = 0; g < n; g++) { const p = pr.get(g); if (!ship[g] && !p) continue; rows.push({g, label: COLS[key].d[g], ship: ship[g], airT: airT[g], seaT: seaT[g], openF: openF[g], lag: lagN[g] ? lagS[g] / lagN[g] : null, inc: p ? p.inc : 0, exp: p ? p.exp : 0, profit: p ? p.profit : 0, margin: p ? p.margin : null, jobs: p ? p.jobs : 0, bk: p && p.jobs ? p.booked / p.jobs : null}); }
  const totS = d3.sum(rows, (r) => r.ship), totP = d3.sum(rows, (r) => r.profit); rows.forEach((r) => { r.shS = totS ? r.ship / totS : null; r.shP = totP > 0 ? r.profit / totP : null; r.ppj = r.jobs ? r.profit / r.jobs : null; });
  const sel = S.sel[key] || new Set(), quick = h('div', {class: 'segs'}, SC_DIMS.slice(0, 8).map((q, i) => h('button', {type: 'button', class: 'btn' + (sc.dim === i ? ' on' : ''), onclick: () => { sc.dim = i; sc.sort = {sort: 'profit', dir: -1}; renderAll(); }}, q.l))), more = h('select', {'aria-label': 'More dimensions'}, h('option', {value: ''}, 'More…'), SC_DIMS.map((q, i) => (i >= 8 ? h('option', {value: i, selected: sc.dim === i}, q.l) : null)));
  more.addEventListener('change', () => { if (more.value !== '') { sc.dim = parseInt(more.value, 10); sc.sort = {sort: 'profit', dir: -1}; renderAll(); } });
  const cols = [{k: 'label', t: d.l}, {k: 'ship', t: 'Shipments', num: true}, {k: 'shS', t: 'Share of shipments', num: true}, {k: 'airT', t: 'Air tonnes', num: true}, {k: 'seaT', t: 'Sea TEUs', num: true}, {k: 'openF', t: 'Financials open', num: true}, {k: 'lag', t: 'Days to financial lock', num: true}, {k: 'inc', t: 'Income', num: true}, {k: 'profit', t: 'Profit', num: true}, {k: 'margin', t: 'Margin', num: true}, {k: 'shP', t: 'Share of profit', num: true}, {k: 'jobs', t: 'Jobs', num: true}, {k: 'ppj', t: 'Profit per job', num: true}, {k: 'bk', t: 'Jobs with cost booked', num: true}];
  const thead = h('thead'), tbody = h('tbody'), note = h('p', {class: 'note'}); let last = [];
  const draw = () => { const st = sc.sort, f = st.sort === 'label' ? (a, b) => a.label.localeCompare(b.label) : (a, b) => (a[st.sort] == null ? -1e18 : a[st.sort]) - (b[st.sort] == null ? -1e18 : b[st.sort]); const list = rows.slice().sort((a, b) => f(a, b) * st.dir); last = list; const shown = list.slice(0, S.def.tableRows); thead.replaceChildren(sortHead(cols, st, draw));
    tbody.replaceChildren(...shown.map((r) => h('tr', {class: 'click' + (sel.has(r.g) ? ' on' : ''), onclick: () => toggle(key, r.g)}, h('td', null, r.label), h('td', {class: 'n'}, fInt(r.ship)), h('td', {class: 'n'}, r.shS == null ? '–' : fS(r.shS)), h('td', {class: 'n'}, r.airT ? f1(r.airT) : '–'), h('td', {class: 'n'}, r.seaT ? fInt(Math.round(r.seaT)) : '–'), h('td', {class: 'n'}, fInt(r.openF)), h('td', {class: 'n'}, r.lag == null ? '–' : r.lag.toFixed(1)),
      h('td', {class: 'n'}, r.inc ? money(r.inc) : '–'), h('td', {class: 'n ' + (r.profit < 0 ? 'bad' : '')}, r.jobs ? money(r.profit) : '–'), h('td', {class: 'n'}, fMargin(r.margin)), h('td', {class: 'n'}, r.shP == null ? '–' : fS(r.shP)), h('td', {class: 'n'}, fInt(r.jobs)), h('td', {class: 'n'}, r.ppj == null ? '–' : money(r.ppj)), h('td', {class: 'n ' + (r.bk != null && r.bk * 100 < S.def.costCoverage ? 'warnt' : '')}, r.bk == null ? '–' : fP0(r.bk)))));
    if (!FIN) [thead,tbody].forEach(section=>section.querySelectorAll('tr').forEach(row=>Array.from(row.children).slice(7).forEach(cell=>cell.remove())));
    note.textContent = 'Showing ' + shown.length + ' of ' + fInt(list.length) + ' rows. Click a header to sort, a row to filter everything. A dash in the profit columns means no job in the profit report matches.'; };
  draw();
  const exportS = () => { const list = last, nn = list.length + 1, tr = nn + 1;
    if (!FIN) { downloadXlsx('operations_scorecard.xlsx', [{name:'Operations scorecard', freeze:true, filter:true, cols:[42,14,14,14,14,14,14], rows:[[d.l,'Shipments','Share of shipments','Air tonnes','Sea TEUs','Financials open','Lock lag days'].map(HDR)].concat(list.map(r=>[r.label,r.ship,r.shS,r.airT,r.seaT,r.openF,r.lag]))}, settingsSheet([[HDR('Rows by'),d.l]])]); return; }
    downloadXlsx('scorecard_by_' + d.l.toLowerCase().replace(/[^a-z]+/g, '_') + '_' + fIso(dDate(MAXDATE)) + '.xlsx', [{name: 'Scorecard', freeze: true, filter: true, cols: [42, 12, 14, 12, 12, 14, 14, 16, 16, 16, 12, 14, 10, 16], rows: [[d.l, 'Shipments', 'Share of shipments', 'Air tonnes', 'Sea TEUs', 'Financials open', 'Income', 'Expense', 'Profit', 'Margin', 'Share of profit', 'Jobs', 'Profit per job'].map(HDR)]
      .concat(list.map((r, i) => { const x = i + 2; return [r.label, {v: r.ship, s: 3}, {f: 'IF(SUM(B$2:B$' + nn + ')=0,"",B' + x + '/SUM(B$2:B$' + nn + '))', s: 2}, {v: +r.airT.toFixed(3), s: 4}, {v: Math.round(r.seaT), s: 3}, {v: r.openF, s: 3}, {v: +r.inc.toFixed(2), s: 3}, {v: +r.exp.toFixed(2), s: 3}, {f: 'G' + x + '-H' + x, s: 3}, {f: 'IF(G' + x + '<=0,"",I' + x + '/G' + x + ')', s: 2}, {f: 'IF(SUM(I$2:I$' + nn + ')=0,"",I' + x + '/SUM(I$2:I$' + nn + '))', s: 2}, {v: r.jobs, s: 3}, {f: 'IF(L' + x + '=0,"",I' + x + '/L' + x + ')', s: 3}]; }))
      .concat([[HDR('Total'), {f: 'SUM(B2:B' + nn + ')', s: 3}, '', {f: 'SUM(D2:D' + nn + ')', s: 4}, {f: 'SUM(E2:E' + nn + ')', s: 3}, {f: 'SUM(F2:F' + nn + ')', s: 3}, {f: 'SUM(G2:G' + nn + ')', s: 3}, {f: 'SUM(H2:H' + nn + ')', s: 3}, {f: 'SUM(I2:I' + nn + ')', s: 3}, {f: 'IF(G' + tr + '<=0,"",I' + tr + '/G' + tr + ')', s: 2}]])}, settingsSheet([[HDR('Rows by'), d.l]])]); };
  root.append(h('div', {class: 'card', style: 'margin-bottom:.9rem'}, h('h2', {class: 'h'}, 'Scorecard by ' + d.l.toLowerCase()), h('p', {class: 'note'}, 'Operations and accounting side by side for the same rows: what was shipped, how fast it was billed, and what it earned. Shipments are counted by shipment date and profit by job date, within the same date range.'), h('div', {class: 'frow'}, quick, more)));
  root.append(card('All rows', null, h('div', null, h('div', {class: 'frow'}, dlButton('Download Excel', exportS)), note, h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, thead, tbody))), 'full'));
  return root;
}

// ================================================================ variance at a glance (summary) and billing health (finance): real history from the registers' invoice dates
const sel = (opts, val, on) => { const e = h('select', null, opts.map((o) => h('option', {value: o[0], selected: String(o[0]) === String(val)}, o[1]))); e.value = String(val); e.addEventListener('change', () => on(e.value)); return e; };
S.bl = {dim: 'branch', show: 'all', sort: {sort: 'over', dir: -1}, vdim: 'branch', vshow: 'all', vsort: {sort: 'adelta', dir: -1}};
function winFacts(w, mo, mp) {
  let n = 0, air = 0, sea = 0, inv = 0, rm = 0; const cust = new Set();
  for (let i = 0; i < N; i++) { if (!mo[i]) continue; if (date[i] >= w.from && date[i] <= w.to) { n++; if (rtype[i] === 0 && rateOK(i)) rm += rmargin(i); if (mode[i]) sea += teus[i]; else air += chg[i]; cust.add(COLS.customer.c[i]); } if (inv1[i] > 0 && inv1[i] >= w.from && inv1[i] <= w.to) inv++; }
  const t = totalsP(mp, w.from, w.to); return {n, air, sea, cust: cust.size, inv, rm, inc: t.inc, exp: t.exp, profit: t.profit, margin: t.margin, jobs: t.jobs, lines: t.lines};
}
const cmpControls = () => { const c = S.cmp; return h('div', {class: 'frow'}, h('label', {class: 'f'}, h('span', null, 'Period'), sel(UNITS, c.unit, (v) => { c.unit = v; c.custom = false; renderAll(); })),
  h('label', {class: 'f'}, h('span', null, 'Against'), sel([['prev', 'The period before'], ['yoy', 'Same period last year']], c.against, (v) => { c.against = v; renderAll(); })),
  h('label', {class: 'f'}, h('span', null, 'Basis'), sel([['todate', 'So far (same number of days)'], ['full', 'Whole period']], c.basis, (v) => { c.basis = v; renderAll(); }))); };
function sVariance() {
  const pr = periods(S.cmp); if (pr.err) return card('Variance', null, h('p', {class: 'empty'}, pr.err), 'full');
  const mo = mask({dates: 'none'}), mp = maskP({dates: 'none'}), a = winFacts(pr.cur, mo, mp), b = winFacts(pr.prev, mo, mp), fin = b.lines > 0;
  const defs = [['Shipments', 'n', 'int', 1, 0], ['Air chargeable tonnes', 'air', 't', 1, 0], ['Sea TEUs', 'sea', 'int', 1, 0], ['Active customers', 'cust', 'int', 1, 0], ['Shipments invoiced', 'inv', 'int', 1, 0], ['Est. freight margin (air export)', 'rm', 'money', 1, 0], ['Income', 'inc', 'money', 1, 1], ['Expense', 'exp', 'money', -1, 1], ['Profit', 'profit', 'money', 1, 1], ['Margin', 'margin', 'pts', 1, 1], ['Jobs in the profit report', 'jobs', 'int', 1, 1]];
  const fv = (t, v) => (v == null ? '–' : t === 'int' ? fInt(Math.round(v)) : t === 't' ? f1(v) : t === 'money' ? money(v) : fMargin(v));
  const body = defs.filter(([lab, k]) => FIN || ['n', 'air', 'sea', 'cust'].includes(k)).map(([lab, k, t, good, isFin]) => { const cur = a[k], pv = b[k], na = false; let ch = '–', pc = '–', tone = '';
    if (!na && cur != null && pv != null) { if (t === 'pts') { const d = (cur - pv) * 100; ch = (d >= 0 ? '+' : '−') + Math.abs(d).toFixed(1) + ' pts'; tone = d * good >= 0 ? 'ok' : 'bad'; } else { const d = cur - pv; ch = sgn(d) + fv(t, Math.abs(d)); pc = pv !== 0 ? fPctS(pctOf(cur, pv)) : (pv === 0 && cur > 0 ? 'new' : '–'); tone = d * good >= 0 ? 'ok' : 'bad'; } }
    return h('tr', null, h('td', null, h('button',{type:'button',class:'link',onclick:()=>{const ids={n:'ops.shipments',air:'ops.air_weight',sea:'ops.teu',cust:'ops.active_customers',inv:'ops.invoiced_count',rm:'ops.rate_margin',inc:'profit.income',exp:'profit.expense',profit:'profit.gp',margin:'profit.margin',jobs:'profit.jobs'};window.MetricTrace?.openWithRequest(metricTraceVariance(ids[k],pr,cur));}},lab+' ↗')), h('td', {class: 'n'}, fv(t, cur)), h('td', {class: 'n'}, na ? 'not loaded' : fv(t, pv)), h('td', {class: 'n ' + tone}, ch), h('td', {class: 'n ' + tone}, pc)); });
  const finHistTxt = D.p.meta.map((mm) => mm.range_from + ' to ' + mm.range_to + ' (' + COMP[mm.co === 'NG' ? 0 : 1] + ')').join('; ');
  return card('Variance: ' + pr.title, 'Value and percentage change, for the filters above. Shipments are by shipment date, invoices by first invoice date, money by job date.', h('div', null, cmpControls(),
    h('div', {class: 'scroll'}, h('table', {class: 'tbl'}, h('thead', null, h('tr', null, h('th', null, 'Measure'), h('th', {class: 'n'}, pr.curName || 'This period'), h('th', {class: 'n'}, pr.prevName || 'Comparison'), h('th', {class: 'n'}, 'Change'), h('th', {class: 'n'}, 'Change %'))), h('tbody', null, body))),
    fin ? null : h('p', {class: 'meta', style: 'color:var(--warn);margin:.5rem 0 0'}, 'The comparison period has zero finance lines under the current filters. Values use uploaded records; percentages require a nonzero prior value. Available report date ranges: ' + finHistTxt + '.')), 'full');
}
function ppBilling() {
  const bl = S.bl, root = h('div'), OLD = S.def.unbilledDays, today = OPS_MAX;
  const Mr = mask(), Ma = mask({dates: 'none'}); let nr = 0, invR = 0, lagS = 0, lagN = 0, lockS = 0, lockN = 0, locked = 0, notInv = 0, over = 0; const ages = [0, 0, 0, 0, 0];
  for (let i = 0; i < N; i++) { if (Mr[i]) { nr++; if (invN[i] > 0) { invR++; if (inv1[i] > 0) { lagS += inv1[i] - date[i]; lagN++; if (opsD[i] > 0) { lockS += inv1[i] - opsD[i]; lockN++; } } } }
    if (Ma[i] && opsD[i] > 0 && invN[i] === 0) { notInv++; const a = today - opsD[i]; if (a > OLD) over++; ages[a <= 7 ? 0 : a <= 30 ? 1 : a <= 60 ? 2 : a <= 90 ? 3 : 4]++; } if (Ma[i] && opsD[i] > 0) locked++; }
  const kp = h('div', {class: 'kpis'}, kpi('Shipments invoiced', nr ? fP0(invR / nr) : '–', null, fInt(invR) + ' of ' + fInt(nr) + ' shipments in the date range'), kpi('Days from shipment to first invoice', lagN ? (lagS / lagN).toFixed(1) : '–', null, 'Average, invoiced shipments in range'), kpi('Days from ops lock to first invoice', lockN ? (lockS / lockN).toFixed(1) : '–', null, 'Average; a negative number means invoiced before the lock'),
    kpi('Locked but not invoiced', fInt(notInv), null, 'Operations locked, no invoice or billing document recorded (ignores the date range)', notInv ? 'warn' : ''), kpi('Not invoiced for more than ' + OLD + ' days', fInt(over), null, 'Since operations lock; the limit is under Definitions', over ? 'bad' : ''));
  const ageCard = card('Locked but not invoiced, by age', 'Days since operations were locked. Bars show how much billing is waiting and for how long.', (() => { const lab = ['Up to 7 days', '8 to 30 days', '31 to 60 days', '61 to 90 days', 'Over 90 days'], mx = Math.max(...ages, 1); return h('div', {class: 'rank'}, lab.map((l, k) => h('div', {class: 'row'}, h('span', {class: 'lab'}, l), h('span', {class: 'track'}, h('span', {class: 'fill', style: 'width:' + (ages[k] / mx * 100) + '%;background:' + (k >= 3 ? 'var(--bad)' : k === 2 ? 'var(--warn)' : '#4c78a8')})), h('span', {class: 'val'}, fInt(ages[k]))))); })());
  // where billing is slow
  const dims = [['branch', 'Branch'], ['job_owner', 'Job owner'], ['customer', 'Customer'], ['x_salesperson', 'Sales person'], ['x_tradelanename', 'Trade lane'], ['carrier', 'Airline or shipping line'], ['destination', 'Destination port']], key = bl.dim, m2 = mask({skip: key, dates: 'none'}), c2 = COLS[key].c, nn = COLS[key].d.length;
  const lk = new Float64Array(nn), iv = new Float64Array(nn), ni = new Float64Array(nn), ov = new Float64Array(nn), ls = new Float64Array(nn), ln = new Float64Array(nn);
  for (let i = 0; i < N; i++) { if (!m2[i] || !(opsD[i] > 0)) continue; const g = c2[i]; lk[g]++; if (invN[i] > 0) { iv[g]++; if (inv1[i] > 0) { ls[g] += inv1[i] - opsD[i]; ln[g]++; } } else { ni[g]++; if (today - opsD[i] > OLD) ov[g]++; } }
  const rows = []; for (let g = 0; g < nn; g++) if (lk[g]) rows.push({g, label: COLS[key].d[g], locked: lk[g], inv: iv[g], pct: iv[g] / lk[g], notInv: ni[g], over: ov[g], lag: ln[g] ? ls[g] / ln[g] : null});
  const selv = S.sel[key] || new Set(), cols = [{k: 'label', t: dims.find((x) => x[0] === key)[1]}, {k: 'locked', t: 'Ops locked', num: true}, {k: 'pct', t: 'Invoiced', num: true}, {k: 'notInv', t: 'Not invoiced', num: true}, {k: 'over', t: 'Over ' + OLD + ' days', num: true}, {k: 'lag', t: 'Days lock to invoice', num: true}], thead = h('thead'), tbody = h('tbody'), note = h('p', {class: 'note'});
  const draw = () => { const st = bl.sort, f = st.sort === 'label' ? (a, b) => a.label.localeCompare(b.label) : (a, b) => (a[st.sort] == null ? -1e18 : a[st.sort]) - (b[st.sort] == null ? -1e18 : b[st.sort]); const list = rows.slice().sort((a, b) => f(a, b) * st.dir), shown = list.slice(0, S.def.tableRows); thead.replaceChildren(sortHead(cols, st, draw));
    tbody.replaceChildren(...shown.map((r) => h('tr', {class: 'click' + (selv.has(r.g) ? ' on' : ''), onclick: () => toggle(key, r.g)}, h('td', null, r.label), h('td', {class: 'n'}, fInt(r.locked)), h('td', {class: 'n'}, fP0(r.pct)), h('td', {class: 'n'}, fInt(r.notInv)), h('td', {class: 'n ' + (r.over ? 'bad' : '')}, fInt(r.over)), h('td', {class: 'n'}, r.lag == null ? '–' : r.lag.toFixed(1))))); note.textContent = 'Showing ' + shown.length + ' of ' + fInt(list.length) + '. Only shipments with operations locked. Click a row to filter everything.'; }; draw();
  const dimSel = sel(dims, key, (v) => { bl.dim = v; bl.sort = {sort: 'over', dir: -1}; renderAll(); });
  const slow = card('Where billing is slow', 'Operations locked but no invoice raised. Fix these first: this is revenue not yet billed.', h('div', null, h('div', {class: 'frow'}, h('label', {class: 'f'}, h('span', null, 'Rows by'), dimSel)), note, h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, thead, tbody))), 'full');
  // month by month: shipments against invoices
  const sm = new Map(), im = new Map(); for (let i = 0; i < N; i++) { if (!Ma[i]) continue; sm.set(mStart[i], (sm.get(mStart[i]) || 0) + 1); if (inv1[i] > 0) { const ms = Math.round(+d3.utcMonth.floor(dDate(inv1[i])) / DMS); im.set(ms, (im.get(ms) || 0) + 1); } }
  const months = [...new Set([...sm.keys(), ...im.keys()])].sort((a, b) => a - b), ymax = Math.max(1, ...months.map((x) => Math.max(sm.get(x) || 0, im.get(x) || 0)));
  const chart = (() => { const box = h('div', {class: 'trend'}); if (!months.length) { box.append(emptyNote()); return box; } const W = Math.max(300, Math.round(($('page').clientWidth || 900) - 50)), H = 250, mb = 28, mt = 24, ml = 46, svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', '0 0 ' + W + ' ' + H).attr('role', 'img').attr('aria-label', 'Shipments and invoices by month');
    const y = d3.scaleLinear([0, ymax], [H - mb, mt]).nice(4), x = d3.scaleBand(months, [ml, W - 8]).padding(0.2), bw = x.bandwidth() / 2; y.ticks(4).forEach((t) => { svg.append('line').attr('x1', ml).attr('x2', W - 8).attr('y1', y(t)).attr('y2', y(t)).style('stroke', 'var(--grid)'); svg.append('text').attr('class', 'tick').attr('x', ml - 6).attr('y', y(t)).attr('text-anchor', 'end').attr('dominant-baseline', 'middle').text(fInt(t)); });
    months.forEach((ms) => { [[sm.get(ms) || 0, '#4c78a8', 0, 'shipments'], [im.get(ms) || 0, '#59a14f', bw, 'shipments invoiced']].forEach(([v, col, off, nm]) => svg.append('rect').attr('x', x(ms) + off).attr('y', y(v)).attr('width', bw).attr('height', Math.max(0, H - mb - y(v))).attr('fill', col).attr('rx', 2).append('title').text(fMon(ms) + ': ' + fInt(v) + ' ' + nm)); svg.append('text').attr('class', 'tick').attr('x', x(ms) + x.bandwidth() / 2).attr('y', H - 8).attr('text-anchor', 'middle').text(d3.utcFormat('%b')(dDate(ms))); });
    svg.append('rect').attr('x', ml).attr('y', 4).attr('width', 10).attr('height', 10).attr('fill', '#4c78a8'); svg.append('text').attr('class', 'tick').attr('x', ml + 14).attr('y', 13).text('Shipments (by shipment date)'); svg.append('rect').attr('x', ml + 190).attr('y', 4).attr('width', 10).attr('height', 10).attr('fill', '#59a14f'); svg.append('text').attr('class', 'tick').attr('x', ml + 204).attr('y', 13).text('Shipments invoiced (by first invoice date)'); return box; })();
  // variance of invoicing
  const pr = periods(S.cmp), vk = bl.vdim, vroot = h('div');
  if (pr.err) vroot.append(h('p', {class: 'empty'}, pr.err)); else {
    const mv = mask({skip: vk, dates: 'none'}), cv = COLS[vk].c, nv = COLS[vk].d.length, A_ = new Float64Array(nv), B_ = new Float64Array(nv); let tA = 0, tB = 0;
    for (let i = 0; i < N; i++) { if (!mv[i] || !(inv1[i] > 0)) continue; if (inv1[i] >= pr.cur.from && inv1[i] <= pr.cur.to) { A_[cv[i]]++; tA++; } if (inv1[i] >= pr.prev.from && inv1[i] <= pr.prev.to) { B_[cv[i]]++; tB++; } }
    let vr = []; for (let g = 0; g < nv; g++) if (A_[g] || B_[g]) vr.push({g, label: COLS[vk].d[g], cur: A_[g], prev: B_[g], delta: A_[g] - B_[g], adelta: Math.abs(A_[g] - B_[g]), pct: B_[g] > 0 ? (A_[g] - B_[g]) / B_[g] * 100 : null});
    vr = vr.filter((r) => !(S.def.varMinBase > 0 && r.prev < S.def.varMinBase) && !(S.def.varMinAbs > 0 && r.adelta < S.def.varMinAbs) && !(S.def.varMinPct > 0 && (r.pct == null ? r.cur > 0 ? false : true : Math.abs(r.pct) < S.def.varMinPct)) && (bl.vshow === 'all' || (bl.vshow === 'up' && r.delta > 0) || (bl.vshow === 'down' && r.delta < 0)));
    const vc = [{k: 'label', t: dims.find((x) => x[0] === vk) ? dims.find((x) => x[0] === vk)[1] : 'Rows'}, {k: 'cur', t: pr.curName || 'This period', num: true}, {k: 'prev', t: pr.prevName || 'Comparison', num: true}, {k: 'delta', t: 'Change', num: true}, {k: 'pct', t: 'Change %', num: true}], vh = h('thead'), vb = h('tbody'); let vlast = [];
    const vdraw = () => { const st = bl.vsort, f = st.sort === 'label' ? (a, b) => a.label.localeCompare(b.label) : st.sort === 'adelta' ? (a, b) => a.adelta - b.adelta : (a, b) => (a[st.sort] == null ? -1e18 : a[st.sort]) - (b[st.sort] == null ? -1e18 : b[st.sort]); const list = vr.slice().sort((a, b) => f(a, b) * st.dir); vlast = list; const shown = list.slice(0, S.def.tableRows); vh.replaceChildren(sortHead(vc, st, vdraw));
      vb.replaceChildren(...shown.map((r) => h('tr', {class: 'click', onclick: () => toggle(vk, r.g)}, h('td', null, r.label), h('td', {class: 'n'}, fInt(r.cur)), h('td', {class: 'n'}, fInt(r.prev)), h('td', {class: 'n ' + (r.delta >= 0 ? 'ok' : 'bad')}, (r.delta >= 0 ? '+' : '−') + fInt(Math.abs(r.delta))), h('td', {class: 'n ' + (r.delta >= 0 ? 'ok' : 'bad')}, r.pct == null ? (r.cur > 0 ? 'new' : '–') : fPctS(r.pct / 100))))); };
    vdraw();
    const expV = () => { const list = vlast, n2 = list.length + 1; downloadXlsx('invoicing_variance_' + fIso(dDate(MAXDATE)) + '.xlsx', [{name: 'Variance', freeze: true, filter: true, cols: [42, 16, 16, 14, 12], rows: [[vc[0].t, 'Shipments invoiced: ' + (pr.curName || 'this period'), 'Shipments invoiced: ' + (pr.prevName || 'comparison'), 'Change', 'Change %'].map(HDR)].concat(list.map((r, i) => { const x = i + 2; return [r.label, {v: r.cur, s: 3}, {v: r.prev, s: 3}, {f: 'B' + x + '-C' + x, s: 3}, {f: 'IF(C' + x + '=0,"",D' + x + '/C' + x + ')', s: 2}]; })).concat([[HDR('Total'), {f: 'SUM(B2:B' + n2 + ')', s: 3}, {f: 'SUM(C2:C' + n2 + ')', s: 3}, {f: 'B' + (n2 + 1) + '-C' + (n2 + 1), s: 3}, {f: 'IF(C' + (n2 + 1) + '=0,"",D' + (n2 + 1) + '/C' + (n2 + 1) + ')', s: 2}]])}, settingsSheet([[HDR('Period'), pr.title]])]); };
    vroot.append(h('p', {class: 'meta'}, h('strong', null, 'Shipments invoiced: ' + fInt(tA) + ' against ' + fInt(tB)), ' (' + (tB > 0 ? fPctS((tA - tB) / tB) : 'no comparison data') + ') · ' + pr.title), cmpControls(),
      h('div', {class: 'frow'}, h('label', {class: 'f'}, h('span', null, 'Rows by'), sel(dims, vk, (v) => { bl.vdim = v; renderAll(); })), h('label', {class: 'f'}, h('span', null, 'Show'), sel([['all', 'All changes'], ['up', 'Increases only'], ['down', 'Decreases only']], bl.vshow, (v) => { bl.vshow = v; renderAll(); })), dlButton('Download Excel', expV)),
      h('p', {class: 'note'}, 'Hides changes smaller than the limits under Definitions: ' + S.def.varMinPct + '% / value ' + S.def.varMinAbs + ' / previous at least ' + S.def.varMinBase + '.'), h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, vh, vb))); }
  root.append(h('p', {class: 'meta'}, 'Invoice counts and dates come from the shipment registers, independently of the job-profit snapshots. Invoiced means the register shows an invoice in either “Invoice No. & Date” or “Billing Details”, counted on the earliest date found. About a third of shipments have a document only in Billing Details, so the two columns are read together.'), kp, h('div', {class: 'grid', style: 'margin-top:.9rem'}, ageCard, card('Shipments against invoices, by month', 'The gap between the bars is billing waiting to happen.', chart), slow, card('Variance: shipments invoiced', 'Value and percentage change against the earlier period, by any angle.', vroot, 'full')));
  return root;
}
// who needs to book costs: jobs with income and no cost yet, by the people and places that own them
S.gap = {dim: 'job_owner', sort: {sort: 'inc', dir: -1}};
function costGapCard() {
  const g = S.gap, dims = [['job_owner', 'Job owner'], ['branch', 'Branch'], ['x_salesperson', 'Sales person'], ['customer', 'Customer'], ['x_tradelanename', 'Trade lane']], key = g.dim, m = maskP({skip: [key, 'jobstatus']});
  for (let i = 0; i < NP; i++) if (m[i] && COLS.jobstatus.pc[i] !== 1) m[i] = 0;
  const rows = groupByP(key, m).map((r) => ({g: r.g, label: r.label, jobs: r.jobs, inc: r.inc})), tot = d3.sum(rows, (r) => r.inc), selv = S.sel[key] || new Set(), cols = [{k: 'label', t: dims.find((x) => x[0] === key)[1]}, {k: 'jobs', t: 'Jobs without cost', num: true}, {k: 'inc', t: 'Income at stake', num: true}, {k: 'sh', t: 'Share', num: true}], thead = h('thead'), tbody = h('tbody');
  rows.forEach((r) => { r.sh = tot ? r.inc / tot : null; });
  const draw = () => { const st = g.sort, f = st.sort === 'label' ? (a, b) => a.label.localeCompare(b.label) : (a, b) => (a[st.sort] == null ? -1e18 : a[st.sort]) - (b[st.sort] == null ? -1e18 : b[st.sort]); const list = rows.slice().sort((a, b) => f(a, b) * st.dir).slice(0, S.def.tableRows); thead.replaceChildren(sortHead(cols, st, draw));
    tbody.replaceChildren(...list.map((r) => h('tr', {class: 'click' + (selv.has(r.g) ? ' on' : ''), onclick: () => { S.sel.jobstatus = new Set([1]); toggle(key, r.g); }}, h('td', null, r.label), h('td', {class: 'n'}, fInt(r.jobs)), h('td', {class: 'n'}, money(r.inc)), h('td', {class: 'n'}, r.sh == null ? '–' : fS(r.sh))))); }; draw();
  return card('Who needs to book costs', 'Jobs with income but no cost booked, by who owns them. Click a row to see only those jobs. The names come from the shipment register.', h('div', null, h('div', {class: 'frow'}, h('label', {class: 'f'}, h('span', null, 'Rows by'), sel(dims, key, (v) => { g.dim = v; renderAll(); })), h('span', {class: 'meta'}, fInt(d3.sum(rows, (r) => r.jobs)) + ' jobs · ' + money(tot) + ' of income')), h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, thead, tbody))), 'full');
}

// ================================================================ rates: estimated freight margin on air exports (the registers' buy and sell rate text)
const ckg = ext(Float64Array, D.ckg), rbuy = ext(Float64Array, D.rbuy), rsell = ext(Float64Array, D.rsell), rbf = ext(Uint8Array, D.rbf), rsf = ext(Uint8Array, D.rsf);
for (let t = 0; t < demoSrc.length; t++) { const i = N + t, s0 = demoSrc[t]; ckg[i] = ckg[s0]; rbuy[i] = rbuy[s0]; rsell[i] = rsell[s0]; rbf[i] = rbf[s0]; rsf[i] = rsf[s0]; }
const rateOK = (i) => { if (!(ckg[i] > 0)) return false; const okf = (f) => f === 1 || (f === 2 && S.def.rateMode !== 'clean'); return okf(rbf[i]) && okf(rsf[i]) && rbuy[i] > 0 && rsell[i] > 0 && rbuy[i] <= S.def.rateMax && rsell[i] <= S.def.rateMax; };
const rmargin = (i) => (rsell[i] - rbuy[i]) * ckg[i];
const fRate = (v) => (v == null ? '–' : '₹' + v.toFixed(1) + '/kg');
function ppRates() {
  const M = mask(), root = h('div'), pr = periods(S.cmp); let nAE = 0, nOK = 0, kg = 0, sellRev = 0, buyCost = 0, mar = 0, neg = 0, negAmt = 0; const bad = {none: 0, text: 0, clean: 0, foreign: 0, lump: 0}, below = [];
  for (let i = 0; i < N; i++) { if (!M[i] || rtype[i] !== 0) continue; nAE++; if (rbf[i] === 3 || rsf[i] === 3) bad.foreign++; else if (rbf[i] === 0 || rsf[i] === 0) bad.none++; else if (rbuy[i] > S.def.rateMax || rsell[i] > S.def.rateMax) bad.lump++; else if (rateOK(i)) { nOK++; if (rbf[i] === 2 || rsf[i] === 2) bad.text++; else bad.clean++; } else bad.none++;
    if (rateOK(i)) { const k = ckg[i]; kg += k; sellRev += rsell[i] * k; buyCost += rbuy[i] * k; mar += rmargin(i); if (rsell[i] < rbuy[i]) { neg++; negAmt += rmargin(i); below.push(i); } } }
  const kp = h('div', {class: 'kpis'}, kpi('Air export shipments', fInt(nAE), null, 'The registers record buy and sell rates for air exports only'), kpi('With usable rates', nAE ? fP0(nOK / nAE) : '–', null, fInt(nOK) + ' shipments; the rest are lump sums, foreign currency or blank'), kpi('Average sell rate', kg ? fRate(sellRev / kg) : '–', null, 'Weighted by chargeable weight'), kpi('Average buy rate', kg ? fRate(buyCost / kg) : '–', null, 'Weighted by chargeable weight'),
    kpi('Freight margin per kg', kg ? fRate(mar / kg) : '–', null, sellRev ? fMargin(mar / sellRev) + ' of the sell value' : ''), kpi('Estimated freight margin', money(mar), null, 'Sell minus buy, times chargeable weight', mar < 0 ? 'bad' : ''), kpi('Selling below buy', fInt(neg), null, neg ? money(Math.abs(negAmt)) + ' given away on these shipments' : 'No shipment sold below its buy rate', neg ? 'bad' : ''));
  // by month
  const mm = new Map(); for (let i = 0; i < N; i++) { if (!M[i] || rtype[i] !== 0 || !rateOK(i)) continue; const e = mm.get(mStart[i]) || {m: 0, k: 0, n: 0}; e.m += rmargin(i); e.k += ckg[i]; e.n++; mm.set(mStart[i], e); }
  const months = [...mm.keys()].sort((a, b) => a - b), mlab = months.map((x) => d3.utcFormat('%b %Y')(dDate(x)));
  const c1 = h('div'); drawChart(c1, {type: 'bar', labels: mlab, series: [{name: 'Estimated freight margin', values: months.map((x) => mm.get(x).m)}], fmt: money}); const c2 = h('div'); drawChart(c2, {type: 'line', labels: mlab, series: [{name: 'Margin per kg', values: months.map((x) => mm.get(x).m / mm.get(x).k)}], fmt: fRate});
  // variance by any angle
  const dims = [['customer', 'Customer'], ['x_salesperson', 'Sales person'], ['branch', 'Branch'], ['x_tradelanename', 'Trade lane'], ['destination', 'Destination port'], ['carrier', 'Airline'], ['job_owner', 'Job owner'], ['x_dischargecountry', 'Destination country']], rt = S.rt = S.rt || {dim: 'customer', show: 'all', sort: {sort: 'adelta', dir: -1}}, vk = rt.dim; let vcard;
  if (pr.err) vcard = h('p', {class: 'empty'}, pr.err); else {
    const mv = mask({skip: vk, dates: 'none'}), cv = COLS[vk].c, nv = COLS[vk].d.length, A_ = new Float64Array(nv), B_ = new Float64Array(nv), Ak = new Float64Array(nv), Bk = new Float64Array(nv);
    for (let i = 0; i < N; i++) { if (!mv[i] || rtype[i] !== 0 || !rateOK(i)) continue; const g = cv[i], d = date[i]; if (d >= pr.cur.from && d <= pr.cur.to) { A_[g] += rmargin(i); Ak[g] += ckg[i]; } if (d >= pr.prev.from && d <= pr.prev.to) { B_[g] += rmargin(i); Bk[g] += ckg[i]; } }
    let vr = []; for (let g = 0; g < nv; g++) if (Ak[g] || Bk[g]) vr.push({g, label: COLS[vk].d[g], cur: A_[g], prev: B_[g], delta: A_[g] - B_[g], adelta: Math.abs(A_[g] - B_[g]), pct: B_[g] > 0 ? (A_[g] - B_[g]) / B_[g] * 100 : null, ck: Ak[g] ? A_[g] / Ak[g] : null, pk: Bk[g] ? B_[g] / Bk[g] : null});
    const tA = d3.sum(vr, (r) => r.cur), tB = d3.sum(vr, (r) => r.prev);
    vr = vr.filter((r) => !(S.def.varMinBase > 0 && Math.abs(r.prev) < S.def.varMinBase) && !(S.def.varMinAbs > 0 && r.adelta < S.def.varMinAbs) && !(S.def.varMinPct > 0 && r.pct != null && Math.abs(r.pct) < S.def.varMinPct) && (rt.show === 'all' || (rt.show === 'up' && r.delta > 0) || (rt.show === 'down' && r.delta < 0)));
    const vc = [{k: 'label', t: dims.find((x) => x[0] === vk)[1]}, {k: 'cur', t: pr.curName || 'This period', num: true}, {k: 'prev', t: pr.prevName || 'Comparison', num: true}, {k: 'delta', t: 'Change', num: true}, {k: 'pct', t: 'Change %', num: true}, {k: 'ck', t: '₹/kg now', num: true}, {k: 'pk', t: '₹/kg before', num: true}], vh = h('thead'), vb = h('tbody'); let last = [];
    const draw = () => { const st = rt.sort, f = st.sort === 'label' ? (a, b) => a.label.localeCompare(b.label) : st.sort === 'adelta' ? (a, b) => a.adelta - b.adelta : (a, b) => (a[st.sort] == null ? -1e18 : a[st.sort]) - (b[st.sort] == null ? -1e18 : b[st.sort]); const list = vr.slice().sort((a, b) => f(a, b) * st.dir); last = list; vh.replaceChildren(sortHead(vc, st, draw));
      vb.replaceChildren(...list.slice(0, S.def.tableRows).map((r) => h('tr', {class: 'click', onclick: () => toggle(vk, r.g)}, h('td', null, r.label), h('td', {class: 'n'}, money(r.cur)), h('td', {class: 'n'}, money(r.prev)), h('td', {class: 'n ' + (r.delta >= 0 ? 'ok' : 'bad')}, sgn(r.delta) + money(Math.abs(r.delta))), h('td', {class: 'n ' + (r.delta >= 0 ? 'ok' : 'bad')}, r.pct == null ? (r.cur > 0 ? 'new' : '–') : fPctS(r.pct / 100)), h('td', {class: 'n'}, fRate(r.ck)), h('td', {class: 'n'}, fRate(r.pk))))); }; draw();
    const exp = () => { const list = last, n2 = list.length + 1; downloadXlsx('freight_margin_variance_' + fIso(dDate(MAXDATE)) + '.xlsx', [{name: 'Variance', freeze: true, filter: true, cols: [42, 18, 18, 16, 12], rows: [[vc[0].t, 'Estimated margin: ' + (pr.curName || 'now'), 'Estimated margin: ' + (pr.prevName || 'before'), 'Change', 'Change %'].map(HDR)].concat(list.map((r, i) => { const x = i + 2; return [r.label, {v: +r.cur.toFixed(2), s: 3}, {v: +r.prev.toFixed(2), s: 3}, {f: 'B' + x + '-C' + x, s: 3}, {f: 'IF(C' + x + '<=0,"",D' + x + '/C' + x + ')', s: 2}]; })).concat([[HDR('Total'), {f: 'SUM(B2:B' + n2 + ')', s: 3}, {f: 'SUM(C2:C' + n2 + ')', s: 3}, {f: 'B' + (n2 + 1) + '-C' + (n2 + 1), s: 3}, {f: 'IF(C' + (n2 + 1) + '<=0,"",D' + (n2 + 1) + '/C' + (n2 + 1) + ')', s: 2}]])}, settingsSheet([[HDR('Period'), pr.title]])]); };
    vcard = h('div', null, h('p', {class: 'meta'}, h('strong', null, 'Estimated freight margin: ' + money(tA) + ' against ' + money(tB)), ' (' + (tB > 0 ? fPctS((tA - tB) / tB) : 'no comparison data') + ') · ' + pr.title), cmpControls(), h('div', {class: 'frow'}, h('label', {class: 'f'}, h('span', null, 'Rows by'), sel(dims, vk, (v) => { rt.dim = v; renderAll(); })), h('label', {class: 'f'}, h('span', null, 'Show'), sel([['all', 'All changes'], ['up', 'Increases only'], ['down', 'Decreases only']], rt.show, (v) => { rt.show = v; renderAll(); })), dlButton('Download Excel', exp)), h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, vh, vb)));
  }
  // selling below buy
  below.sort((a, b) => rmargin(a) - rmargin(b)); const bt = h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, h('thead', null, h('tr', null, ['Shipment', 'Date', 'Customer', 'Sales person', 'Buy ₹/kg', 'Sell ₹/kg', 'Weight kg', 'Given away'].map((x, k) => h('th', {class: k > 3 ? 'n' : ''}, x)))), h('tbody', null, below.slice(0, 40).map((i) => h('tr', null, h('td', null, D.no[i]), h('td', null, fIso(dDate(date[i]))), h('td', null, catv('customer', i)), h('td', null, catv('x_salesperson', i)), h('td', {class: 'n'}, rbuy[i].toFixed(1)), h('td', {class: 'n'}, rsell[i].toFixed(1)), h('td', {class: 'n'}, fInt(Math.round(ckg[i]))), h('td', {class: 'n bad'}, money(Math.abs(rmargin(i)))))))));
  // estimated against actual, on jobs that appear in both the register and the profit report
  const pm = maskP(), seen = new Map(); for (let i = 0; i < NP; i++) { if (!pm[i]) continue; const j = pjob[i], s = psidx[i]; if (s < 0 || rtype[s] !== 0 || !rateOK(s)) continue; const e = seen.get(j) || {est: rmargin(s), act: 0, s, i}; e.act += pinc[i] - pexp[i]; seen.set(j, e); }
  const ea = [...seen.values()], tE = d3.sum(ea, (e) => e.est), tAct = d3.sum(ea, (e) => e.act);
  const eaCard = card('Estimated against actual', 'Jobs in both the register (rates) and the profit report. The estimate covers freight only, while actual profit covers every charge, and most jobs have no cost booked yet, so expect actual to exceed the estimate for now.', ea.length ? h('div', null, h('div', {class: 'kpis'}, kpi('Jobs compared', fInt(ea.length), null, ''), kpi('Estimated freight margin', money(tE), null, 'From the rates'), kpi('Actual profit', money(tAct), null, 'From the profit report'), kpi('Difference', sgn(tAct - tE) + money(Math.abs(tAct - tE)), null, 'Actual minus estimate')),
    h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, h('thead', null, h('tr', null, ['Job', 'Customer', 'Estimated', 'Actual', 'Difference'].map((x, k) => h('th', {class: k > 1 ? 'n' : ''}, x)))), h('tbody', null, ea.sort((a, b) => Math.abs(b.act - b.est) - Math.abs(a.act - a.est)).slice(0, 25).map((e) => h('tr', null, h('td', null, D.no[e.s]), h('td', null, catv('customer', e.s)), h('td', {class: 'n'}, money(e.est)), h('td', {class: 'n'}, money(e.act)), h('td', {class: 'n ' + (e.act - e.est >= 0 ? 'ok' : 'bad')}, sgn(e.act - e.est) + money(Math.abs(e.act - e.est))))))))) : h('p', {class: 'empty'}, 'No air export job with usable rates matches the profit report for these filters.'), 'full');
  const qual = card('How the rates were read', 'The rate columns are free text. The first number is taken as the rate per kg. Limits are under Definitions.', h('ul', {class: 'notes'}, h('li', null, fInt(bad.clean) + ' shipments have plain numbers in both columns.'), h('li', null, fInt(bad.text) + ' have text such as “512.00 ALL IN” or “840nn”; the number is used (Definitions can switch this off).'), h('li', null, fInt(bad.lump) + ' have a figure above ₹' + fInt(S.def.rateMax) + ' per kg, which is a lump sum, so they are left out.'), h('li', null, fInt(bad.foreign) + ' are in a foreign currency and are left out.'), h('li', null, fInt(bad.none) + ' have a blank or unreadable rate, or no weight.')));
  root.append(h('p', {class: 'meta'}, 'Estimated freight margin = (sell rate − buy rate) × chargeable weight, for air exports, for every month of the year. It is an estimate of freight only: other charges, duties and unbooked costs are not in it.'), kp, h('div', {class: 'grid', style: 'margin-top:.9rem'}, card('Estimated freight margin by month', 'Shipment date. Hover a bar for the value.', c1), card('Margin per kg by month', 'Weighted by chargeable weight.', c2), card('Variance: estimated freight margin', 'Change in value and percentage against the earlier period, by any angle.', vcard, 'full'), card('Selling below buy', 'The 40 shipments where the sell rate is under the buy rate. A pricing control issue.', bt, 'full'), eaCard, qual));
  return root;
}
// ================================================================ build your own visual: any measure by any angle, saved to My dashboard
const PAL = ['#4c78a8', '#f58518', '#54a24b', '#e45756', '#72b7b2', '#b279a2', '#9d755d', '#bab0ac'];
const VM = {
  ops: {count: {l: 'Shipments', f: 'int', add: () => 1}, air: {l: 'Air chargeable tonnes', f: 't', add: (i) => (mode[i] ? 0 : chg[i])}, sea: {l: 'Sea TEUs', f: 'int', add: (i) => (mode[i] ? teus[i] : 0)}, inv: {l: 'Shipments invoiced', f: 'int', add: (i) => (invN[i] > 0 ? 1 : 0)}, openfin: {l: 'Financials still open', f: 'int', add: (i) => (COLS.stage.c[i] === STAGE_FIN ? 1 : 0)},
    rmar: {l: 'Estimated freight margin (air export)', f: 'money', add: (i) => (rtype[i] === 0 && rateOK(i) ? rmargin(i) : 0)}, rkg: {l: 'Freight margin per kg (air export)', f: 'rate', num: (i) => (rtype[i] === 0 && rateOK(i) ? rmargin(i) : 0), den: (i) => (rtype[i] === 0 && rateOK(i) ? ckg[i] : 0)},
    lag: {l: 'Days from ops lock to financial lock', f: 'days', num: (i) => (opsD[i] > 0 && finD[i] > 0 ? finD[i] - opsD[i] : 0), den: (i) => (opsD[i] > 0 && finD[i] > 0 ? 1 : 0)}},
  fin: {income: {l: 'Income', f: 'money', add: (i) => pinc[i]}, expense: {l: 'Expense', f: 'money', add: (i) => pexp[i]}, profit: {l: 'Profit', f: 'money', add: (i) => pinc[i] - pexp[i]}, margin: {l: 'Margin', f: 'pct', num: (i) => pinc[i] - pexp[i], den: (i) => pinc[i]}, jobs: {l: 'Jobs', f: 'int', set: (i) => pjob[i]}, lines: {l: 'Job records', f: 'int', add: () => 1}}};
const VD = {ops: [['date', 'Shipment date', () => date], ['inv', 'First invoice date', () => inv1], ['ops', 'Operations lock date', () => opsD], ['fin', 'Financials lock date', () => finD]], fin: [['job', 'Job date', () => pjd]]};
const VT = [['time:day', 'Day'], ['time:week', 'Week'], ['time:month', 'Month'], ['time:quarter', 'Quarter'], ['time:year', 'Year (follows the year setting)']];
const vDims = (ds) => VT.concat(Object.keys(COLS).filter((k) => ds === 'fin' || COLS[k].own).map((k) => [k, COLS[k].l]).sort((a, b) => a[1].localeCompare(b[1])));
const fmtV = (f, v) => (v == null || Number.isNaN(v) ? '–' : f === 'int' ? fInt(Math.round(v)) : f === 't' ? f1(v) + ' t' : f === 'money' ? money(v) : f === 'pct' ? fMargin(v) : f === 'rate' ? fRate(v) : v.toFixed(1) + ' days');
const vLabel = (ds, k) => (VM[ds][k] || {}).l || k, dLabel = (ds, k) => (vDims(ds).find((x) => x[0] === k) || [0, k])[1];
const autoTitle = (c) => vLabel(c.data, c.measure) + ' by ' + dLabel(c.data, c.dim).toLowerCase() + (c.split && c.split !== 'none' ? ' and ' + dLabel(c.data, c.split).toLowerCase() : '');
function runVisual(cfg) {
  if (['p_charge','p_party'].includes(cfg.dim) || ['p_charge','p_party'].includes(cfg.split)) return {err:'Charge/vendor breakdowns are unavailable in the job-level report. Edit this visual to choose another dimension.'};
  const ds = cfg.data, M = (VM[ds] || {})[cfg.measure]; if (!FIN && (ds === 'fin' || ['rmar', 'rkg'].includes(cfg.measure))) return {err: 'Finance access is required.'}; if (!M) return {err: 'Pick a measure.'};
  const ops = ds === 'ops', n = ops ? N : NP, m = ops ? mask({dates: 'none'}) : maskP({dates: 'none'}), df = VD[ds].find((x) => x[0] === cfg.date) || VD[ds][0], da = df[2](), w = win(), tm = cfg.dim.indexOf('time:') === 0, unit = tm ? cfg.dim.slice(5) : null;
  if (!tm && !COLS[cfg.dim]) return {err: 'Pick what to show by.'}; const kd = tm ? null : (ops ? COLS[cfg.dim].c : COLS[cfg.dim].pc), sp = cfg.split && cfg.split !== 'none' && COLS[cfg.split], ks = sp ? (ops ? sp.c : sp.pc) : null, cell = () => ({a: 0, d: 0, ids:new Set(), s: M.set ? new Set() : null});
  const acc = (c, i) => {c.ids.add(i); if (M.set) c.s.add(M.set(i)); else if (M.add) c.a += M.add(i); else { c.a += M.num(i); c.d += M.den(i); } }, val = (c) => (M.set ? c.s.size : M.den ? ((cfg.measure==='margin'?c.d>0:!!c.d) ? c.a / c.d : null) : c.a), merge = (x, y) => {y.ids.forEach(i=>x.ids.add(i));x.a += y.a; x.d += y.d; if (x.s) y.s.forEach((v) => x.s.add(v)); };
  const g = new Map(), stot = new Map(); // g: group -> Map(series -> cell)
  for (let i = 0; i < n; i++) { if (!m[i]) continue; const dv = da[i]; if (!(dv > 0) || dv < w.from || dv > w.to) continue; const gk = tm ? (unit === 'day' ? dv : pStart(unit, dv)) : kd[i], sk = sp ? ks[i] : 0; let r = g.get(gk); if (!r) { r = new Map(); g.set(gk, r); } let c = r.get(sk); if (!c) { c = cell(); r.set(sk, c); } acc(c, i); let t = stot.get(sk); if (!t) { t = cell(); stot.set(sk, t); } acc(t, i); }
  let skeys = [...stot.keys()].sort((a, b) => (val(stot.get(b)) || 0) - (val(stot.get(a)) || 0)), other = false; if (skeys.length > 6) { other = true; skeys = skeys.slice(0, 6); }
  const tot = (r) => { const c = cell(); r.forEach((x) => merge(c, x)); return c; }; let keys = [...g.keys()];
  if (tm) keys.sort((a, b) => a - b); else { keys.sort((a, b) => cfg.sort === 'label' ? COLS[cfg.dim].d[a].localeCompare(COLS[cfg.dim].d[b]) : (val(tot(g.get(b))) || 0) - (val(tot(g.get(a))) || 0)); }
  const lab = (k) => (tm ? (unit === 'day' ? fDay(k) : unit === 'week' ? 'Week of ' + d3.utcFormat('%d %b')(dDate(k)) : unit === 'month' ? d3.utcFormat('%b %Y')(dDate(k)) : pName(unit, k)) : COLS[cfg.dim].d[k]);
  let rows = keys.map((k) => ({label: lab(k), r: g.get(k)})); const top = Math.max(1, parseInt(cfg.top, 10) || 25);
  if (!tm && rows.length > top) { const rest = rows.slice(top), o = new Map(); rest.forEach((x) => x.r.forEach((c, sk) => { let y = o.get(sk); if (!y) { y = cell(); o.set(sk, y); } merge(y, c); })); rows = rows.slice(0, top); if (M.add || M.den || M.set) rows.push({label: 'Other (' + rest.length + ')', r: o}); }
  const names = skeys.map((sk) => (sp ? COLS[cfg.split].d[sk] : M.l)); if (other) names.push('Other');
  const series = names.map((nm, si) => ({name: nm, indices:rows.map(row=>{const c=cell();row.r.forEach((x,sk)=>{if(si<skeys.length?sk===skeys[si]:!skeys.includes(sk))merge(c,x);});return [...c.ids];}), values: rows.map((row) => { if (si < skeys.length) { const c = row.r.get(skeys[si]); return c ? val(c) : null; } const c = cell(); row.r.forEach((x, sk) => { if (!skeys.includes(sk)) merge(c, x); }); return val(c); }), num: rows.map((row) => { if (si < skeys.length) { const c = row.r.get(skeys[si]); return c ? c.a : 0; } const c=cell();row.r.forEach((x,sk)=>{if(!skeys.includes(sk))merge(c,x);});return c.a; }), den: rows.map((row) => { if (si < skeys.length) { const c = row.r.get(skeys[si]); return c ? c.d : 0; } const c=cell();row.r.forEach((x,sk)=>{if(!skeys.includes(sk))merge(c,x);});return c.d; })}));
  const all = cell(); stot.forEach((c) => merge(all, c)); return {indices:[...all.ids],labels: rows.map((x) => x.label), series, f: M.f, total: val(all), ratio: !!M.den, distinct: !!M.set, measure: M.l, tm};
}
function drawChart(box, sp) {
  const type = sp.type, labels = sp.labels, series = sp.series, fmt = sp.fmt; if (!labels.length || !series.length) { box.append(emptyNote()); return; }
  if (type === 'number') { box.append(h('div', {class: 'bignum',role:'button',tabindex:0,onclick:()=>sp.inspect?.()}, sp.total == null ? '–' : fmt(sp.total)), h('div', {class: 'meta'}, sp.caption || '')); return; }
  if (type === 'table') { const head = h('thead', null, h('tr', null, h('th', null, sp.dimLabel || ''), series.map((s) => h('th', {class: 'n'}, s.name)))), body = h('tbody', null, labels.map((l, i) => h('tr', null, h('td', null, l), series.map((s) => h('td', {class: 'n'}, h('button',{type:'button',class:'link',onclick:()=>sp.inspect?.(i,series.indexOf(s))},fmt(s.values[i]))))))); box.append(h('div', {class: 'scroll'}, h('table', {class: 'tbl'}, head, body))); return; }
  const W = sp.w || 640, many = labels.length > 10, H = sp.h || (type === 'hbar' ? Math.max(220, 40 + labels.length * 26) : 300), mb = type === 'hbar' || type === 'donut' ? 20 : many ? 74 : 34, ml = type === 'hbar' ? 150 : 56, mt = series.length > 1 ? 30 : 16, mr = 12;
  const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', '0 0 ' + W + ' ' + H).attr('role', 'img').attr('aria-label', sp.alt || 'Chart');
  if (series.length > 1 && type !== 'donut') series.forEach((s, k) => { svg.append('rect').attr('x', 6 + k * 118).attr('y', 6).attr('width', 10).attr('height', 10).attr('fill', PAL[k % 8]); svg.append('text').attr('class', 'tick').attr('x', 20 + k * 118).attr('y', 15).text(s.name.length > 14 ? s.name.slice(0, 13) + '…' : s.name); });
  const cut = (t, k) => (String(t).length > k ? String(t).slice(0, k - 1) + '…' : String(t));
  if (type === 'donut') { const s0 = series[0].values.map((v) => Math.max(0, v || 0)), sum = d3.sum(s0) || 1, R = Math.min(H, W) / 2 - 14, arc = d3.arc().innerRadius(R * 0.58).outerRadius(R), g = svg.append('g').attr('transform', 'translate(' + (R + 14) + ',' + H / 2 + ')');
    d3.pie().sort(null)(s0).forEach((a, k) => { g.append('path').attr('d', arc(a)).attr('fill', PAL[k % 8]).style('cursor','pointer').on('click',()=>sp.inspect?.(k,0)).append('title').text(labels[k] + ': ' + fmt(series[0].values[k]) + ' (' + (s0[k] / sum * 100).toFixed(1) + '%)'); });
    labels.slice(0, 12).forEach((l, k) => { svg.append('rect').attr('x', R * 2 + 40).attr('y', 20 + k * 20).attr('width', 10).attr('height', 10).attr('fill', PAL[k % 8]); svg.append('text').attr('class', 'tick').attr('x', R * 2 + 56).attr('y', 29 + k * 20).text(cut(l, 22) + '  ' + (s0[k] / sum * 100).toFixed(0) + '%'); }); return; }
  const stack = type === 'stack', vals = series.map((s) => s.values.map((v) => v || 0)), hi = stack ? d3.max(labels.map((_, i) => d3.sum(vals, (v) => Math.max(0, v[i])))) : d3.max(vals, (v) => d3.max(v)), lo = Math.min(0, stack ? d3.min(labels.map((_, i) => d3.sum(vals, (v) => Math.min(0, v[i])))) : d3.min(vals, (v) => d3.min(v)));
  if (type === 'hbar') { const x = d3.scaleLinear([lo, hi || 1], [ml, W - mr - 60]).nice(4), y = d3.scaleBand(labels.map((_, i) => i), [mt, H - mb]).padding(0.25), bh = y.bandwidth() / series.length;
    x.ticks(4).forEach((t) => { svg.append('line').attr('x1', x(t)).attr('x2', x(t)).attr('y1', mt).attr('y2', H - mb).style('stroke', 'var(--grid)'); svg.append('text').attr('class', 'tick').attr('x', x(t)).attr('y', H - 4).attr('text-anchor', 'middle').text(fmt(t)); });
    labels.forEach((l, i) => { svg.append('text').attr('class', 'tick').attr('x', ml - 6).attr('y', y(i) + y.bandwidth() / 2).attr('text-anchor', 'end').attr('dominant-baseline', 'middle').text(cut(l, 22)).append('title').text(l); series.forEach((s, k) => { const v = s.values[i] || 0; svg.append('rect').attr('x', x(Math.min(0, v))).attr('y', y(i) + k * bh).attr('width', Math.abs(x(v) - x(0))).attr('height', bh).attr('fill', PAL[k % 8]).attr('rx', 2).style('cursor','pointer').on('click',()=>sp.inspect?.(i,k)).append('title').text(l + ' · ' + s.name + ': ' + fmt(s.values[i])); if (series.length === 1) svg.append('text').attr('class', 'lbl').attr('x', x(Math.max(0, v)) + 4).attr('y', y(i) + bh / 2).attr('dominant-baseline', 'middle').text(fmt(s.values[i])); }); }); return; }
  const y = d3.scaleLinear([lo, hi || 1], [H - mb, mt]).nice(4), x = d3.scaleBand(labels.map((_, i) => i), [ml, W - mr]).padding(0.2), bw = x.bandwidth() / (stack || type === 'line' ? 1 : series.length);
  y.ticks(4).forEach((t) => { svg.append('line').attr('x1', ml).attr('x2', W - mr).attr('y1', y(t)).attr('y2', y(t)).style('stroke', 'var(--grid)'); svg.append('text').attr('class', 'tick').attr('x', ml - 6).attr('y', y(t)).attr('text-anchor', 'end').attr('dominant-baseline', 'middle').text(fmt(t)); });
  const step = Math.ceil(labels.length / 14); labels.forEach((l, i) => { if (i % step) return; svg.append('text').attr('class', 'tick').attr('transform', 'translate(' + (x(i) + x.bandwidth() / 2) + ',' + (H - mb + 14) + ')' + (many ? ' rotate(-38)' : '')).attr('text-anchor', many ? 'end' : 'middle').text(cut(l, 14)); });
  if (type === 'line') { series.forEach((s, k) => { const pts = s.values.map((v, i) => (v == null ? null : [x(i) + x.bandwidth() / 2, y(v)])).filter(Boolean); svg.append('path').attr('d', d3.line()(pts)).attr('fill', 'none').attr('stroke', PAL[k % 8]).attr('stroke-width', 2); s.values.forEach((v, i) => { if (v != null) svg.append('circle').attr('cx', x(i) + x.bandwidth() / 2).attr('cy', y(v)).attr('r', 3.5).attr('fill', PAL[k % 8]).style('cursor','pointer').on('click',()=>sp.inspect?.(i,k)).append('title').text(labels[i] + ' · ' + s.name + ': ' + fmt(v)); }); }); return; }
  labels.forEach((l, i) => { let up = 0, dn = 0; series.forEach((s, k) => { const v = s.values[i] || 0; let y0, y1, xx; if (stack) { if (v >= 0) { y0 = up; y1 = up + v; up = y1; } else { y0 = dn; y1 = dn + v; dn = y1; } xx = x(i); } else { y0 = 0; y1 = v; xx = x(i) + k * bw; } svg.append('rect').attr('x', xx).attr('y', Math.min(y(y0), y(y1))).attr('width', bw).attr('height', Math.abs(y(y0) - y(y1))).attr('fill', PAL[k % 8]).attr('rx', 2).style('cursor','pointer').on('click',()=>sp.inspect?.(i,k)).append('title').text(l + ' · ' + s.name + ': ' + fmt(s.values[i])); });
    if (series.length === 1 && labels.length <= 14) svg.append('text').attr('class', 'lbl').attr('x', x(i) + x.bandwidth() / 2).attr('y', y(Math.max(0, vals[0][i])) - 4).attr('text-anchor', 'middle').text(fmt(series[0].values[i])); });
}
const visGet = () => { try { return JSON.parse(localStorage.getItem('ngVisuals') || '[]'); } catch (e) { return []; } };
const visSet = (a) => { try { localStorage.setItem('ngVisuals', JSON.stringify(a)); } catch (e) { /* not available */ } srvPut('visuals', a); };
const visId = () => 'v' + Date.now().toString(36) + Math.floor(Math.random() * 1e4).toString(36);
function visSave(cfg, editId) { const all = visGet(), c = Object.assign({}, cfg, {title: cfg.title || autoTitle(cfg)}); if (editId && all.some((x) => x.id === editId)) { c.id = editId; all[all.findIndex((x) => x.id === editId)] = c; } else { c.id = visId(); all.push(c); } visSet(all); return c.id; }
function visualMetricPayload(cfg,res,row,series){const map={ops:{count:'ops.shipments',air:'ops.air_weight',sea:'ops.teu',inv:'ops.invoice_reference_count',openfin:'ops.financials_open',rmar:'ops.rate_margin',rkg:'ops.rate_margin_kg',lag:'ops.lock_lag'},fin:{income:'profit.income',expense:'profit.expense',profit:'profit.gp',margin:'profit.margin',jobs:'profit.jobs',lines:'profit.rows'}},metric=map[cfg.data][cfg.measure],q=metricTraceSelection(metric,cfg.title||autoTitle(cfg));q.indices=row==null?res.indices:res.series[series].indices[row];q.previous_indices=[];q.compare=false;q.displayed_value=row==null?res.total:res.series[series].values[row];q.context.visual_definition=cfg;q.context.date_basis=(VD[cfg.data].find(x=>x[0]===cfg.date)||VD[cfg.data][0])[1];q.context.segment=row==null?'Entire visual':{row:res.labels[row],series:res.series[series].name};return q;}
function visSpec(cfg, res, w) { return {inspect:(row,series)=>window.MetricTrace?.openWithRequest(visualMetricPayload(cfg,res,row,series)),type: cfg.type, labels: res.labels, series: res.series, fmt: (v) => fmtV(res.f, v), total: res.total, dimLabel: cfg.dim.indexOf('time:') === 0 ? dLabel(cfg.data, cfg.dim) : dLabel(cfg.data, cfg.dim), caption: res.measure + ' for the filters above', alt: cfg.title || autoTitle(cfg), w: w}; }
function visCsv(res, cfg) { const q = (x) => '"' + String(typeof x==='string'&&/^[\s]*[=+@-]|^[\t\r]/.test(x)?"'"+x:x == null ? '' : x).replace(/"/g, '""') + '"', rows = [[dLabel(cfg.data, cfg.dim)].concat(res.series.map((s) => s.name))]; res.labels.forEach((l, i) => rows.push([l].concat(res.series.map((s) => (s.values[i] == null ? '' : s.values[i]))))); return '\ufeff' + rows.map((r) => r.map(q).join(',')).join('\n'); }
function dlText(name, text, mime) { const a = h('a', {href: URL.createObjectURL(new Blob([text], {type: mime})), download: name}); document.body.append(a); a.click(); a.remove(); }
function visExcel(cfg, res) { const nm = (cfg.title || autoTitle(cfg)).replace(/[^A-Za-z0-9]+/g, '_').slice(0, 40), nr = res.labels.length + 1, ns = res.series.length;
  let rows; if (res.ratio) { rows = [[dLabel(cfg.data, cfg.dim), 'Numerator', 'Denominator', res.measure].map(HDR)].concat(res.labels.map((l, i) => { const x = i + 2, a = d3.sum(res.series, (s) => s.num[i]), d_ = d3.sum(res.series, (s) => s.den[i]); return [l, {v: +a.toFixed(4), s: 3}, {v: +d_.toFixed(4), s: 3}, {f: 'IF(C' + x + '=0,"",B' + x + '/C' + x + ')', s: res.f === 'pct' ? 2 : 3}]; })); }
  else { const L = (k) => String.fromCharCode(66 + k); rows = [[dLabel(cfg.data, cfg.dim)].concat(res.series.map((s) => s.name), ns > 1 ? ['Total'] : [], ['Share']).map(HDR)].concat(res.labels.map((l, i) => { const x = i + 2, tc = ns > 1 ? L(ns) : 'B'; return [l].concat(res.series.map((s) => ({v: s.values[i] == null ? 0 : +s.values[i].toFixed(4), s: 3})), ns > 1 ? [{f: 'SUM(B' + x + ':' + L(ns - 1) + x + ')', s: 3}] : [], res.distinct ? [''] : [{f: 'IF(SUM(' + tc + '$2:' + tc + '$' + nr + ')=0,"",' + tc + x + '/SUM(' + tc + '$2:' + tc + '$' + nr + '))', s: 2}]); })); }
  downloadXlsx(nm + '_' + fIso(dDate(MAXDATE)) + '.xlsx', [{name: 'Visual', freeze: true, filter: true, cols: [40, 16, 16, 16, 16, 16, 16, 16, 12], rows}, settingsSheet([[HDR('Visual'), cfg.title || autoTitle(cfg)], [HDR('Data'), cfg.data === 'ops' ? 'Shipments (register)' : 'Job records (profit report)']])]); }
function visCard(cfg, o) { o = o || {}; const res = runVisual(cfg), body = h('div'), msg = h('span', {class: 'meta'});
  if (res.err) body.append(h('p', {class: 'empty'}, res.err)); else drawChart(body, visSpec(cfg, res, o.w));
  const acts = !res.err ? h('div', {class: 'frow vacts'}, (o.actions||[]).map(([l, f]) => h('button', {type: 'button', class: 'btn', onclick: f}, l)), dlButton('Calculation & records',()=>window.MetricTrace?.openWithRequest(visualMetricPayload(cfg,res))),dlButton('Records Excel',()=>window.MetricTrace?.exportWithRequest(visualMetricPayload(cfg,res)).catch(e=>alert(e.message))),res.err ? null : dlButton('Summary Excel', () => visExcel(cfg, res)), res.err ? null : h('button', {type: 'button', class: 'btn', onclick: () => dlText('visual.csv', visCsv(res, cfg), 'text/csv')}, 'CSV'), msg) : null;
  return card(cfg.title || autoTitle(cfg), vLabel(cfg.data, cfg.measure) + ' · by ' + dLabel(cfg.data, cfg.dim).toLowerCase() + (cfg.split && cfg.split !== 'none' ? ' · split by ' + dLabel(cfg.data, cfg.split).toLowerCase() : '') + ' · ' + (VD[cfg.data].find((x) => x[0] === cfg.date) || VD[cfg.data][0])[1].toLowerCase() + ' · follows the filters above', h('div', null, body, acts), o.cls); }
const defCfg = (ds) => ds === 'fin' ? {data: 'fin', measure: 'profit', dim: 'branch', split: 'none', date: 'job', type: 'hbar', top: 25, sort: 'value', title: ''} : {data: 'ops', measure: 'count', dim: 'time:month', split: 'none', date: 'date', type: 'bar', top: 25, sort: 'value', title: ''};
S.vis = {cfg: defCfg('ops'), editId: null, note: ''};
const VTEMPLATES = [{data: 'ops', measure: 'count', dim: 'time:month', split: 'report', date: 'date', type: 'stack', top: 25, sort: 'value', title: 'Shipments by month and report'}, {data: 'fin', measure: 'profit', dim: 'customer', split: 'none', date: 'job', type: 'hbar', top: 25, sort: 'value', title: 'Top 25 customers by profit'}, {data: 'fin', measure: 'profit', dim: 'x_salesperson', split: 'none', date: 'job', type: 'hbar', top: 25, sort: 'value', title: 'Profit by sales person'},
  {data: 'ops', measure: 'rmar', dim: 'time:month', split: 'none', date: 'date', type: 'bar', top: 25, sort: 'value', title: 'Estimated freight margin by month'}, {data: 'ops', measure: 'inv', dim: 'time:month', split: 'none', date: 'inv', type: 'line', top: 25, sort: 'value', title: 'Shipments invoiced by month'}, {data: 'ops', measure: 'openfin', dim: 'branch', split: 'none', date: 'date', type: 'hbar', top: 25, sort: 'value', title: 'Financials still open, by branch'},
  {data: 'ops', measure: 'air', dim: 'destination', split: 'none', date: 'date', type: 'hbar', top: 25, sort: 'value', title: 'Air tonnes by destination'}, {data: 'fin', measure: 'income', dim: 'branch', split: 'none', date: 'job', type: 'donut', top: 8, sort: 'value', title: 'Income by branch'}];
function vBuild() {
  const v = S.vis, c = v.cfg, root = h('div'), ds = c.data, setC = (k, val) => { c[k] = val; renderAll(); };
  const L = (txt, el) => h('label', {class: 'f'}, h('span', null, txt), el), measures = Object.keys(VM[ds]).filter((k) => FIN || !['inv', 'rmar', 'rkg'].includes(k)).map((k) => [k, VM[ds][k].l]);
  const title = h('input', {type: 'text', value: c.title, placeholder: autoTitle(c), 'aria-label': 'Title', style: 'min-width:16rem'}); title.addEventListener('input', () => { c.title = title.value; });
  const ctl = h('div', {class: 'card', style: 'margin-bottom:.9rem'}, h('h2', {class: 'h'}, v.editId ? 'Change this visual' : 'Build a visual'), h('p', {class: 'note'}, 'Pick what to measure, how to cut it and how to draw it. The filters above apply to every visual. Save it to keep it on My dashboard.'),
    h('div', {class: 'frow'}, L('Data', sel([['ops', 'Shipments (register)']].concat(FIN ? [['fin', 'Job records (finance)']] : []), ds, (x) => { v.cfg = Object.assign(defCfg(x), {title: c.title, type: c.type}); renderAll(); })), L('Measure', sel(measures, c.measure, (x) => setC('measure', x))), L('Show by', sel(vDims(ds), c.dim, (x) => { c.dim = x; if (x.indexOf('time:') === 0 && c.type === 'hbar') c.type = 'bar'; renderAll(); })), L('Split by', sel([['none', 'No split']].concat(vDims(ds).filter((x) => x[0].indexOf('time:') !== 0)), c.split, (x) => setC('split', x)))),
    h('div', {class: 'frow'}, L('Date used', sel(VD[ds].map((x) => [x[0], x[1]]), c.date, (x) => setC('date', x))), L('Chart', sel([['bar', 'Bars'], ['hbar', 'Horizontal bars'], ['stack', 'Stacked bars'], ['line', 'Line'], ['donut', 'Donut'], ['table', 'Table'], ['number', 'Single number']], c.type, (x) => setC('type', x))), L('How many rows', sel([['5', 'Top 5'], ['8', 'Top 8'], ['10', 'Top 10'], ['15', 'Top 15'], ['25', 'Top 25'], ['50', 'Top 50']], String(c.top), (x) => setC('top', parseInt(x, 10)))), L('Order by', sel([['value', 'Largest first'], ['label', 'Name']], c.sort, (x) => setC('sort', x))), L('Title', title)));
  const res = runVisual(c), prev = h('div'); if (res.err) prev.append(h('p', {class: 'empty'}, res.err)); else drawChart(prev, visSpec(c, res));
  const note = h('span', {class: 'meta'}, v.note); const save = (asNew) => { const id = visSave(c, asNew ? null : v.editId); v.editId = id; v.note = 'Saved to My dashboard'; renderAll(); };
  const acts = h('div', {class: 'frow'}, h('button', {type: 'button', class: 'btn on', onclick: () => save(false)}, v.editId ? 'Save changes' : 'Save to My dashboard'), v.editId ? h('button', {type: 'button', class: 'btn', onclick: () => save(true)}, 'Save as a new copy') : null, h('button', {type: 'button', class: 'btn', onclick: () => { v.cfg = defCfg('ops'); v.editId = null; v.note = ''; renderAll(); }}, 'Start again'), h('button', {type: 'button', class: 'btn', onclick: () => goto('mine', 'v_mine')}, 'Open My dashboard'), res.err ? null : dlButton('Excel', () => visExcel(c, res)), res.err ? null : h('button', {type: 'button', class: 'btn', onclick: () => dlText('visual.csv', visCsv(res, c), 'text/csv')}, 'CSV'), note);
  root.append(ctl, card(c.title || autoTitle(c), 'Preview · follows the filters above · ' + (res.err ? '' : 'total ' + fmtV(res.f, res.total)), h('div', null, prev, acts), 'full'), h('p', {class: 'meta'}, 'Tip: shipments invoiced by month, split by branch, with the date set to first invoice date, shows billing by branch. Estimated freight margin by sales person shows who prices well.'));
  return root;
}
function vMine() {
  const all = visGet(), root = h('div'), mv = (i, d) => { const a = visGet(), j = i + d; if (j < 0 || j >= a.length) return; [a[i], a[j]] = [a[j], a[i]]; visSet(a); renderAll(); };
  const bar = h('div', {class: 'frow', style: 'margin-bottom:.8rem'}, h('button', {type: 'button', class: 'btn on', onclick: () => { S.vis = {cfg: defCfg('ops'), editId: null, note: ''}; goto('mine', 'v_build'); }}, 'Build a new visual'), h('button', {type: 'button', class: 'btn', onclick: () => dlText('my_visuals.json', JSON.stringify(visGet(), null, 1), 'application/json')}, 'Export my visuals'),
    (() => { const f = h('input', {type: 'file', accept: '.json', style: 'display:none'}); f.addEventListener('change', () => { const r = new FileReader(); r.onload = () => { try { const a = JSON.parse(r.result), cur = visGet(); a.forEach((x) => cur.push(Object.assign({}, x, {id: visId()}))); visSet(cur); renderAll(); } catch (e) { /* not a visuals file */ } }; if (f.files[0]) r.readAsText(f.files[0]); }); return h('span', null, h('button', {type: 'button', class: 'btn', onclick: () => f.click()}, 'Import visuals'), f); })(), h('span', {class: 'meta'}, 'Saved in this browser. In the live system they are saved to your login and can be shared with the team.'));
  root.append(bar);
  if (!all.length) { root.append(card('Start from a template', 'Pick one to add it to your dashboard, then change it any way you like.', h('div', {class: 'frow'}, VTEMPLATES.map((t) => h('button', {type: 'button', class: 'btn', onclick: () => { visSave(t, null); renderAll(); }}, t.title))), 'full')); return root; }
  root.append(h('div', {class: 'vgrid'}, all.map((cfg, i) => visCard(cfg, {w: 520, actions: [['Edit', () => { S.vis = {cfg: Object.assign({}, cfg), editId: cfg.id, note: ''}; goto('mine', 'v_build'); }], ['Copy', () => { const a = visGet(); a.splice(i + 1, 0, Object.assign({}, cfg, {id: visId(), title: (cfg.title || autoTitle(cfg)) + ' (copy)'})); visSet(a); renderAll(); }], ['Left', () => mv(i, -1)], ['Right', () => mv(i, 1)], ['Delete', () => { visSet(visGet().filter((x) => x.id !== cfg.id)); renderAll(); }]]}))),
    h('div', {class: 'frow', style: 'margin-top:.8rem'}, h('span', {class: 'meta'}, 'Add a template: '), VTEMPLATES.map((t) => h('button', {type: 'button', class: 'btn', onclick: () => { visSave(t, null); renderAll(); }}, t.title))));
  return root;
}

// ================================================================ agent variation report: the ERP's Variation Report layout, 12 months, plus change columns
S.vr = {q: '', page: 0, size: 25, sort: {sort: 'label', dir: 1}, hide: new Set()};
const LOPN = ['AE', 'AI', 'SE', 'SI'];
function agentRows() {
  const m = mask({dates: 'none'}), asOf = MAXDATE, ms0 = pStart('month', asOf), starts = [], idx = new Map(), nA = COLS.agent.d.length, cnt = new Array(nA), own = new Array(nA), oc = COLS.job_owner.c, last = new Int32Array(nA).fill(-1), ac = COLS.agent.c, thr = S.def.declinePct / 100, [ay, am] = ymd(asOf);
  for (let k = 0; k < 12; k++) { const st = addMonths(ms0, -k); starts.push(st); idx.set(st, k); }
  for (let i = 0; i < N; i++) { if (!m[i]) continue; const a = ac[i]; let c = cnt[a]; if (!c) c = cnt[a] = new Int32Array(12); const k = idx.get(mStart[i]); if (k !== undefined) c[k]++; let om = own[a]; if (!om) om = own[a] = new Map(); const pd0 = om.get(oc[i]); if (pd0 === undefined || date[i] > pd0) om.set(oc[i], date[i]); if (last[a] < 0 || date[i] > date[last[a]] || (date[i] === date[last[a]] && i > last[a])) last[a] = i; }
  const rows = [], info = D.agentInfo;
  for (let a = 0; a < nA; a++) { const c = cnt[a]; if (!c) continue; let total = 0; for (let k = 0; k < 12; k++) total += c[k]; if (!total) continue; const li = last[a], inf = info[a] || ['', '', '', '', '', ''], [ly, lm] = ymd(date[li]);
    const a3 = (c[1] + c[2] + c[3]) / 3, p3 = (c[4] + c[5] + c[6]) / 3, since = (ay - ly) * 12 + (am - lm), ch = p3 === 0 ? null : Math.round((a3 / p3 - 1) * 1e9) / 1e9;
    const status = since >= S.def.lapsedMonths ? 'Lapsed' : p3 === 0 ? 'New' : ch <= -thr ? 'Declining' : ch >= thr ? 'Growing' : 'Steady';
    const jo = COLS.job_owner.d, prevOwners = [...own[a].entries()].filter(([o]) => o !== oc[li] && jo[o] !== '(blank)').sort((x, y) => y[1] - x[1] || jo[x[0]].localeCompare(jo[y[0]])).slice(0, 5).map(([o, dy]) => jo[o] + ' (' + d3.utcFormat('%b %Y')(dDate(dy)) + ')').join(', ');
    const r = {a, prevOwners, label: COLS.agent.d[a], country: inf[0], contact: inf[4] || '', email: inf[5] || '', network: inf[1], conf: inf[2], owner: catv('job_owner', li), sales: catv('x_salesperson', li), lop: LOPN[rtype[li]], lastDate: date[li], total, d1: c[1] - c[2], p1: c[2] === 0 ? null : (c[1] - c[2]) / c[2], a3, p3: ch, prev3: p3, since, status};
    for (let k = 0; k < 12; k++) r['m' + k] = c[k]; rows.push(r); }
  return {rows, starts, asOf};
}
function vVariation() {
  const vr = S.vr, {rows, starts, asOf} = agentRows(), root = h('div'), mlab = starts.map((st) => d3.utcFormat('%b %Y')(dDate(st))), nomSel = S.sel.nomination || new Set();
  const cols = [{k: 'label', t: 'Agent Name'}, {k: 'country', t: 'Country'}, {k: 'contact', t: 'Contact Name'}, {k: 'email', t: 'Email Address'}, {k: 'network', t: 'Network'}, {k: 'conf', t: 'Conference Attended By'}, {k: 'owner', t: 'Job Owner'}, {k: 'prevOwners', t: 'Previous Job Owners'}, {k: 'sales', t: 'Sales Person'}, {k: 'lop', t: 'Last Shipment LOP'}, {k: 'lastDate', t: 'Last Shipment Date'}]
    .concat(mlab.map((l, k) => ({k: 'm' + k, t: l, num: true})), [{k: 'total', t: 'Total', num: true}, {k: 'd1', t: mlab[1] + ' vs ' + mlab[2], num: true}, {k: 'p1', t: 'Change %', num: true}, {k: 'a3', t: 'Last 3 months average', num: true}, {k: 'p3', t: 'vs previous 3 months', num: true}, {k: 'since', t: 'Months since last shipment', num: true}, {k: 'status', t: 'Status'}]);
  const vis = () => cols.filter((c) => !vr.hide.has(c.k)), nomBtn = (lab, code, tip) => h('button', {type: 'button', class: 'btn' + ((code == null ? nomSel.size === 0 : nomSel.size === 1 && nomSel.has(code)) ? ' on' : ''), title: tip || '', onclick: () => { if (code == null) delete S.sel.nomination; else S.sel.nomination = new Set([code]); vr.page = 0; renderAll(); }}, lab);
  const tabs = h('div', {class: 'segs'}, nomBtn('All shipments', null), ['Agent Nomination', 'Self Nomination', 'Sub Agent'].map((n) => { const code = COLS.nomination.d.indexOf(n); return code < 0 ? null : nomBtn(n === 'Self Nomination' ? 'Free Hand' : n, code, n === 'Self Nomination' ? 'Free Hand is read as Self Nomination in the register' : ''); }));
  const search = h('input', {type: 'search', value: vr.q, placeholder: 'Search agent, country, job owner, sales person', 'aria-label': 'Search', style: 'min-width:14rem'}), sizeSel = h('select', {'aria-label': 'Entries'}, [10, 25, 50, 100, 500].map((n) => h('option', {value: n, selected: vr.size === n}, n)));
  const thead = h('thead'), tbody = h('tbody'), info = h('p', {class: 'note'}), pager = h('div', {class: 'frow'}); let list = [];
  const fmtC = (c, r) => { const v = r[c.k]; if (c.k === 'lastDate') return fIso(dDate(v)); if (c.k === 'p1' || c.k === 'p3') return v == null ? '–' : fPctS(v); if (c.k === 'a3') return v.toFixed(1); if (c.k === 'd1') return (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v); return typeof v === 'number' ? fInt(v) : (v || ''); };
  const draw = () => { const q = vr.q.trim().toLowerCase(), st = vr.sort, f = (a, b) => { const x = a[st.sort], y = b[st.sort]; if (typeof x === 'string' || typeof y === 'string') return String(x || '').localeCompare(String(y || '')); return (x == null ? -1e18 : x) - (y == null ? -1e18 : y); };
    list = rows.filter((r) => !q || (r.label + ' ' + r.country + ' ' + r.owner + ' ' + r.prevOwners + ' ' + r.sales + ' ' + r.network).toLowerCase().includes(q)).sort((a, b) => f(a, b) * st.dir); const pages = Math.max(1, Math.ceil(list.length / vr.size)); vr.page = Math.min(vr.page, pages - 1); const from = vr.page * vr.size, shown = list.slice(from, from + vr.size), vc = vis(), agSel = S.sel.agent || new Set();
    thead.replaceChildren(sortHead(vc, st, draw)); tbody.replaceChildren(...shown.map((r) => h('tr', {class: 'click' + (agSel.has(r.a) ? ' on' : ''), onclick: () => toggle('agent', r.a)}, vc.map((c) => h('td', {class: (c.num ? 'n ' : '') + (c.k === 'status' ? 'st-' + r.status.toLowerCase() : '') + ((c.k === 'd1' || c.k === 'p1' || c.k === 'p3') ? (r[c.k] > 0 ? ' ok' : r[c.k] < 0 ? ' bad' : '') : '')}, fmtC(c, r))))));
    info.textContent = 'Showing ' + (list.length ? from + 1 : 0) + ' to ' + Math.min(from + vr.size, list.length) + ' of ' + fInt(list.length) + ' agents'; pager.replaceChildren(h('button', {type: 'button', class: 'btn', disabled: vr.page === 0, onclick: () => { vr.page--; draw(); }}, 'Previous'), h('span', {class: 'meta'}, 'Page ' + (vr.page + 1) + ' of ' + pages), h('button', {type: 'button', class: 'btn', disabled: vr.page >= pages - 1, onclick: () => { vr.page++; draw(); }}, 'Next')); };
  search.addEventListener('input', () => { vr.q = search.value; vr.page = 0; draw(); }); sizeSel.addEventListener('change', () => { vr.size = parseInt(sizeSel.value, 10); vr.page = 0; draw(); });
  const colMenu = h('details', {class: 'colmenu'}, h('summary', {class: 'btn'}, 'Column visibility'), h('div', {class: 'colbox'}, cols.map((c) => h('label', {class: 'mo'}, h('input', {type: 'checkbox', checked: !vr.hide.has(c.k), onchange: () => { if (vr.hide.has(c.k)) vr.hide.delete(c.k); else vr.hide.add(c.k); renderAll(); }}), h('span', {class: 'mt'}, c.t)))));
  const csv = () => { const q = (x) => '"' + String(typeof x==='string'&&/^[\s]*[=+@-]|^[\t\r]/.test(x)?"'"+x:x == null ? '' : x).replace(/"/g, '""') + '"', vc = vis(); dlText('variation_report.csv', '\ufeff' + [vc.map((c) => q(c.t)).join(',')].concat(list.map((r) => vc.map((c) => q(c.k === 'lastDate' ? fIso(dDate(r[c.k])) : c.k === 'p1' || c.k === 'p3' ? (r[c.k] == null ? '' : (r[c.k] * 100).toFixed(1) + '%') : r[c.k])).join(','))).join('\n'), 'text/csv'); };
  const excel = () => { const [ay, am] = ymd(asOf), ad = dayOf2(asOf), thr = S.def.declinePct / 100, N_ = S.def.lapsedMonths, asd = 'DATE(' + ay + ',' + (am + 1) + ',' + ad + ')', n1 = list.length + 1, L = colL;
    const base = ['Agent Name', 'Country', 'Contact Name', 'Email Address', 'Network', 'Conference Attended By', 'Job Owner', 'Previous Job Owners (month of last shipment)', 'Sales Person', 'Last Shipment LOP', 'Last Shipment Date'], nb = base.length, M0 = nb, TOT = nb + 12, D1 = TOT + 1, P1 = TOT + 2, A3 = TOT + 3, PV = TOT + 4, P3 = TOT + 5, SN = TOT + 6, LD = nb - 1;
    const head = base.concat(mlab, ['Total', mlab[1] + ' vs ' + mlab[2], 'Change %', 'Last 3 months average', 'Previous 3 months average', 'vs previous 3 months', 'Months since last shipment', 'Status']).map(HDR);
    const body = list.map((r, i) => { const x = i + 2, c = (k) => L(k) + x; return [r.label, r.country, r.contact, r.email, r.network, r.conf, r.owner, r.prevOwners, r.sales, r.lop, {v: r.lastDate + 25569, s: 5}].concat(Array.from({length: 12}, (_, k) => ({v: r['m' + k], s: 3})), [{f: 'SUM(' + c(M0) + ':' + c(M0 + 11) + ')', s: 3}, {f: c(M0 + 1) + '-' + c(M0 + 2), s: 3}, {f: 'IF(' + c(M0 + 2) + '=0,"",(' + c(M0 + 1) + '-' + c(M0 + 2) + ')/' + c(M0 + 2) + ')', s: 2}, {f: 'AVERAGE(' + c(M0 + 1) + ':' + c(M0 + 3) + ')', s: 4}, {f: 'AVERAGE(' + c(M0 + 4) + ':' + c(M0 + 6) + ')', s: 4}, {f: 'IF(' + c(PV) + '=0,"",' + c(A3) + '/' + c(PV) + '-1)', s: 2}, {f: '(YEAR(' + asd + ')-YEAR(' + c(LD) + '))*12+MONTH(' + asd + ')-MONTH(' + c(LD) + ')', s: 3}, {f: 'IF(' + c(SN) + '>=' + N_ + ',"Lapsed",IF(' + c(PV) + '=0,"New",IF(' + c(A3) + '/' + c(PV) + '-1<=-' + thr + ',"Declining",IF(' + c(A3) + '/' + c(PV) + '-1>=' + thr + ',"Growing","Steady"))))'}]); });
    const tot = [HDR('Total')].concat(Array(nb - 1).fill(''), Array.from({length: 12}, (_, k) => ({f: 'SUM(' + L(M0 + k) + '2:' + L(M0 + k) + n1 + ')', s: 3})), [{f: 'SUM(' + L(TOT) + '2:' + L(TOT) + n1 + ')', s: 3}]);
    downloadXlsx('agent_variation_report_' + fIso(dDate(asOf)) + '.xlsx', [{name: 'Variation report', freeze: true, filter: true, cols: [38, 18, 16, 24, 18, 20, 18, 42, 18, 8, 13].concat(Array(12).fill(9), [9, 12, 10, 12, 12, 12, 12, 12]), rows: [head].concat(body, [tot])}, settingsSheet([[HDR('Months'), mlab[0] + ' to ' + mlab[11] + ' (current month to ' + fIso(dDate(asOf)) + ')'], [HDR('Declining or growing'), 'Last 3 complete months average against the previous 3, at least ' + S.def.declinePct + '%'], [HDR('Lapsed'), 'No shipment for ' + N_ + ' months or more'], [HDR('Job owner'), 'The owner of the agent’s latest shipment; previous owners are the 5 before, each with the month of their latest shipment for this agent'], [HDR('Agent'), 'Booking Thru; the customer where Booking Thru is Self; names follow the Organization master']])]); };
  draw();
  root.append(h('div', {class: 'card', style: 'margin-bottom:.9rem'}, h('h2', {class: 'h'}, 'Agent variation report'), h('p', {class: 'note'}, 'Shipments per agent for the last 12 months, as in the ERP’s Variation Report, with change columns added. The agent is the Booking Thru party, or the customer where the booking is Self. Company, report and other filters above apply; the date range does not (it always shows 12 months to ' + fDay(asOf) + ').'),
    h('div', {class: 'frow'}, tabs), h('div', {class: 'frow'}, h('label', {class: 'f'}, h('span', null, 'Show'), sizeSel), h('label', {class: 'f'}, h('span', null, 'Search'), search), h('button', {type: 'button', class: 'btn', onclick: () => window.print()}, 'Print'), h('button', {type: 'button', class: 'btn', onclick: csv}, 'CSV'), dlButton('Excel', excel), colMenu),
    h('p', {class: 'meta'}, 'Status: Lapsed = no shipment for ' + S.def.lapsedMonths + ' months or more · Declining / Growing = the last 3 complete months average moved by at least ' + S.def.declinePct + '% against the 3 before · New = nothing in those earlier 3 months. Job Owner is the owner of the agent’s latest shipment; Previous Job Owners lists the 5 before, each with the month of their latest shipment for the agent. Contact name and email appear as soon as the Organization master export includes them. Limits are under Definitions.')),
    card('Agents', null, h('div', null, info, h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, thead, tbody)), pager), 'full'));
  return root;
}
const colL = (i) => (i < 26 ? String.fromCharCode(65 + i) : 'A' + String.fromCharCode(65 + i - 26));
const dayOf2 = (day) => { const d0 = dDate(day); return d0.getUTCDate(); };

// ================================================================ sales performance report: the ERP's layout, one row per agent, LOB tabs
S.sp = {q: '', page: 0, size: 25, sort: {sort: 'total', dir: -1}, hide: new Set()};
function vSales() {
  const sp = S.sp, {rows, starts, asOf} = agentRows(), root = h('div'), repSel = S.sel.report || new Set(), dd = dDate(asOf), ordn = ['1st', '2nd', '3rd', '4th', '5th'][Math.ceil(dd.getUTCDate() / 7) - 1], mlab = starts.map((st, k) => (k === 0 ? d3.utcFormat('%b')(dDate(st)) + ' ' + ordn + ' Week' : d3.utcFormat('%b %Y')(dDate(st))));
  const cols = [{k: 'sales', t: 'SalesPerson'}, {k: 'label', t: 'Agent Name'}, {k: 'country', t: 'Country Name'}, {k: 'owner', t: 'JobOwner'}, {k: 'prevOwners', t: 'Previous Job Owners'}].concat(mlab.map((l, k) => ({k: 'm' + k, t: l, num: true})), [{k: 'total', t: 'Total', num: true}]);
  const lobBtn = (lab, code) => h('button', {type: 'button', class: 'btn' + ((code == null ? repSel.size === 0 : repSel.size === 1 && repSel.has(code)) ? ' on' : ''), onclick: () => { if (code == null) delete S.sel.report; else S.sel.report = new Set([code]); S.qm.clear(); sp.page = 0; renderAll(); }}, lab);
  const tabs = h('div', {class: 'segs'}, lobBtn('All LOBs', null), [0, 1, 2, 3].map((c) => lobBtn(REPN[c], c)));
  const search = h('input', {type: 'search', value: sp.q, placeholder: 'Search agent, country, job owner, sales person', 'aria-label': 'Search', style: 'min-width:14rem'}), sizeSel = h('select', {'aria-label': 'Entries'}, [10, 25, 50, 100, 500].map((n) => h('option', {value: n, selected: sp.size === n}, n)));
  const thead = h('thead'), tbody = h('tbody'), info = h('p', {class: 'note'}), pager = h('div', {class: 'frow'}); let list = [];
  const vis = () => cols.filter((c) => !sp.hide.has(c.k));
  const draw = () => { const q = sp.q.trim().toLowerCase(), st = sp.sort, f = (a, b) => { const x = a[st.sort], y = b[st.sort]; if (typeof x === 'string' || typeof y === 'string') return String(x || '').localeCompare(String(y || '')); return (x == null ? -1e18 : x) - (y == null ? -1e18 : y); };
    list = rows.filter((r) => !q || (r.label + ' ' + r.country + ' ' + r.owner + ' ' + r.prevOwners + ' ' + r.sales).toLowerCase().includes(q)).sort((a, b) => f(a, b) * st.dir); const pages = Math.max(1, Math.ceil(list.length / sp.size)); sp.page = Math.min(sp.page, pages - 1); const from = sp.page * sp.size, shown = list.slice(from, from + sp.size), vc = vis(), agSel = S.sel.agent || new Set();
    thead.replaceChildren(sortHead(vc, st, draw)); tbody.replaceChildren(...shown.map((r) => h('tr', {class: 'click' + (agSel.has(r.a) ? ' on' : ''), onclick: () => toggle('agent', r.a)}, vc.map((c) => h('td', {class: c.num ? 'n' : ''}, c.num ? fInt(r[c.k]) : (r[c.k] || ''))))));
    info.textContent = 'Showing ' + (list.length ? from + 1 : 0) + ' to ' + Math.min(from + sp.size, list.length) + ' of ' + fInt(list.length) + ' agents'; pager.replaceChildren(h('button', {type: 'button', class: 'btn', disabled: sp.page === 0, onclick: () => { sp.page--; draw(); }}, 'Previous'), h('span', {class: 'meta'}, 'Page ' + (sp.page + 1) + ' of ' + pages), h('button', {type: 'button', class: 'btn', disabled: sp.page >= pages - 1, onclick: () => { sp.page++; draw(); }}, 'Next')); };
  search.addEventListener('input', () => { sp.q = search.value; sp.page = 0; draw(); }); sizeSel.addEventListener('change', () => { sp.size = parseInt(sizeSel.value, 10); sp.page = 0; draw(); });
  const colMenu = h('details', {class: 'colmenu'}, h('summary', {class: 'btn'}, 'Column visibility'), h('div', {class: 'colbox'}, cols.map((c) => h('label', {class: 'mo'}, h('input', {type: 'checkbox', checked: !sp.hide.has(c.k), onchange: () => { if (sp.hide.has(c.k)) sp.hide.delete(c.k); else sp.hide.add(c.k); renderAll(); }}), h('span', {class: 'mt'}, c.t)))));
  const csv = () => { const q = (x) => '"' + String(typeof x==='string'&&/^[\s]*[=+@-]|^[\t\r]/.test(x)?"'"+x:x == null ? '' : x).replace(/"/g, '""') + '"', vc = vis(); dlText('sales_performance_report.csv', '\ufeff' + [vc.map((c) => q(c.t)).join(',')].concat(list.map((r) => vc.map((c) => q(r[c.k])).join(','))).join('\n'), 'text/csv'); };
  const excel = () => { const n1 = list.length + 1, L = colL, M0 = 5; downloadXlsx('sales_performance_report_' + fIso(dDate(asOf)) + '.xlsx', [{name: 'Sales performance', freeze: true, filter: true, cols: [20, 38, 20, 20, 44].concat(Array(12).fill(11), [10]), rows: [cols.map((c) => HDR(c.t))].concat(list.map((r, i) => { const x = i + 2; return [r.sales, r.label, r.country, r.owner, r.prevOwners].concat(Array.from({length: 12}, (_, k) => ({v: r['m' + k], s: 3})), [{f: 'SUM(' + L(M0) + x + ':' + L(M0 + 11) + x + ')', s: 3}]); }), [[HDR('Total'), '', '', '', ''].concat(Array.from({length: 12}, (_, k) => ({f: 'SUM(' + L(M0 + k) + '2:' + L(M0 + k) + n1 + ')', s: 3})), [{f: 'SUM(' + L(M0 + 12) + '2:' + L(M0 + 12) + n1 + ')', s: 3}])])}, settingsSheet([[HDR('Months'), mlab[0] + ' (month so far, to ' + fIso(dDate(asOf)) + ') back to ' + mlab[11]], [HDR('LOB'), repSel.size === 1 ? REPN[[...repSel][0]] : 'All'], [HDR('Agent'), 'Booking Thru; the customer where Booking Thru is Self; names follow the Organization master'], [HDR('SalesPerson and JobOwner'), 'Taken from the agent’s latest shipment'], [HDR('Previous Job Owners'), 'The 5 job owners before the latest, each with the month of their latest shipment for this agent']])]); };
  draw();
  root.append(h('div', {class: 'card', style: 'margin-bottom:.9rem'}, h('h2', {class: 'h'}, 'Sales performance report'), h('p', {class: 'note'}, 'Shipments per agent, month by month, in the ERP’s Sales Performance layout. Pick a LOB with the tabs and a company with the switch above (it opens on both, as in the sample you shared). SalesPerson and JobOwner come from the agent’s latest shipment, and Previous Job Owners lists the 5 before that, each with the month of their latest shipment for the agent. The date range does not apply: it always shows the month so far and the 11 months before.'),
    h('div', {class: 'frow'}, tabs), h('div', {class: 'frow'}, h('label', {class: 'f'}, h('span', null, 'Show'), sizeSel), h('label', {class: 'f'}, h('span', null, 'Search'), search), h('button', {type: 'button', class: 'btn', onclick: () => window.print()}, 'Print'), h('button', {type: 'button', class: 'btn', onclick: csv}, 'CSV'), dlButton('Excel', excel), colMenu)),
    card('Agents', null, h('div', null, info, h('div', {class: 'scroll tall'}, h('table', {class: 'tbl'}, thead, tbody)), pager), 'full'));
  return root;
}

const PAGES = {overview: pageOverview, compare: pageCompare, customers: pageCustomers, lanes: pageLanes, ops: pageOps, ship: pageShip, changes: pageChanges, status: pageStatus, p_overview: ppOverview, p_explorer: ppExplorer, p_branches: ppBranches, p_customers: ppCustomers, p_jobs: ppJobs, p_quality: ppQuality, p_compare: ppCompare, p_status: ppStatus, s_owner: sOwner, s_score: sScore, p_billing: ppBilling, p_rates: ppRates, v_mine: vMine, v_build: vBuild, o_agents: vVariation, o_sales: vSales};

// ---------------------------------------------------------------- filter bar + menu
function selLabel(key) { const set = S.sel[key]; if (!set || !set.size) return 'All'; const names = [...set].slice(0, 1).map((j) => COLS[key].d[j]); return names[0] + (set.size > 1 ? ' +' + (set.size - 1) : ''); }
function renderFilterButtons() {
  const keys = MAIN.concat(S.group === 'profit' ? PMAIN : [], S.extra.filter((k) => S.group === 'profit' || COLS[k].own)), box = $('fbtns');
  box.replaceChildren(...keys.map((k) => { const on = S.sel[k] && S.sel[k].size, b = h('span', {class: 'fb' + (on ? ' on' : '')},
    h('button', {type: 'button', class: 'fbtn', 'data-key': k, onclick: (e) => openMenu(k, e.currentTarget)}, h('span', {class: 'fl'}, COLS[k].l + ': '), h('b', null, selLabel(k))),
    S.extra.includes(k) && !on ? h('button', {type: 'button', class: 'fx', 'aria-label': 'Remove ' + COLS[k].l + ' filter', onclick: () => { S.extra = S.extra.filter((x) => x !== k); renderAll(); }}, '×') : null); return b; }),
    h('button', {type: 'button', class: 'fbtn add', 'data-key': '__add', onclick: (e) => openMenu('__add', e.currentTarget)}, '+ Add filter'));
  const chips = []; for (const k in S.sel) { const set = S.sel[k]; if (!set || !set.size) continue; const names = [...set].map((j) => COLS[k].d[j]);
    chips.push(h('button', {type: 'button', class: 'chip', title: COLS[k].own || S.group === 'profit' ? '' : 'Applies to the profit pages only', onclick: () => { if (k === 'report') { S.qm.clear(); S.qd.clear(); } delete S.sel[k]; renderAll(); }}, COLS[k].l + ': ' + names.slice(0, 2).join(', ') + (names.length > 2 ? ' +' + (names.length - 2) : '') + '  ×')); }
  if (S.rel || S.from != null || S.to != null) chips.push(h('button', {type: 'button', class: 'chip', onclick: () => { S.rel = null; S.from = null; S.to = null; renderAll(); }}, 'Dates: ' + (S.rel ? relLabel(S.rel) + ' (' + fDay(R.w.from) + ' – ' + fDay(R.w.to) + ')' : fDay(R.w.from) + ' – ' + fDay(R.w.to)) + '  ×'));
  if (chips.length) chips.push(h('button', {type: 'button', class: 'btn', id: 'clearall', onclick: () => { S.sel = {}; S.qm.clear(); S.qd.clear(); S.rel = null; S.from = null; S.to = null; renderAll(); }}, 'Clear all'));
  $('chips').replaceChildren(...chips);
  $('status').textContent = S.group === 'summary' || S.group === 'mine' ? 'Showing ' + fInt(R.n) + ' of ' + fInt(N) + ' shipments and ' + fInt(R.t.lines) + ' job records · ' + fDay(R.w.from) + ' to ' + fDay(R.w.to) : S.group === 'profit' ? 'Showing ' + fInt(R.n) + ' of ' + fInt(NP) + ' job records · ' + fDay(R.w.from) + ' to ' + fDay(R.w.to) + ' by ' + 'job date' + ' · ' + fInt(R.t.jobs) + ' jobs' : 'Showing ' + fInt(R.n) + ' of ' + fInt(N) + ' shipments · ' + fDay(R.w.from) + ' to ' + fDay(R.w.to) + ' by shipment date' + (R.mixed ? ' · air and sea are shown separately, never added together' : '');
}
function applyQuick() {
  const modes = S.qm.size ? [...S.qm] : ['air', 'sea'], dirs = S.qd.size ? [...S.qd] : ['exp', 'imp'], set = [];
  for (let r = 0; r < 4; r++) if (modes.includes(r < 2 ? 'air' : 'sea') && dirs.includes(r % 2 === 0 ? 'exp' : 'imp')) set.push(r);
  if (set.length === 4) delete S.sel.report; else S.sel.report = new Set(set); renderAll();
}
function renderStatic() {
  const on = (el, v) => el.classList.toggle('on', v);
  document.querySelectorAll('#qMode button').forEach((b) => on(b, S.qm.has(b.dataset.v)));
  document.querySelectorAll('#qDir button').forEach((b) => on(b, S.qd.has(b.dataset.v)));
  document.querySelectorAll('[data-g]').forEach((e) => { e.hidden = !e.dataset.g.split(' ').includes(S.group); });
  if (!FIN) document.querySelectorAll('#grpSeg button[data-v="profit"]').forEach((b) => { b.hidden = true; });
  document.querySelectorAll('#grpSeg button').forEach((b) => on(b, b.dataset.v === S.group));
  { const cs = S.sel.company; document.querySelectorAll('#coSeg button').forEach((b) => { const v = b.dataset.v; on(b, v === 'both' ? !cs || cs.size === 0 || cs.size === 2 : !!cs && cs.size === 1 && cs.has(v === 'ng' ? 0 : 1)); }); }
  document.querySelectorAll('#rankSeg button').forEach((b) => on(b, b.dataset.v === S.rank)); document.querySelectorAll('#basisSeg button').forEach((b) => on(b, b.dataset.v === S.def.pBasis));
  const vbtn = document.querySelector('#mSeg button[data-v="volume"]'); if (S.group === 'ops') vbtn.disabled = R.mixed; if (S.group === 'ops') vbtn.title = R.mixed ? 'Air and sea are never added together. Select only air or only sea reports to see volume.' : '';
  if (S.group === 'ops') document.querySelectorAll('#mSeg button').forEach((b) => on(b, (b.dataset.v === 'volume') === R.useVol));
  $('cmp').checked = S.compare;
  { const fm = S.def.fyStart, mn = (k) => d3.utcFormat('%b')(new Date(Date.UTC(2000, k - 1, 1)));
    document.querySelector('#ybSeg button[data-v="fy"]').textContent = 'Accounting year (' + mn(fm) + '–' + mn(fm === 1 ? 12 : fm - 1) + ')';
    document.querySelectorAll('#ybSeg button').forEach((b) => on(b, (b.dataset.v === 'fy') === FYB()));
    document.querySelector('#presets button[data-v="ytd"]').textContent = FYB() ? 'Financial year to date' : 'Year to date';
    const ys = $('yearSel'), cur = yearOfDay(asOfDay()), opts = [['all', 'All dates'], ['ytd', FYB() ? 'This financial year so far' : 'This year so far'], ['last', FYB() ? 'Last financial year' : 'Last year']];
    for (let y = cur; y > cur - S.def.historyYears; y--) opts.push(['y:' + y, yearName(y)]);
    const cv = S.rel && S.rel.kind === 'year' ? 'y:' + S.rel.y : S.rel && S.rel.kind === 'ytd' ? 'ytd' : S.rel && S.rel.kind === 'lastyear' ? 'last' : (!S.rel && S.from == null && S.to == null ? 'all' : '');
    ys.replaceChildren(...(cv === '' ? [new Option('Custom or relative range', '')] : []), ...opts.map(([v, t]) => new Option(t, v))); ys.value = cv; }
  if (S.rel && S.rel.kind === 'last') { if (document.activeElement !== $('relN')) $('relN').value = S.rel.n; $('relU').value = S.rel.unit; }
  if (document.activeElement !== $('dFrom')) $('dFrom').value = fIso(dDate(R.w.from)); if (document.activeElement !== $('dTo')) $('dTo').value = fIso(dDate(R.w.to));
  document.querySelectorAll('#tabs button[data-p]').forEach((b) => { const a = b.dataset.p === S.page; b.classList.toggle('on', a); b.setAttribute('aria-selected', String(a)); });
}
const menuEl = $('menu'), mq = $('mq'), ml = $('ml'), mh = $('mh');
function openMenu(key, anchor) {
  if (MENU.key === key && !menuEl.hidden) { closeMenu(); return; }
  MENU.key = key; MENU.q = ''; mq.value = ''; menuEl.hidden = false; const r = anchor.getBoundingClientRect(), left = Math.min(r.left + window.scrollX, window.innerWidth - 330);
  menuEl.style.left = Math.max(6, left) + 'px'; menuEl.style.top = (r.bottom + window.scrollY + 4) + 'px'; renderMenu(); mq.focus();
}
function closeMenu() { MENU.key = null; menuEl.hidden = true; }
function renderMenu() {
  if (!MENU.key) return; const key = MENU.key, needle = MENU.q.trim().toLowerCase(), scroll = ml.scrollTop;
  document.querySelector('#menu .ma').style.display = key === '__add' ? 'none' : '';
  if (key === '__add') {
    mh.textContent = 'Add a filter'; const opts = EXTRA.concat(S.group === 'profit' ? PEXTRA : []).filter((k) => !S.extra.includes(k) && (!needle || COLS[k].l.toLowerCase().includes(needle)));
    ml.replaceChildren(...opts.map((k) => h('button', {type: 'button', class: 'mo pick', onclick: () => { S.extra.push(k); closeMenu(); renderAll(); const b = document.querySelector('.fbtn[data-key="' + k + '"]'); if (b) openMenu(k, b); }}, h('span', {class: 'mt'}, COLS[k].l), h('i', null, fInt(COLS[k].d.length) + ' values'))), opts.length ? null : h('p', {class: 'empty'}, 'No more columns match.'));
    $('mf').textContent = 'Every other column of the ERP report can be added here in the live system.'; return;
  }
  mh.textContent = COLS[key].l; const pro = S.group === 'profit', m = pro ? maskP({skip: key}) : mask({skip: key}), c = pro ? COLS[key].pc : COLS[key].c, cnt = new Float64Array(COLS[key].d.length); for (let i = 0, nn = pro ? NP : N; i < nn; i++) if (m[i]) cnt[c[i]]++;
  const sel = S.sel[key] || new Set(); let ids = []; for (let j = 0; j < cnt.length; j++) if ((cnt[j] > 0 || sel.has(j)) && (!needle || COLS[key].d[j].toLowerCase().includes(needle))) ids.push(j);
  ids.sort((a, b) => cnt[b] - cnt[a]); MENU.visible = ids; const shown = ids.slice(0, 300);
  ml.replaceChildren(...shown.map((j) => h('label', {class: 'mo' + (cnt[j] === 0 ? ' zero' : '')}, h('input', {type: 'checkbox', checked: sel.has(j), onchange: () => toggle(key, j)}), h('span', {class: 'mt', title: COLS[key].d[j]}, COLS[key].d[j]), h('i', null, fInt(cnt[j])),
    h('button', {type: 'button', class: 'only', onclick: (e) => { e.preventDefault(); e.stopPropagation(); setOnly(key, j); }}, 'Only'))), ids.length ? null : h('p', {class: 'empty'}, 'No matching values.'));
  $('mf').textContent = fInt(ids.length) + ' values' + (ids.length > 300 ? ' (first 300 shown; type to narrow)' : '') + '. Counts follow the other filters. Select all ticks every value that matches the search.'; ml.scrollTop = scroll;
}
function menuAll() { const key = MENU.key; if (!key || key === '__add') return; if (key === 'report') { S.qm.clear(); S.qd.clear(); } const set = S.sel[key] || (S.sel[key] = new Set()); (MENU.visible || []).forEach((j) => set.add(j)); if (!set.size) delete S.sel[key]; renderAll(); }
function menuClear() { const key = MENU.key; if (!key || key === '__add') return; if (key === 'report') { S.qm.clear(); S.qd.clear(); } delete S.sel[key]; renderAll(); }

// ---------------------------------------------------------------- render loop
function reportingContext() {
  const w = win(), notes = [];
  let current = {from:w.from,to:w.to}, previous = {from:w.pfrom,to:w.pto};
  if (S.page === 'compare' || S.page === 'p_compare') {
    const period = periods(S.page === 'compare' ? S.cmp : S.pcmp);
    if (!period.err) { current=period.cur; previous=period.prev; }
  }
  const overlap = Math.min(current.to, previous.to) - Math.max(current.from, previous.from) + 1;
  if (S.compare && overlap > 0) notes.push('The selected comparison ranges overlap by ' + overlap + ' days. Select one calendar or accounting year for an annual comparison.');
  if (FIN && S.group !== 'ops' && S.def.pBasis === 'job') {
    const selected = S.sel.company;
    for (let co=0; co<2; co++) if ((!selected || !selected.size || selected.has(co)) && !(D.p.co || []).includes(co)) notes.push(COMP[co] + ': no job-level finance records loaded for this access scope. Upload current and historical Job Date reports; legacy billing-date charge records are excluded.');
    for (const meta of D.p.meta || []) {
      const co = meta.co === 'NG' ? 0 : 1;
      if (selected && selected.size && !selected.has(co)) continue;
      const first = isoD(meta.range_from), last = isoD(meta.range_to);
      if (!Number.isFinite(first) || !Number.isFinite(last)) continue;
      const ranges = (meta.ranges || [[meta.range_from,meta.range_to]]).map(r => r.map(isoD)).sort((a,b)=>a[0]-b[0]);
      const covered = period => { let cursor=period.from; for (const [a,b] of ranges) { if(b<cursor) continue; if(a>cursor) return false; cursor=Math.max(cursor,b+1); if(cursor>period.to) return true; } return cursor>period.to; };
      if (!covered(current) || (S.compare && !covered(previous))) notes.push(COMP[co] + ' finance source reports cover ' + fDay(first) + ' to ' + fDay(last) + '. Some selected dates have no loaded Job Date source report. Upload the missing historical or current-period files. Values and variances continue to use the uploaded records.');
    }
  }
  return notes.length ? h('aside', {class:'card reporting-context', role:'note', style:'margin-bottom:.9rem;font-size:.82rem;border-left:3px solid var(--warn)'}, notes.map(text=>h('p',{class:'meta',style:'margin:.3rem 0'},text))) : null;
}
function renderPage() { const p = $('page'); p.replaceChildren(PAGES[S.page]()); const context = reportingContext(); if (context) p.prepend(context); }
function renderAll() {
  S.def.pBasis = 'job';
  if (S.page === 'p_charges') S.page = 'p_overview';
  for (const k of Object.keys(S.sel)) if (!COLS[k]) delete S.sel[k];
  S.extra = S.extra.filter(k => COLS[k]); compute(); renderStatic(); renderFilterButtons(); renderPage(); renderMenu(); }
const DEF_FIELDS = [
  {k: 'topN', l: 'Top N', h: 'How many items the “top” lists show (customers, branches, lanes, carriers, ports) and what the top-N share uses.', t: 'num', min: 1, max: 200},
  {k: 'heatN', l: 'Customers in the monthly heatmap', h: 'Rows in the customer-by-month grid.', t: 'num', min: 1, max: 60},
  {k: 'tableRows', l: 'Rows shown in tables', h: 'Customer, lane and job-owner tables.', t: 'num', min: 5, max: 500},
  {k: 'wlRows', l: 'Worklist rows shown', h: 'Open shipments listed on the Operations page.', t: 'num', min: 10, max: 3000},
  {k: 'pageSize', l: 'Shipments per page', h: 'Rows per page on the Shipments page.', t: 'num', min: 10, max: 500},
  {k: 'oldDays', l: 'Open for more than (days)', h: 'An open shipment older than this counts as overdue.', t: 'num', min: 1, max: 3650},
  {k: 'buckets', l: 'Age bands (days)', h: 'Upper limit of each band, comma separated. Example: 30,60,90,180.', t: 'text'},
  {k: 'activeMin', l: 'Active customer means at least (shipments)', h: 'A customer counts as active with this many shipments in the range.', t: 'num', min: 1, max: 1000},
  {k: 'grain', l: 'Trend grouping', h: 'Automatic picks days or months from the length of the range.', t: 'sel', opts: [['auto', 'Automatic'], ['day', 'Day'], ['week', 'Week'], ['month', 'Month']]},
  {k: 'autoDays', l: 'Automatic grouping switches to months above (days)', h: 'Only used when grouping is Automatic.', t: 'num', min: 7, max: 3650},
  {k: 'relEnd', l: 'Relative dates end at', h: 'Last N days, this month, year to date and the Compare page count back from this day.', t: 'sel', opts: [['data', 'The latest data date'], ['today', 'Today']]},
  {k: 'historyYears', l: 'Years of history (this year plus earlier)', h: 'The window moves by itself each January. In the live system an admin sets how many years are kept.', t: 'num', min: 1, max: 10},
  {k: 'fyStart', l: 'Accounting year starts in month (1-12)', h: 'Used when the year setting at the top is Accounting year. 4 means April to March, as in India.', t: 'num', min: 1, max: 12},
  {k: 'weekStart', l: 'Week starts on', h: 'Used by week-on-week comparisons and weekly grouping.', t: 'sel', opts: [[1, 'Monday'], [0, 'Sunday']], num: true},
  {k: 'flatPct', l: 'Count as flat when change is within (%)', h: 'Compare page: changes this small are labelled flat.', t: 'num', min: 0, max: 100},
  {k: 'varMinPct', l: 'Show changes of at least (%)', h: 'Compare page filter. 0 shows everything.', t: 'num', min: 0, max: 10000},
  {k: 'varMinBase', l: 'Ignore items whose previous value is below', h: 'Compare page filter that stops tiny bases giving huge percentages. 0 keeps everything.', t: 'num', min: 0, max: 100000},
  {k: 'varMinAbs', l: 'Show changes of at least (value)', h: 'Compare page filter on the size of the change itself.', t: 'num', min: 0, max: 100000},
  {k: 'compare', l: 'Compare with', h: 'The period used for the change figures.', t: 'sel', opts: [['prev', 'The period just before'], ['yoy', 'Same period last year']]},
];
function renderDefs() {
  const box = $('defs'); box.replaceChildren();
  DEF_FIELDS.forEach((f) => {
    let inp;
    if (f.t === 'sel') { inp = h('select', {'aria-label': f.l}, f.opts.map((o) => h('option', {value: o[0], selected: String(S.def[f.k]) === String(o[0])}, o[1]))); inp.value = String(S.def[f.k]); }
    else inp = h('input', {type: f.t === 'num' ? 'number' : 'text', value: S.def[f.k], 'aria-label': f.l, min: f.min, max: f.max, step: 1});
    inp.addEventListener('change', () => {
      let v = inp.value;
      if (f.t === 'num') { v = parseInt(v, 10); if (isNaN(v)) v = DEFAULTS[f.k]; v = Math.min(f.max, Math.max(f.min, v)); inp.value = v; }
      else if (f.k === 'buckets') { if (!String(v).split(',').some((x) => parseInt(x, 10) > 0)) v = DEFAULTS.buckets; inp.value = v; }
      if (f.num) v = parseInt(v, 10); S.def[f.k] = v; saveDefs(); renderAll();
    });
    box.append(h('label', {class: 'df'}, h('span', {class: 'dl'}, f.l + (f.t !== 'sel' ? '  (default ' + DEFAULTS[f.k] + ')' : '')), inp, h('small', null, f.h)));
  });
  box.append(h('div', {class: 'df'}, h('button', {type: 'button', class: 'btn', id: 'defReset', onclick: () => { S.def = Object.assign({}, DEFAULTS); saveDefs(); renderDefs(); renderAll(); }}, 'Reset all to defaults'), h('small', null, 'Saved in this browser. In the live system each user keeps their own, and an admin sets the company defaults.')));
}
const DEF_PROFIT = [
  {k: 'lowMargin', l: 'Profit: low margin means below (%)', h: 'A job with a margin below this (and some cost booked) is flagged low margin.', t: 'num', min: 0, max: 100},
  {k: 'costCoverage', l: 'Profit: warn when jobs with cost booked fall below (%)', h: 'The profit overview warns that margins are too high when fewer jobs than this have a cost booked.', t: 'num', min: 0, max: 100},
  {k: 'moneyUnit', l: 'Profit: show amounts in', h: 'Lakh and crore follow Indian practice.', t: 'sel', opts: [['auto', 'Automatic (₹ lakh and crore)'], ['inr', 'Rupees'], ['k', 'Thousands'], ['lakh', 'Lakh'], ['cr', 'Crore']]},

  {k: 'jobRows', l: 'Profit: jobs shown in the jobs table', h: 'Rows listed on the Jobs page of the profit view.', t: 'num', min: 10, max: 3000}];
DEF_PROFIT.push({k: 'lapsedMonths', l: 'Agents: lapsed after no shipment for (months)', h: 'The agent variation report marks an agent lapsed after this many months without a shipment.', t: 'num', min: 1, max: 24}, {k: 'declinePct', l: 'Agents: declining or growing when the 3-month average moves by (%)', h: 'Last 3 complete months against the 3 before.', t: 'num', min: 1, max: 1000}, {k: 'rateMode', l: 'Rates: which buy and sell rates to use', h: 'The rate columns are free text. Plain numbers are safest; numbers read from text such as “512.00 ALL IN” add coverage.', t: 'sel', opts: [['text', 'Plain numbers and numbers read from text'], ['clean', 'Plain numbers only']]}, {k: 'rateMax', l: 'Rates: highest believable rate (₹ per kg)', h: 'Anything above this is a lump sum, not a per-kg rate, and is left out.', t: 'num', min: 100, max: 100000}, {k: 'unbilledDays', l: 'Billing: late when operations locked and not invoiced for more than (days)', h: 'Shipments past this age with no invoice are counted as late billing.', t: 'num', min: 1, max: 365}, {k: 'ownerConc', l: 'Summary: warn when one customer brings more than (% of profit)', h: 'The owner summary flags customer concentration above this share.', t: 'num', min: 1, max: 100},
  {k: 'unassignedShare', l: 'Summary: warn when unassigned sales or missing trade lane exceeds (% of profit)', h: 'Flags profit that cannot be credited to a sales person or trade lane.', t: 'num', min: 1, max: 100},
  {k: 'unassignedNames', l: 'Summary: sales person names that mean not assigned', h: 'Comma separated. “Administrator” is the ERP default user.', t: 'text'});
DEF_PROFIT.forEach((f) => DEF_FIELDS.push(f));
function viewsGet() { try { return JSON.parse(localStorage.getItem('ngViews') || '{}'); } catch (e) { return {}; } }
function viewsSet(v) { try { localStorage.setItem('ngViews', JSON.stringify(v)); } catch (e) { /* not available */ } srvPut('views', v); }
function snapshotView() { const sel = {},selNames={}; for (const k in S.sel){sel[k] = [...S.sel[k]];if(COLS[k])selNames[k]=[...S.sel[k]].map(i=>COLS[k].d[i]).filter(v=>v!==undefined);}return {version:2,selNames,group: S.group, page: S.page, sel, from: S.from, to: S.to, rel: S.rel, rank: S.rank, measure: S.measure, qm: [...S.qm], qd: [...S.qd], extra: S.extra.slice()}; }
function renderViews() { const v = viewsGet(), sel = $('viewSel'); sel.replaceChildren(new Option('Saved views…', ''), ...Object.keys(v).sort().map((n) => new Option(n, n))); }
function saveView(name) { if (!name) return; const v = viewsGet(); v[name] = snapshotView(); viewsSet(v); renderViews(); $('viewSel').value = name; }
function applyView(name) { const v = viewsGet()[name]; if (!v) return; if(!v.selNames&&Object.entries(v.sel||{}).some(([k,values])=>!['company','report'].includes(k)&&values.length)){alert('This older view stores numeric filter positions that cannot be safely restored after imports. Re-select its filters and save it again.');return;}
 if(v.selNames&&Object.entries(v.selNames).some(([k,values])=>!COLS[k]||values.some(value=>!COLS[k].d.includes(value)))){alert('This view contains filter names absent from the current authorized data. It was not applied; review the filters and save it again.');$('viewSel').value='';return;}S.sel={};let missing=false;if(v.selNames){for(const[k,values]of Object.entries(v.selNames)){if(!COLS[k]){missing=true;continue;}const codes=values.map(value=>COLS[k].d.indexOf(value));if(codes.some(i=>i<0))missing=true;S.sel[k]=new Set(codes);}}else for(const k in v.sel)if(COLS[k])S.sel[k]=new Set(v.sel[k]); Object.assign(S, {group: v.group, page: v.page === 'p_charges' ? 'p_overview' : v.page, from: v.from, to: v.to, rel: v.rel, rank: v.rank, measure: v.measure, extra: (v.extra || []).filter(k => COLS[k])}); S.qm = new Set(v.qm); S.qd = new Set(v.qd);if(!FIN&&S.group==='profit'){S.group='ops';S.page='overview';}syncBounds();renderAll();if(missing)alert('Some saved filter names are absent from the current authorized data. Missing selections were kept unmatched, rather than broadening the view.'); }
function wire() {
  document.querySelectorAll('#grpSeg button').forEach((b) => b.addEventListener('click', () => setGroup(b.dataset.v)));
  $('viewSave').addEventListener('click', () => { const nm = window.prompt ? window.prompt('Name this view (it keeps the page, the filters and the dates)') : ''; if (nm && nm.trim()) saveView(nm.trim()); });
  $('viewSel').addEventListener('change', () => { if ($('viewSel').value) applyView($('viewSel').value); });
  $('viewDel').addEventListener('click', () => { const nm = $('viewSel').value; if (!nm) return; const v = viewsGet(); delete v[nm]; viewsSet(v); renderViews(); });
  $('printBtn').addEventListener('click', () => window.print());
  document.querySelectorAll('#coSeg button').forEach((b) => b.addEventListener('click', () => { const v = b.dataset.v; if (v === 'both') delete S.sel.company; else S.sel.company = new Set([v === 'ng' ? 0 : 1]); renderAll(); }));
  document.querySelectorAll('#rankSeg button').forEach((b) => b.addEventListener('click', () => { S.rank = b.dataset.v; renderAll(); }));
  document.querySelectorAll('#basisSeg button').forEach((b) => b.addEventListener('click', () => { S.def.pBasis = b.dataset.v; saveDefs(); setPBasis(b.dataset.v); renderAll(); }));
  $('defBtn').addEventListener('click', () => { const open = $('defs').hidden; $('defs').hidden = !open; $('defBtn').setAttribute('aria-expanded', String(open)); });
  document.querySelectorAll('#qMode button').forEach((b) => b.addEventListener('click', () => { const v = b.dataset.v; if (S.qm.has(v)) S.qm.delete(v); else S.qm.add(v); applyQuick(); }));
  document.querySelectorAll('#qDir button').forEach((b) => b.addEventListener('click', () => { const v = b.dataset.v; if (S.qd.has(v)) S.qd.delete(v); else S.qd.add(v); applyQuick(); }));
  document.querySelectorAll('#mSeg button').forEach((b) => b.addEventListener('click', () => { if (b.disabled) return; S.measure = b.dataset.v; renderAll(); }));
  $('cmp').addEventListener('change', () => { S.compare = $('cmp').checked; renderAll(); });
  const setDate = (which, el) => { if (!el.value) return; const d = isoD(el.value); if (isNaN(d)) return; S.rel = null; S[which] = d; renderAll(); };
  $('dFrom').addEventListener('change', () => setDate('from', $('dFrom'))); $('dTo').addEventListener('change', () => setDate('to', $('dTo')));
  document.querySelectorAll('#presets button').forEach((b) => b.addEventListener('click', () => { const p = b.dataset.v; S.from = null; S.to = null;
    S.rel = p === '30' ? {kind: 'last', n: 30, unit: 'days'} : p === 'month' ? {kind: 'month'} : p === 'last' ? {kind: 'lastmonth'} : p === 'ytd' ? {kind: 'ytd'} : null; renderAll(); }));
  document.querySelectorAll('#ybSeg button').forEach((b) => b.addEventListener('click', () => { S.def.yearBasis = b.dataset.v; saveDefs(); renderAll(); }));
  $('yearSel').addEventListener('change', () => { const v = $('yearSel').value; if (v === '') return; S.from = null; S.to = null;
    S.rel = v === 'all' ? null : v === 'ytd' ? {kind: 'ytd'} : v === 'last' ? {kind: 'lastyear'} : {kind: 'year', y: parseInt(v.slice(2), 10)}; renderAll(); });
  const relGo = () => { let n = parseInt($('relN').value, 10); if (isNaN(n) || n < 1) n = 30; n = Math.min(3650, n); $('relN').value = n; S.from = null; S.to = null; S.rel = {kind: 'last', n, unit: $('relU').value}; renderAll(); };
  $('relGo').addEventListener('click', relGo); $('relN').addEventListener('keydown', (e) => { if (e.key === 'Enter') relGo(); }); $('relU').addEventListener('change', relGo);
  document.querySelectorAll('#tabs button[data-p]').forEach((b) => b.addEventListener('click', () => { S.page = b.dataset.p; renderAll(); window.scrollTo(0, 0); }));
  mq.addEventListener('input', () => { MENU.q = mq.value; renderMenu(); });
  $('mAll').addEventListener('click', menuAll); $('mClear').addEventListener('click', menuClear); $('mClose').addEventListener('click', closeMenu);
  document.addEventListener('click', (e) => { if (!menuEl.hidden && !menuEl.contains(e.target) && !e.target.closest('.fbtn')) closeMenu(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenu(); });
  let t; window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(() => { compute(); renderPage(); }, 150); });
}
$('asof').textContent = fDay(MAXDATE); $('nrows').textContent = fInt(N);
S.exp = S.exp || {dim: 0, sort: {sort: 'profit', dir: -1}}; setPBasis(S.def.pBasis); renderDefs(); renderViews(); wire(); renderAll();
window.NG_BOOT = function () { const t = D.built_at ? new Date(D.built_at).toLocaleString([], {dateStyle: 'medium', timeStyle: 'short'}) : ''; const el = document.getElementById('fresh'); if (el) el.textContent = t ? 'Updated ' + t : ''; };
function metricTraceVariance(metric,pr,displayed){
 const fin=metric.startsWith('profit.'),m=fin?maskP({dates:'none'}):mask({dates:'none'}),p=fin?maskP({dates:'none'}):mask({dates:'none'}),dates=metric==='ops.invoiced_count'?inv1:fin?pdate:date;
 for(let i=0;i<m.length;i++){if(dates[i]<pr.cur.from||dates[i]>pr.cur.to)m[i]=0;if(dates[i]<pr.prev.from||dates[i]>pr.prev.to)p[i]=0;}
 const q=metricTraceSelection(metric,'Variance');q.indices=Array.from(m).flatMap((v,i)=>v?[i]:[]);q.previous_indices=Array.from(p).flatMap((v,i)=>v?[i]:[]);q.displayed_value=displayed;q.context.period=pr;q.context.active_min=1;q.context.date_basis=metric==='ops.invoiced_count'?'First parsed invoice date':fin?'Job Date':'Shipment Date';return q;
}
function metricTraceCategory(metric,key,code){
 const fin=metric.startsWith('profit.'),m=fin?maskP({skip:key}):mask({skip:key}),p=fin?maskP({skip:key,dates:'prev'}):mask({skip:key,dates:'prev'}),codes=fin?COLS[key].pc:COLS[key].c;
 for(let i=0;i<m.length;i++)if(codes[i]!==code){m[i]=0;p[i]=0;}
 const q=metricTraceSelection(metric,COLS[key].l+': '+COLS[key].d[code]);q.indices=Array.from(m).flatMap((v,i)=>v?[i]:[]);q.previous_indices=Array.from(p).flatMap((v,i)=>v?[i]:[]);q.context.segment={dimension:COLS[key].l,value:COLS[key].d[code]};
 if(fin){const t=totalsP(m);q.displayed_value=metric==='profit.income'?t.inc:metric==='profit.expense'?t.exp:t.profit;}else{const t=opsFacts(m);q.displayed_value=metric==='ops.air_weight'?t.air:metric==='ops.teu'?t.sea:t.n;}
 return q;
}
function metricTraceSelection(metric,label) {
 const fin=metric.startsWith('profit.');let m=fin?maskP():mask(),p=fin?maskP({dates:'prev'}):mask({dates:'prev'});
 if((fin&&S.page==='p_compare')||(!fin&&S.page==='compare')){const pr=periods(S.cmp);if(pr.err)throw Error(pr.err);m=fin?maskP({dates:'none'}):mask({dates:'none'});p=fin?maskP({dates:'none'}):mask({dates:'none'});const dates=fin?pdate:date;for(let i=0;i<m.length;i++){if(dates[i]<pr.cur.from||dates[i]>pr.cur.to)m[i]=0;if(dates[i]<pr.prev.from||dates[i]>pr.prev.to)p[i]=0;}}
 if(fin&&S.page==='p_explorer'){const d=EXP_DIMS[S.exp.dim]||EXP_DIMS[0];m=maskP({skip:d.k});p=maskP({skip:d.k,dates:'prev'});if(d.mode!=null)for(let i=0;i<NP;i++){const ok=psidx[i]>=0&&mode[psidx[i]]===d.mode;if(!ok){m[i]=0;p[i]=0;}}}
 if(fin&&S.page==='p_customers'){m=maskP({skip:'customer'});p=maskP({skip:'customer',dates:'prev'});}
 if(!fin&&(['ops.waiting_lock','ops.financials_open','ops.old_open','ops.oldest_open','ops.locked_no_invoice','ops.overdue_invoice'].includes(metric)||(metric==='ops.lock_lag'&&(S.group==='summary'||S.page==='ops')))){m=mask({dates:'none'});p=new Uint8Array(N);}
 if(metric.startsWith('profit.rate_matched_'))for(let i=0;i<NP;i++){const si=psidx[i];if(si<0||rtype[si]!==0||!rateOK(si)){m[i]=0;p[i]=0;}}
 if(fin&&S.page==='p_quality'){const skip=metric==='profit.intercompany_proxy'?'p_ic':'jobstatus';m=maskP({skip});p=maskP({skip,dates:'prev'});}
 const t=fin?totalsP(m):null;
 const values=fin?{'profit.income':t.inc,'profit.expense':t.exp,'profit.gp':t.profit,'profit.jobs':t.jobs,'profit.margin':t.margin,'profit.per_job':t.jobs?t.profit/t.jobs:null,'profit.cost_coverage':t.jobs?t.booked/t.jobs:null,'profit.expected_adjusted':t.profit-pExpectedByLob(m).est}:{'ops.shipments':Array.from(m).reduce((n,x)=>n+(x?1:0),0),'ops.air_weight':opsFacts(m).air,'ops.teu':opsFacts(m).sea};
 if(!fin){const ids=Array.from(m).flatMap((v,i)=>v?[i]:[]),open=ids.filter(i=>COLS.stage.d[COLS.stage.c[i]]!=='Closed'),invoice=ids.filter(i=>invN[i]>0),dated=invoice.filter(i=>inv1[i]>0),lockedDates=dated.filter(i=>opsD[i]>0),noInvoice=ids.filter(i=>opsD[i]>0&&invN[i]===0);Object.assign(values,{'ops.waiting_lock':ids.filter(i=>COLS.stage.c[i]===STAGE_PEND).length,'ops.financials_open':ids.filter(i=>COLS.stage.c[i]===STAGE_FIN).length,'ops.old_open':open.filter(i=>OPS_MAX-date[i]>S.def.oldDays).length,'ops.oldest_open':open.reduce((v,i)=>Math.max(v,OPS_MAX-date[i]),0),'ops.invoiced_share':ids.length?invoice.length/ids.length:null,'ops.invoice_lag':dated.length?d3.sum(dated,i=>inv1[i]-date[i])/dated.length:null,'ops.lock_invoice_lag':lockedDates.length?d3.sum(lockedDates,i=>inv1[i]-opsD[i])/lockedDates.length:null,'ops.locked_no_invoice':noInvoice.length,'ops.overdue_invoice':noInvoice.filter(i=>OPS_MAX-opsD[i]>S.def.unbilledDays).length});}
 if(metric.startsWith('ops.rate_')||metric.startsWith('profit.rate_matched_')){const ids=fin?Array.from(m).flatMap((v,i)=>v?[psidx[i]]:[]):Array.from(m).flatMap((v,i)=>v&&rtype[i]===0?[i]:[]),ok=ids.filter(i=>rateOK(i)),kg=d3.sum(ok,i=>ckg[i]),sell=d3.sum(ok,i=>rsell[i]*ckg[i]),buy=d3.sum(ok,i=>rbuy[i]*ckg[i]);Object.assign(values,{'ops.rate_air_exports':ids.length,'ops.rate_usable':ids.length?ok.length/ids.length:null,'ops.rate_sell':kg?sell/kg:null,'ops.rate_buy':kg?buy/kg:null,'ops.rate_margin_kg':kg?(sell-buy)/kg:null,'ops.rate_margin':sell-buy,'ops.rate_below_buy':ok.filter(i=>rsell[i]<rbuy[i]).length,'profit.rate_matched_count':ids.length,'profit.rate_matched_estimate':sell-buy,'profit.rate_matched_actual':t?.profit,'profit.rate_matched_difference':t?t.profit-(sell-buy):null});}
 if(fin&&['profit.air_yield','profit.ocean_yield','profit.matched_share','profit.best_dimension'].includes(metric)){const d=EXP_DIMS[S.exp.dim]||EXP_DIMS[0],rs=groupByP(d.k,m);values[metric]=metric==='profit.air_yield'?(d3.sum(rs,r=>r.airT)>0?d3.sum(rs,r=>r.airP)/d3.sum(rs,r=>r.airT):null):metric==='profit.ocean_yield'?(d3.sum(rs,r=>r.seaT)>0?d3.sum(rs,r=>r.seaP)/d3.sum(rs,r=>r.seaT):null):metric==='profit.best_dimension'?d3.max(rs.filter(r=>r.profit>0),r=>r.profit)??null:t.jobs?pbyJob(m).filter(r=>psidx[r.i0]>=0).length/t.jobs:null;}
 if(fin&&['profit.cost_not_booked_proxy','profit.billing_pending_proxy','profit.loss_making','profit.low_margin'].includes(metric)){const status={'profit.cost_not_booked_proxy':1,'profit.billing_pending_proxy':2,'profit.loss_making':3,'profit.low_margin':4}[metric];values[metric]=pbyJob(m).filter(r=>r.status===status).length;}
 if(metric==='profit.negative_income_rows')values[metric]=Array.from(m).filter((v,i)=>v&&pinc[i]<0).length;
 if(metric==='profit.intercompany_proxy')values[metric]=pbyJob(m).filter(r=>pcatv('p_ic',r.i0)==='Intercompany').length;
 if(['ops.period_new_customers','ops.period_absent_customers'].includes(metric)){const current=new Map(),previous=new Map();for(let i=0;i<N;i++){const c=COLS.customer.c[i];if(m[i])current.set(c,(current.get(c)||0)+1);if(p[i])previous.set(c,(previous.get(c)||0)+1);}values[metric]=metric==='ops.period_new_customers'?[...current].filter(([c,n])=>n>=S.def.activeMin&&!previous.has(c)).length:[...previous].filter(([c,n])=>n>=S.def.activeMin&&!current.has(c)).length;}
 if(metric==='ops.customer_concentration')values[metric]=top10(m,R.useVol);
 if(metric==='ops.active_customers')values[metric]=S.group==='summary'?opsFacts(m).cust:activeCust(m);
 if(metric==='ops.lock_lag')values[metric]=opsFacts(m).lag;
 if(['profit.customers','profit.customers_80','profit.biggest_customer','profit.loss_customers'].includes(metric)){const rs=groupByP('customer',m).sort((a,b)=>b.profit-a.profit),total=d3.sum(rs,r=>r.profit),positive=d3.sum(rs.filter(r=>r.profit>0),r=>r.profit);let cum=0,num=0;rs.forEach(r=>{if(r.profit>0&&cum<.8*positive){cum+=r.profit;num++;}});values[metric]={'profit.customers':rs.length,'profit.customers_80':num,'profit.biggest_customer':rs.length?rs[0].profit/(total||1):null,'profit.loss_customers':rs.filter(r=>r.profit<0).length}[metric];}
 return {metric,dataset_built_at:D.built_at,displayed_value:values[metric],indices:Array.from(m).flatMap((v,i)=>v?[i]:[]),previous_indices:Array.from(p).flatMap((v,i)=>v?[i]:[]),context:{low_margin:S.def.lowMargin,top_n:S.def.topN,concentration_measure:R.useVol?(R.air?'air_weight_t':'teu'):'count',dimension_key:(EXP_DIMS[S.exp.dim]||EXP_DIMS[0]).k,rate_mode:S.def.rateMode,rate_max:S.def.rateMax,active_min:S.group==='summary'?1:S.def.activeMin,old_days:S.def.oldDays,unbilled_days:S.def.unbilledDays,age_as_of:OPS_MAX,period:(S.page==='p_compare'||S.page==='compare')?periods(S.cmp):win(),date_basis:fin?'Job Date':'Shipment Date',page:S.page,visual:label,filters:Object.fromEntries(Object.entries(S.sel).map(([k,v])=>[k,[...v].map(i=>COLS[k]?.d[i]??i)]))}};
}
window.NG = {visualMetricPayload,traceVariance:metricTraceVariance,periods,win,pctOf,pctChange,traceCategory:metricTraceCategory,exportVisibleVisuals,traceSelection:metricTraceSelection,agentRows, runVisual, visGet, visSave, defCfg, VTEMPLATES, rateOK, rmargin, saveView, applyView, viewsGet, goto, setGroup, opsFacts, maskP, groupByP, totalsP, pbyJob, pExpectedByLob, money, NP, NPA, NJ, pinc, pexp, pjob, psidx, pjInc, pjExp, D, S, DEFAULTS, renderDefs, COLS, D, mask, compute, renderAll, toggle, csvOf, openMenu, menuAll, menuClear, get R() { return R; }, N, MAXDATE, MINDATE};
})();
