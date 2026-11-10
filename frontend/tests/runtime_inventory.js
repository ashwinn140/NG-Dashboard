// Runtime visual inventory. Run from repo root after:
//   python scripts/build_audit_fixture.py
// Renders every registered dashboard page for each role against the synthetic
// fixture and records every card/KPI/table/chart plus its explanation state.
// Output: audit/runtime_visual_inventory.json and .csv. Never touches production.
const {JSDOM,VirtualConsole}=require('jsdom');const fs=require('fs');
const html=fs.readFileSync('app/web/dashboard.html','utf8');
const src=fs.readFileSync('frontend/app_prod.js','utf8');
const traceSrc=fs.readFileSync('app/web/metric_trace.js','utf8');
const m=src.match(/const PAGES = \{([^}]*)\}/);
const allPages=[...m[1].matchAll(/([A-Za-z0-9_]+)\s*:/g)].map(x=>x[1]);
const groups={summary:['s_owner','s_score'],ops:['overview','compare','customers','lanes','ops','ship','o_agents','o_sales','changes','status'],profit:['p_overview','p_compare','p_explorer','p_branches','p_customers','p_jobs','p_quality','p_billing','p_rates','p_status'],mine:['v_mine','v_build']};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{const rows=[],errors={},unvisited=new Set(allPages);
for(const role of ['admin','ops','finance']){
 const data=JSON.parse(fs.readFileSync('/tmp/ng-fixture-'+role+'.json','utf8')),errs=[],vc=new VirtualConsole();
 const me={...(data.user||{}),name:role,role,csrf:'audit-test'};
 vc.on('jsdomError',e=>{if(!/navigation|CSS stylesheet/.test(e.message))errs.push(e.message)});
 const dom=new JSDOM(html,{url:'http://audit.test/',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.__ME=me;w.matchMedia=()=>({matches:false,media:'',addListener(){},removeListener(){},addEventListener(){},removeEventListener(){},dispatchEvent(){return false}});w.scrollTo=()=>{};w.SVGElement.prototype.getComputedTextLength=()=>30;w.Blob=global.Blob;w.URL.createObjectURL=()=>'blob:x';w.fetch=async u=>({ok:true,status:200,json:async()=>String(u).startsWith('/api/me')?me:data,text:async()=>JSON.stringify(data),headers:{get:()=>null}});}});
 const w=dom.window,d=w.document;for(let i=0;i<60&&!w.NG;i++)await sleep(100);
 if(!w.NG){errors[role]=['boot failed',...errs];continue}await sleep(200);w.eval(traceSrc);await sleep(50);const ng=w.NG;
 for(const [group,pages] of Object.entries(groups)){
  if(role==='ops'&&group==='profit')continue;ng.setGroup(group);
  for(const page of pages){unvisited.delete(page);
   try{ng.S.page=page;ng.renderAll();await sleep(30);}catch(e){(errors[role+':'+page]=errors[role+':'+page]||[]).push(String(e));continue}
   const root=d.querySelector('#page');if(!root)continue;
   [...root.querySelectorAll('.card')].forEach((el,idx)=>{
    const isKpi=el.classList.contains('kpi');
    const title=(isKpi?el.querySelector('.kl'):el.querySelector('h2'))?.textContent.trim()||'(untitled)';
    const ex=el.querySelector('details.business-explanation');
    const action=[...el.querySelectorAll('button,a')].find(b=>b.textContent.trim()==='Calculation & records');
    const ps=ex?[...ex.querySelectorAll('p')]:[];
    const what=ps.find(p=>p.textContent.startsWith('What this means'))?.textContent.replace('What this means: ','')||'';
    const how=ps.find(p=>p.textContent.startsWith('How it is calculated'))?.textContent.replace('How it is calculated: ','')||'';
    rows.push({role,group,page,idx,kind:isKpi?'kpi':'card',title,
      tables:el.querySelectorAll('table').length,charts:el.querySelectorAll('svg').length,
      has_explanation:!!ex,calc_verified:!!how&&!/not yet verified/i.test(how),has_reconciliation_action:!!action,
      reconciliation_metric:action?.dataset.traceMetric||action?.dataset.metricId||'',reconciliation_dimension:action?.dataset.traceDimension||'',what,how});
   });
  }}
 if(errs.length)errors[role+':jsdom']=errs;dom.window.close();}
fs.mkdirSync('audit',{recursive:true});
fs.writeFileSync('audit/runtime_visual_inventory.json',JSON.stringify({rows,errors,registered_pages_not_visited:[...unvisited]},null,1));
const esc=v=>'"'+String(v).replace(/"/g,'""')+'"';const cols=['role','group','page','idx','kind','title','tables','charts','has_explanation','calc_verified','has_reconciliation_action','reconciliation_metric','reconciliation_dimension','what','how'];
fs.writeFileSync('audit/runtime_visual_inventory.csv',[cols.join(','),...rows.map(r=>cols.map(c=>esc(r[c])).join(','))].join('\n'));
const uniq=new Map();rows.forEach(r=>{const k=r.role+'|'+r.page+'|'+r.title;if(!uniq.has(k))uniq.set(k,r)});
const u=[...uniq.values()];
console.log(JSON.stringify({role_page_visual_instances:rows.length,unique_page_title_visuals:u.length,
 kpis:u.filter(r=>r.kind==='kpi').length,cards:u.filter(r=>r.kind==='card').length,
 with_table:u.filter(r=>r.tables).length,with_chart:u.filter(r=>r.charts).length,
 with_reconciliation_action:u.filter(r=>r.has_reconciliation_action).length,
 without_reconciliation_action:u.filter(r=>!r.has_reconciliation_action).length,
 reconciliation_action_with_unverified_calculation:u.filter(r=>r.has_reconciliation_action&&!r.calc_verified).length,
 no_explanation_block:u.filter(r=>!r.has_explanation).length,
 explanation_but_calc_unverified:u.filter(r=>r.has_explanation&&!r.calc_verified).length,
 calc_verified:u.filter(r=>r.calc_verified).length,
 registered_pages_not_visited:[...unvisited],errors:Object.keys(errors)},null,1));
if(u.some(r=>r.has_reconciliation_action&&!r.calc_verified))throw Error('A reconciliation action is attached to a visual with an unverified calculation.');
if(Object.keys(errors).length)throw Error('Runtime visual inventory found browser errors: '+JSON.stringify(errors));
if(unvisited.size)throw Error('Runtime visual inventory did not visit registered pages: '+[...unvisited].join(', '));
})().catch(e=>{console.error(e);process.exit(1)});
