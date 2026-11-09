// Run from repo root after python scripts/build_audit_fixture.py. Requires jsdom.
// Regression: Quality-page KPIs keep click-to-filter AND show verified explanations.
const {JSDOM,VirtualConsole}=require('jsdom');const fs=require('fs');
const html=fs.readFileSync('app/web/dashboard.html','utf8'),data=JSON.parse(fs.readFileSync('/tmp/ng-fixture-admin.json','utf8'));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));let fails=0;const check=(l,ok,d)=>{console.log((ok?'PASS ':'FAIL ')+l,ok?'':(d||''));if(!ok)fails++};
(async()=>{const vc=new VirtualConsole();vc.on('jsdomError',()=>{});
const dom=new JSDOM(html,{url:'http://audit.test/',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.SVGElement.prototype.getComputedTextLength=()=>30;w.Blob=global.Blob;w.URL.createObjectURL=()=>'blob:x';w.fetch=async()=>({ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data),headers:{get:()=>null}});}});
const w=dom.window,d=w.document;for(let i=0;i<60&&!w.NG;i++)await sleep(100);await sleep(200);const ng=w.NG;
ng.setGroup('profit');ng.S.page='p_quality';ng.renderAll();
for(const t of ['Cost not booked','Costs booked, no income recorded','Loss-making','Low margin','Negative income rows','Company-name matched jobs']){
 const k=[...d.querySelectorAll('#page .card.kpi')].find(e=>e.querySelector('.kl')?.textContent.trim()===t);
 check(t+': KPI present',!!k);if(!k)continue;
 const ps=[...k.querySelectorAll('details.business-explanation p')].map(p=>p.textContent);
 check(t+': has What this means',ps.some(p=>p.startsWith('What this means: ')&&!/for the selected reporting scope/.test(p)),ps);
 check(t+': calculation verified (not the placeholder)',ps.some(p=>p.startsWith('How it is calculated: ')&&!/not yet verified/i.test(p)),ps);
 check(t+': no interactive element nested in a button',!k.closest('button')&&![...k.querySelectorAll('button')].some(b=>b.querySelector('details')));
}
const hit=d.querySelector('#page button.kpi-hit');check('KPI hit button exists',!!hit);
hit.click();await sleep(50);check('click applies the job-status filter',ng.S.sel&&ng.S.sel.jobstatus&&ng.S.sel.jobstatus.size===1,JSON.stringify([...(ng.S.sel.jobstatus||[])]));
dom.window.close();console.log(fails?'FAILED '+fails:'ALL PASSED');process.exit(fails?1:0)})().catch(e=>{console.error(e);process.exit(1)});
