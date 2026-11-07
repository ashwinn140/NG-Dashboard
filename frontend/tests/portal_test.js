// The sign-in page and the admin portal, opened like a browser would.  node portal_test.js http://127.0.0.1:8765  (demo users from scripts/seed_demo.py)
const {JSDOM,VirtualConsole}=require('jsdom'); const BASE=process.argv[2]||'http://127.0.0.1:8765'; const sleep=ms=>new Promise(r=>setTimeout(r,ms)); let fails=0;
const chk=(l,ok,x)=>{if(!ok)fails++;console.log((ok?'PASS  ':'FAIL  ')+l+(x?'   ['+x+']':''))};
async function page(path,cookie){const errs=[];const r=await fetch(BASE+path,{headers:cookie?{cookie}:{},redirect:'manual'});const html=await r.text();const vc=new VirtualConsole();vc.on('jsdomError',e=>errs.push((e.detail&&e.detail.stack||e.message).split('\n').slice(0,3).join(' | ')));
 const jar={c:cookie||''};const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,url:BASE+path,beforeParse(w){w.fetch=async(u,o)=>{o=Object.assign({},o||{});o.headers=Object.assign({},o.headers||{},jar.c?{cookie:jar.c}:{});o.redirect='manual';const res=await fetch(new URL(u,BASE),o);const sc=res.headers.getSetCookie?res.headers.getSetCookie():[];if(sc.length)jar.c=sc.map(x=>x.split(';')[0]).join('; ');return res};w.alert=()=>{};w.prompt=()=>null;}});
 await sleep(900);return {w:dom.window,d:dom.window.document,errs,jar,status:r.status}}
const click=async(w,el)=>{el.dispatchEvent(new w.MouseEvent('click',{bubbles:true,cancelable:true}));await sleep(500)};
(async()=>{
 const lp=await page('/login');const {w,d}=lp;
 chk('the sign-in page opens with the product name',/Performance Dashboard/.test(d.body.textContent));
 chk('with email not set up, the sign-in page hides the email tab and says why',d.getElementById('t1').style.display==='none'&&/not set up/i.test(d.getElementById('msg').textContent),d.getElementById('msg').textContent.slice(0,70));
 d.getElementById('login').value='admin@demo.test';d.getElementById('pw').value='wrong-password';d.getElementById('f2').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await sleep(900);
 chk('a wrong password shows a plain message and stays on the page',/not right/.test(d.getElementById('msg').textContent)&&d.getElementById('msg').className==='bad',d.getElementById('msg').textContent);
 d.getElementById('pw').value='Demo-admin-1234';d.getElementById('f2').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await sleep(1200);
 chk('the right password signs in (the page tries to go to the dashboard)',lp.jar.c.includes('ng_session'));
 chk('no script errors on the sign-in page',lp.errs.filter(e=>!/navigation|Not implemented/.test(e)).length===0,lp.errs.slice(0,2).join(' || '));
 const cookie=lp.jar.c;const ap=await page('/admin',cookie);const A=ap.d,W=ap.w;for(let i=0;i<40&&!/Setup checklist/.test(A.getElementById('main').textContent);i++)await sleep(250);
 chk('the admin portal opens for the administrator',ap.status===200&&/Administration/.test(A.body.textContent));
 const tabs=[...A.querySelectorAll('#nav button')].map(b=>b.textContent);chk('all eight sections are there',tabs.length===8,tabs.join(' | '));
 const txt=()=>A.getElementById('main').textContent;
 chk('overview: a setup checklist, with what is still to do and how',/Setup checklist/.test(txt())&&/to do|all done/.test(txt()),txt().match(/Setup checklist[^A-Z]*/)[0].slice(0,50));
 chk('overview: health, and history by year for shipments and for profit',/Health/.test(txt())&&/Shipment history by year/.test(txt())&&/Job profit history by year/.test(txt()));
 const go=async(name)=>{await click(W,[...A.querySelectorAll('#nav button')].find(b=>b.textContent===name));return txt()};
 let t=await go('Imports');chk('imports: the log lists the loaded files',/promoted/.test(t)&&/Ship_Reg_AE_NG1/.test(t),(t.match(/promoted/g)||[]).length+' promoted entries');
 chk('imports: every loaded report has an Undo button',[...A.querySelectorAll('#main button')].filter(b=>b.textContent==='Undo').length>=8);
 t=await go('Upload a report');chk('upload: the drop box and the check button',/Drop \.xlsx files here/.test(t)&&[...A.querySelectorAll('#main button')].some(b=>b.textContent==='Check the files'));
 t=await go('Previous reports');chk('previous reports: explained, with what is loaded now',/earlier years once/.test(t)&&/What is loaded now/.test(t));
 t=await go('Organization master');chk('organization master: company choice, file, check and load',/Organization master/.test(t)&&/two weeks/.test(t)&&[...A.querySelectorAll('#main button')].some(b=>b.textContent==='Load it'));
 t=await go('Users');chk('users: the three demo users are listed with roles',/Demo Admin/.test(t)&&/Demo Finance/.test(t)&&/Demo Operations/.test(t)&&/operations/.test(t));
 await click(W,[...A.querySelectorAll('#main button')].find(b=>b.textContent==='Add a user'));chk('users: the add form opens with role, companies, LOBs and the money tick',/Companies/.test(txt())&&/LOBs/.test(txt())&&/Can see money/.test(txt()));
 t=await go('Settings');chk('settings: history years, financial year, alert email, retention',/Years of history/.test(t)&&/Financial year starts/.test(t)&&/Send alerts to/.test(t)&&/Preview what would be removed/.test(t));
 t=await go('Activity log');chk('activity log opens',/Activity log/.test(t));
 chk('no script errors anywhere in the admin portal',ap.errs.filter(e=>!/navigation|Not implemented/.test(e)).length===0,ap.errs.slice(0,2).join(' || '));
 const op=await page('/login');op.d.getElementById('login').value='ops@demo.test';op.d.getElementById('pw').value='Demo-ops-12345';op.d.getElementById('f2').dispatchEvent(new op.w.Event('submit',{bubbles:true,cancelable:true}));await sleep(1200);
 const adm=await fetch(BASE+'/admin',{headers:{cookie:op.jar.c},redirect:'manual'});chk('an operations user is turned away from the admin portal',adm.status===303);
 console.log(fails?'\nPORTAL TEST: '+fails+' PROBLEMS':'\nPORTAL TEST: passes');process.exit(fails?1:0)})();
