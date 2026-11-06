import re
s = open('app.js.pre_merge', encoding='utf-8').read()
def rep(old, new, cnt=1):
    global s
    assert old in s, "NOT FOUND: " + old[:110]; s = s.replace(old, new, cnt)
setup, core, pages, extra, spages, fpages, vpages, apages = (open(f, encoding='utf-8').read() for f in ('pr_setup.js', 'pr_core.js', 'pr_pages.js', 'pr_extra.js', 's_pages.js', 'f_pages.js', 'v_pages.js', 'a_pages.js'))
pages = pages.replace('S.cust', 'S.pcust')
# ---- 1. data: shared dictionaries with codes for the shipment rows (c) and the profit lines (pc)
rep("for (const k in D.cols) { const c = ext(Uint16Array, D.cols[k].c); for (let t = 0; t < demoSrc.length; t++) c[N + t] = c[demoSrc[t]]; COLS[k] = {l: D.cols[k].l, d: D.cols[k].d, c}; }",
    "for (const k in D.cols) { const dc = D.cols[k], c = dc.c ? ext(Uint16Array, dc.c) : new Uint16Array(NA); if (dc.c) for (let t = 0; t < demoSrc.length; t++) c[N + t] = c[demoSrc[t]]; COLS[k] = {l: dc.l, d: dc.d, c, own: !!dc.c}; }\n" + setup)
rep("COLS.lane = {l: 'Lane', d: names, c: codes}; }", "const lpc = new Uint16Array(NPA), poc = COLS.origin.pc, pdc = COLS.destination.pc; for (let i = 0; i < NPA; i++) { const key = poc[i] * 1000 + pdc[i]; let j = lm.get(key); if (j === undefined) { j = names.length; lm.set(key, j); names.push(COLS.origin.d[poc[i]] + ' → ' + COLS.destination.d[pdc[i]]); } lpc[i] = j; } COLS.lane = {l: 'Lane', d: names, c: codes, pc: lpc, own: true}; }")
rep("const STAGE_PEND =", "const OPS_MIN = MINDATE, OPS_MAX = MAXDATE;\nconst STAGE_PEND =")
# ---- 2. state, definitions
rep("const S = {page: 'overview', from: null, to: null, rel: null,", "const S = {page: 'overview', group: 'ops', rank: 'profit', pdemo: false, exp: null, jobs: {q: '', sort: 'profit', dir: -1}, pcust: {sort: 'profit', dir: -1}, pcmp: {unit: 'month', against: 'prev', basis: 'todate', anchor: null, custom: false, A: {from: null, to: null}, B: {from: null, to: null}, dim: 'branch', measure: 'profit', show: 'all', tsort: {sort: 'adelta', dir: -1}}, from: null, to: null, rel: null,")
rep("yearBasis: 'fy', historyYears: 3,", "yearBasis: 'fy', historyYears: 3, moneyUnit: 'auto', lowMargin: 10, costCoverage: 80, jobRows: 300, pBasis: 'bill',")
# ---- 3. filtering
rep("for (const k in S.sel) { if (skip.has(k)) continue; const set = S.sel[k];", "for (const k in S.sel) { if (skip.has(k) || !COLS[k].own) continue; const set = S.sel[k];")
i0 = s.index("function compute() {"); i1 = s.index("\n}\n", i0) + 3
s = s[:i0] + """function syncBounds() { MINDATE = Math.min(OPS_MIN, PMIN); MAXDATE = Math.max(OPS_MAX, PMAX); }   // one date range for the whole dashboard, so switching views never changes it
function setGroup(g) { S.group = g; S.page = g === 'ops' ? 'overview' : 'p_overview'; syncBounds(); renderAll(); }
function compute() {
  syncBounds();
  if (S.group === 'profit') { recomputeJobsP(); const M = maskP(), P = maskP({dates: 'prev'}), t = totalsP(M), tp = totalsP(P); R = {w: win(), M, P, t, tp, n: t.lines}; return; }
  const M = mask(), P = mask({dates: 'prev'}); let n = 0, air = 0, sea = 0, np = 0;
  for (let i = 0; i < N; i++) { if (M[i]) { n++; if (mode[i]) sea++; else air++; } if (P[i]) np++; }
  const mixed = air > 0 && sea > 0, useVol = S.measure === 'volume' && !mixed;
  R = {w: win(), M, P, n, np, air, sea, mixed, useVol};
}
""" + s[i1:]
rep("function kpi(label, value, delta, note) {\n  return h('div', {class: 'card kpi'}, h('div', {class: 'kl'}, label), h('div', {class: 'kv'}, value),", "function kpi(label, value, delta, note, tone) {\n  return h('div', {class: 'card kpi'}, h('div', {class: 'kl'}, label), h('div', {class: 'kv' + (tone ? ' ' + tone : '')}, value),")
rep("function periods() {\n  const c = S.cmp;", "function periods(c0) {\n  const c = c0 || S.cmp;")
# ---- 4. profit code goes in just before the page map
rep("const PAGES = {", core + "\n" + pages + "\n" + extra + "\n" + spages + "\n" + fpages + "\n" + vpages + "\n" + apages + "\nconst PAGES = {")
i0 = s.index("const PAGES = {"); j = s.index("};", i0) + 2
s = s[:j - 2] + ", p_overview: ppOverview, p_explorer: ppExplorer, p_branches: ppBranches, p_customers: ppCustomers, p_charges: ppCharges, p_jobs: ppJobs, p_quality: ppQuality, p_compare: ppCompare, p_status: ppStatus, s_owner: sOwner, s_score: sScore, p_billing: ppBilling, p_rates: ppRates, v_mine: vMine, v_build: vBuild, o_agents: vVariation, o_sales: vSales};" + s[j:]
# ---- 5. filter bar and menus know about the two groups
rep("const keys = MAIN.concat(S.extra), box = $('fbtns');", "const keys = MAIN.concat(S.group === 'profit' ? PMAIN : [], S.extra.filter((k) => S.group === 'profit' || COLS[k].own)), box = $('fbtns');")
rep("chips.push(h('button', {type: 'button', class: 'chip',", "chips.push(h('button', {type: 'button', class: 'chip', title: COLS[k].own || S.group === 'profit' ? '' : 'Applies to the profit pages only',")
s = re.sub(r"  \$\('status'\)\.textContent = .*\n", "  $('status').textContent = S.group === 'profit' ? 'Showing ' + fInt(R.n) + ' of ' + fInt(NP) + ' charge lines · ' + fDay(R.w.from) + ' to ' + fDay(R.w.to) + ' by ' + (S.def.pBasis === 'job' ? 'job date' : 'billing date') + ' · ' + fInt(R.t.jobs) + ' jobs' : 'Showing ' + fInt(R.n) + ' of ' + fInt(N) + ' shipments · ' + fDay(R.w.from) + ' to ' + fDay(R.w.to) + ' by shipment date' + (R.mixed ? ' · air and sea are shown separately, never added together' : '');\n", s, count=1)
rep("const opts = EXTRA.filter((k) => !S.extra.includes(k)", "const opts = EXTRA.concat(S.group === 'profit' ? PEXTRA : []).filter((k) => !S.extra.includes(k)")
rep("mh.textContent = COLS[key].l; const m = mask({skip: key}), c = COLS[key].c, cnt = new Float64Array(COLS[key].d.length); for (let i = 0; i < N; i++) if (m[i]) cnt[c[i]]++;",
    "mh.textContent = COLS[key].l; const pro = S.group === 'profit', m = pro ? maskP({skip: key}) : mask({skip: key}), c = pro ? COLS[key].pc : COLS[key].c, cnt = new Float64Array(COLS[key].d.length); for (let i = 0, nn = pro ? NP : N; i < nn; i++) if (m[i]) cnt[c[i]]++;")
rep("  const vbtn = document.querySelector('#mSeg button[data-v=\"volume\"]'); vbtn.disabled = R.mixed;", "  document.querySelectorAll('[data-g]').forEach((e) => { e.hidden = e.dataset.g !== S.group; });\n  document.querySelectorAll('#grpSeg button').forEach((b) => on(b, b.dataset.v === S.group));\n  { const cs = S.sel.company; document.querySelectorAll('#coSeg button').forEach((b) => { const v = b.dataset.v; on(b, v === 'both' ? !cs || cs.size === 0 || cs.size === 2 : !!cs && cs.size === 1 && cs.has(v === 'ng' ? 0 : 1)); }); }\n  document.querySelectorAll('#rankSeg button').forEach((b) => on(b, b.dataset.v === S.rank)); document.querySelectorAll('#basisSeg button').forEach((b) => on(b, b.dataset.v === S.def.pBasis));\n  const vbtn = document.querySelector('#mSeg button[data-v=\"volume\"]'); if (S.group === 'ops') vbtn.disabled = R.mixed;")
rep("vbtn.title = R.mixed ?", "if (S.group === 'ops') vbtn.title = R.mixed ?")
rep("document.querySelectorAll('#mSeg button').forEach((b) => on(b, (b.dataset.v === 'volume') === R.useVol));", "if (S.group === 'ops') document.querySelectorAll('#mSeg button').forEach((b) => on(b, (b.dataset.v === 'volume') === R.useVol));")
rep("function wire() {", """const DEF_PROFIT = [
  {k: 'lowMargin', l: 'Profit: low margin means below (%)', h: 'A job with a margin below this (and some cost booked) is flagged low margin.', t: 'num', min: 0, max: 100},
  {k: 'costCoverage', l: 'Profit: warn when jobs with cost booked fall below (%)', h: 'The profit overview warns that margins are too high when fewer jobs than this have a cost booked.', t: 'num', min: 0, max: 100},
  {k: 'moneyUnit', l: 'Profit: show amounts in', h: 'Lakh and crore follow Indian practice.', t: 'sel', opts: [['auto', 'Automatic (₹ lakh and crore)'], ['inr', 'Rupees'], ['k', 'Thousands'], ['lakh', 'Lakh'], ['cr', 'Crore']]},
  {k: 'pBasis', l: 'Profit: date filter uses', h: 'The profit report is built on billing date. Job date is when the job was opened.', t: 'sel', opts: [['bill', 'Billing date'], ['job', 'Job date']]},
  {k: 'jobRows', l: 'Profit: jobs shown in the jobs table', h: 'Rows listed on the Jobs page of the profit view.', t: 'num', min: 10, max: 3000}];
DEF_PROFIT.forEach((f) => DEF_FIELDS.push(f));
function wire() {
  document.querySelectorAll('#grpSeg button').forEach((b) => b.addEventListener('click', () => setGroup(b.dataset.v)));
  document.querySelectorAll('#coSeg button').forEach((b) => b.addEventListener('click', () => { const v = b.dataset.v; if (v === 'both') delete S.sel.company; else S.sel.company = new Set([v === 'ng' ? 0 : 1]); renderAll(); }));
  document.querySelectorAll('#rankSeg button').forEach((b) => b.addEventListener('click', () => { S.rank = b.dataset.v; renderAll(); }));
  document.querySelectorAll('#basisSeg button').forEach((b) => b.addEventListener('click', () => { S.def.pBasis = b.dataset.v; saveDefs(); setPBasis(b.dataset.v); renderAll(); }));""")
rep("renderDefs(); wire(); renderAll();", "S.exp = S.exp || {dim: 0, sort: {sort: 'profit', dir: -1}}; setPBasis(S.def.pBasis); renderDefs(); wire(); renderAll();")
rep("window.NG = {S,", "window.NG = {setGroup, maskP, groupByP, totalsP, pbyJob, pExpectedByLob, money, NP, NPA, NJ, pinc, pexp, pjob, psidx, pjInc, pjExp, D, S,")

# ---- 6. owner's summary group, promoted filters, saved views, printing
rep("const S = {page: 'overview', group: 'ops',", "const S = {page: 's_owner', group: 'summary',")
rep("moneyUnit: 'auto', lowMargin: 10,", "moneyUnit: 'auto', ownerConc: 25, unassignedShare: 20, unassignedNames: 'Administrator', lowMargin: 10,")
rep("const MAIN = ['company', 'report', 'branch', 'customer', 'shipper', 'consignee', 'job_owner', 'carrier', 'origin', 'destination', 'nomination', 'consol', 'cargo', 'status', 'stage'];", "const MAIN = ['company', 'report', 'branch', 'customer', 'x_salesperson', 'shipper', 'consignee', 'job_owner', 'carrier', 'origin', 'destination', 'x_tradelanename', 'x_dischargecountry', 'nomination', 'consol', 'cargo', 'status', 'stage'];")
rep("const EXTRA = Object.keys(COLS).filter((k) => k.startsWith('x_'))", "const EXTRA = Object.keys(COLS).filter((k) => k.startsWith('x_') && !MAIN.includes(k))")
rep("function compute() {\n  syncBounds();", """function compute() {
  syncBounds();
  if (S.group === 'summary') { const M = mask(), P = mask({dates: 'prev'}); let n = 0, np = 0; for (let i = 0; i < N; i++) { if (M[i]) n++; if (P[i]) np++; } recomputeJobsP(); const t = totalsP(maskP()), tp = totalsP(maskP({dates: 'prev'})); R = {w: win(), M, P, n, np, air: 0, sea: 0, mixed: false, useVol: false, t, tp}; return; }""")
rep("$('status').textContent = S.group === 'profit' ?", "$('status').textContent = S.group === 'summary' ? 'Showing ' + fInt(R.n) + ' of ' + fInt(N) + ' shipments and ' + fInt(R.t.lines) + ' charge lines · ' + fDay(R.w.from) + ' to ' + fDay(R.w.to) : S.group === 'profit' ?")
rep("function setGroup(g) { S.group = g; S.page = g === 'ops' ? 'overview' : 'p_overview';", "function setGroup(g) { S.group = g; S.page = g === 'ops' ? 'overview' : g === 'summary' ? 's_owner' : 'p_overview';")
rep("e.hidden = e.dataset.g !== S.group;", "e.hidden = !e.dataset.g.split(' ').includes(S.group);")
rep("kpi('Oldest open shipment (days)', fInt(oldest), null, 'Days since shipment date')", "kpi('Oldest open shipment (days)', fInt(oldest), null, 'Days since shipment date'), kpi('Days from ops lock to financial lock', opsFacts(M).lag == null ? '–' : opsFacts(M).lag.toFixed(1), null, 'Average, where both are recorded')")
rep("DEF_PROFIT.forEach((f) => DEF_FIELDS.push(f));", """DEF_PROFIT.push({k: 'ownerConc', l: 'Summary: warn when one customer brings more than (% of profit)', h: 'The owner summary flags customer concentration above this share.', t: 'num', min: 1, max: 100},
  {k: 'unassignedShare', l: 'Summary: warn when unassigned sales or missing trade lane exceeds (% of profit)', h: 'Flags profit that cannot be credited to a sales person or trade lane.', t: 'num', min: 1, max: 100},
  {k: 'unassignedNames', l: 'Summary: sales person names that mean not assigned', h: 'Comma separated. “Administrator” is the ERP default user.', t: 'text'});
DEF_PROFIT.forEach((f) => DEF_FIELDS.push(f));
function viewsGet() { try { return JSON.parse(localStorage.getItem('ngViews') || '{}'); } catch (e) { return {}; } }
function viewsSet(v) { try { localStorage.setItem('ngViews', JSON.stringify(v)); } catch (e) { /* not available */ } }
function snapshotView() { const sel = {}; for (const k in S.sel) sel[k] = [...S.sel[k]]; return {group: S.group, page: S.page, sel, from: S.from, to: S.to, rel: S.rel, rank: S.rank, measure: S.measure, qm: [...S.qm], qd: [...S.qd], extra: S.extra.slice()}; }
function renderViews() { const v = viewsGet(), sel = $('viewSel'); sel.replaceChildren(new Option('Saved views…', ''), ...Object.keys(v).sort().map((n) => new Option(n, n))); }
function saveView(name) { if (!name) return; const v = viewsGet(); v[name] = snapshotView(); viewsSet(v); renderViews(); $('viewSel').value = name; }
function applyView(name) { const v = viewsGet()[name]; if (!v) return; S.sel = {}; for (const k in v.sel) S.sel[k] = new Set(v.sel[k]); Object.assign(S, {group: v.group, page: v.page, from: v.from, to: v.to, rel: v.rel, rank: v.rank, measure: v.measure, extra: v.extra || []}); S.qm = new Set(v.qm); S.qd = new Set(v.qd); syncBounds(); renderAll(); }""")
rep("  document.querySelectorAll('#grpSeg button').forEach((b) => b.addEventListener('click', () => setGroup(b.dataset.v)));", """  document.querySelectorAll('#grpSeg button').forEach((b) => b.addEventListener('click', () => setGroup(b.dataset.v)));
  $('viewSave').addEventListener('click', () => { const nm = window.prompt ? window.prompt('Name this view (it keeps the page, the filters and the dates)') : ''; if (nm && nm.trim()) saveView(nm.trim()); });
  $('viewSel').addEventListener('change', () => { if ($('viewSel').value) applyView($('viewSel').value); });
  $('viewDel').addEventListener('click', () => { const nm = $('viewSel').value; if (!nm) return; const v = viewsGet(); delete v[nm]; viewsSet(v); renderViews(); });
  $('printBtn').addEventListener('click', () => window.print());""")
rep("renderDefs(); wire(); renderAll();", "renderDefs(); renderViews(); wire(); renderAll();")
rep("window.NG = {setGroup,", "window.NG = {saveView, applyView, viewsGet, goto, setGroup, opsFacts,")


# ---- 7. billing and variance
rep("const date = ext(Int32Array, D.date), opsD = ext(Int32Array, D.ops), finD = ext(Int32Array, D.fin);", "const date = ext(Int32Array, D.date), opsD = ext(Int32Array, D.ops), finD = ext(Int32Array, D.fin), inv1 = ext(Int32Array, D.inv1), invN = ext(Uint8Array, D.invN);")
rep("date[i] = date[s0] - 365 * k;", "date[i] = date[s0] - 365 * k; inv1[i] = inv1[s0] > 0 ? inv1[s0] - 365 * k : inv1[s0]; invN[i] = invN[s0];")
rep("moneyUnit: 'auto', ownerConc: 25,", "moneyUnit: 'auto', unbilledDays: 30, ownerConc: 25,")
rep("DEF_PROFIT.push({k: 'ownerConc',", "DEF_PROFIT.push({k: 'unbilledDays', l: 'Billing: late when operations locked and not invoiced for more than (days)', h: 'Shipments past this age with no invoice are counted as late billing.', t: 'num', min: 1, max: 365}, {k: 'ownerConc',")


# ---- 8. rates, build-your-own visuals
rep("moneyUnit: 'auto', unbilledDays: 30,", "moneyUnit: 'auto', rateMode: 'text', rateMax: 5000, unbilledDays: 30,")
rep("DEF_PROFIT.push({k: 'unbilledDays',", "DEF_PROFIT.push({k: 'rateMode', l: 'Rates: which buy and sell rates to use', h: 'The rate columns are free text. Plain numbers are safest; numbers read from text such as “512.00 ALL IN” add coverage.', t: 'sel', opts: [['text', 'Plain numbers and numbers read from text'], ['clean', 'Plain numbers only']]}, {k: 'rateMax', l: 'Rates: highest believable rate (₹ per kg)', h: 'Anything above this is a lump sum, not a per-kg rate, and is left out.', t: 'num', min: 100, max: 100000}, {k: 'unbilledDays',")
rep("if (S.group === 'summary') { const M = mask(), P = mask({dates: 'prev'});", "if (S.group === 'summary' || S.group === 'mine') { const M = mask(), P = mask({dates: 'prev'});")
rep("$('status').textContent = S.group === 'summary' ?", "$('status').textContent = S.group === 'summary' || S.group === 'mine' ?")
rep("g === 'summary' ? 's_owner' : 'p_overview';", "g === 'summary' ? 's_owner' : g === 'mine' ? 'v_mine' : 'p_overview';")
rep("window.NG = {saveView,", "window.NG = {runVisual, visGet, visSave, defCfg, VTEMPLATES, rateOK, rmargin, saveView,")


# ---- 9. agent variation report
rep("moneyUnit: 'auto', rateMode: 'text',", "moneyUnit: 'auto', lapsedMonths: 2, declinePct: 30, rateMode: 'text',")
rep("DEF_PROFIT.push({k: 'rateMode',", "DEF_PROFIT.push({k: 'lapsedMonths', l: 'Agents: lapsed after no shipment for (months)', h: 'The agent variation report marks an agent lapsed after this many months without a shipment.', t: 'num', min: 1, max: 24}, {k: 'declinePct', l: 'Agents: declining or growing when the 3-month average moves by (%)', h: 'Last 3 complete months against the 3 before.', t: 'num', min: 1, max: 1000}, {k: 'rateMode',")
rep("const MAIN = ['company', 'report', 'branch', 'customer', 'x_salesperson',", "const MAIN = ['company', 'report', 'branch', 'customer', 'agent', 'x_salesperson',")
rep("const SC_DIMS = [{k: 'customer', l: 'Customer'},", "const SC_DIMS = [{k: 'customer', l: 'Customer'}, {k: 'agent', l: 'Agent'},")
rep("window.NG = {runVisual,", "window.NG = {agentRows, runVisual,")

open('app_merged.js', 'w', encoding='utf-8').write(s)
# ---- template
t = open('template.html.pre_merge', encoding='utf-8').read()
def trep(old, new):
    global t
    assert old in t, "TEMPLATE NOT FOUND: " + old[:90]; t = t.replace(old, new, 1)
trep('<nav class="tabs" id="tabs" aria-label="Pages">', '<div class="frow" id="grpRow"><span class="lbl2">View</span><div id="grpSeg"><button type="button" class="btn on" data-v="ops">Operations</button><button type="button" class="btn" data-v="profit">Profit</button></div></div>\n  <div id="tabs">\n  <nav class="tabs" data-g="ops" aria-label="Operations pages">')
trep('<button type="button" disabled title="Needs the profit analysis report">Profit (waiting for report)</button>\n  </nav>', '</nav>\n  <nav class="tabs" data-g="profit" aria-label="Profit pages" hidden>\n    <button type="button" data-p="p_overview" aria-selected="false">Profit overview</button>\n    <button type="button" data-p="p_compare" aria-selected="false">Variance</button>\n    <button type="button" data-p="p_explorer" aria-selected="false">Profitability by…</button>\n    <button type="button" data-p="p_branches" aria-selected="false">Branch profit</button>\n    <button type="button" data-p="p_customers" aria-selected="false">Customers</button>\n    <button type="button" data-p="p_charges" aria-selected="false">Charges and vendors</button>\n    <button type="button" data-p="p_jobs" aria-selected="false">Jobs</button>\n    <button type="button" data-p="p_quality" aria-selected="false">Profit quality</button>\n    <button type="button" data-p="p_billing" aria-selected="false">Billing health</button>\n    <button type="button" data-p="p_status" aria-selected="false">Finance data status</button>\n  </nav>\n  </div>')
trep('<span class="lbl2">Reports</span>', '<span class="lbl2">Company</span>\n      <div id="coSeg"><button type="button" class="btn" data-v="both">Both</button><button type="button" class="btn" data-v="ng">New Globe</button><button type="button" class="btn" data-v="ncs">Neutral Consolidation</button></div>\n      <span class="lbl2">Reports</span>')
trep('<span class="lbl2">Measure</span>\n      <div id="mSeg">', '<span class="lbl2" data-g="ops">Measure</span>\n      <div id="mSeg" data-g="ops">')
trep('<label class="f"><input type="checkbox" id="cmp" checked>', '<span class="lbl2" data-g="profit" hidden>Rank by</span><div id="rankSeg" data-g="profit" hidden><button type="button" class="btn" data-v="profit">Profit</button><button type="button" class="btn" data-v="income">Income</button><button type="button" class="btn" data-v="expense">Expense</button></div>\n      <span class="lbl2" data-g="profit" hidden>Date basis</span><div id="basisSeg" data-g="profit" hidden title="The profit report is built on billing date. Job date is when the job was opened."><button type="button" class="btn" data-v="bill">Billing date</button><button type="button" class="btn" data-v="job">Job date</button></div>\n      <label class="f"><input type="checkbox" id="cmp" checked>')
trep('<span class="ribbon" title="Added in a later build step">Ask AI: coming in a later step</span>', '<span class="ribbon" title="Added in a later build step">Ask AI: coming in a later step</span><span class="ribbon" title="Finance and Management roles only in the live system">Finance view: Finance and Management</span>')
trep('<title>New Globe and Neutral Consolidation: performance dashboard (review version)</title>', '<title>New Globe and Neutral Consolidation: performance and profit dashboard (review version)</title>') if '<title>New Globe and Neutral Consolidation: performance dashboard (review version)</title>' in t else None

trep('<div id="grpSeg"><button type="button" class="btn on" data-v="ops">Operations</button><button type="button" class="btn" data-v="profit">Profit</button></div></div>', '<div id="grpSeg"><button type="button" class="btn on" data-v="summary">Owner’s summary</button><button type="button" class="btn" data-v="ops">Operations</button><button type="button" class="btn" data-v="profit">Finance</button></div>\n    <span class="lbl2" style="margin-left:1rem">Views</span><select id="viewSel" aria-label="Saved views"><option value="">Saved views…</option></select><button type="button" class="btn" id="viewSave">Save this view</button><button type="button" class="btn" id="viewDel">Delete view</button><button type="button" class="btn" id="printBtn">Print this page</button></div>')
trep('<nav class="tabs" data-g="ops" aria-label="Operations pages">', '<nav class="tabs" data-g="summary" aria-label="Summary pages">\n    <button type="button" data-p="s_owner" class="on" aria-selected="true">Owner’s summary</button>\n    <button type="button" data-p="s_score" aria-selected="false">Scorecard by any angle</button>\n  </nav>\n  <nav class="tabs" data-g="ops" aria-label="Operations pages" hidden>')
trep('<button type="button" data-p="overview" class="on" aria-selected="true">Overview</button>', '<button type="button" data-p="overview" aria-selected="false">Overview</button>')


trep('<button type="button" class="btn" data-v="profit">Finance</button></div>', '<button type="button" class="btn" data-v="profit">Finance</button><button type="button" class="btn" data-v="mine">My visuals</button></div>')
trep('<nav class="tabs" data-g="ops" aria-label="Operations pages" hidden>', '<nav class="tabs" data-g="mine" aria-label="My visuals" hidden>\n    <button type="button" data-p="v_mine" aria-selected="false">My dashboard</button>\n    <button type="button" data-p="v_build" aria-selected="false">Build a visual</button>\n  </nav>\n  <nav class="tabs" data-g="ops" aria-label="Operations pages" hidden>')
trep('<button type="button" data-p="p_billing" aria-selected="false">Billing health</button>', '<button type="button" data-p="p_billing" aria-selected="false">Billing health</button>\n    <button type="button" data-p="p_rates" aria-selected="false">Rate margin</button>')


trep('<button type="button" data-p="changes" aria-selected="false">Changes since last report</button>', '<button type="button" data-p="o_agents" aria-selected="false">Agent variation report</button>\n    <button type="button" data-p="changes" aria-selected="false">Changes since last report</button>')


trep('<button type="button" data-p="o_agents" aria-selected="false">Agent variation report</button>', '<button type="button" data-p="o_agents" aria-selected="false">Agent variation report</button>\n    <button type="button" data-p="o_sales" aria-selected="false">Sales performance report</button>')

open('template_merged.html', 'w', encoding='utf-8').write(t)
print("merged ok", len(s) // 1024, "KB")
