import WebSocket from 'ws';

const BASE = 'http://localhost:9222';

async function main() {
  const tabs = await (await fetch(BASE + '/json')).json();
  const tab = tabs.find(t => t.id === 'A8EF703FCD95D1B1C6EC1FA6DF20C64D')
         || tabs.find(t => t.url.includes('superlive'));
  if (!tab) { console.log('Tab not found'); return; }

  const ws = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0, pending = {};
  const send = (m, p) => new Promise(r => {
    const msgId = ++id; pending[msgId] = r;
    ws.send(JSON.stringify({id: msgId, method: m, params: p}));
  });

  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; }
  };

  await send('Network.enable');

  // Collect API requests
  const apiReqs = [];
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.method === 'Network.requestWillBeSent') {
      const req = d.params.request;
      if (req.url.includes('api.spl-web')) {
        apiReqs.push({ url: req.url, method: req.method, postData: req.postData, id: d.params.requestId, time: Date.now() });
      }
    }
    if (d.method === 'Network.responseReceived') {
      const match = apiReqs.find(x => x.id === d.params.requestId && !x.status);
      if (match) {
        match.status = d.params.response.status;
        match.responseTime = Date.now();
      }
    }
    if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; }
  };

  // Get first card's position
  const r = await send('Runtime.evaluate', {
    expression: `(function() {
      const a = document.querySelector("a[href*=\\\"/livestream/\\\"]");
      if (!a) return null;
      const rect = a.getBoundingClientRect();
      return { x: ~~(rect.x + rect.width/2), y: ~~(rect.y + rect.height/2), w: ~~rect.width, h: ~~rect.height };
    })()`,
    returnByValue: true
  });
  const pos = r.result?.result?.value;
  if (!pos) { console.log('No card found'); ws.close(); return; }

  console.log(`Card center: (${pos.x}, ${pos.y}), size: ${pos.w}x${pos.h}`);

  // Scroll to make card visible first
  await send('Runtime.evaluate', {
    expression: `window.scrollTo(0, 0)`,
    returnByValue: true
  });

  // Move mouse to a neutral position first (top-left corner)
  await send('Input.dispatchMouseEvent', {
    type: 'mouseMoved',
    x: 0,
    y: 0,
    button: 'none',
    buttons: 0
  });
  await new Promise(r => setTimeout(r, 500));

  // Actually move the mouse over the card — real browser-level hover
  console.log(`\nMoving mouse to (${pos.x}, ${pos.y})...`);

  // Move in steps for realism
  const steps = 10;
  for (let i = 1; i <= steps; i++) {
    const cx = Math.round(0 + (pos.x - 0) * (i / steps));
    const cy = Math.round(0 + (pos.y - 0) * (i / steps));
    await send('Input.dispatchMouseEvent', {
      type: 'mouseMoved',
      x: cx,
      y: cy,
      button: 'none',
      buttons: 0
    });
    await new Promise(r => setTimeout(r, 30));
  }

  // Wait for potential network calls
  await new Promise(r => setTimeout(r, 5000));

  // Print captured API requests
  console.log(`\n=== API requests during hover (${apiReqs.length}) ===`);
  for (const req of apiReqs) {
    console.log(`  ${req.method} ${req.url}`);
    if (req.postData) console.log(`    POST: ${req.postData.substring(0, 300)}`);
    if (req.status) console.log(`    -> ${req.status}`);
    console.log('');
  }
  if (apiReqs.length === 0) console.log('  (none)');

  // Check console errors / warnings
  const consoleCheck = await send('Runtime.evaluate', {
    expression: `(function() {
      try {
        var p = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
        var s = p?._s?.get('discover');
        var firstItem = s?.items?.[0];
        return JSON.stringify({
          storeItems: s?.items?.length || 0,
          firstItemPrivate: firstItem?.is_private,
          firstItemPremium: firstItem?.is_premium,
          firstItemAllowed: firstItem?.is_allowed,
          firstItemReason: firstItem?.disallowed_reason || null,
          firstStreamStatus: firstItem?.stream_details?.status,
          firstStreamPreview: firstItem?.stream_details?.preview_allowed,
        });
      } catch(e) { return 'error: ' + e.message; }
    })()`,
    returnByValue: true,
    timeout: 5000
  });
  console.log('\n=== Pinia store state after hover ===');
  console.log(consoleCheck.result?.result?.value || 'N/A');

  // Also check: did a video element change?
  const videoCheck = await send('Runtime.evaluate', {
    expression: `(function() {
      const v = document.querySelector("a[href*=\\\"/livestream/\\\"] video");
      if (!v) return 'no video';
      return JSON.stringify({
        paused: v.paused,
        muted: v.muted,
        hasSrc: !!v.src,
        hasSrcObject: !!v.srcObject,
        readyState: v.readyState,
        style: (v.getAttribute('style') || '').substring(0, 200)
      });
    })()`,
    returnByValue: true,
    timeout: 5000
  });
  console.log('\n=== Video state after hover ===');
  console.log(videoCheck.result?.result?.value || 'N/A');

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
