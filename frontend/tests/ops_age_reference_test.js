// Run from repo root after python scripts/build_audit_fixture.py. Requires jsdom.
// Regression: operational ageing is measured from the latest SHIPMENT-register date,
// even when a finance job date is later (finance dates widen the dashboard range only).
const {JSDOM,VirtualConsole}=require('jsdom');const fs=require('fs');
const html=fs.readFileSync('app/web/dashboard.html','utf8');const sleep=ms=>new Promise(r=>setTimeout(r,ms));let fails=0;
const check=(l,ok,d)=>{console.log((ok?'PASS ':'FAIL ')+l,ok?'':JSON.stringify(d));if(!ok)fails++};
async function run(shift){
 const data=JSON.parse(fs.readFileSync('/tmp/ng-fixture-admin.json','utf8')),maxShip=Math.max(...data.date);
 if(shift)for(let i=0;i<data.p.jd.length;i++)if(data.p.jd[i]>0){data.p.jd[i]=maxShip+shift;break}
 const vc=new VirtualConsole();vc.on('jsdomError',()=>{});
 const dom=new JSDOM(html,{url:'http://audit.test/',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.SVGElement.prototype.getComputedTextLength=()=>30;w.Blob=global.Blob;w.URL.createObjectURL=()=>'blob:x';w.fetch=async()=>({ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data),headers:{get:()=>null}});}});
 const w=dom.window,d=w.document;for(let i=0;i<60&&!w.NG;i++)await sleep(100);await sleep(200);const ng=w.NG;
 const kv=t=>{const k=[...d.querySelectorAll('#page .card.kpi')].find(e=>e.querySelector('.kl')?.textContent.trim().startsWith(t));return k&&k.querySelector('.kv').textContent.trim()};
 ng.setGroup('ops');ng.S.page='ops';ng.renderAll();
 const closed=ng.COLS.stage.d.indexOf('Closed'),st=ng.COLS.stage.c;let exp=0,expOld=0;
 for(let i=0;i<ng.N;i++)if(st[i]!==closed){const a=maxShip-data.date[i];exp=Math.max(exp,a);if(a>ng.S.def.oldDays)expOld++}
 const out={oldest:kv('Oldest open'),old:kv('Open more than'),exp,expOld,
  note:[...d.querySelectorAll('#page p.meta')].map(p=>p.textContent).find(t=>t.includes('Age counts'))};
 ng.S.page='o_agents';ng.renderAll();out.agentsRendered=!!d.querySelector('#page .card');
 dom.window.close();return out}
(async()=>{const base=await run(0),shifted=await run(45);
 for(const [n,r] of [['baseline',base],['finance date 45 days after last shipment',shifted]]){
  check(n+': oldest open = days from last shipment date',r.oldest===String(r.exp),r);
  check(n+': open-more-than count matches independent recount',r.old===String(r.expOld),r);
  check(n+': note names the latest shipment-register date',/latest shipment-register date/.test(r.note||''),r);
  check(n+': agent variation page renders',r.agentsRendered,r)}
 check('later finance date does not change operational ageing',base.oldest===shifted.oldest&&base.old===shifted.old,[base,shifted]);
 console.log(fails?'FAILED '+fails:'ALL PASSED');process.exit(fails?1:0)})().catch(e=>{console.error(e);process.exit(1)});
