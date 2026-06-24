import WebSocket from 'ws';

const BASE = 'http://localhost:9222';

async function main() {
  const tabs = await (await fetch(BASE + '/json')).json();
  const tab = tabs.find(t => t.url.includes('superlive') && !t.url.includes('doubleclick'));
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

  console.log('Connected to:', tab.id);
  await send('Network.enable');
  console.log('Network enabled');

  let previewResponse = null;
  const origHandler = ws.onmessage;
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    // Intercept network events
    if (d.method === 'Network.requestWillBeSent') {
      const req = d.params.request;
      if (req.url.includes('preview_premium_stream')) {
        previewResponse = { url: req.url, method: req.method, postData: req.postData, id: d.params.requestId };
      }
    }
    if (d.method === 'Network.responseReceived' && previewResponse && d.params.requestId === previewResponse.id) {
      previewResponse.status = d.params.response.status;
    }
    if (d.method === 'Network.loadingFinished' && previewResponse && d.params.requestId === previewResponse.id) {
      previewResponse.done = true;
      previewResponse.encodedLen = d.params.encodedDataLength;
    }
    if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; }
  };

  // Get card position
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

  console.log(`Card at (${pos.x}, ${pos.y})`);

  // Move mouse to hover
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

  // Try to get response body
  if (previewResponse && previewResponse.id) {
    try {
      const bodyResp = await send('Network.getResponseBody', { requestId: previewResponse.id });
      const body = bodyResp.result?.body;
      if (body) {
        previewResponse.body = bodyResp.result?.base64Encoded
          ? Buffer.from(body, 'base64').toString()
          : body;
      }
    } catch (e) {
      previewResponse.body = '(unavailable: ' + e.message + ')';
    }
  }

  // Print result
  if (previewResponse) {
    console.log('\n=== preview_premium_stream ===');
    console.log('Method:', previewResponse.method);
    console.log('Status:', previewResponse.status);
    if (previewResponse.postData) {
      try { console.log('Request:', JSON.stringify(JSON.parse(previewResponse.postData), null, 2)); }
      catch { console.log('Request:', previewResponse.postData); }
    }
    if (previewResponse.body) {
      try { console.log('Response:', JSON.stringify(JSON.parse(previewResponse.body), null, 2)); }
      catch { console.log('Response:', previewResponse.body); }
    }
  } else {
    console.log('No preview_premium_stream call detected');
  }

  // Video state
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
        rect: (function(){try{var r=v.getBoundingClientRect(); return {x:~~r.x,y:~~r.y,w:~~r.width,h:~~r.height}}catch(e){return null}})()
      });
    })()`,
    returnByValue: true
  });
  console.log('\nVideo state:', v.result?.result?.value);

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
