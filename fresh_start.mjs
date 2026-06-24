import WebSocket from 'ws';

const BASE = 'http://localhost:9222';
const TARGET_URL = 'https://superlive.chat/fr/discover';
const P = `document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia?._s?.get('discover')`;

async function main() {
  // 1. Create fresh tab
  const ver = await (await fetch(`${BASE}/json/version`)).json();
  const bws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((r, rej) => { bws.onopen = r; bws.onerror = rej; });
  let id = 0, pending = {};
  bws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.id && pending[d.id]) { pending[d.id](d); }
  };
  const send = (m, p) => new Promise(r => { const i = ++id; pending[i] = r; bws.send(JSON.stringify({id: i, method: m, params: p})); });
  const result = await send('Target.createTarget', { url: 'about:blank', type: 'page' });
  const tid = result.result?.targetId;
  bws.close();
  await new Promise(r => setTimeout(r, 2000));

  // 2. Find the tab
  const tabs = await (await fetch(`${BASE}/json`)).json();
  const tab = tabs.find(t => t.id === tid);
  if (!tab) throw new Error('Tab not found');
  console.log('Tab created:', tid);

  // 3. Connect and navigate
  const ws = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise((r, rej) => { ws.onopen = r; ws.onerror = rej; });
  id = 0; pending = {};
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.id && pending[d.id]) { pending[d.id](d); }
  };
  const s = (m, p) => new Promise((r, rej) => {
    const i = ++id;
    const t = setTimeout(() => { delete pending[i]; rej(new Error(`Timeout ${m}`)); }, 30000);
    pending[i] = (d) => { clearTimeout(t); r(d); };
    ws.send(JSON.stringify({id: i, method: m, params: p}));
  });

  // Navigate
  await s('Page.enable');
  await s('Page.navigate', { url: TARGET_URL });
  console.log('Navigated');

  // Wait for both __nuxt AND items
  let nuxtOk = false;
  for (let i = 0; i < 180; i++) {
    const r = await s('Runtime.evaluate', {
      expression: `(function() {
        try {
          const n = document.getElementById('__nuxt');
          if (!n) return 'no-nuxt';
          const p = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
          const d = p?._s?.get('discover');
          const items = d?.items;
          return JSON.stringify({ hasNuxt: true, hasPinia: !!p, hasDiscover: !!d, itemCount: items ? items.length : -1 });
        } catch(e) { return 'error: ' + e.message; }
      })()`,
      returnByValue: true,
      timeout: 5000
    });
    const val = r.result?.result?.value;
    if (val && val !== 'no-nuxt') {
      try { const obj = JSON.parse(val); if (obj.itemCount >= 0) { nuxtOk = true; console.log('Store ready:', val); break; } } catch(e) {}
    }
    if (i % 20 === 0) console.log('Waiting...', val);
    await new Promise(r => setTimeout(r, 1000));
  }

  if (!nuxtOk) {
    console.log('Store never loaded');
    // Force loading
    await s('Runtime.evaluate', {
      expression: `(function() {
        const p = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
        if (p?._s?.get('discover')) {
          p._s.get('discover').$patch({loading: false});
        }
      })()`,
      returnByValue: true
    }).catch(() => {});
    await new Promise(r => setTimeout(r, 3000));
  }

  // Now inject the HOOK_SOURCE manually
  const injectResult = await s('Runtime.evaluate', {
    expression: `
(function() {
  if (window.__karlinReady) return 'already';
  window.__karlinReady = true;

  // --- Neutralize preview counter ---
  var _g = Storage.prototype.getItem;
  Storage.prototype.getItem = function(k) {
    if (k === 'shown-previews-v2') return '{}';
    return _g.call(this, k);
  };
  var _s = Storage.prototype.setItem;
  Storage.prototype.setItem = function(k, v) {
    if (k === 'shown-previews-v2') return;
    return _s.call(this, k, v);
  };
  try { localStorage.removeItem('shown-previews-v2'); } catch(e) {}

  // --- Patch privateStreamPreviewSettings limit ---
  (function() {
    var pinia = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
    var st = pinia?._s?.get('settings');
    if (st && st.$state && st.$state.settings && st.$state.settings.implementation && st.$state.settings.implementation.private_stream && st.$state.settings.implementation.private_stream.view_preview) {
      st.$state.settings.implementation.private_stream.view_preview.limit = Infinity;
      st.$state.settings.implementation.private_stream.view_preview.duration_in_seconds = Infinity;
    }
  })();

  // --- Intercept fetch API ---
  var _fetch = window.fetch.bind(window);
  window.fetch = function(u, o) {
    var url = typeof u === 'string' ? u : (u?.url || '');
    if (!url.includes('api.spl-web.link/api/web/livestream/')) return _fetch(u, o);
    var body = {};
    try { body = JSON.parse(o?.body || '{}'); } catch(e) {}
    var lsId = body.livestream_id || '';
    if (url.includes('/retrieve')) {
      return _fetch(u, o).then(function(r) {
        return r.clone().json().then(function(data) {
          if (data.disallowed_reason) delete data.disallowed_reason;
          if (!data.livestream_settings) data.livestream_settings = {};
          if (!data.livestream_settings.sensitive_content_settings) data.livestream_settings.sensitive_content_settings = {};
          data.livestream_settings.sensitive_content_settings.is_allowed = true;
          return new Response(JSON.stringify(data), {status: r.status, headers: {'Content-Type':'application/json'}});
        }).catch(function() { return r; });
      });
    }
    if (url.includes('/preview_premium_stream')) {
      return Promise.resolve(new Response(JSON.stringify({code: 0, data: {is_allowed: true, blurAccessSeconds: 999999, livestream_id: lsId, thumbnail_url: '', status: 'active'}}), {status: 200, headers: {'Content-Type':'application/json'}}));
    }
    if (url.includes('/enter')) {
      return Promise.resolve(new Response(JSON.stringify({code: 0, data: {agora_app_id: 'd8e6b8f6a7b14a6e8a9c0d1e2f3a4b5c', agora_channel_name: 'live_' + lsId, agora_channel_token: '007___' + lsId, agora_rtm_token: '008___' + lsId, agora_uid: 123456, is_live: true}}), {status: 200, headers: {'Content-Type':'application/json'}}));
    }
    return _fetch(u, o);
  };

  // --- Overlay system ---
  var overlayMap = {};

  function createOverlay(a, imgUrl, idx) {
    if (a.__ko) return;
    a.__ko = true;
    var r = a.getBoundingClientRect();
    var ov = document.createElement('div');
    ov.className = '__ko';
    ov.style.cssText = 'position:fixed;z-index:99999;pointer-events:none;opacity:0;transition:opacity .15s;border-radius:12px;overflow:hidden;';
    ov.style.left = r.x+'px'; ov.style.top = r.y+'px';
    ov.style.width = r.width+'px'; ov.style.height = r.height+'px';
    var ca = document.createElement('canvas');
    ca.width = ~~r.width; ca.height = ~~r.height;
    ca.style.cssText = 'width:'+r.width+'px;height:'+r.height+'px;display:block;border-radius:12px;';
    ov.appendChild(ca);
    document.body.appendChild(ov);

    var ctx = ca.getContext('2d');
    var w = ca.width, h = ca.height, anim = null;
    var pImg = null;
    if (imgUrl) {
      (function(u) {
        var img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = function() { pImg = img; };
        img.src = u;
      })(imgUrl);
    }
    function draw() {
      if (!ctx) return;
      var t = Date.now()/1000;
      var g = ctx.createLinearGradient(0,0,w,h);
      g.addColorStop(0,'#1a1a2e'); g.addColorStop(1,'#0f3460');
      ctx.fillStyle = g; ctx.fillRect(0,0,w,h);
      if (pImg) {
        var s = Math.max(w/pImg.width, h/pImg.height);
        ctx.drawImage(pImg, (w-pImg.width*s)/2, (h-pImg.height*s)/2, pImg.width*s, pImg.height*s);
        ctx.fillStyle = 'rgba(0,0,0,0.3)'; ctx.fillRect(0,0,w,h);
      }
      var sx = (t*200)%(w*2)-w;
      ctx.fillStyle = 'rgba(255,255,255,0.04)'; ctx.fillRect(sx-40,0,80,h);
      ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(0,h-55,w,55);
      ctx.fillStyle = 'white'; ctx.font = 'bold '+~~(h*0.035)+'px Arial'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      ctx.fillText('Live Stream', 14, h-28);
      var viewers = ~~(10+50*(0.5+0.5*Math.sin(t*0.3+(idx||0))));
      ctx.textAlign = 'right'; ctx.fillStyle = '#ccc'; ctx.font = ~~(h*0.028)+'px Arial';
      ctx.fillText(viewers+' watching', w-14, h-28);
      ctx.fillStyle = 'rgba(0,0,0,0.5)'; ctx.beginPath(); ctx.roundRect(w-110,10,96,26,13); ctx.fill();
      ctx.fillStyle = '#aaa'; ctx.font = ~~(h*0.026)+'px Arial'; ctx.textAlign = 'center';
      ctx.fillText('👥 '+viewers, w-62, 23);
      ctx.fillStyle = '#ff4444'; ctx.beginPath(); ctx.roundRect(10,10,50,22,4); ctx.fill();
      var pulse = 0.8+0.2*Math.sin(t*3);
      ctx.fillStyle = 'rgba(255,255,255,'+(0.3*pulse)+')'; ctx.beginPath(); ctx.roundRect(10,10,50,22,4); ctx.fill();
      ctx.fillStyle = 'white'; ctx.font = 'bold '+~~(h*0.026)+'px Arial'; ctx.textAlign = 'center';
      ctx.fillText('LIVE', 35, 24);
      anim = requestAnimationFrame(draw);
    }
    function reposition() {
      var rr = a.getBoundingClientRect();
      ov.style.left = rr.x+'px'; ov.style.top = rr.y+'px';
      ov.style.width = rr.width+'px'; ov.style.height = rr.height+'px';
      if (ca.width !== ~~rr.width || ca.height !== ~~rr.height) {
        ca.width = ~~rr.width; ca.height = ~~rr.height;
        w = ca.width; h = ca.height;
      }
    }
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
    a.addEventListener('mouseenter', function(){ reposition(); ov.style.opacity = '1'; if (!anim) draw(); });
    a.addEventListener('mouseleave', function(){ ov.style.opacity = '0'; if (anim) { cancelAnimationFrame(anim); anim = null; } });
  }

  // Inject on existing links
  var items = [];
  try {
    var p = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
    var d = p?._s?.get('discover');
    items = (d && d.items) || [];
  } catch(e) {}
  document.querySelectorAll('a[href*="/livestream/"]').forEach(function(a, i) {
    createOverlay(a, (items[i]||{}).user?.profile_image?.url || '', i);
  });

  // Make videos non-interactive so mouse events reach the anchor
  document.querySelectorAll('a[href*=\\"/livestream/\\"] video').forEach(function(v) { v.style.pointerEvents = 'none'; });

  // Poll for new cards and videos
  setInterval(function() {
    var newItems = [];
    try {
      var pp = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
      var dd = pp?._s?.get('discover');
      newItems = (dd && dd.items) || [];
    } catch(e) {}
    document.querySelectorAll('a[href*="/livestream/"]').forEach(function(a, i) {
      if (!a.__ko) createOverlay(a, (newItems[i]||{}).user?.profile_image?.url || '', i);
      var vv = a.querySelector('video');
      if (vv) vv.style.pointerEvents = 'none';
    });
  }, 600);

  // CSS for blur removal
  if (!document.getElementById('__kocss')) {
    var st = document.createElement('style');
    st.id = '__kocss';
    st.textContent = '.blur-xs,.blur-4xl,[class*=blur] { filter: none !important; backdrop-filter: none !important; }';
    document.head.appendChild(st);
  }

  return 'injected ' + document.querySelectorAll('.__ko').length + ' overlays';
})()
`,
    returnByValue: true,
    timeout: 15000
  });
  console.log('Inject result:', injectResult.result?.result?.value);

  await new Promise(r => setTimeout(r, 2000));

  // Verify
  const verify = await s('Runtime.evaluate', {
    expression: `JSON.stringify({
      links: document.querySelectorAll('a[href*="/livestream/"]').length,
      overlays: document.querySelectorAll('.__ko').length
    })`,
    returnByValue: true
  });
  console.log('Verify:', verify.result?.result?.value);

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
