// Run from repo root after python scripts/build_audit_fixture.py. Requires jsdom.
// Regressions for the Operations pages: lane keys, declining accounts, data-status pill.
const {JSDOM,VirtualConsole}=require('jsdom');const fs=require('fs');
const html=fs.readFileSync('app/web/dashboard.html','utf8');const sleep=ms=>new Promise(r=>setTimeout(r,ms));let fails=0;
const check=(l,ok,d)=>{console.log((ok?'PASS ':'FAIL ')+l,ok?'':JSON.stringify(d));if(!ok)fails++};
async function boot(mutate){
 const data=JSON.parse(fs.readFileSync('/tmp/ng-fixture-admin.json','utf8'));if(mutate)mutate(data);
 const vc=new VirtualConsole();vc.on('jsdomError',()=>{});
 const dom=new JSDOM(html,{url:'http://audit.test/',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.SVGElement.prototype.getComputedTextLength=()=>30;w.Blob=global.Blob;w.URL.createObjectURL=()=>'blob:x';w.__recentJobsCalls=0;w.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')};w.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');this.dispatchEvent(new w.Event('close'))};w.fetch=async(url)=>{if(String(url).includes('/api/customers/recent-jobs')){w.__recentJobsCalls++;return {ok:true,status:200,json:async()=>({histories:[{customer:'Fixture customer',jobs:[5,4,3,2,1].map(n=>({company:'NG',job_no:'JOB-'+n,job_date:'2026-01-0'+n,lob:'FFWD AIR EXP',job_owner:'Repeated Owner',owner_status:'available'}))}]})};}return {ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data),headers:{get:()=>null}};};}});
 const w=dom.window;for(let i=0;i<60&&!w.NG;i++)await sleep(100);await sleep(200);return {dom,w,d:w.document,ng:w.NG,data}}
(async()=>{
 // 1) lanes: with more than 1,000 destination ports, origin 0 -> dest 1000 and origin 1 -> dest 0 are different lanes
 {const {dom,w,d,ng}=await boot(data=>{const dc=data.cols.destination;for(let k=dc.d.length;k<1105;k++)dc.d.push('ZZ Dummy Port '+k);
   const oc=data.cols.origin;if(oc.d.length<3)for(let k=oc.d.length;k<3;k++)oc.d.push('ZZ Origin '+k);
   const n=data.rep.length;for(let i=0;i<n;i++){dc.c[i]=0;oc.c[i]=2}                         // park everything on one lane
   for(let i=0;i<3;i++){oc.c[i]=0;dc.c[i]=1000}for(let i=3;i<5;i++){oc.c[i]=1;dc.c[i]=0}});
  ng.S.def.topN=200;ng.S.sel={};ng.S.from=null;ng.S.to=null;ng.S.rel=null;ng.setGroup('ops');ng.S.page='overview';ng.renderAll();
  const card=[...d.querySelectorAll('#page article')].find(e=>/lanes/i.test(e.querySelector('h2')?.textContent)&&/Top/.test(e.querySelector('h2').textContent));
  const rows=[...card.querySelectorAll('.rank .row')].map(r=>({lab:r.querySelector('.lab').textContent,val:r.querySelector('.val').textContent}));
  const a=rows.find(r=>r.lab.endsWith('ZZ Dummy Port 1000')),b=rows.find(r=>r.lab.endsWith('→ '+ng.COLS.destination.d[0]) && !r.lab.startsWith(ng.COLS.origin.d[2]));
  check('lanes: two distinct lanes are not merged when the destination list exceeds 1,000',!!a&&!!b&&/^3\b/.test(a.val)&&/^2\b/.test(b.val),rows.slice(0,6));dom.window.close()}
 // 2) declining accounts must include a customer who shipped before and has no shipments now
 {const {dom,w,d,ng,data}=await boot();
  const cc=ng.COLS.customer.c,dates=data.date,mx=Math.max(...dates),cur={from:mx-29,to:mx},prev={from:mx-59,to:mx-30};
  const inC=new Set(),inP={};for(let i=0;i<dates.length;i++){if(dates[i]>=cur.from&&dates[i]<=cur.to)inC.add(cc[i]);else if(dates[i]>=prev.from&&dates[i]<=prev.to)inP[cc[i]]=(inP[cc[i]]||0)+1}
  const lostIds=Object.keys(inP).filter(j=>!inC.has(+j));
  check('fixture has a customer present before and absent now (test precondition)',lostIds.length>0,{inP:Object.keys(inP).length,inC:inC.size});
  ng.S.sel={};ng.S.rel=null;ng.S.from=cur.from;ng.S.to=cur.to;ng.S.def.compare='prev';ng.S.def.topN=500;ng.setGroup('ops');ng.S.page='customers';ng.renderAll();
  const card=[...d.querySelectorAll('#page article')].find(e=>e.querySelector('h2')?.textContent==='Declining accounts');
  const labels=[...card.querySelectorAll('.rank .row .lab')].map(e=>e.textContent);
  const missing=lostIds.filter(j=>!labels.includes(ng.COLS.customer.d[+j]));
  check('declining accounts lists customers who dropped to zero shipments',missing.length===0,{missing:missing.map(j=>ng.COLS.customer.d[+j]),labels:labels.slice(0,5)});dom.window.close()}
 // 3) data status pill follows the report's date range
 {const {dom,w,d,ng}=await boot();ng.setGroup('ops');ng.S.page='status';ng.renderAll();
  const pills=()=>[...d.querySelectorAll('#page table tbody td .pill')].map(e=>e.textContent);
  const before=pills();ng.D.meta.forEach(m=>{m.range_to='2000-01-31'});ng.renderAll();const after=pills();
  check('status pill shows Current while inside the stated range',before.length>0&&before.every(t=>t==='Current'),before);
  check('status pill shows Range ended after the stated range',after.length>0&&after.every(t=>t==='Range ended'),after);dom.window.close()}

 // 4) customer rows expose a separate recent-job action and show five distinct source jobs
 {const {dom,w,d,ng}=await boot();ng.S.sel={};ng.S.rel=null;ng.S.from=null;ng.S.to=null;ng.setGroup('ops');ng.S.page='customers';ng.renderAll();
  const button=[...d.querySelectorAll('#page button')].find(b=>b.textContent==='View jobs');
  check('Operations Customers exposes a View jobs action',!!button);
  if(button){button.dispatchEvent(new w.MouseEvent('click',{bubbles:true,cancelable:true}));await sleep(650);
   const dialog=d.querySelector('dialog[open]'),jobs=dialog?[...dialog.querySelectorAll('tbody tr')]:[];
   check('View jobs opens a customer history dialog',!!dialog);
   check('customer history shows the last five distinct JPR jobs',jobs.length===5&&jobs[0].textContent.includes('JOB-5'),jobs.map(r=>r.textContent));
   check('customer owner preload and View jobs each make one request',w.__recentJobsCalls===2,w.__recentJobsCalls);
   check('repeated Job Owner values remain visible',jobs.filter(r=>r.textContent.includes('Repeated Owner')).length===5);
  }
  dom.window.close()}

 // Filter popovers must not stringify null DOM placeholders after real options.
 {const {dom,w,d,ng}=await boot();ng.setGroup('profit');ng.renderAll();
  const anchor=d.querySelector('.fbtn');ng.openMenu('p_lob',anchor);
  const stray=()=>[...d.querySelector('#ml').childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).filter(Boolean);
  check('populated filter menu has no literal null placeholder',!stray().includes('null'),stray());
  const q=d.querySelector('#mq');q.value='no-such-lob-fixture';q.dispatchEvent(new w.Event('input'));
  check('empty filter search keeps its meaningful empty state',d.querySelector('#ml').textContent.includes('No matching values.'));
  ng.openMenu('__add',anchor);
  check('add-filter menu has no literal null placeholder',!stray().includes('null'),stray());dom.window.close()}

 console.log(fails?'FAILED '+fails:'ALL PASSED');process.exit(fails?1:0)})().catch(e=>{console.error(e);process.exit(1)});
