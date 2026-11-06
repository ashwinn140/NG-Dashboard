"""Builds the production dashboard page: the same app code, but the data comes from the server, saved things are kept per login, and money is hidden from people without access."""
import re
s = open('app_merged.js', encoding='utf-8').read()
def rep(old, new):
    global s
    assert s.count(old) >= 1, "NOT FOUND: " + old[:100]; s = s.replace(old, new, 1)
# 1. data from the server
rep("const bin = atob(document.getElementById('data').textContent.trim());\nconst D = JSON.parse(fflate.strFromU8(fflate.gunzipSync(fflate.strToU8(bin, true))));",
    "const D = window.__D;\nconst SERVER = !!window.__ME, FIN = !SERVER || !!(D.user && D.user.finance);\nfunction srvPut(name, val) { if (!SERVER) return; try { fetch('/api/prefs/' + name, {method: 'PUT', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': window.__ME.csrf}, body: JSON.stringify(val)}).catch(() => {}); } catch (e) { /* offline */ } }")
# 2. saved visuals, views and definitions follow the person, not the browser
rep("function saveDefs() { try { localStorage.setItem('ngDefs', JSON.stringify(S.def)); } catch (e) { /* ignore */ } }", "function saveDefs() { try { localStorage.setItem('ngDefs', JSON.stringify(S.def)); } catch (e) { /* ignore */ } srvPut('defs', S.def); }")
rep("const visSet = (a) => { try { localStorage.setItem('ngVisuals', JSON.stringify(a)); } catch (e) { /* not available */ } };", "const visSet = (a) => { try { localStorage.setItem('ngVisuals', JSON.stringify(a)); } catch (e) { /* not available */ } srvPut('visuals', a); };")
rep("function viewsSet(v) { try { localStorage.setItem('ngViews', JSON.stringify(v)); } catch (e) { /* not available */ } }", "function viewsSet(v) { try { localStorage.setItem('ngViews', JSON.stringify(v)); } catch (e) { /* not available */ } srvPut('views', v); }")
# 3. money is only for people who may see it
rep("function setGroup(g) { S.group = g;", "function setGroup(g) { if (g === 'profit' && !FIN) return; S.group = g;")
rep("  document.querySelectorAll('[data-g]').forEach((e) => { e.hidden = !e.dataset.g.split(' ').includes(S.group); });", "  document.querySelectorAll('[data-g]').forEach((e) => { e.hidden = !e.dataset.g.split(' ').includes(S.group); });\n  if (!FIN) document.querySelectorAll('#grpSeg button[data-v=\"profit\"]').forEach((b) => { b.hidden = true; });")
rep("h('h2', {class: 'h', style: 'margin:.9rem 0 .4rem'}, 'Accounting'), h('div', {class: 'kpis'}, accK),", "FIN ? h('h2', {class: 'h', style: 'margin:.9rem 0 .4rem'}, 'Accounting') : null, FIN ? h('div', {class: 'kpis'}, accK) : null,")
rep("const body = defs.map(([lab, k, t, good, isFin]) => {", "const body = defs.filter(([lab, k]) => FIN || ['n', 'air', 'sea', 'cust'].includes(k)).map(([lab, k, t, good, isFin]) => {")
rep("  { const Mb = mask({dates: 'none'}); let late = 0;", "  if (FIN) { const Mb = mask({dates: 'none'}); let late = 0;")
rep("  { let neg = 0, give = 0;", "  if (FIN) { let neg = 0, give = 0;")
rep("measures = Object.keys(VM[ds]).map((k) => [k, VM[ds][k].l]);", "measures = Object.keys(VM[ds]).filter((k) => FIN || !['inv', 'rmar', 'rkg'].includes(k)).map((k) => [k, VM[ds][k].l]);")
rep("L('Data', sel([['ops', 'Shipments (register)'], ['fin', 'Charge lines (finance)']], ds,", "L('Data', sel([['ops', 'Shipments (register)']].concat(FIN ? [['fin', 'Charge lines (finance)']] : []), ds,")
# 4. a small data-freshness note
rep("window.NG = {", "window.NG_BOOT = function () { const t = D.built_at ? new Date(D.built_at).toLocaleString([], {dateStyle: 'medium', timeStyle: 'short'}) : ''; const el = document.getElementById('fresh'); if (el) el.textContent = t ? 'Updated ' + t : ''; };\nwindow.NG = {")
open('app_prod.js', 'w', encoding='utf-8').write(s)
assert '</script' not in s
# ---- page
t = open('template_merged.html', encoding='utf-8').read()
def trep(old, new):
    global t
    assert old in t, "TEMPLATE NOT FOUND: " + old[:100]; t = t.replace(old, new, 1)
i0 = t.index('<div style="display:flex;gap:.5rem;flex-wrap:wrap"><span class="ribbon">Review version'); i1 = t.index('</div>', i0) + 6
t = t[:i0] + '<div class="userbox" id="userbox"><span id="fresh"></span></div>' + t[i1:]
t = t.replace('<title>New Globe and Neutral Consolidation: performance and profit dashboard (review version)</title>', '<title>{{PRODUCT}} · New Globe and Neutral Consolidation</title>').replace('<h1>New Globe and Neutral Consolidation: performance dashboard</h1>', '<h1>{{PRODUCT}}</h1>').replace('<p class="sub">Data as of', '<p class="sub">New Globe and Neutral Consolidation · data as of')
trep('<div id="app">', '<a class="skip" href="#page">Skip to the content</a>\n<div id="app">\n  <div id="boot" role="status">Loading the dashboard…</div>')
trep('<section class="card" id="filters" aria-label="Filters">', '<button type="button" class="btn fToggle" id="fToggle" aria-expanded="false" aria-controls="filters">Filters <span id="fCount"></span></button>\n  <section class="card collapsed" id="filters" aria-label="Filters">')
css = open('style.css', encoding='utf-8').read() + """
.userbox{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap;font-size:.8rem;color:var(--muted)}.userbox a,.userbox button{font:inherit;font-size:.8rem;color:var(--fg);background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:.3rem .65rem;cursor:pointer;text-decoration:none}
.skip{position:absolute;left:-999px;top:0}.skip:focus{left:1rem;top:1rem;z-index:99;background:var(--panel);padding:.5rem .8rem;border:1px solid var(--line);border-radius:var(--r)}
#boot{padding:3rem 1rem;text-align:center;color:var(--muted)}#boot button{font:inherit;margin-left:.5rem}
.fToggle{display:none}:focus-visible{outline:3px solid color-mix(in srgb,var(--accent) 45%,transparent);outline-offset:1px}
@media (max-width:760px){
  h1{font-size:1.25rem}header.top{margin-bottom:.4rem}
  #grpRow{flex-wrap:nowrap;overflow-x:auto;padding-bottom:.2rem}#grpSeg{flex-wrap:nowrap}#grpSeg .btn{white-space:nowrap}#grpRow .lbl2,#viewSel,#viewSave,#viewDel,#printBtn{display:none}
  .tabs{flex-wrap:nowrap;overflow-x:auto;scroll-snap-type:x proximity;padding-bottom:.3rem;-webkit-overflow-scrolling:touch}.tabs button{flex:0 0 auto;scroll-snap-align:start;white-space:nowrap}
  .btn,.fbtn,.tabs button{min-height:42px}select,input,.q,.f input[type=date]{font-size:16px!important;min-height:42px}
  .fToggle{display:inline-flex;align-items:center;gap:.4rem;margin:.3rem 0 .6rem}#filters.collapsed>*:not(#chips):not(#status){display:none}
  .kpis{grid-template-columns:repeat(2,minmax(0,1fr))!important}.grid{grid-template-columns:1fr!important}.card{padding:.8rem}
  #menu{left:0!important;right:0!important;bottom:0!important;top:auto!important;width:100%!important;max-width:100%!important;max-height:72vh;border-radius:14px 14px 0 0}
  .tbl td:first-child,.tbl th:first-child{position:sticky;left:0;background:var(--panel);z-index:1}
}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
"""
fflate = open('vendor/fflate.js', encoding='utf-8').read(); d3 = open('vendor/d3.min.js', encoding='utf-8').read()
boot = r"""
(function () {
  const boot = document.getElementById('boot'), fail = (m) => { boot.textContent = m + ' '; const b = document.createElement('button'); b.textContent = 'Try again'; b.onclick = () => location.reload(); boot.append(b); };
  (async () => {
    try {
      const mr = await fetch('/api/me', {credentials: 'same-origin'}); if (mr.status === 401) { location.href = '/login'; return; }
      window.__ME = await mr.json();
      const [dr, pr] = await Promise.all([fetch('/api/dataset', {credentials: 'same-origin'}), fetch('/api/prefs', {credentials: 'same-origin'})]);
      if (dr.status === 401) { location.href = '/login'; return; } if (!dr.ok) throw new Error('data');
      window.__D = await dr.json(); const prefs = pr.ok ? await pr.json() : {};
      try { [['visuals', 'ngVisuals'], ['views', 'ngViews'], ['defs', 'ngDefs']].forEach(([n, k]) => { if (prefs[n] !== undefined) localStorage.setItem(k, JSON.stringify(prefs[n])); else localStorage.removeItem(k); }); } catch (e) { /* storage blocked */ }
      const s = document.createElement('script'); s.textContent = document.getElementById('appsrc').textContent; document.body.appendChild(s);
      boot.remove(); if (window.NG_BOOT) window.NG_BOOT();
      const u = window.__ME, box = document.getElementById('userbox'); box.prepend(Object.assign(document.createElement('span'), {textContent: u.name + ' · ' + u.role}));
      if (u.role === 'admin') box.append(Object.assign(document.createElement('a'), {href: '/admin', textContent: 'Administration'}));
      const pw = document.createElement('button'); pw.textContent = 'Password'; pw.onclick = async () => { const cur = prompt('Current password (leave empty if you sign in by email link)') || ''; const nw = prompt('New password (10+ characters, letters and a number)'); if (!nw) return;
        const r = await fetch('/api/me/password', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': u.csrf}, body: JSON.stringify({current: cur, new: nw})}); alert(r.ok ? 'Password saved.' : (await r.json()).detail); }; box.append(pw);
      const out = document.createElement('button'); out.textContent = 'Sign out'; out.onclick = async () => { await fetch('/auth/logout', {method: 'POST', credentials: 'same-origin'}); location.href = '/login'; }; box.append(out);
      const f = document.getElementById('filters'), tg = document.getElementById('fToggle'), cnt = document.getElementById('fCount');
      tg.onclick = () => { const c = f.classList.toggle('collapsed'); tg.setAttribute('aria-expanded', String(!c)); };
      new MutationObserver(() => { const n = document.querySelectorAll('#chips .chip').length; cnt.textContent = n ? '(' + n + ' on)' : ''; }).observe(document.getElementById('chips'), {childList: true, subtree: true});
      if (!window.matchMedia('(max-width:760px)').matches) f.classList.remove('collapsed');
    } catch (e) { fail('The dashboard could not load its data.'); }
  })();
})();
"""
t = t.replace('__CSS__', css)
i0 = t.index('<script type="text/plain" id="data">__DATA__</script>'); i1 = t.index('<script>__APP__</script>') + len('<script>__APP__</script>')
page = t[:i0] + '<script>' + fflate + '</script>\n<script>' + d3 + '</script>\n<script id="appsrc" type="text/plain">' + s + '</script>\n<script>' + boot + '</script>' + t[i1:]
import re as _re
left = _re.findall(r'__[A-Z0-9]{3,}__', page); print("placeholders left:", left)
open('../app/web/dashboard.html', 'w', encoding='utf-8').write(page); print("production page", len(page.encode()) // 1024, "KB")
