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

  await send('Network.enable');

  const apiReqs = [];
  let pendingBody = {};

  ws.onmessage = e => {
    const d = JSON.parse(e.data);

    if (d.method === 'Network.requestWillBeSent') {
      const req = d.params.request;
      if (req.url.includes('api.spl-web')) {
        apiReqs.push({
          url: req.url, method: req.method,
          postData: req.postData,
          id: d.params.requestId, time: Date.now()
        });
      }
    }

    if (d.method === 'Network.responseReceived') {
      const match = apiReqs.find(x => x.id === d.params.requestId && !x.status);
      if (match) {
        match.status = d.params.response.status;
        match.mimeType = d.params.response.mimeType;
        // Request body for preview_premium_stream
        if (d.params.requestId) pendingBody[d.params.requestId] = match;
      }
    }

    if (d.method === 'Network.loadingFinished') {
      const match = apiReqs.find(x => x.id === d.params.requestId);
      if (match) {
        match.encodedLen = d.params.encodedDataLength;
      }
    }

    if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; }
  };

  // Get first card position
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

  // Move mouse
  for (let i = 1; i <= 10; i++) {
    await send('Input.dispatchMouseEvent', {
      type: 'mouseMoved',
      x: Math.round(pos.x * i / 10),
      y: Math.round(pos.y * i / 10),
      button: 'none', buttons: 0
    });
    await new Promise(r => setTimeout(r, 30));
  }

  await new Promise(r => setTimeout(r, 3000));

  // Get response body via Network.getResponseBody
  for (const req of apiReqs) {
    if (req.id) {
      try {
        const bodyResp = await send('Network.getResponseBody', { requestId: req.id });
        const body = bodyResp.result?.body;
        if (body) {
          req.responseBody = bodyResp.result?.base64Encoded
            ? Buffer.from(body, 'base64').toString()
            : body;
        }
      } catch(e) {
        req.responseBody = '(could not fetch: ' + e.message + ')';
      }
    }
  }

  // Print full details
  for (const req of apiReqs) {
    console.log(`\n--- ${req.method} ${req.url} ---`);
    if (req.postData) {
      try { console.log(`POST: ${JSON.stringify(JSON.parse(req.postData), null, 2)}`); }
      catch { console.log(`POST: ${req.postData}`); }
    }
    console.log(`Status: ${req.status}`);
    if (req.responseBody) {
      try { console.log(`Response: ${JSON.stringify(JSON.parse(req.responseBody), null, 2)}`); }
      catch { console.log(`Response: ${req.responseBody.substring(0, 500)}`); }
    }
  }

  if (apiReqs.length === 0) console.log('No API calls');

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
