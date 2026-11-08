// Run from repository root after python scripts/build_audit_fixture.py. Requires jsdom.
const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('fs'),html=fs.readFileSync('app/web/dashboard.html','utf8');
const groups={summary:['s_owner','s_score'],ops:['overview','compare','customers','lanes','ops','ship','o_agents','o_sales','changes','status'],profit:['p_overview','p_compare','p_explorer','p_branches','p_customers','p_jobs','p_quality','p_billing','p_rates','p_status'],mine:['v_mine','v_build']};
// Monetary checks allow less than half a paisa for floating-point aggregation order.
let results=[];function check(label,ok,detail){results.push({label,ok:!!ok,detail});console.log((ok?'PASS ':'FAIL ')+label,detail||'')};const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{for(const role of ['admin','ops','finance']){
const data=JSON.parse(fs.readFileSync('/tmp/ng-fixture-'+role+'.json','utf8')),errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>{if(!/navigation|CSS stylesheet/.test(e.message))errors.push(e.message)});
const dom=new JSDOM(html,{url:'http://audit.test/',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.SVGElement.prototype.getComputedTextLength=()=>30;w.Blob=global.Blob;w.__downloads=[];w.URL.createObjectURL=b=>{w.__downloads.push(b);return 'blob:audit'};w.URL.revokeObjectURL=()=>{};w.scrollTo=()=>{};w.matchMedia=()=>({matches:false,addListener(){},addEventListener(){}});w.fetch=async(url,opt)=>({ok:true,status:200,json:async()=>url==='/api/me'?{name:'Audit',role:role==='admin'?'admin':role==='ops'?'operations':'finance',csrf:'synthetic'}:url==='/api/dataset'?data:{}})}});
const w=dom.window,d=w.document;for(let i=0;i<50&&!w.NG;i++)await sleep(100);if(!w.NG){check(role+' boot',false,errors);dom.window.close();continue}await sleep(200);const ng=w.NG;
check(role+' source rows',ng.N===data.rep.length&&ng.NP===data.p.co.length);check(role+' no simulated lines',ng.NPA===ng.NP);check(role+' BI removed',!d.querySelector('[href="/phase2/intelligence"]'));
for(const [group,pages]of Object.entries(groups)){if(role==='ops'&&group==='profit')continue;ng.setGroup(group);for(const page of pages){try{ng.S.page=page;ng.renderAll();check(role+' page '+page,!!d.querySelector('#page .card')||page==='changes')}catch(e){check(role+' page '+page,false,e.stack)}}}
for(let co=0;co<2;co++)for(let rt=0;rt<4;rt++){
const si=data.rep.map((r,i)=>i).filter(i=>(data.rep[i]<4?0:1)===co&&data.rep[i]%4===rt&&data.date[i]>=20089&&data.date[i]<=20453),pi=data.p.co.map((r,i)=>i).filter(i=>data.p.co[i]===co&&data.p.rt[i]===rt&&data.p.jd[i]>=20089&&data.p.jd[i]<=20453);
ng.S.group='summary';ng.S.sel={company:new w.Set([co]),report:new w.Set([rt])};ng.S.rel=null;ng.S.from=20089;ng.S.to=20453;ng.compute();const expected=[si.length,pi.reduce((s,i)=>s+data.p.income[i],0),pi.reduce((s,i)=>s+data.p.expense[i],0)],actual=[ng.R.n,ng.R.t.inc,ng.R.t.exp];check(role+' company/LOB totals '+co+'/'+rt,actual.every((v,i)=>Math.abs(v-expected[i])<0.005),actual);
}
ng.S.sel={};ng.S.from=null;ng.S.to=null;ng.compute();for(const dim of ['company','report','branch','customer','x_salesperson','lane','p_lob','p_ic']){const m=ng.maskP(),t=ng.totalsP(m),rows=ng.groupByP(dim,m);const differences=[rows.reduce((s,r)=>s+r.inc,0)-t.inc,rows.reduce((s,r)=>s+r.exp,0)-t.exp];check(role+' group totals '+dim,differences.every(v=>Math.abs(v)<0.005),{differenceINR:differences,toleranceINR:0.005})}
if(role==='admin'){
ng.S.def.compare='yoy';ng.S.from=19723;ng.S.to=19782;ng.compute();check('leap year calendar dates',ng.R.w.pfrom===19358&&ng.R.w.pto===19416,[ng.R.w.pfrom,ng.R.w.pto]);ng.S.def.compare='prev';ng.S.from=null;ng.S.to=null;ng.S.sel={};ng.S.group='summary';ng.S.page='s_owner';ng.renderAll();check('KPI previous values',[...d.querySelectorAll('#page .kpi .delta')].every(el=>el.textContent.includes('pts')||el.textContent.includes('Previous:')));check('mobile filter not sticky',w.getComputedStyle(d.querySelector('.filter-toolbar')).position==='relative');
for(const ds of ['ops','fin'])for(const measure of ds==='ops'?['count','air','sea']:['income','expense','profit','lines']){const cfg=ng.defCfg(ds);cfg.measure=measure;cfg.dim='company';const v=ng.runVisual(cfg),exp=ds==='ops'?measure==='count'?data.rep.length:measure==='air'?data.chg.reduce((s,v,i)=>s+(data.rep[i]%4<2?v:0),0):data.teus.reduce((s,v,i)=>s+(data.rep[i]%4>=2?v:0),0):measure==='income'?data.p.income.reduce((s,v)=>s+v,0):measure==='expense'?data.p.expense.reduce((s,v)=>s+v,0):measure==='profit'?data.p.income.reduce((s,v,i)=>s+v-data.p.expense[i],0):data.p.co.length;check('visual builder '+ds+'/'+measure,Math.abs(v.total-exp)<0.005,[v.total,exp])}
}
if(role==='admin'){
 ng.S.cmp.custom=true;ng.S.cmp.A={from:20089,to:20453};ng.S.cmp.B={from:19723,to:20088};ng.S.group='summary';ng.S.page='s_owner';ng.renderAll();
 const variance=[...d.querySelectorAll('#page article')].find(e=>e.textContent.includes('Variance:'));
 check('summary variance keeps zero finance baseline',!!variance&&!variance.textContent.includes('not loaded')&&variance.textContent.includes('Income'));
}
if(role==='ops'){
 ng.S.group='summary';ng.S.page='s_owner';ng.renderAll();check('operations hides profit charts',![...d.querySelectorAll('#page h2')].some(e=>/by profit|Profit by week/.test(e.textContent)));
 ng.S.page='s_score';ng.renderAll();check('operations scorecard hides money headers',![...d.querySelectorAll('#page th')].some(e=>/Income|Profit|Margin/.test(e.textContent)));
 [...d.querySelectorAll('#page button')].find(e=>e.textContent==='Download Excel').click();await sleep(10);
 const zip=require(process.cwd()+'/frontend/vendor/fflate.js').unzipSync(new Uint8Array(await w.__downloads.at(-1).arrayBuffer()));const sheet=new TextDecoder().decode(zip['xl/worksheets/sheet1.xml']);
 check('operations Excel contains no monetary columns',!/(Income|Expense|Profit|Margin)/.test(sheet));
 check('saved finance measure blocked',!!ng.runVisual({data:'ops',measure:'rmar'}).err);check('no finance view',ng.S.group!=='profit');check('rates redacted',data.rbuy.every(v=>v===0)&&data.rsell.every(v=>v===0))}
check(role+' no script errors',!errors.length,errors);dom.window.close();}
fs.writeFileSync('/tmp/ng-dom-results.json',JSON.stringify(results,null,2));console.log('RESULT',results.filter(r=>r.ok).length+'/'+results.length);process.exit(results.every(r=>r.ok)?0:1)})().catch(e=>{console.error(e);process.exit(1)});
