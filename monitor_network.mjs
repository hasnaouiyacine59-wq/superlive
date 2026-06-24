import WebSocket from 'ws';

const BASE = 'http://localhost:9222';

async function main() {
  // List all tabs so user can pick
  const tabs = await (await fetch(BASE + '/json')).json();
  console.log('Available tabs:');
  tabs.forEach((t, i) => {
    if (t.url && t.url !== 'about:blank') {
      console.log(`  [${i}] ${t.id.substring(0, 20)}... | ${(t.title || '').substring(0, 60)} | ${t.url.substring(0, 80)}`);
    }
  });

  // Find the discover page or first non-blank tab
  let tab = tabs.find(t => t.url.includes('superlive') || t.url.includes('discover'));
  if (!tab) tab = tabs.find(t => t.url && t.url !== 'about:blank' && !t.url.includes('doubleclick') && !t.url.includes('google'));
  if (!tab) { console.log('No suitable tab found. Creating new one...'); return; }

  console.log(`\nConnecting to: ${tab.title || 'untitled'}`);
  console.log(`URL: ${tab.url}`);
  console.log(`ID: ${tab.id}`);

  const ws = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0, pending = {};

  const send = (m, p) => new Promise(r => {
    const msgId = ++id;
    pending[msgId] = r;
    ws.send(JSON.stringify({id: msgId, method: m, params: p}));
  });

  await send('Network.enable');
  await send('Page.enable');

  // Enable Input domain for mouse tracking
  await send('Input.dispatchMouseEvent', {}).catch(() => {}); // just warm up

  console.log('\n=== NETWORK MONITOR ACTIVE ===');
  console.log('Hover over premium cards now. Live feed below:');
  console.log('(Ctrl+C to stop)\n');

  // Real-time network logging
  const seenReqs = new Set();
  let reqCount = 0;

  ws.onmessage = e => {
    const d = JSON.parse(e.data);

    if (d.method === 'Network.requestWillBeSent') {
      const req = d.params.request;
      // Filter to interesting API calls
      if (req.url.includes('api.spl-web')) {
        reqCount++;
        const ts = new Date().toLocaleTimeString();
        console.log(`[${ts}] >>> ${req.method} ${req.url.substring(0, 150)}`);
        if (req.postData) {
          console.log(`      POST: ${req.postData.substring(0, 200)}`);
        }
        seenReqs.add(d.params.requestId);
      }
    }

    if (d.method === 'Network.responseReceived') {
      if (seenReqs.has(d.params.requestId)) {
        const resp = d.params.response;
        console.log(`      <<< ${resp.status} ${resp.mimeType} (${(resp.transferSize || 0)} bytes)`);
      }
    }

    if (d.method === 'Network.loadingFinished') {
      if (seenReqs.has(d.params.requestId)) {
        console.log(`      === DONE (${d.params.encodedDataLength} bytes)`);
        seenReqs.delete(d.params.requestId);
      }
    }

    if (d.id && pending[d.id]) {
      pending[d.id](d);
      delete pending[d.id];
    }
  };

  // Pinia dump for reference
  const storeInfo = await send('Runtime.evaluate', {
    expression: `(function() {
      try {
        const p = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
        const s = p?._s?.get('discover');
        if (!s || !s.items) return 'no store';
        return 'Store has ' + s.items.length + ' items, loading=' + s.loading;
      } catch(e) { return 'error'; }
    })()`,
    returnByValue: true,
    timeout: 5000
  });
  console.log(`\nPinia store: ${storeInfo.result?.result?.value || 'N/A'}`);

  // Give a hint about element positions
  const positions = await send('Runtime.evaluate', {
    expression: `(function() {
      const links = document.querySelectorAll("a[href*=\\\"/livestream/\\\"]");
      const results = [];
      for (let i = 0; i < Math.min(links.length, 5); i++) {
        const r = links[i].getBoundingClientRect();
        const centerX = r.x + r.width / 2;
        const centerY = r.y + r.height / 2;
        results.push({idx: i, href: links[i].href.substring(0,60), x: ~~centerX, y: ~~centerY});
      }
      return JSON.stringify(results, null, 2);
    })()`,
    returnByValue: true,
    timeout: 5000
  });
  console.log('\nCard positions (if you want script to hover):');
  console.log(positions.result?.result?.value || 'N/A');

  // Keep alive and printing for 2 minutes
  await new Promise(r => setTimeout(r, 120000));
  console.log(`\nMonitoring ended. ${reqCount} API requests captured.`);
  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
