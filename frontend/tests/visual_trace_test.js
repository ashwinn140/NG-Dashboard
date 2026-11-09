const{JSDOM,VirtualConsole}=require('jsdom'),fs=require('fs'),assert=require('node:assert/strict');const D=JSON.parse(fs.readFileSync('/tmp/ng-fixture-admin.json','utf8')),vc=new VirtualConsole(),errors=[];vc.on('jsdomError',e=>{if(!/navigation|CSS stylesheet/.test(e.message))errors.push(e.message)});
const dom=new JSDOM(fs.readFileSync('app/web/dashboard.html','utf8'),{url:'http://visual.test',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.matchMedia=()=>({matches:false,addEventListener(){}});w.scrollTo=()=>{};w.SVGElement.prototype.getComputedTextLength=()=>20;w.fetch=async u=>({ok:true,status:200,json:async()=>u==='/api/me'?{name:'Test',csrf:'test',role:'admin'}:u==='/api/dataset'?D:{}})}});
(async()=>{const w=dom.window;for(let i=0;i<100&&!w.NG;i++)await new Promise(r=>setTimeout(r,20));const n=w.NG;assert.ok(n);n.S.sel={};n.S.rel=null;n.S.from=20089;n.S.to=21000;n.S.group='profit';n.compute();n.COLS.customer.d=Array.from({length:9},(_,i)=>'Synthetic '+i);n.COLS.customer.pc=Array.from({length:D.p.co.length},(_,i)=>i%9);
 for(const cfg of [{data:'fin',measure:'margin',dim:'branch',split:'customer',date:'job',type:'bar',top:1},{data:'fin',measure:'profit',dim:'customer',split:'branch',date:'job',type:'bar',top:1}]){const r=n.runVisual(cfg);assert.ok(!r.err);const memberships=[];for(let si=0;si<r.series.length;si++)for(let row=0;row<r.labels.length;row++){const indices=r.series[si].indices[row];memberships.push(...indices);const q=n.visualMetricPayload(cfg,r,row,si);assert.deepEqual(Array.from(q.indices),Array.from(indices));if(cfg.measure==='margin'&&r.series[si].values[row]!==null){const inc=indices.reduce((sum,i)=>sum+D.p.income[i],0),exp=indices.reduce((sum,i)=>sum+D.p.expense[i],0);assert.ok(Math.abs((inc-exp)/inc-r.series[si].values[row])<1e-9);if(r.series[si].name==='Other')assert.ok(r.series[si].den[row]>0,'Other ratio denominator retained');}}
 assert.equal(new Set(memberships).size,r.indices.length);assert.equal(memberships.length,r.indices.length,'no repeated source rows across chart cells');}
 
// Origin selections are OR within the field; destination is AND across fields.
// Top Lanes must use the same filtered row set rather than dropping both port filters.
n.S.group='ops';n.S.page='overview';n.S.sel={};
const od=n.COLS.origin.d,dd=n.COLS.destination.d;
const mumbai=od.findIndex(x=>String(x).includes('Mumbai')),newYork=dd.findIndex(x=>String(x).includes('New York'));
assert.ok(mumbai>=0&&newYork>=0,'fixture contains Mumbai and New York');
const nhava=od.length;od.push('Nhava Sheva');const dubai=dd.length;dd.push('Dubai');
n.COLS.origin.c[0]=mumbai;n.COLS.destination.c[0]=dubai;
n.COLS.origin.c[1]=nhava;n.COLS.destination.c[1]=dubai;
n.COLS.origin.c[2]=nhava;n.COLS.destination.c[2]=newYork;
n.COLS.origin.c[3]=mumbai;n.COLS.destination.c[3]=newYork;
n.S.sel={origin:new Set([mumbai,nhava]),destination:new Set([dubai])};n.compute();
const selected=n.mask(),lane=n.laneAgg();
assert.equal(selected[0],1);assert.equal(selected[1],1);assert.equal(selected[2],0);assert.equal(selected[3],0);
assert.equal(lane.rows.reduce((sum,r)=>sum+r.cnt,0),2,'lane aggregation counts only the two matching origin/destination combinations');
assert.ok(lane.rows.every(r=>[mumbai,nhava].includes(r.o)&&r.d===dubai),'no unrelated lanes survive the multi-select');
n.S.sel={origin:new Set([mumbai,nhava])};n.compute();const originOnly=n.mask();
assert.ok(Array.from(originOnly).every((v,i)=>!v||[mumbai,nhava].includes(n.COLS.origin.c[i])),'clearing destination retains only selected origins');
n.S.sel={};n.compute();assert.equal(Array.from(n.mask()).reduce((s,v)=>s+v,0),n.N,'clearing all restores the full fixture');

// Explicit card actions must expose metric-backed evidence without changing normal card clicks.
n.S.sel={customer:new Set([n.COLS.customer.c[0]])};n.compute();n.renderAll();
const requiredCards=['Trend','Top '+n.S.def.topN+' customers','Top '+n.S.def.topN+' branches','Top '+n.S.def.topN+' lanes','Top '+n.S.def.topN+' airlines and shipping lines','Shipment mix'];
const buttons=[...w.document.querySelectorAll('#page .card button')].filter(b=>b.textContent.trim()==='Calculation & records');
const byTitle=new Map(buttons.map(b=>[b.closest('.card')?.querySelector('h2')?.textContent.trim(),b]));
for(const title of requiredCards)assert.ok(byTitle.has(title),'supported operational visual exposes explicit reconciliation: '+title);
assert.ok(!byTitle.has('The two companies'),'company split has no unsupported single-metric action');
assert.ok(!byTitle.has('Income against margin'),'scatter with multiple measures has no misleading single-metric action');
const trend=byTitle.get('Trend');assert.ok(trend,'trend has an explicit evidence action');
let trendPayload=null;w.NG.traceVisual('ops.shipments',null,'Trend');trendPayload=w.NG.traceVisual('ops.shipments',null,'Trend');
assert.equal(trendPayload.displayed_value,n.opsFacts(n.mask()).n,'trend evidence total equals its selected shipment scope');

let opened=null;w.MetricTrace={openWithRequest:q=>{opened=q;}};
byTitle.get('Top '+n.S.def.topN+' customers').click();
assert.equal(opened.metric,'ops.shipments');assert.equal(opened.context.segment.value,n.COLS.customer.d[n.COLS.customer.c[0]],'single selected customer gets item-level evidence');
assert.ok(opened.indices.every(i=>n.COLS.customer.c[i]===n.COLS.customer.c[0]),'selected-customer evidence contains only that customer');
n.S.sel={customer:new Set([n.COLS.customer.c[0],n.COLS.customer.c[1]])};n.compute();
const whole=n.traceVisual('ops.shipments','customer','Top customers'),expected=n.mask({skip:'customer'});
assert.deepEqual(Array.from(whole.indices),Array.from(expected).flatMap((v,i)=>v?[i]:[]),'multi-select uses the full ranking visual scope, excluding only its own dimension');
assert.equal(whole.context.filters.customer,undefined,'ranking scope does not claim a customer filter that it deliberately excludes');
assert.deepEqual(errors,[]);w.close();console.log('PASS custom visual trace: exact group/split/Other membership, ratio numerators and denominators, no duplicate rows.');})().catch(e=>{console.error(e);dom.window.close();process.exit(1)});
