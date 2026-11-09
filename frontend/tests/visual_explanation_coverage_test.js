const{JSDOM,VirtualConsole}=require('jsdom'),fs=require('fs'),assert=require('node:assert/strict');
const D=JSON.parse(fs.readFileSync('/tmp/ng-fixture-admin.json','utf8')),vc=new VirtualConsole(),errors=[];
vc.on('jsdomError',e=>{if(!/navigation|CSS stylesheet/.test(e.message))errors.push(e.message)});
const dom=new JSDOM(fs.readFileSync('app/web/dashboard.html','utf8'),{url:'http://visual-explanations.test',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.matchMedia=()=>({matches:false,addEventListener(){}});w.scrollTo=()=>{};w.SVGElement.prototype.getComputedTextLength=()=>20;w.fetch=async u=>({ok:true,status:200,json:async()=>u==='/api/me'?{name:'Test',csrf:'test',role:'admin'}:u==='/api/dataset'?D:{}})}});
(async()=>{const w=dom.window;for(let i=0;i<100&&!w.NG;i++)await new Promise(r=>setTimeout(r,20));const n=w.NG;assert.ok(n);
const explanation=(group,page,title,phrase)=>{n.setGroup(group);n.S.page=page;n.renderAll();const c=[...w.document.querySelectorAll('#page .card')].find(x=>x.querySelector('h2')?.textContent.trim()===title);assert.ok(c,'visual exists: '+group+'/'+page+'/'+title);const d=c.querySelector('.business-explanation');assert.ok(d,'visual has explanation: '+title);assert.ok(!d.textContent.includes('Calculation not yet verified'),'visual calculation verified: '+title);assert.ok(d.textContent.toLowerCase().includes(phrase.toLowerCase()),'explanation states source/formula: '+title);};
explanation('summary','s_owner','What needs your attention','independent checks');
explanation('summary','s_owner','Top '+n.S.def.topN+' customers by profit','simple JPR');
explanation('summary','s_owner','Shipments by month','Shipment Date');
explanation('summary','s_score','Scorecard by customer','Job Date');
explanation('ops','o_agents','Agent variation report','Booking Thru');
explanation('ops','o_sales','Sales performance report','Booking Thru');
explanation('profit','p_explorer','Profitability by customer','simple JPR');
explanation('profit','p_customers','Income against margin','square root');
explanation('profit','p_billing','Locked but not invoiced, by age','operations-lock date');
explanation('profit','p_billing','Where billing is slow','operations-locked');
explanation('profit','p_billing','Shipments against invoices, by month','different date fields');
explanation('profit','p_billing','Variance: shipments invoiced','first invoice date');
explanation('profit','p_compare','Variance: change in value and percentage','absolute comparison value');
explanation('profit','p_status','Profit data status','simple Job Profit Analysis Report');
explanation('profit','p_status','Matched to the shipment register','unique match');

// Targeted acceptance: verified operations comparison charts expose source-backed
// Calculation & records for their exact current and comparison period rows.
const evidenceDay=s=>Math.round(Date.parse(s)/86400000);
n.setGroup('ops');n.S.page='compare';n.S.measure='count';
n.S.cmp.custom=true;n.S.cmp.A={from:evidenceDay('2026-10-01'),to:evidenceDay('2026-10-03')};n.S.cmp.B={from:evidenceDay('2026-09-01'),to:evidenceDay('2026-09-03')};n.renderAll();
for(const title of ['Running total','Period by period']){
 const c=[...w.document.querySelectorAll('#page .card')].find(x=>x.querySelector('h2')?.textContent.trim()===title);
 assert.ok(c,'operations comparison visual exists: '+title);
 const b=c.querySelector('.mt-info');assert.ok(b,'Calculation & records action exists: '+title);
 assert.equal(b.dataset.traceMetric,'ops.shipments');
 const q=n.traceVisual('ops.shipments',null,title);
 assert.ok(q.indices.length>0,'current-period records supplied: '+title);
 assert.ok(q.previous_indices.length>0,'comparison-period records supplied: '+title);
 assert.ok(q.indices.every(i=>D.date[i]>=evidenceDay('2026-10-01')&&D.date[i]<=evidenceDay('2026-10-03')),'current evidence respects current Shipment Date range: '+title);
 assert.ok(q.previous_indices.every(i=>D.date[i]>=evidenceDay('2026-09-01')&&D.date[i]<=evidenceDay('2026-09-03')),'comparison evidence respects comparison Shipment Date range: '+title);
 assert.equal(q.context.date_basis,'Shipment Date');
}

assert.deepEqual(errors,[]);w.close();console.log('PASS verified visual explanations: summary, scorecard, agent reports, profitability, billing, variance and source-status pages.');})().catch(e=>{console.error(e);dom.window.close();process.exit(1)});
