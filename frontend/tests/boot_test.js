// Opens the real production page against a running server, as different people.  node boot_test.js http://127.0.0.1:8765
const {JSDOM,VirtualConsole}=require('jsdom'); const BASE=process.argv[2]||'http://127.0.0.1:8765'; const sleep=ms=>new Promise(r=>setTimeout(r,ms)); let fails=0;
const chk=(l,ok,x)=>{if(!ok)fails++;console.log((ok?'PASS  ':'FAIL  ')+l+(x?'   ['+x+']':''))};
async function login(login,password){const r=await fetch(BASE+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({login,password})});const c=(r.headers.getSetCookie?r.headers.getSetCookie():[]).map(x=>x.split(';')[0]).join('; ');return {ok:r.ok,cookie:c}}
async function open(cookie){const errs=[];const html=await (await fetch(BASE+'/',{headers:{cookie}})).text();const vc=new VirtualConsole();vc.on('jsdomError',e=>errs.push((e.detail&&e.detail.stack||e.message).split('\n').slice(0,3).join(' | ')));
 const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,url:BASE+'/',beforeParse(w){w.SVGElement.prototype.getComputedTextLength=()=>30;w.scrollTo=()=>{};w.matchMedia=w.matchMedia||(()=>({matches:false,addListener(){},removeListener(){}}));w.fetch=(u,o)=>{o=Object.assign({},o||{});o.headers=Object.assign({},o.headers||{},{cookie});return fetch(new URL(u,BASE),o)};}});
 const w=dom.window;for(let i=0;i<80&&!w.NG;i++)await sleep(150);await sleep(300);return {w,d:w.document,errs}}
const click=async(w,el)=>{el.dispatchEvent(new w.MouseEvent('click',{bubbles:true,cancelable:true}));await sleep(90)};
(async()=>{
 const A=await login('admin@demo.test','Demo-admin-1234'); chk('administrator signs in',A.ok&&A.cookie.includes('ng_session'));
 const a=await open(A.cookie); const {w,d}=a; chk('the page loads its data from the server and starts',!!w.NG&&!d.getElementById('boot'),'shipments '+(w.NG&&w.NG.N));
 chk('the person is shown with a link to Administration and a sign-out',/Demo Admin/.test(d.getElementById('userbox').textContent)&&!!d.querySelector('#userbox a[href="/admin"]')&&/Sign out/.test(d.getElementById('userbox').textContent));
 chk('the data is the full set: 21,409 shipments and 1,210 charge lines',w.NG.N===21409&&w.NG.NP===1210);
 chk('data freshness is shown',/Updated/.test(d.getElementById('fresh').textContent),d.getElementById('fresh').textContent);
 const groups={summary:['s_owner','s_score'],ops:['overview','compare','customers','lanes','ops','ship','o_agents','o_sales','changes','status'],profit:['p_overview','p_compare','p_explorer','p_branches','p_customers','p_charges','p_jobs','p_quality','p_billing','p_rates','p_status'],mine:['v_mine','v_build']};
 let bad=[];for(const g in groups){w.NG.setGroup(g);await sleep(60);for(const p of groups[g]){await click(w,d.querySelector(`#tabs button[data-p="${p}"]`));const cards=d.querySelectorAll('#page .card').length;if(!cards)bad.push(p)}}
 chk('every page of every view renders with the server data (4 views, 25 pages)',bad.length===0,bad.join(','));
 chk('no script errors for the administrator',a.errs.filter(e=>!/navigation/.test(e)).length===0,a.errs.slice(0,2).join(' || '));
 // saving a visual reaches the server and follows the person
 w.NG.setGroup('mine');await sleep(50);w.NG.visSave(w.NG.defCfg('ops'),null);await sleep(600);const pr=await (await fetch(BASE+'/api/prefs',{headers:{cookie:A.cookie}})).json();
 chk('a visual saved in the page is stored on the server',Array.isArray(pr.visuals)&&pr.visuals.length>=1,'saved '+(pr.visuals||[]).length);
 const a2=await open(A.cookie);chk('opening the dashboard again (another device) shows it',a2.w.NG.visGet().length>=1,a2.w.NG.visGet().length+' visual(s)');
 // operations user: limited and no money
 const O=await login('ops@demo.test','Demo-ops-12345');const o=await open(O.cookie);
 chk('operations user: only New Globe Air Export (9,777 shipments), no charge lines',o.w.NG.N===9777&&o.w.NG.NP===0,o.w.NG.N+' shipments, '+o.w.NG.NP+' lines');
 chk('operations user: no Finance view and no Administration link',[...o.d.querySelectorAll('#grpSeg button')].find(b=>b.dataset.v==='profit').hidden===true&&!o.d.querySelector('#userbox a[href="/admin"]'));
 o.w.NG.setGroup('profit');await sleep(60);chk('operations user cannot switch to Finance',o.w.NG.S.group!=='profit',o.w.NG.S.group);
 o.w.NG.setGroup('summary');await sleep(80);const txt=o.d.getElementById('page').textContent;chk('the owner summary for operations shows no money (no Accounting section, no ₹ income or profit)',!/Accounting/.test(txt)&&!/Profit after expected costs/.test(txt)&&!/Estimated freight margin/.test(txt));
 let bad2=[];for(const p of ['s_owner','s_score']){await click(o.w,o.d.querySelector(`#tabs button[data-p="${p}"]`));if(!o.d.querySelectorAll('#page .card').length)bad2.push(p)}o.w.NG.setGroup('ops');for(const p of groups.ops){await click(o.w,o.d.querySelector(`#tabs button[data-p="${p}"]`));if(!o.d.querySelectorAll('#page .card').length)bad2.push(p)}o.w.NG.setGroup('mine');for(const p of groups.mine){await click(o.w,o.d.querySelector(`#tabs button[data-p="${p}"]`));if(!o.d.querySelectorAll('#page .card').length)bad2.push(p)}
 chk('operations user: every page they can reach renders',bad2.length===0,bad2.join(','));chk('no script errors for the operations user',o.errs.filter(e=>!/navigation/.test(e)).length===0,o.errs.slice(0,2).join(' || '));
 const builderOpts=[...(()=>{o.w.NG.S.vis.cfg=o.w.NG.defCfg('ops');o.w.NG.renderAll();return o.d.querySelectorAll('#page select option')})()].map(x=>x.textContent);chk('the visual builder offers no finance data to operations',!builderOpts.some(t=>/Charge lines/.test(t))&&!builderOpts.some(t=>/Estimated freight margin|Shipments invoiced/.test(t)));
 // a stranger
 const s=await fetch(BASE+'/',{redirect:'manual'});chk('a stranger is sent to the sign-in page',s.status===303&&s.headers.get('location')==='/login');
 const lg=await (await fetch(BASE+'/login')).text();chk('the sign-in page has the email link, code and password forms',/Send me a sign-in link/.test(lg)&&/6-digit code/.test(lg)&&/User ID and password/.test(lg));
 const ad=await fetch(BASE+'/admin',{headers:{cookie:O.cookie},redirect:'manual'});chk('operations user is turned away from /admin',ad.status===303);
 // phone layout is in the page
 const html=await (await fetch(BASE+'/',{headers:{cookie:A.cookie}})).text();chk('the phone layout is in the page (filters fold away, tabs scroll, menus become sheets)',/max-width:760px/.test(html)&&/fToggle/.test(html)&&/#filters\.collapsed/.test(html)&&/min-height:42px/.test(html)&&/font-size:16px!important/.test(html));
 chk('the page has a skip link and a loading state',/class="skip"/.test(html)&&/id="boot"/.test(html));
 console.log(fails?'\nBOOT TEST: '+fails+' PROBLEMS':'\nBOOT TEST: passes');process.exit(fails?1:0)})();
