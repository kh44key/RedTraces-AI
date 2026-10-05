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
    /* RedTraces intelligence-workbench treatment: information density without decorative noise. */
    body,body.source-instagram,body.source-facebook,body.source-twitter,body.source-x,body.source-telegram{background:radial-gradient(ellipse at 63% -10%,rgba(26,126,112,.20),transparent 42%),#07110f;color:#eaf5f1}
    .shell{width:min(1480px,100%);grid-template-columns:225px minmax(550px,1fr) 300px;background:rgba(6,17,15,.72);box-shadow:0 0 0 1px rgba(133,200,182,.08)}
    .left{background:linear-gradient(180deg,#091815,#07110f);padding:22px 16px}.brand{padding:0 8px;margin-bottom:30px}.brand svg{filter:drop-shadow(0 0 10px rgba(39,215,189,.35))}.brand b{font-size:15px;letter-spacing:.8px}.brand b i{color:#27d7bd}.brand small{color:#69847b}
    .nav-btn{border-radius:7px;padding:11px 12px;color:#9db5ad}.nav-btn.active,.nav-btn:hover{background:rgba(39,215,189,.09);border-color:rgba(39,215,189,.14);color:#eff9f5;box-shadow:inset 2px 0 #27d7bd}.nav-btn.active .ic{color:#27d7bd}.add-btn{border:1px solid rgba(39,215,189,.42);border-radius:7px;background:rgba(39,215,189,.12);color:#77ead7;letter-spacing:.2px}.sys{padding:10px;border:1px solid rgba(132,187,171,.12);border-radius:8px;background:#0a1714}.pulse{background:#48d79b;box-shadow:0 0 0 4px rgba(72,215,155,.1)}
    main{border-color:rgba(132,187,171,.13)}.topbar{height:64px;background:rgba(7,17,15,.90);border-color:rgba(132,187,171,.13);padding:0 20px}.product-label{color:#5fbaaa}.topbar h1{font-size:18px;color:#f0f8f5}.icon-btn{border-radius:7px;background:#0c1c18;border-color:rgba(132,187,171,.18)}.source-profile{padding:15px 20px;background:linear-gradient(90deg,rgba(39,215,189,.08),transparent);border-color:rgba(132,187,171,.12)}.source-mark{width:40px;height:40px;border-radius:8px;background:#0f2924;color:#67e6d0;box-shadow:none;border:1px solid rgba(39,215,189,.28)}.source-profile b{font-size:13px}.source-profile span{color:#87a39a}.source-profile .profile-state{color:#67e6b7}.profile-state i{background:#67e6b7}
    .analysis-plane{margin:18px 20px 14px;min-height:184px;border:1px solid rgba(39,215,189,.18);border-radius:10px;overflow:hidden;position:relative;background:radial-gradient(circle at 48% 50%,rgba(39,215,189,.11),transparent 24%),linear-gradient(105deg,#0a1b18,#0a1513)}.analysis-plane::before{content:'';position:absolute;inset:0;background:linear-gradient(rgba(67,170,149,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(67,170,149,.05) 1px,transparent 1px);background-size:30px 30px;mask-image:linear-gradient(90deg,transparent,black 15%,black 85%,transparent)}.plane-label{position:absolute;top:14px;left:16px;font-size:10px;color:#91b4a8;letter-spacing:1.2px;font-weight:800}.plane-label b{display:block;color:#dcefe9;font-size:13px;letter-spacing:0;margin-top:3px}.network{position:absolute;inset:28px 10px 8px;width:calc(100% - 20px);height:calc(100% - 36px)}.network path{fill:none;stroke:#439e8f;stroke-width:1;opacity:.65}.network .hot{stroke:#d7b261;stroke-width:1.4}.network circle{fill:#64d8c0;stroke:#0b2520;stroke-width:4}.network circle.hot{fill:#e3b75c}.plane-stats{position:absolute;right:14px;top:14px;display:flex;gap:7px}.plane-stat{padding:6px 8px;border:1px solid rgba(125,185,171,.16);background:rgba(6,17,15,.68);border-radius:5px;font-size:10px;color:#88a89e}.plane-stat b{color:#e8f7f2;margin-right:3px}
    .card{margin:0 20px;border:1px solid rgba(132,187,171,.13);border-radius:9px;background:rgba(12,29,25,.72);padding:15px 16px;margin-bottom:9px}.card:hover{background:#10251f;border-color:rgba(39,215,189,.28)}.avatar{width:38px;height:38px;flex-basis:38px;border-radius:7px!important;border:1px solid rgba(120,207,187,.26)!important;box-shadow:none!important}.name{color:#e9f6f2}.handle,.time,.dot{color:#819c93}.content{color:#c3d6d0;line-height:1.55}.tag{border-radius:4px;background:rgba(39,215,189,.08);border-color:rgba(39,215,189,.17);color:#75dfcc}.tag.dom{background:rgba(232,100,109,.09);border-color:rgba(232,100,109,.2);color:#eea1a8}.sev{border-radius:4px}.section-head,.search-wrap{border-color:rgba(132,187,171,.13);padding-left:20px;padding-right:20px}.search-box{border-radius:6px;background:#0b1b17;border-color:rgba(132,187,171,.16)}.primary{border-radius:6px;background:#29c9ae;color:#04100d}.right{padding:16px;background:#081511}.side-card{border-radius:9px;background:#0b1c18;border-color:rgba(132,187,171,.14);box-shadow:none}.side-card h2{color:#dceee8;border-color:rgba(132,187,171,.13);font-size:12px;letter-spacing:.6px;text-transform:uppercase}.stat{border-color:rgba(132,187,171,.11)}.stat b{color:#e8f7f2}.stat span{color:#819c93}.acct,.chan{border-color:rgba(132,187,171,.1)}
    .source-instagram .card,.source-facebook .card{margin:0 20px 9px;background:rgba(12,29,25,.72);border-radius:9px}.source-instagram .source-profile,.source-facebook .source-profile{margin:0;border:0;border-bottom:1px solid rgba(132,187,171,.12);border-radius:0;background:linear-gradient(90deg,rgba(39,215,189,.08),transparent)}.source-instagram .source-mark,.source-facebook .source-mark{border-radius:8px;background:#0f2924;font-family:inherit}.source-instagram .topbar,.source-facebook .topbar{background:rgba(7,17,15,.90)}
    /* Platform-inspired collection layouts. RedTraces controls and data labels remain explicit. */
    .story-strip{display:none}
    body.source-instagram{--accent:#d62976;background:#fafafa;color:#262626}.source-instagram .shell{background:#fafafa;box-shadow:none;grid-template-columns:230px minmax(480px,1fr) 300px}.source-instagram .left{background:#fff;border-color:#dbdbdb}.source-instagram .brand b{color:#262626;font-family:Georgia,serif;font-size:18px;letter-spacing:-.4px}.source-instagram .brand b i{color:#d62976}.source-instagram .brand small{color:#777}.source-instagram .nav-btn{color:#333;border-radius:8px}.source-instagram .nav-btn.active,.source-instagram .nav-btn:hover{background:#f2f2f2;color:#111;box-shadow:none;border-color:transparent}.source-instagram .add-btn{background:linear-gradient(135deg,#f58529,#dd2a7b 55%,#8134af);color:#fff;border:0;border-radius:9px}.source-instagram .sys{background:#fff;border-color:#e7e7e7;color:#333}.source-instagram .sys small{color:#777!important}.source-instagram .topbar{background:#fff;border-color:#dbdbdb}.source-instagram .topbar h1{color:#262626}.source-instagram .product-label{color:#d62976}.source-instagram .icon-btn{background:#fff;border-color:#ddd;color:#333}.source-instagram .source-profile{background:#fff;border-color:#dbdbdb;padding:14px 20px}.source-instagram .source-mark{background:linear-gradient(135deg,#f9ce34,#ee2a7b,#6228d7);border:0;color:#fff}.source-instagram .source-profile b{color:#262626}.source-instagram .source-profile span{color:#777}.source-instagram .source-profile .profile-state{color:#28a745}.source-instagram .analysis-plane{display:none}.source-instagram .story-strip{display:flex;gap:15px;margin:20px;border:1px solid #dbdbdb;border-radius:10px;background:#fff;padding:14px 12px;overflow:auto}.source-instagram .story{flex:none;text-align:center;font-size:10px;color:#333}.source-instagram .story i{display:grid;place-items:center;width:54px;height:54px;margin:auto auto 5px;border-radius:50%;background:#fff;border:3px solid transparent;background-image:linear-gradient(#fff,#fff),linear-gradient(135deg,#f9ce34,#ee2a7b,#6228d7);background-origin:border-box;background-clip:padding-box,border-box;color:#777;font-style:normal;font-size:18px}.source-instagram .card{background:#fff!important;border:1px solid #dbdbdb!important;border-radius:9px!important;box-shadow:none!important}.source-instagram .card:hover{background:#fff!important}.source-instagram .avatar{border-radius:50%!important;border-color:#d62976!important}.source-instagram .name,.source-instagram .content{color:#262626}.source-instagram .handle,.source-instagram .time,.source-instagram .dot{color:#8e8e8e}.source-instagram .tag{background:#f5f5f5;border-color:#e2e2e2;color:#d62976}.source-instagram .right{background:#fafafa}.source-instagram .side-card{background:#fff;border-color:#dbdbdb}.source-instagram .side-card h2,.source-instagram .stat b{color:#262626}.source-instagram .stat span{color:#777}
    body.source-facebook{--accent:#1877f2;background:#f0f2f5;color:#1c1e21}.source-facebook .shell{background:#f0f2f5;box-shadow:none;grid-template-columns:245px minmax(500px,1fr) 280px}.source-facebook .left{background:#fff;border-color:#dfe3e8}.source-facebook .brand b{color:#1877f2;font-size:16px}.source-facebook .brand b i{color:#1877f2}.source-facebook .nav-btn{color:#30343a;border-radius:7px}.source-facebook .nav-btn.active,.source-facebook .nav-btn:hover{background:#e7f3ff;color:#1877f2;box-shadow:none;border-color:transparent}.source-facebook .add-btn{background:#1877f2;color:#fff;border:0;border-radius:7px}.source-facebook .sys{background:#fff;border-color:#dfe3e8;color:#30343a}.source-facebook .topbar{background:#fff;border-color:#dfe3e8}.source-facebook .topbar h1{color:#1c1e21}.source-facebook .product-label{color:#1877f2}.source-facebook .icon-btn{background:#f0f2f5;border-color:#dfe3e8;color:#333}.source-facebook .source-profile{background:#fff;border-color:#dfe3e8}.source-facebook .source-mark{background:#1877f2;border:0;color:#fff}.source-facebook .source-profile b{color:#1c1e21}.source-facebook .source-profile span{color:#65676b}.source-facebook .analysis-plane{display:none}.source-facebook .story-strip{display:flex;gap:9px;margin:16px 20px;padding:10px;border-radius:8px;background:#fff;border:1px solid #dfe3e8;overflow:auto}.source-facebook .story{min-width:86px;height:88px;padding:8px;border-radius:7px;background:linear-gradient(145deg,#e7f3ff,#fff);font-size:11px;color:#1877f2}.source-facebook .story i{display:grid;place-items:center;width:32px;height:32px;margin-bottom:10px;border-radius:50%;background:#1877f2;color:#fff;font-style:normal}.source-facebook .card{background:#fff!important;border:1px solid #dfe3e8!important;border-radius:8px!important;box-shadow:0 1px 2px rgba(0,0,0,.06)!important}.source-facebook .card:hover{background:#fff!important}.source-facebook .name,.source-facebook .content{color:#1c1e21}.source-facebook .handle,.source-facebook .time,.source-facebook .dot{color:#65676b}.source-facebook .tag{background:#e7f3ff;border-color:#c9e2ff;color:#1877f2}.source-facebook .right{background:#f0f2f5}.source-facebook .side-card{background:#fff;border-color:#dfe3e8}.source-facebook .side-card h2,.source-facebook .stat b{color:#1c1e21}.source-facebook .stat span{color:#65676b}
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
    <section class="story-strip" aria-label="Source monitoring shortcuts"><div class="story"><i>+</i>Add source</div><div class="story"><i>⌕</i>Explore</div><div class="story"><i>!</i>High risk</div><div class="story"><i>◎</i>Indicators</div><div class="story"><i>▤</i>Archive</div></section>
    <section class="panel active" id="livePanel">
      <div class="analysis-plane" aria-label="Live source correlation topology">
        <div class="plane-label">LIVE CORRELATION MAP<b>Source → entity → indicator</b></div>
        <div class="plane-stats"><span class="plane-stat"><b id="signalCount">0</b>signals</span><span class="plane-stat"><b id="indicatorCount">0</b>indicators</span></div>
        <svg class="network" viewBox="0 0 760 145" preserveAspectRatio="none" aria-hidden="true">
          <path d="M58 73 C170 73 196 25 330 28 S470 89 688 27"/><path d="M58 73 C164 73 215 118 361 112 S520 49 688 27"/><path d="M58 73 C171 73 230 67 397 72 S540 112 688 27" class="hot"/><path d="M58 73 C183 73 244 31 430 49 S568 94 688 27"/>
          <circle cx="58" cy="73" r="7"/><circle cx="330" cy="28" r="6"/><circle cx="361" cy="112" r="6"/><circle cx="397" cy="72" r="6"/><circle cx="430" cy="49" r="6"/><circle class="hot" cx="688" cy="27" r="8"/>
        </svg>
      </div>
      <div id="liveFeed"><div class="notice"><span class="spinner"></span></div></div>
    </section>
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
  async function loadLive(){try{S.live=await gj('/leaks?limit=50');cLive.textContent=S.live.length;signalCount.textContent=S.live.length;indicatorCount.textContent=S.live.reduce((n,x)=>n+(x.detected_entities||[]).length+(x.detected_domains||[]).length,0);render(liveFeed,S.live)}catch(e){fail(liveFeed)}}
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
