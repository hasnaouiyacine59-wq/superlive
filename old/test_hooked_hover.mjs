import WebSocket from 'ws';

const BASE = 'http://localhost:9222';

async function main() {
  const tabs = await (await fetch(BASE + '/json')).json();
  const tab = tabs.find(t => t.id === 'A8EF703FCD95D1B1C6EC1FA6DF20C64D');
  if (!tab) { console.log('Tab not found'); return; }

  const ws = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0, pending = {};

  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; }
  };
  const send = (m, p) => new Promise((r, rej) => {
    const msgId = ++id;
    const timer = setTimeout(() => { delete pending[msgId]; rej(new Error(`Timeout ${m}`)); }, 30000);
    pending[msgId] = (d) => { clearTimeout(timer); r(d); };
    ws.send(JSON.stringify({id: msgId, method: m, params: p}));
  });

  await send('Network.enable');

  // Track preview_premium_stream calls
  let previewReq = null;
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.method === 'Network.requestWillBeSent') {
      const req = d.params.request;
      if (req.url.includes('preview_premium_stream')) {
        previewReq = { url: req.url, method: req.method, postData: req.postData, id: d.params.requestId };
        console.log('>>> preview_premium_stream request intercepted');
      }
    }
    if (d.method === 'Network.responseReceived' && previewReq && d.params.requestId === previewReq.id) {
      previewReq.status = d.params.response.status;
      console.log('<<< preview_premium_stream status:', d.params.response.status);
    }
    if (d.method === 'Network.loadingFinished' && previewReq && d.params.requestId === previewReq.id) {
      previewReq.done = true;
    }
    if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; }
  };

  // Hover over first card
  const r = await send('Runtime.evaluate', {
    expression: `(function() {
      const a = document.querySelector("a[href*=\\\"/livestream/\\\"]");
      if (!a) return null;
      const rect = a.getBoundingClientRect();
      return { x: ~~(rect.x + rect.width/2), y: ~~(rect.y + rect.height/2) };
    })()`,
    returnByValue: true
  });
  const pos = r.result?.result?.value;
  if (!pos) { console.log('No card'); ws.close(); return; }

  console.log(`Hovering card at (${pos.x}, ${pos.y})`);

  for (let i = 1; i <= 15; i++) {
    await send('Input.dispatchMouseEvent', {
      type: 'mouseMoved',
      x: Math.round(pos.x * i / 15),
      y: Math.round(pos.y * i / 15),
      button: 'none', buttons: 0
    });
    await new Promise(r => setTimeout(r, 20));
  }

  await new Promise(r => setTimeout(r, 3000));

  // Capture response body if real call went through
  if (previewReq && previewReq.id && !previewReq.intercepted) {
    try {
      const bodyResp = await send('Network.getResponseBody', { requestId: previewReq.id });
      const body = bodyResp.result?.body;
      if (body) {
        previewReq.body = bodyResp.result?.base64Encoded ? Buffer.from(body, 'base64').toString() : body;
      }
    } catch (e) {}
  }

  // Check if video is playing now
  const v = await send('Runtime.evaluate', {
    expression: `(function() {
      const a = document.querySelector("a[href*=\\\"/livestream/\\\"]");
      const v = a ? a.querySelector('video') : null;
      if (!v) return JSON.stringify({hasVideo: false});
      return JSON.stringify({
        hasVideo: true,
        paused: v.paused,
        muted: v.muted,
        hasSrc: !!v.src,
        hasSrcObject: !!v.srcObject,
        readyState: v.readyState,
        canvasInjected: !!v.__karlin
      });
    })()`,
    returnByValue: true
  });

  // Check store limits
  const store = await send('Runtime.evaluate', {
    expression: `(function() {
      try {
        const p = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
        const s = p?._s?.get('settings');
        if (!s) return 'no settings store';
        const vp = s.$state?.settings?.implementation?.private_stream?.view_preview;
        if (!vp) return 'no view_preview';
        return JSON.stringify({ limit: vp.limit, duration_in_seconds: vp.duration_in_seconds });
      } catch(e) { return 'error: ' + e.message; }
    })()`,
    returnByValue: true
  });

  // Check shown-previews-v2 value
  const ls = await send('Runtime.evaluate', {
    expression: `(function() {
      try { return localStorage.getItem('shown-previews-v2') || '(null)'; } catch(e) { return 'error'; }
    })()`,
    returnByValue: true
  });

  console.log('\n=== RESULTS ===');
  console.log('API call made?', previewReq ? 'YES (but hook should intercept it)' : 'NO (hook intercepted it)');
  if (previewReq && previewReq.body) {
    console.log('Real response body:', previewReq.body.substring(0, 200));
  }
  console.log('Video state:', v.result?.result?.value);
  console.log('Store limit:', store.result?.result?.value);
  console.log('shown-previews-v2:', ls.result?.result?.value);

  if (previewReq) {
    console.log('\nIntercepted by hook?', previewReq.status ? 'NO - real network call went through' : 'YES - hook intercepted before network');
  }

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
