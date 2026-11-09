// Run from repo root after python scripts/build_audit_fixture.py. Requires jsdom.
// Variance views must warn when the current period has far fewer jobs with cost booked than the comparison period.
const {JSDOM,VirtualConsole}=require('jsdom');const fs=require('fs');
const html=fs.readFileSync('app/web/dashboard.html','utf8');const sleep=ms=>new Promise(r=>setTimeout(r,ms));let fails=0;
const check=(l,ok,d)=>{console.log((ok?'PASS ':'FAIL ')+l,ok?'':JSON.stringify(d));if(!ok)fails++};
const ser=s=>Math.round(Date.UTC(+s.slice(0,4),+s.slice(5,7)-1,+s.slice(8,10))/86400000);
async function run(scenario){
 const data=JSON.parse(fs.readFileSync('/tmp/ng-fixture-admin.json','utf8')),p=data.p;
 for(let i=0;i<p.jd.length;i++){p.jd[i]=ser(i<20?'2026-09-15':i<40?'2026-10-15':'2026-06-15');p.expense[i]=Math.max(p.expense[i],100);p.income[i]=Math.max(p.income[i],500);
  if(scenario==='lag'&&i>=20&&i<40&&(i-20)%4!==0)p.expense[i]=0;            // Oct: 1 line in 4 keeps a cost (jobs are counted distinct, so 25% of jobs)
  if(scenario==='lag_both'&&i<40&&(i%4)!==0)p.expense[i]=0;}                // both periods equally poor
 const vc=new VirtualConsole();vc.on('jsdomError',()=>{});
 const dom=new JSDOM(html,{url:'http://audit.test/',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.SVGElement.prototype.getComputedTextLength=()=>30;w.Blob=global.Blob;w.URL.createObjectURL=()=>'blob:x';w.fetch=async()=>({ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data),headers:{get:()=>null}});}});
 const w=dom.window,d=w.document;for(let i=0;i<60&&!w.NG;i++)await sleep(100);await sleep(200);const ng=w.NG;
 const A={from:ser('2026-10-01'),to:ser('2026-10-31')},B={from:ser('2026-09-01'),to:ser('2026-09-30')},out={};
 ng.setGroup('profit');ng.S.page='p_compare';Object.assign(ng.S.pcmp,{custom:true,A:{...A},B:{...B}});ng.renderAll();
 out.compareNote=[...d.querySelectorAll('#page .cost-lag-note')].map(e=>e.textContent);
 ng.setGroup('summary');ng.S.page='s_owner';ng.S.cmp.custom=true;ng.S.cmp.A={...A};ng.S.cmp.B={...B};ng.renderAll();
 out.summaryNote=[...d.querySelectorAll('#page .cost-lag-note')].map(e=>e.textContent);
 dom.window.close();return out}
(async()=>{
 const ok=await run('ok'),lag=await run('lag'),both=await run('lag_both');
 check('normal coverage: no warning on Finance comparison page',ok.compareNote.length===0,ok);
 check('normal coverage: no warning on summary variance card',ok.summaryNote.length===0,ok);
 check('lagging current period: warning on Finance comparison page',lag.compareNote.length===1&&/only \d+ of \d+ jobs \(25%\)/.test(lag.compareNote[0])&&/100%/.test(lag.compareNote[0]),lag);
 check('lagging current period: warning on summary variance card',lag.summaryNote.length===1&&/only \d+ of \d+ jobs \(25%\)/.test(lag.summaryNote[0]),lag);
 check('both periods equally poor: no warning (not a lag)',both.compareNote.length===0&&both.summaryNote.length===0,both);
 console.log(fails?'FAILED '+fails:'ALL PASSED');process.exit(fails?1:0)})().catch(e=>{console.error(e);process.exit(1)});
