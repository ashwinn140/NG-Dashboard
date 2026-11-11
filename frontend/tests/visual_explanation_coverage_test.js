const{JSDOM,VirtualConsole}=require('jsdom'),fs=require('fs'),assert=require('node:assert/strict');
const D=JSON.parse(fs.readFileSync('/tmp/ng-fixture-admin.json','utf8')),vc=new VirtualConsole(),errors=[];
vc.on('jsdomError',e=>{if(!/navigation|CSS stylesheet/.test(e.message))errors.push(e.message)});
const dom=new JSDOM(fs.readFileSync('app/web/dashboard.html','utf8'),{url:'http://visual-explanations.test',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.matchMedia=()=>({matches:false,addEventListener(){}});w.scrollTo=()=>{};w.SVGElement.prototype.getComputedTextLength=()=>20;w.fetch=async u=>({ok:true,status:200,json:async()=>u==='/api/me'?{name:'Test',csrf:'test',role:'admin'}:u==='/api/dataset'?D:{}})}});
(async()=>{const w=dom.window;for(let i=0;i<100&&!w.NG;i++)await new Promise(r=>setTimeout(r,20));const n=w.NG;assert.ok(n);w.eval(fs.readFileSync('app/web/metric_trace.js','utf8'));
const explanation=(group,page,title,phrase)=>{n.setGroup(group);n.S.page=page;n.renderAll();const c=[...w.document.querySelectorAll('#page .card')].find(x=>x.querySelector('h2')?.textContent.trim()===title);assert.ok(c,'visual exists: '+group+'/'+page+'/'+title);const d=c.querySelector('.business-explanation');assert.ok(d,'visual has explanation: '+title);assert.ok(!d.textContent.includes('Calculation not yet verified'),'visual calculation verified: '+title);assert.ok(d.textContent.toLowerCase().includes(phrase.toLowerCase()),'explanation states source/formula: '+title);};
explanation('summary','s_owner','What needs your attention','independent checks');
explanation('summary','s_owner','Top '+n.S.def.topN+' customers by profit','simple JPR');
explanation('summary','s_owner','Shipments by month','Shipment Date');
explanation('summary','s_score','Scorecard by customer','Job Date');
n.setGroup('summary');n.S.page='s_owner';n.S.sel={};n.renderAll();
const summaryVariance=[...w.document.querySelectorAll('#page .card')].find(x=>x.querySelector('h2')?.textContent.trim().startsWith('Variance:'));
assert.ok(summaryVariance,'summary period variance table exists');
const varianceRows=[...summaryVariance.querySelectorAll('tbody tr')];
assert.ok(varianceRows.length>0,'summary variance table has measures');
let varianceRequest=null;const originalVarianceOpen=w.MetricTrace.openWithRequest;w.MetricTrace.openWithRequest=q=>{varianceRequest=q;};
const varianceMetricByLabel={'Shipments':'ops.shipments','Air chargeable tonnes':'ops.air_weight','Sea TEUs':'ops.teu','Active customers':'ops.active_customers','Shipments invoiced':'ops.invoiced_count','Est. freight margin (air export)':'ops.rate_margin','Income':'profit.income','Expense':'profit.expense','Profit':'profit.gp','Margin':'profit.margin','Jobs in the profit report':'profit.jobs'};
for(const row of varianceRows){
 const button=row.querySelector('td:first-child button.link');assert.ok(button,'each variance measure has a record action');
 const label=button.textContent.replace(/\s*↗$/,'').trim();button.click();
 assert.equal(varianceRequest?.metric,varianceMetricByLabel[label],'variance evidence maps to the correct source metric: '+label);
 assert.ok(Array.isArray(varianceRequest.indices)&&Array.isArray(varianceRequest.previous_indices),'variance evidence contains both comparison-period record selections: '+label);
}
w.MetricTrace.openWithRequest=originalVarianceOpen;

explanation('ops','o_agents','Agent variation report','Booking Thru');
explanation('ops','o_sales','Sales performance report','Booking Thru');
explanation('profit','p_explorer','Profitability by customer','simple JPR');
explanation('profit','p_customers','Income against margin','square root');
explanation('profit','p_billing','Locked but not invoiced, by age','operations-lock date');
explanation('profit','p_billing','Where billing is slow','operations-locked');
n.setGroup('profit');n.S.page='p_billing';n.renderAll();
const billingCard=[...w.document.querySelectorAll('#page .card')].find(x=>x.querySelector('h2')?.textContent.trim()==='Where billing is slow');
assert.ok(billingCard,'billing bottleneck table exists');
assert.equal(billingCard.querySelector('.mt-info')?.dataset.traceMetric,'ops.locked_no_invoice','billing card exposes source-backed evidence');
assert.ok([...billingCard.querySelectorAll('tbody button')].some(b=>b.textContent.trim()==='Locked'),'dimension rows expose all locked shipment records');
assert.ok([...billingCard.querySelectorAll('tbody button')].some(b=>b.textContent.trim()==='Unbilled'),'dimension rows expose the unbilled subset');
const ageCard=[...w.document.querySelectorAll('#page .card')].find(x=>x.querySelector('h2')?.textContent.trim()==='Locked but not invoiced, by age');
assert.ok(ageCard&&[...ageCard.querySelectorAll('button')].filter(b=>b.textContent.trim()==='View records').length===5,'all five ageing buckets expose contributing records');
assert.ok([...w.document.querySelectorAll('#page .kpis .mt-info')].length>=5,'billing KPIs expose their own calculation and records');
const billingMonth=[...w.document.querySelectorAll('#page svg[aria-label="Shipments and invoices by month"] rect[style*="cursor"]')];
assert.ok(billingMonth.length>0,'monthly shipment/invoice bars are individually drillable');
const billingVariance=[...w.document.querySelectorAll('#page .card')].find(x=>x.querySelector('h2')?.textContent.trim()==='Variance: shipments invoiced');
assert.ok(billingVariance,'invoice variance visual exists');
const invoiceVarianceRows=[...billingVariance.querySelectorAll('tbody tr')];
assert.ok(invoiceVarianceRows.length===0||invoiceVarianceRows.every(row=>[...row.querySelectorAll('button')].some(b=>b.textContent.trim()==='View records')),'every populated invoice variance row exposes current and comparison records');
assert.ok(billingVariance?.querySelector('.mt-info'),'invoice variance visual exposes a header-level Calculation & records action');
assert.equal(billingVariance.querySelector('.mt-info')?.dataset.traceMetric,'ops.invoiced_count','invoice variance evidence uses first-invoice-date records');
explanation('profit','p_billing','Shipments against invoices, by month','different date fields');
explanation('profit','p_billing','Variance: shipments invoiced','first invoice date');
explanation('profit','p_compare','Variance: change in value and percentage','absolute comparison value');
explanation('profit','p_status','Profit data status','simple Job Profit Analysis Report');
explanation('profit','p_status','Matched to the shipment register','unique match');

// Finance-authorized scorecard retains its finance evidence action.
n.setGroup('ops');n.S.page='s_score';n.S.sel={};n.renderAll();
const opsScorecard=[...w.document.querySelectorAll('#page .card')].find(x=>x.querySelector('h2')?.textContent.trim()==='All rows');
assert.ok(opsScorecard,'scorecard All rows table exists');
assert.equal(opsScorecard.querySelector('.mt-info')?.dataset.traceMetric,'profit.gp','finance-authorized scorecard retains finance evidence');

assert.deepEqual(errors,[]);w.close();
console.log('PASS verified visual explanations: summary, scorecard, agent reports, profitability, billing, variance and source-status pages.');})().catch(e=>{console.error(e);dom.window.close();process.exit(1)});
