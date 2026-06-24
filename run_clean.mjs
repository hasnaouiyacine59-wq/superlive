import WebSocket from 'ws';
import { readFileSync } from 'fs';

const BASE = 'http://localhost:9222';
const TARGET_URL = 'https://superlive.chat/fr/discover';
const P = `document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia?._s?.get('discover')`;

async function main() {
  // Create fresh tab
  const ver = await (await fetch(`${BASE}/json/version`)).json();
  const bws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res, rej) => { bws.onopen = res; bws.onerror = rej; });
  let id = 0, pending = {};
  bws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; }
  };
  const send = (m, p) => new Promise(r => { const msgId = ++id; pending[msgId] = r; bws.send(JSON.stringify({id: msgId, method: m, params: p})); });
  const result = await send('Target.createTarget', { url: 'about:blank', type: 'page' });
  const tid = result.result?.targetId;
  bws.close();
  await new Promise(r => setTimeout(r, 1500));

  // Find the tab WebSocket URL
  const tabs = await (await fetch(`${BASE}/json`)).json();
  const tab = tabs.find(t => t.id === tid);
  if (!tab) throw new Error('Created tab not found');

  const ws = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  id = 0; pending = {};
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; }
  };
  const sendToTab = (m, p) => new Promise((r, rej) => {
    const msgId = ++id;
    const timer = setTimeout(() => { delete pending[msgId]; rej(new Error(`Timeout ${m}`)); }, 30000);
    pending[msgId] = (d) => { clearTimeout(timer); r(d); };
    ws.send(JSON.stringify({id: msgId, method: m, params: p}));
  });

  // Read the HOOK_SOURCE from unlock.mjs
  const source = readFileSync('unlock.mjs', 'utf-8');
  const hookMatch = source.match(/const HOOK_SOURCE = `([\s\S]*?)`;/);
  if (!hookMatch) throw new Error('Could not extract HOOK_SOURCE');
  const HOOK_SOURCE = hookMatch[1];

  // Register for all future documents
  await sendToTab('Page.addScriptToEvaluateOnNewDocument', { source: HOOK_SOURCE });
  console.log('Script registered for new documents');

  // Navigate
  await sendToTab('Page.enable');
  await sendToTab('Page.navigate', { url: TARGET_URL });

  // Wait for Nuxt
  for (let i = 0; i < 90; i++) {
    const r = await sendToTab('Runtime.evaluate', { expression: '!!document.getElementById("__nuxt")', returnByValue: true, timeout: 3000 });
    if (r.result?.result?.value) break;
    await new Promise(r => setTimeout(r, 1000));
  }
  console.log('Nuxt mounted');

  // Wait for items
  for (let i = 0; i < 60; i++) {
    const r = await sendToTab('Runtime.evaluate', {
      expression: `try { return typeof ${P}?.items?.length } catch(e) { return 'error' }`,
      returnByValue: true, timeout: 3000
    });
    if (r.result?.result?.value === 'number') break;
    if (i === 0) await new Promise(r => setTimeout(r, 3000));
    else await new Promise(r => setTimeout(r), 1000);
  }

  // Set mobile viewport
  try { await sendToTab('Emulation.setDeviceMetricsOverride', { width: 600, height: 900, deviceScaleFactor: 2, mobile: true }); } catch {}

  let itemsLen = 0;
  try {
    const r = await sendToTab('Runtime.evaluate', { expression: `${P}.items.length`, returnByValue: true, timeout: 5000 });
    itemsLen = r.result?.result?.value || 0;
  } catch(e) {
    console.log('Items not ready, forcing...');
    await sendToTab('Runtime.evaluate', { expression: `${P}.\$patch({loading: false})`, returnByValue: true, timeout: 5000 }).catch(() => {});
    await new Promise(r => setTimeout(r, 3000));
    try {
      const r = await sendToTab('Runtime.evaluate', { expression: `${P}.items.length`, returnByValue: true, timeout: 5000 });
      itemsLen = r.result?.result?.value || 0;
    } catch(e2) {}
  }
  console.log(`Items: ${itemsLen}`);

  if (itemsLen > 0) {
    // Patch settings
    await sendToTab('Runtime.evaluate', {
      expression: `(function(){
        try {
          var p = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
          var s = p._s.get('settings');
          if (s && s.$state && s.$state.settings) {
            s.$state.settings.implementation.private_stream.view_preview.limit = Infinity;
            s.$state.settings.implementation.private_stream.view_preview.duration_in_seconds = Infinity;
          }
        } catch(e) {}
      })()`,
      returnByValue: true
    });

    // Patch thumbnails
    await sendToTab('Runtime.evaluate', {
      expression: `(function(){
        const s = ${P};
        let p = 0;
        for (const i of s.items) {
          if (i.stream_details && i.user?.profile_image?.url) {
            i.stream_details.title_image_url = i.user.profile_image.url;
            p++;
          }
        }
        return p;
      })()`,
      returnByValue: true
    }).then(r => console.log(`Patched: ${r.result?.result?.value}`));
  }

  // CSS
  await sendToTab('Runtime.evaluate', {
    expression: `(function(){
      if (!document.getElementById('ok')) {
        var s = document.createElement('style');
        s.id = 'ok';
        s.textContent = '.blur-xs,.blur-4xl,[class*=blur] { filter: none !important; backdrop-filter: none !important; }';
        document.head.appendChild(s);
      }
    })()`,
    returnByValue: true
  });
  console.log('CSS injected');

  // Wait for overlays
  await new Promise(r => setTimeout(r, 3000));

  const overlayCheck = await sendToTab('Runtime.evaluate', {
    expression: `JSON.stringify({
      links: document.querySelectorAll('a[href*="/livestream/"]').length,
      overlays: document.querySelectorAll('.__karlin-overlay').length
    })`,
    returnByValue: true
  });
  console.log('Overlays:', overlayCheck.result?.result?.value);
  console.log('✓ Done — hover to preview');
  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
