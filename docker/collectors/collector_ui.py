"""Shared RedTraces AI-themed standalone dashboard for the social collectors.

The operator normally works from the unified :3000 dashboard; this page is what
you see if you open a collector's own port directly (e.g. :8103). It talks to the
same REST endpoints every collector exposes, so one template serves them all.
"""


def dashboard_html(platform: str, glyph: str, accent: str = "#ff2f4d") -> str:
    """Return a source-aware RedTraces AI collection console.

    The panels intentionally borrow familiar feed conventions (profile strip,
    cards, source-colour accents) without impersonating a social platform.
    They remain clearly labelled as analyst monitoring tools.
    """
    source = platform.lower().replace(" ", "-")
    target_label = {
        "instagram": "profile or hashtag",
        "facebook": "page or group",
        "telegram": "channel",
        "x": "account",
    }.get(source, "source")
    source_copy = {
        "instagram": "Profile and hashtag intelligence feed",
        "facebook": "Page and group intelligence feed",
        "telegram": "Channel intelligence feed",
        "x": "Account intelligence feed",
    }.get(source, "Source intelligence feed")
    return (
        r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>RedTraces AI — __PLATFORM__ Intelligence</title>
  <style>
    :root{--bg:#06070b;--bg2:#0a0c12;--panel:#0f131d;--panel2:#141a26;--line:rgba(150,168,200,.14);--ink:#eef2f8;--ink2:#9aa6bd;--ink3:#5c6880;--accent:__ACCENT__;--red:#ff2f4d;--good:#37d39b;--amber:#ffb64a}
    *{box-sizing:border-box}html{color-scheme:dark}
    body{margin:0;background:radial-gradient(circle at 78% 6%,#161020 0,transparent 32%),linear-gradient(135deg,#06070b,#0a0c12 55%,#080a10);color:var(--ink);font:15px/1.45 'Inter','Segoe UI',system-ui,Arial,sans-serif;min-height:100vh}
    button,input,select{font:inherit}button{color:inherit;cursor:pointer}
    .shell{width:min(1180px,100%);margin:auto;display:grid;grid-template-columns:250px minmax(0,1fr) 320px;min-height:100vh}
    .left{position:sticky;top:0;height:100vh;padding:20px 18px;border-right:1px solid var(--line)}
    .brand{display:flex;align-items:center;gap:11px;margin-bottom:24px}
    .brand svg{width:32px;height:32px;filter:drop-shadow(0 0 10px rgba(255,47,77,.35))}
    .brand b{font-size:16px;letter-spacing:1px}.brand b i{color:var(--red);font-style:normal}
    .brand small{display:block;font-size:8px;letter-spacing:2px;color:var(--ink3);margin-top:2px}
    nav{display:flex;flex-direction:column;gap:4px}
    .nav-btn{display:flex;align-items:center;gap:14px;border:1px solid transparent;background:transparent;border-radius:8px;padding:12px 14px;font-size:13px;color:var(--ink2);text-align:left}
    .nav-btn .ic{width:20px;text-align:center;color:var(--ink3)}
    .nav-btn.active,.nav-btn:hover{color:#fff;background:color-mix(in srgb,var(--accent),transparent 88%);border-color:color-mix(in srgb,var(--accent),transparent 74%)}
    .nav-btn.active{box-shadow:inset 3px 0 var(--accent)}.nav-btn.active .ic{color:var(--accent)}
    .add-btn{width:100%;margin-top:16px;border:0;background:var(--accent);color:#06070b;font-weight:800;font-size:13px;padding:13px;border-radius:999px}
    .sys{position:absolute;bottom:20px;left:18px;right:18px;display:flex;align-items:center;gap:10px;font-size:11px;color:var(--ink2)}
    .pulse{width:9px;height:9px;border-radius:50%;background:var(--good);box-shadow:0 0 0 4px rgba(55,211,155,.15)}
    main{border-right:1px solid var(--line);min-width:0}
    .topbar{position:sticky;top:0;z-index:5;background:rgba(6,7,11,.8);backdrop-filter:blur(12px);border-bottom:1px solid var(--line);height:56px;display:flex;align-items:center;justify-content:space-between;padding:0 18px}
    .topbar h1{font-size:17px;margin:0;letter-spacing:.5px}
    .product-label{display:block;color:var(--accent);font-size:9px;letter-spacing:1.4px;font-weight:800;margin-bottom:1px}
    .icon-btn{border:1px solid var(--line);background:var(--panel2);width:36px;height:36px;border-radius:6px}
    .source-profile{display:flex;align-items:center;gap:11px;padding:14px 18px;border-bottom:1px solid var(--line);background:linear-gradient(90deg,color-mix(in srgb,var(--accent),transparent 88%),transparent)}
    .source-mark{width:42px;height:42px;border-radius:14px;display:grid;place-items:center;background:linear-gradient(135deg,var(--accent),#7b2cbf);color:#fff;font-size:20px;font-weight:800;box-shadow:0 8px 20px color-mix(in srgb,var(--accent),transparent 75%)}
    .source-profile b{display:block;font-size:13px}.source-profile span{display:block;color:var(--ink3);font-size:11px}.source-profile .profile-state{margin-left:auto;color:var(--good);font-weight:800;font-size:10px;letter-spacing:1px}.profile-state i{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--good);box-shadow:0 0 0 4px rgba(55,211,155,.12);margin-right:5px}
    .panel{display:none;padding:4px 0}.panel.active{display:block}
    .section-head{padding:14px 18px;border-bottom:1px solid var(--line);font-weight:700;font-size:13px;display:flex;justify-content:space-between;align-items:center}
    .count{color:var(--accent)}
    .search-wrap{padding:14px 18px;border-bottom:1px solid var(--line);display:flex;gap:8px}
    .search-box{flex:1;display:flex;background:var(--panel2);border:1px solid var(--line);border-radius:999px;overflow:hidden}
    .search-box:focus-within{border-color:var(--accent)}
    .search-box span{padding:11px 0 11px 15px;color:var(--ink3)}.search-box input{width:100%;border:0;outline:0;background:transparent;color:var(--ink);padding:11px}
    .primary{border:0;background:var(--accent);color:#06070b;font-weight:800;border-radius:999px;padding:0 18px}
    .card{display:flex;gap:12px;padding:14px 18px;border-bottom:1px solid var(--line)}
    .card:hover{background:rgba(255,255,255,.015)}
    .avatar{flex:0 0 42px;width:42px;height:42px;border-radius:50%;display:grid;place-items:center;font-weight:800;color:#fff}
    .body{min-width:0;flex:1}.meta{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
    .name{font-weight:700}.handle,.time,.dot{color:var(--ink3);font-size:13px}
    .sev{margin-left:auto;font-size:10px;font-weight:800;text-transform:uppercase;border-radius:999px;padding:2px 9px}
    .sev.high{background:rgba(255,47,77,.16);color:#ff6274;border:1px solid rgba(255,47,77,.4)}
    .sev.moderate{background:rgba(255,182,74,.16);color:var(--amber);border:1px solid rgba(255,182,74,.4)}
    .sev.low{background:rgba(55,211,155,.16);color:var(--good);border:1px solid rgba(55,211,155,.4)}
    .content{margin:6px 0 9px;white-space:pre-wrap;overflow-wrap:anywhere}
    .tags{display:flex;flex-wrap:wrap;gap:6px}.tag{font-size:12px;border-radius:999px;padding:2px 9px;background:color-mix(in srgb,var(--accent),transparent 84%);color:var(--accent);border:1px solid color-mix(in srgb,var(--accent),transparent 60%)}
    .tag.dom{background:rgba(255,47,77,.12);color:#ff8a97;border-color:rgba(255,47,77,.4)}
    .notice{padding:34px 18px;text-align:center;color:var(--ink3)}
    .empty{padding:48px 24px;text-align:center}.empty h2{margin:0 0 8px}.empty p{color:var(--ink3);max-width:340px;margin:auto}
    .spinner{display:inline-block;width:20px;height:20px;border:3px solid var(--line);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
    .chan{display:flex;justify-content:space-between;align-items:center;padding:13px 18px;border-bottom:1px solid var(--line)}
    .danger{background:rgba(255,47,77,.12);color:#ff8a97;border:1px solid rgba(255,47,77,.4);padding:5px 12px;border-radius:999px}
    .right{padding:16px}.side-card{border:1px solid var(--line);border-radius:14px;margin-bottom:16px;overflow:hidden;background:var(--panel)}
    .side-card h2{font-size:14px;margin:0;padding:13px 15px;border-bottom:1px solid var(--line)}
    .stat-grid{display:grid;grid-template-columns:1fr 1fr}.stat{padding:14px 15px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
    .stat b{font-size:20px;display:block}.stat span{color:var(--ink3);font-size:12px}
    .acct{display:flex;align-items:center;gap:8px;padding:9px 15px;border-bottom:1px solid var(--line);font-size:13px}
    .acct .d{width:8px;height:8px;border-radius:50%;flex:none}
    dialog{width:min(480px,calc(100% - 24px));border:1px solid var(--line);border-radius:14px;background:var(--panel);color:var(--ink);padding:0}
    dialog::backdrop{background:rgba(6,7,11,.7)}.mhead{display:flex;justify-content:space-between;align-items:center;padding:12px 15px;border-bottom:1px solid var(--line)}
    .mbody{padding:18px}.mbody label{font-weight:700;display:block;margin-bottom:7px}
    .mbody input,.mbody select{width:100%;border:1px solid var(--line);border-radius:9px;background:var(--bg2);color:var(--ink);padding:12px;outline:0;margin-bottom:12px}
    .mbody input:focus,.mbody select:focus{border-color:var(--accent)}.mbody p{color:var(--ink3);font-size:12px}
    /* Familiar source cues, deliberately kept inside the RedTraces analyst console. */
    .source-instagram{--accent:#ff5da2;background:radial-gradient(circle at 75% 0,#48194a 0,transparent 30%),linear-gradient(140deg,#110d18,#090b12 60%)}
    .source-instagram .source-mark{border-radius:50%;background:conic-gradient(from 210deg,#ffcb55,#ff5d87,#a65de8,#ffcb55);position:relative}.source-instagram .source-mark::after{content:'';position:absolute;inset:5px;border:2px solid #fff;border-radius:12px}.source-instagram .card{margin:12px 14px;border:1px solid rgba(255,93,162,.2);border-radius:16px;background:linear-gradient(145deg,#17111c,#10131b)}.source-instagram .card:hover{background:#1d1421}.source-instagram .avatar{border:2px solid #ff5da2;box-shadow:0 0 0 2px #7b2cbf}.source-instagram .source-profile{margin:10px 14px;border:1px solid rgba(255,93,162,.2);border-radius:16px}.source-instagram .topbar{background:rgba(16,10,18,.87)}
    .source-facebook{--accent:#4f93e6;background:radial-gradient(circle at 75% 0,#142c53 0,transparent 32%),linear-gradient(140deg,#0a111c,#090d14 60%)}
    .source-facebook .source-mark{border-radius:50%;background:#2374e1;font-family:Arial,sans-serif}.source-facebook .card{margin:10px 14px;border:1px solid rgba(79,147,230,.2);border-radius:12px;background:#111b29;box-shadow:0 6px 18px rgba(0,0,0,.16)}.source-facebook .card:hover{background:#152235}.source-facebook .source-profile{background:#111b29;margin:10px 14px;border:1px solid rgba(79,147,230,.22);border-radius:12px}.source-facebook .topbar{background:rgba(10,17,28,.9)}.source-facebook .avatar{border-radius:12px}
    .source-twitter,.source-x{--accent:#76b7ff;background:radial-gradient(circle at 75% 0,#132942 0,transparent 30%),linear-gradient(140deg,#05090e,#080d13 60%)}.source-twitter .source-mark,.source-x .source-mark{border-radius:50%;background:#111}.source-twitter .card,.source-x .card{padding:16px 18px}.source-telegram{--accent:#37aee2}.source-telegram .source-mark{border-radius:50%;background:#229ed9}
    @media(max-width:960px){.shell{grid-template-columns:1fr}.left,.right{position:relative;height:auto;border-right:0}}
  </style>
</head>
<body class="source-__SOURCE_CLASS__">
<div class="shell">
  <aside class="left">
    <div class="brand">
      <svg viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg"><g transform="translate(256,256)"><path d="M 78,-75 L 104,-60 L 104,60 L 0,120 L -104,60 L -104,-60 L 0,-120 L 26,-105" fill="none" stroke="#ff2f4d" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/><path d="M -44,-6 L -12,26 L 52,-42" fill="none" stroke="#ff2f4d" stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/></g></svg>
      <div><b>RED<i>TRACES</i> AI</b><small>__PLATFORM__ COLLECTION</small></div>
    </div>
    <nav>
      <button class="nav-btn active" data-panel="live"><span class="ic">⌂</span>Live feed</button>
      <button class="nav-btn" data-panel="archive"><span class="ic">▤</span>Archive</button>
      <button class="nav-btn" data-panel="search"><span class="ic">⌕</span>Explore</button>
      <button class="nav-btn" data-panel="targets"><span class="ic">◎</span>Targets</button>
    </nav>
    <button class="add-btn" onclick="targetModal.showModal()">+ Add __TARGET_LABEL__</button>
    <div class="sys"><span class="pulse"></span><div><b>Monitor active</b><br><small style="color:var(--ink3)">Scanning __PLATFORM__ __GLYPH__</small></div></div>
  </aside>
  <main>
    <header class="topbar"><div><small class="product-label">REDTRACES AI / SOURCE MONITOR</small><h1 id="ttl">Live feed</h1></div><button class="icon-btn" onclick="refresh()" aria-label="Refresh feed">↻</button></header>
    <section class="source-profile"><div class="source-mark">__GLYPH__</div><div><b>__PLATFORM__ monitored sources</b><span>__SOURCE_COPY__ · CTI-enriched results</span></div><span class="profile-state"><i></i>LIVE</span></section>
    <section class="panel active" id="livePanel"><div id="liveFeed"><div class="notice"><span class="spinner"></span></div></div></section>
    <section class="panel" id="archivePanel"><div class="section-head"><span>Complete alert archive</span><span class="count" id="arcCount">0</span></div><div id="arcFeed"></div></section>
    <section class="panel" id="searchPanel">
      <div class="search-wrap"><div class="search-box"><span>⌕</span><input id="kw" placeholder="Search posts, accounts, domains, severity…"></div><button class="primary" onclick="runSearch()">Search</button></div>
      <div id="searchFeed"><div class="empty"><h2>Search the archive</h2><p>Find monitored posts by keyword, account, entity, domain or priority.</p></div></div>
    </section>
    <section class="panel" id="targetsPanel">
      <div class="section-head"><span>Monitored __TARGET_LABEL__ sources</span><button class="primary" onclick="targetModal.showModal()">+ Add</button></div>
      <div id="chanList"><div class="notice"><span class="spinner"></span></div></div>
      <div class="empty" style="border-top:1px solid var(--line)"><h2>Scan a dump file</h2><p>Upload a line-by-line text/raw file to detect exposures locally.</p>
        <input type="file" id="fileIn" style="display:none" onchange="uploadFile(this)"><button class="primary" style="margin-top:16px" onclick="fileIn.click()">Upload file</button></div>
    </section>
  </main>
  <aside class="right">
    <section class="side-card"><h2>Monitor overview</h2><div class="stat-grid">
      <div class="stat"><b id="cLive">—</b><span>Recent alerts</span></div><div class="stat"><b id="cToday">—</b><span>Today</span></div>
      <div class="stat"><b id="cWeek">—</b><span>This week</span></div><div class="stat"><b><span class="pulse" style="display:inline-block"></span></b><span>Scraper</span></div>
    </div></section>
    <section class="side-card"><h2>Crawler status</h2><div id="acctList"><p style="padding:12px 15px;color:var(--ink3);font-size:13px">Loading…</p></div></section>
  </aside>
</div>
<dialog id="targetModal"><div class="mhead"><h2 style="font-size:17px;margin:0">Add monitored target</h2><button class="icon-btn" onclick="targetModal.close()">×</button></div>
  <div class="mbody">
    <label>Target type</label><select id="tType"><option value="channel">__TARGET_LABEL__</option><option value="keyword">Entity keyword</option></select>
    <label>Handle or term</label><input id="tVal" placeholder="e.g. username_or_term">
    <p>Approved __TARGET_LABEL__ sources are polled by the collector; keywords widen the entity watchlist.</p>
    <div style="text-align:right;margin-top:10px"><button class="primary" onclick="submitTarget()">Start monitoring</button></div>
  </div></dialog>
<script>
  const S={live:[],archive:[],chans:[],dates:{today:[],this_week:[],all_time:[]},panel:'live'};
  const titles={live:'Live feed',archive:'Archive',search:'Explore',targets:'Targets'};
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function fdate(v){if(!v)return '';const d=new Date(v);if(isNaN(d))return esc(v);const s=Math.floor((Date.now()-d)/1000);if(s<60)return 'now';if(s<3600)return Math.floor(s/60)+'m';if(s<86400)return Math.floor(s/3600)+'h';return d.toLocaleDateString()}
  function acolor(n){let h=0;for(const c of String(n))h=(h*31+c.charCodeAt(0))%360;return `hsl(${h} 60% 45%)`}
  function card(l,showId){const u=l.author_username||'unknown',e=l.detected_entities||[],d=l.detected_domains||[],sev=(l.severity||'High');
    return `<article class="card"><div class="avatar" style="background:${acolor(u)}">${esc(u.slice(0,2).toUpperCase())}</div><div class="body"><div class="meta"><span class="name">${esc(u)}</span><span class="handle">@${esc(u)}</span><span class="dot">·</span><span class="time">${fdate(l.tweet_date||l.processed_at)}</span>${showId?`<span class="handle">#${esc(l.id)}</span>`:''}<span class="sev ${esc(sev.toLowerCase())}">${esc(sev)}</span></div><div class="content">${esc(l.text||'')}</div><div class="tags">${e.map(x=>`<span class="tag">◎ ${esc(x)}</span>`).join('')}${d.map(x=>`<span class="tag dom">↗ ${esc(x)}</span>`).join('')}</div></div></article>`}
  function render(el,rows,showId,empty){el.innerHTML=rows.length?rows.map(x=>card(x,showId)).join(''):`<div class="empty"><h2>Nothing here yet</h2><p>${empty||'No monitored posts found.'}</p></div>`}
  async function gj(u){const r=await fetch(u);if(!r.ok)throw 0;return r.json()}
  function fail(el){el.innerHTML='<div class="empty"><h2>Unable to load</h2><p>Check the database connection, then refresh.</p></div>'}
  async function loadLive(){try{S.live=await gj('/leaks?limit=50');cLive.textContent=S.live.length;render(liveFeed,S.live)}catch(e){fail(liveFeed)}}
  async function loadArchive(){arcFeed.innerHTML='<div class="notice"><span class="spinner"></span></div>';try{S.archive=await gj('/leaks?limit=5000');arcCount.textContent=S.archive.length+' records';render(arcFeed,S.archive,true)}catch(e){fail(arcFeed)}}
  async function loadChans(){chanList.innerHTML='<div class="notice"><span class="spinner"></span></div>';try{S.chans=await gj('/channels');chanList.innerHTML=S.chans.length?S.chans.map(c=>`<div class="chan"><b>@${esc(c.username)}</b>${c.source_type==='system'?'<span style="color:var(--ink3);font-size:12px">always on</span>':`<button class="danger" onclick="rmChan('${esc(c.username)}')">Remove</button>`}</div>`).join(''):'<div class="notice">No targets configured.</div>'}catch(e){fail(chanList)}}
  async function rmChan(u){if(confirm('Remove @'+u+'?')){await fetch('/remove-channel?username='+encodeURIComponent(u),{method:'DELETE'});loadChans()}}
  async function runSearch(){const q=kw.value.trim();searchFeed.innerHTML='<div class="notice"><span class="spinner"></span></div>';try{render(searchFeed,await gj('/search-leaks?keyword='+encodeURIComponent(q)))}catch(e){fail(searchFeed)}}
  async function loadDates(){try{S.dates=await gj('/leaks-by-date');cToday.textContent=S.dates.today.length;cWeek.textContent=S.dates.this_week.length}catch(e){}}
  async function loadAccts(){const C={online:'#37d39b',cooling:'#ffb64a',error:'#ff2f4d',inactive:'#7d8aa3',offline:'#7d8aa3'};
    try{const a=await gj('/accounts');acctList.innerHTML=a.length?a.map(x=>`<div class="acct"><span class="d" style="background:${C[x.status]||'#7d8aa3'}"></span><b style="flex:1">@${esc(x.username||x.session_name||'session')}</b><span style="font-size:11px;color:var(--ink3);text-transform:uppercase">${esc(x.status||'')}</span></div>${x.note?`<div style="font-size:11px;color:var(--ink3);padding:0 15px 8px 30px">${esc(x.note)}</div>`:''}`).join(''):'<p style="padding:12px 15px;color:var(--ink3);font-size:13px">No crawler session registered.</p>'}catch(e){acctList.innerHTML='<p style="padding:12px 15px;color:var(--ink3);font-size:13px">Unable to load status.</p>'}}
  function switchPanel(n){S.panel=n;document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));document.getElementById(n+'Panel').classList.add('active');document.querySelectorAll('.nav-btn').forEach(x=>x.classList.toggle('active',x.dataset.panel===n));ttl.textContent=titles[n];if(n==='archive')loadArchive();if(n==='targets')loadChans()}
  function refresh(){({live:loadLive,archive:loadArchive,search:runSearch,targets:loadChans})[S.panel]()}
  async function submitTarget(){const t=tType.value,v=tVal.value.trim();if(!v)return;await fetch(t==='channel'?'/add-channel':'/add-keyword',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(t==='channel'?{username:v}:{term:v})});targetModal.close();tVal.value='';if(S.panel==='targets')loadChans()}
  async function uploadFile(i){if(!i.files||!i.files[0])return;const fd=new FormData();fd.append('file',i.files[0]);try{const r=await fetch('/upload-file',{method:'POST',body:fd});const j=await r.json();alert('Processed! '+j.leaks_detected+' exposures detected.');refresh()}catch(e){alert('Error processing file.')}}
  document.querySelectorAll('.nav-btn').forEach(b=>b.addEventListener('click',()=>switchPanel(b.dataset.panel)));
  kw.addEventListener('keydown',e=>{if(e.key==='Enter')runSearch()});
  loadLive();loadDates();loadAccts();setInterval(loadLive,15000);setInterval(loadAccts,30000);setInterval(loadDates,60000);
</script>
</body>
</html>
        """
        .replace("__PLATFORM__", platform)
        .replace("__GLYPH__", glyph)
        .replace("__ACCENT__", accent)
        .replace("__SOURCE_CLASS__", source)
        .replace("__TARGET_LABEL__", target_label)
        .replace("__SOURCE_COPY__", source_copy)
    )
