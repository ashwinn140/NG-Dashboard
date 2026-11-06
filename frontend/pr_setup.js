// ---- job profit lines, joined to the shipment registers by job number (the "VLOOKUP"); they share the same dictionaries, so every filter applies to both
const PD_ = D.p, NP = PD_.co.length, PSH = [7, 31, 365], pdemoSrc = [], pdemoK = [];
for (let i = 0; i < NP; i++) PSH.forEach((sh, k) => { if (hash01(i, 50 + k) < 0.8) { pdemoSrc.push(i); pdemoK.push(k); } });
const NPA = NP + pdemoSrc.length, pext = (T, a) => { const x = new T(NPA); x.set(a); return x; };
const pco = pext(Uint8Array, PD_.co), prt = pext(Uint8Array, PD_.rt), pinc = pext(Float64Array, PD_.income), pexp = pext(Float64Array, PD_.expense), ptd = pext(Int32Array, PD_.td), pjd = pext(Int32Array, PD_.jd), psidx = pext(Int32Array, PD_.sidx);
const pdemo = new Uint8Array(NPA), pjob = new Int32Array(NPA);
for (let t = 0; t < pdemoSrc.length; t++) { const i = NP + t, s0 = pdemoSrc[t], f = 0.7 + 0.6 * hash01(s0, 90 + pdemoK[t]); pco[i] = pco[s0]; prt[i] = prt[s0]; pinc[i] = pinc[s0] * f; pexp[i] = pexp[s0] * f; ptd[i] = ptd[s0] - PSH[pdemoK[t]]; pjd[i] = pjd[s0] - PSH[pdemoK[t]]; psidx[i] = psidx[s0]; pdemo[i] = 1; }
for (const k in D.cols) { const pc = pext(Uint16Array, D.cols[k].pc); for (let t = 0; t < pdemoSrc.length; t++) pc[NP + t] = pc[pdemoSrc[t]]; COLS[k].pc = pc; }
COLS.company.pc = pco; COLS.company.own = true; COLS.report.own = true; COLS.report.pc = prt; COLS.report.d = REPN.concat(['Other (road, general)']);
COLS.jobstatus = {l: 'Job status', d: ['Healthy', 'Cost not booked', 'Billing pending', 'Loss-making', 'Low margin'], c: null, pc: new Uint8Array(NPA), own: false};
COLS.band = {l: 'Job margin band', d: ['Loss (below 0%)', '0 to 10%', '10 to 30%', '30 to 60%', '60 to 99%', '100% (no cost booked)', 'No income'], c: null, pc: new Uint8Array(NPA), own: false};
{ const jm = new Map(), jc = COLS.p_job.pc; for (let i = 0; i < NPA; i++) { const k = pco[i] * 100000 + jc[i]; let j = jm.get(k); if (j === undefined) { j = jm.size; jm.set(k, j); } pjob[i] = j; } var NJ = jm.size; }
const pjInc = new Float64Array(NJ), pjExp = new Float64Array(NJ), pjFirst = new Int32Array(NJ).fill(-1);
for (let i = 0; i < NP; i++) { const j = pjob[i]; pjInc[j] += pinc[i]; pjExp[j] += pexp[i]; if (pjFirst[j] < 0) pjFirst[j] = i; }
for (let t = 0; t < pdemoSrc.length; t++) if (pjFirst[pjob[NP + t]] < 0) pjFirst[pjob[NP + t]] = pdemoSrc[t];
let pdate = ptd, PMIN = 0, PMAX = 0;
function setPBasis(b) { pdate = b === 'job' ? pjd : ptd; PMIN = 1e9; PMAX = -1e9; for (let i = 0; i < NP; i++) if (pdate[i] > 0) { if (pdate[i] < PMIN) PMIN = pdate[i]; if (pdate[i] > PMAX) PMAX = pdate[i]; } }
setPBasis('bill');
const PMAIN = ['p_lob', 'p_charge', 'p_party', 'jobstatus', 'band', 'p_ic'], PEXTRA = ['p_job', 'p_mode', 'p_direction', 'p_kind'];
