// Run from repo root after python scripts/build_audit_fixture.py. Requires jsdom.
// Explanations must show the viewer's LIVE Definitions values (not "set under Definitions").
const {JSDOM,VirtualConsole}=require('jsdom');const fs=require('fs');
const html=fs.readFileSync('app/web/dashboard.html','utf8'),data=JSON.parse(fs.readFileSync('/tmp/ng-fixture-admin.json','utf8'));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));let fails=0;const check=(l,ok,d)=>{console.log((ok?'PASS ':'FAIL ')+l,ok?'':JSON.stringify(d));if(!ok)fails++};
(async()=>{const vc=new VirtualConsole();vc.on('jsdomError',()=>{});
const dom=new JSDOM(html,{url:'http://audit.test/',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.SVGElement.prototype.getComputedTextLength=()=>30;w.Blob=global.Blob;w.URL.createObjectURL=()=>'blob:x';w.fetch=async()=>({ok:true,status:200,json:async()=>data,text:async()=>JSON.stringify(data),headers:{get:()=>null}});}});
const w=dom.window,d=w.document;for(let i=0;i<60&&!w.NG;i++)await sleep(100);await sleep(200);const ng=w.NG;
const how=(label)=>{const k=[...d.querySelectorAll('#page .card.kpi')].find(e=>e.querySelector('.kl')?.textContent.trim().startsWith(label));
 return k?{what:[...k.querySelectorAll('details p')].find(p=>p.textContent.startsWith('What this means'))?.textContent||'',how:[...k.querySelectorAll('details p')].find(p=>p.textContent.startsWith('How it is calculated'))?.textContent||''}:null};
const cases=[['profit','p_quality','Low margin','lowMargin',10,25,v=>new RegExp('currently '+v+'%')],
 ['ops','ops','Open more than','oldDays',90,45,v=>new RegExp('currently '+v+' days')],
 ['profit','p_billing','Not invoiced for more than','unbilledDays',30,12,v=>new RegExp('currently '+v+' days')]];
for(const [g,pg,label,key,def,alt,rx] of cases){
 ng.S.def[key]=def;ng.setGroup(g);ng.S.page=pg;ng.renderAll();let r=how(label);
 check(label+': present with default '+def,!!r);if(!r)continue;
 check(label+': shows live default '+def,rx(def).test(r.what+' '+r.how),r);
 check(label+': no unfilled placeholder',!/\{(lowMargin|oldDays|unbilledDays)\}/.test(r.what+r.how),r);
 check(label+': calculation is verified text',!/not yet verified/i.test(r.how),r);
 ng.S.def[key]=alt;ng.renderAll();r=how(label);
 check(label+': follows a changed setting ('+alt+')',!!r&&rx(alt).test(r.what+' '+r.how),r);
 ng.S.def[key]=def;
}
ng.setGroup('profit');ng.S.page='p_billing';ng.renderAll();const li=how('Locked but not invoiced');
check('Locked but not invoiced: verified explanation',!!li&&!/not yet verified/i.test(li.how)&&/Billing Details/.test(li.how),li);
dom.window.close();console.log(fails?'FAILED '+fails:'ALL PASSED');process.exit(fails?1:0)})().catch(e=>{console.error(e);process.exit(1)});
