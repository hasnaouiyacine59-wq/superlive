#!/usr/bin/env node
import WebSocket from 'ws';

const CDP_PORT = 9222;
const BASE = `http://localhost:${CDP_PORT}`;
const TARGET_URL = 'https://superlive.chat/fr/discover';
const POLL_INTERVAL = 5000;
const RECONNECT_DELAY = 3000;

const HOOK_SOURCE = `
if (!window.__HOOK_V3) {
  window.__HOOK_V3 = true;

  // --- Clean up V2 hooks ---
  // Clear all intervals/timeouts that V2 may have set (brute force: clear everything up to the current highest timer)
  ;(function() {
    var maxId = window.setTimeout(function(){}, 0);
    for (var i = 0; i <= maxId; i++) {
      window.clearInterval(i);
      window.clearTimeout(i);
    }
  })();
  // Remove old V2 overlays from DOM
  document.querySelectorAll('.__karlin-overlay').forEach(function(el) { el.remove(); });
  // Reset the overlay marker on links so V3 can create fresh overlays
  document.querySelectorAll('a[href*="/livestream/"]').forEach(function(a) {
    delete a.__karlinOverlay;
  });
  // Clear V2's window-level overlay map
  window.__karlinOverlays = {};

  // --- Neutralize localStorage preview counter ---
  var _origGetItem = Storage.prototype.getItem;
  Storage.prototype.getItem = function(k) {
    if (k === 'shown-previews-v2') return '{}';
    return _origGetItem.call(this, k);
  };
  var _origSetItem = Storage.prototype.setItem;
  Storage.prototype.setItem = function(k, v) {
    if (k === 'shown-previews-v2') return;
    return _origSetItem.call(this, k, v);
  };
  try { localStorage.removeItem('shown-previews-v2'); } catch(e) {}

  // --- Patch Pinia privateStreamPreviewSettings ---
  (function() {
    var _int = setInterval(function() {
      try {
        var pinia = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
        if (pinia) {
          var st = pinia._s.get('settings');
          if (st && st.$state && st.$state.settings && st.$state.settings.implementation && st.$state.settings.implementation.private_stream && st.$state.settings.implementation.private_stream.view_preview) {
            st.$state.settings.implementation.private_stream.view_preview.limit = Infinity;
            st.$state.settings.implementation.private_stream.view_preview.duration_in_seconds = Infinity;
            clearInterval(_int);
          }
        }
      } catch(e) {}
    }, 500);
  })();

  // --- Intercept fetch API ---
  var _origFetch = window.fetch.bind(window);
  window.fetch = function(u, o) {
    var s = typeof u === 'string' ? u : u?.url || '';
    if (!s.includes('api.spl-web.link/api/web/livestream/')) return _origFetch(u, o);
    var body = {};
    try { body = JSON.parse(o?.body || '{}'); } catch(e) {}
    var lsId = body.livestream_id || '';
    if (s.includes('/retrieve')) {
      return _origFetch(u, o).then(function(r) {
        return r.clone().json().then(function(data) {
          if (data.disallowed_reason) delete data.disallowed_reason;
          if (!data.livestream_settings) data.livestream_settings = {};
          if (!data.livestream_settings.sensitive_content_settings) data.livestream_settings.sensitive_content_settings = {};
          data.livestream_settings.sensitive_content_settings.is_allowed = true;
          return new Response(JSON.stringify(data), {status: r.status, headers: {'Content-Type':'application/json'}});
        }).catch(function() { return r; });
      });
    }
    if (s.includes('/preview_premium_stream')) {
      return Promise.resolve(new Response(JSON.stringify({code: 0, data: {is_allowed: true, blurAccessSeconds: 999999, livestream_id: lsId, thumbnail_url: '', status: 'active'}}), {status: 200, headers: {'Content-Type':'application/json'}}));
    }
    if (s.includes('/enter')) {
      return Promise.resolve(new Response(JSON.stringify({code: 0, data: {agora_app_id: 'd8e6b8f6a7b14a6e8a9c0d1e2f3a4b5c', agora_channel_name: 'live_' + lsId, agora_channel_token: '007___' + lsId, agora_rtm_token: '008___' + lsId, agora_uid: 123456, is_live: true}}), {status: 200, headers: {'Content-Type':'application/json'}}));
    }
    return _origFetch(u, o);
  };

  // --- CSS: remove blur effects ---
  if (!document.getElementById('__kh')) {
    var st = document.createElement('style');
    st.id = '__kh';
    st.textContent = '.blur-xs,.blur-4xl,[class*=blur] { filter: none !important; backdrop-filter: none !important; }';
    document.head.appendChild(st);
  }

  // --- Overlay system ---
  function karlinMakeOverlay(a, imgUrl, idx) {
    if (a.__karlinOverlay) return;
    a.__karlinOverlay = true;

    var rect = a.getBoundingClientRect();
    var ov = document.createElement('div');
    ov.className = '__karlin-overlay';
    ov.style.cssText = 'position:fixed;z-index:99999;pointer-events:none;opacity:0;transition:opacity 0.15s;border-radius:12px;overflow:hidden;';
    ov.style.left = rect.x + 'px';
    ov.style.top = rect.y + 'px';
    ov.style.width = rect.width + 'px';
    ov.style.height = rect.height + 'px';

    var ca = document.createElement('canvas');
    ca.width = Math.round(rect.width);
    ca.height = Math.round(rect.height);
    ca.style.cssText = 'width:100%;height:100%;display:block;border-radius:12px;';
    ov.appendChild(ca);
    document.body.appendChild(ov);

    var ctx = ca.getContext('2d');
    var w = ca.width, h = ca.height;
    var animId = null;
    var profileImg = null;
    var active = false;

    if (imgUrl) {
      (function(u) {
        var img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = function() { profileImg = img; };
        img.onerror = function() {};
        img.src = u;
      })(imgUrl);
    }

    function draw() {
      if (!ctx || !active) { animId = null; return; }
      var t = Date.now() / 1000;
      var g = ctx.createLinearGradient(0,0,w,h);
      g.addColorStop(0, '#1a1a2e'); g.addColorStop(1, '#0f3460');
      ctx.fillStyle = g; ctx.fillRect(0,0,w,h);
      if (profileImg) {
        var scale = Math.max(w/profileImg.width, h/profileImg.height);
        ctx.drawImage(profileImg, (w-profileImg.width*scale)/2, (h-profileImg.height*scale)/2, profileImg.width*scale, profileImg.height*scale);
        ctx.fillStyle = 'rgba(0,0,0,0.3)'; ctx.fillRect(0,0,w,h);
      }
      var sx = (t*200)%(w*2)-w;
      ctx.fillStyle = 'rgba(255,255,255,0.04)'; ctx.fillRect(sx-40,0,80,h);
      ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(0,h-55,w,55);
      ctx.fillStyle = 'white'; ctx.font = 'bold ' + Math.round(h*0.035) + 'px Arial'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      ctx.fillText('Live Stream', 14, h-28);
      var viewers = Math.floor(10 + 50*(0.5+0.5*Math.sin(t*0.3+(idx||0))));
      ctx.textAlign = 'right'; ctx.fillStyle = '#ccc'; ctx.font = Math.round(h*0.028) + 'px Arial';
      ctx.fillText(viewers+' watching', w-14, h-28);
      ctx.fillStyle = 'rgba(0,0,0,0.5)'; ctx.beginPath(); ctx.roundRect(w-110,10,96,26,13); ctx.fill();
      ctx.fillStyle = '#aaa'; ctx.font = Math.round(h*0.026) + 'px Arial'; ctx.textAlign = 'center';
      ctx.fillText('\\uD83D\\uDC65 '+viewers, w-62, 23);
      ctx.fillStyle = '#ff4444'; ctx.beginPath(); ctx.roundRect(10,10,50,22,4); ctx.fill();
      var pulse = 0.8+0.2*Math.sin(t*3);
      ctx.fillStyle = 'rgba(255,255,255,'+(0.3*pulse)+')'; ctx.beginPath(); ctx.roundRect(10,10,50,22,4); ctx.fill();
      ctx.fillStyle = 'white'; ctx.font = 'bold ' + Math.round(h*0.026) + 'px Arial'; ctx.textAlign = 'center';
      ctx.fillText('LIVE', 35, 24);
      animId = requestAnimationFrame(draw);
    }

    function reposition() {
      var r = a.getBoundingClientRect();
      ov.style.left = r.x + 'px';
      ov.style.top = r.y + 'px';
      ov.style.width = r.width + 'px';
      ov.style.height = r.height + 'px';
      if (ca.width !== Math.round(r.width) || ca.height !== Math.round(r.height)) {
        ca.width = Math.round(r.width);
        ca.height = Math.round(r.height);
        w = ca.width; h = ca.height;
      }
    }

    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);

    // Use mouseenter/mouseleave on the anchor.
    // Child <video> elements have pointer-events:none so they pass through.
    a.addEventListener('mouseenter', function() {
      reposition();
      active = true;
      ov.style.opacity = '1';
      if (!animId) draw();
    });
    a.addEventListener('mouseleave', function() {
      active = false;
      ov.style.opacity = '0';
      if (animId) { cancelAnimationFrame(animId); animId = null; }
    });
  }

  // --- Watch for video elements and make them non-interactive ---
  function disableVideoPointerEvents() {
    document.querySelectorAll('a[href*="/livestream/"] video').forEach(function(v) {
      if (v.style.pointerEvents !== 'none') v.style.pointerEvents = 'none';
    });
  }

  // --- Poll for new cards and set up overlays ---
  setInterval(function() {
    var items = [];
    try {
      var pinia = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
      var ds = pinia?._s?.get('discover');
      items = (ds && ds.items) || [];
    } catch(e) {}

    var links = document.querySelectorAll('a[href*="/livestream/"]');
    links.forEach(function(a, i) {
      if (!a.__karlinOverlay) {
        var item = items[i] || {};
        karlinMakeOverlay(a, item.user?.profile_image?.url || '', i);
      }
    });

    disableVideoPointerEvents();
  }, 600);

  // Initial run
  setTimeout(function() {
    disableVideoPointerEvents();
  }, 100);
}
`;

// --- CDP Session ---

class Session {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.pending = new Map();
    this.ready = new Promise((res, rej) => {
      ws.onopen = res;
      ws.onerror = rej;
    });
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.id && this.pending.has(m.id)) {
        const { r, j } = this.pending.get(m.id);
        this.pending.delete(m.id);
        m.error ? j(new Error(m.error.message)) : r(m);
      }
    };
  }

  async init() {
    await Promise.race([
      this.ready,
      new Promise((_, rej) => setTimeout(() => rej(new Error('WS connect timeout')), 15000))
    ]);
    await this.send('Runtime.enable');
    await this.send('Page.enable');
  }

  async send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++this.id;
      this.pending.set(id, { r: resolve, j: reject });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`Timeout: ${method}`));
        }
      }, 30000);
    });
  }

  async eval(expr, opts = {}) {
    const r = await this.send('Runtime.evaluate', {
      expression: expr,
      returnByValue: true,
      awaitPromise: opts.awaitPromise !== false,
      timeout: opts.timeout || 30000,
    });
    if (r.result?.exceptionDetails) {
      const e = r.result.exceptionDetails;
      throw new Error(e.text + ' | ' + (e.exception?.description || '').substring(0, 200));
    }
    return r.result?.result?.value;
  }

  close() {
    try { this.ws.close(); } catch {}
  }
}

// --- Tab management ---

async function findOrCreateTab() {
  const tabs = await (await fetch(`${BASE}/json`)).json();
  const existing = tabs.find(t => t.url && t.url.includes('superlive.chat') && !t.url.includes('doubleclick'));
  if (existing) return { tab: existing, created: false };

  // Create new tab
  const ver = await (await fetch(`${BASE}/json/version`)).json();
  const bws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res, rej) => { bws.onopen = res; bws.onerror = rej; });
  let bid = 0;
  const tid = await new Promise((resolve, reject) => {
    bws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.id === bid) resolve(m.result?.targetId);
      else if (m.error) reject(new Error(m.error.message));
    };
    bid = 1;
    bws.send(JSON.stringify({ id: bid, method: 'Target.createTarget', params: { url: 'about:blank', type: 'page' } }));
    setTimeout(() => reject(new Error('createTarget timeout')), 15000);
  });
  bws.close();
  await new Promise(r => setTimeout(r, 2000));

  const tabs2 = await (await fetch(`${BASE}/json`)).json();
  const tab = tabs2.find(t => t.id === tid);
  if (!tab) throw new Error('Created tab not found in listing');
  return { tab, created: true };
}

async function setupDiscover(sess) {
  // Wait for Nuxt and Pinia store
  for (let i = 0; i < 90; i++) {
    const r = await sess.eval('!!document.getElementById("__nuxt")', { awaitPromise: false });
    if (r) break;
    await new Promise(r => setTimeout(r, 1000));
  }

  // Check items
  let itemsLen = 0;
  for (let i = 0; i < 60; i++) {
    try {
      const r = await sess.eval(
        `document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia?._s?.get('discover')?.items?.length`,
        { awaitPromise: false }
      );
      if (typeof r === 'number' && r >= 0) { itemsLen = r; break; }
    } catch {}
    if (i === 0) await new Promise(r => setTimeout(r, 3000));
    else await new Promise(r => setTimeout(r), 1000);
  }

  if (!itemsLen) {
    // Force load
    await sess.eval(`(function(){
      try {
        var p = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia?._s?.get('discover');
        if (p) p.$patch({loading: false});
      } catch(e) {}
    })()`, { awaitPromise: false });
    await new Promise(r => setTimeout(r, 3000));
  }

  // Wait for overlays to appear (from HOOK_SOURCE polling)
  for (let i = 0; i < 30; i++) {
    const cnt = await sess.eval(
      'document.querySelectorAll(".__karlin-overlay").length',
      { awaitPromise: false }
    );
    if (cnt > 0) break;
    await new Promise(r => setTimeout(r, 1000));
  }
}

async function ensureHooks(sess) {
  // Register for future documents
  const result = await sess.send('Page.addScriptToEvaluateOnNewDocument', { source: HOOK_SOURCE });
  const scriptId = result.result?.identifier;
  console.log(`  Hook registered (scriptId=${scriptId})`);

  // Inject into current document
  await sess.eval(HOOK_SOURCE, { timeout: 10000 });
  console.log('  Hook injected into current page');
  return scriptId;
}

// --- Health check ---

async function checkTabAlive(tabId) {
  try {
    const tabs = await (await fetch(`${BASE}/json`)).json();
    return tabs.some(t => t.id === tabId);
  } catch {
    return false;
  }
}

// --- Main daemon loop ---

async function run(signal) {
  let tabId = null;
  let sess = null;

  while (!signal.aborted) {
    try {
      // Step 1: find or create tab
      console.log('[daemon] Finding discover tab...');
      const { tab, created } = await findOrCreateTab();
      tabId = tab.id;
      console.log(`[daemon] Tab: ${tabId} (${created ? 'created' : 'existing'})`);

      // Step 2: connect
      sess = new Session(new WebSocket(tab.webSocketDebuggerUrl));
      await sess.init();
      console.log('[daemon] CDP connected');

      // Step 3: navigate to discover if not already there
      if (!tab.url?.includes('/fr/discover')) {
        console.log('[daemon] Navigating to discover...');
        await sess.send('Page.navigate', { url: TARGET_URL });
      }

      // Step 4: register hooks
      console.log('[daemon] Injecting hooks...');
      await ensureHooks(sess);

      // Step 5: wait for store & overlays
      console.log('[daemon] Setting up discover page...');
      await setupDiscover(sess);

      const overlayCount = await sess.eval(
        'document.querySelectorAll(".__karlin-overlay").length',
        { awaitPromise: false }
      );
      console.log(`[daemon] Overlays: ${overlayCount}`);
      console.log(`[daemon] Hover over cards to see animated previews`);

      // Step 6: monitor loop
      while (!signal.aborted) {
        await new Promise(r => setTimeout(r, POLL_INTERVAL));

        // Check tab still alive
        if (!await checkTabAlive(tabId)) {
          console.log('[daemon] Tab gone, reconnecting...');
          break;
        }

        // Verify hooks still active (eval should succeed)
        try {
          const ok = await sess.eval('!!window.__HOOK_V3', { awaitPromise: false, timeout: 5000 });
          if (!ok) {
            console.log('[daemon] Hook missing, re-injecting...');
            await sess.eval(HOOK_SOURCE, { timeout: 10000 });
          }
        } catch (e) {
          // Connection might be dead; surface outer loop will handle
          throw e;
        }
      }

      // Cleanup session before reconnect
      if (sess) { sess.close(); sess = null; }

    } catch (e) {
      console.error(`[daemon] Error: ${e.message}`);
      if (sess) { try { sess.close(); } catch {} sess = null; }
      if (signal.aborted) break;
      console.log(`[daemon] Retrying in ${RECONNECT_DELAY/1000}s...`);
      await new Promise(r => setTimeout(r, RECONNECT_DELAY));
    }
  }

  console.log('[daemon] Stopped');
}

// --- Entry point ---

const signal = { aborted: false };
process.on('SIGINT', () => {
  console.log('\n[daemon] Shutting down...');
  signal.aborted = true;
  process.exit(0);
});
process.on('SIGTERM', () => {
  signal.aborted = true;
  process.exit(0);
});

run(signal).catch(e => {
  console.error('Fatal:', e.message);
  process.exit(1);
});
