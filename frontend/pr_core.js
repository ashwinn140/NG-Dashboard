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
  opt = opt || {}; const skip = new Set([].concat(opt.skip || [])), NN = opt.demo && S.pdemo ? NPA : NP, m = new Uint8Array(NPA); m.fill(1, 0, NN);
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
const pkeyRank = (key, opt) => { const m = maskP({skip: key}), sel = S.sel[key] || new Set(); return prankList(groupByP(key, m), (r) => toggle(key, r.g), (r) => sel.has(r.g), opt); };
