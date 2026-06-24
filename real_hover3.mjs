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
  const send = (m, p) => new Promise((r, rej) => {
    const msgId = ++id;
    const timer = setTimeout(() => { delete pending[msgId]; rej(new Error(`Timeout ${m}`)); }, 15000);
    pending[msgId] = (d) => { clearTimeout(timer); r(d); };
    ws.send(JSON.stringify({id: msgId, method: m, params: p}));
  });

  await send('Network.enable');

  // Patch fetch to capture response before hover
  await send('Runtime.evaluate', {
    expression: `(function() {
      if (window.__karlinCapture) return;
      var origFetch = window.fetch;
      window.__karlinCapture = [];
      window.fetch = function(u, o) {
        var url = typeof u === 'string' ? u : u.url;
        if (url.includes('preview_premium_stream')) {
          return origFetch(u, o).then(function(r) {
            r.clone().json().then(function(data) {
              window.__karlinCapture.push({url: url, response: data});
            }).catch(function(){});
            return r;
          });
        }
        return origFetch(u, o);
      };
    })()`,
    returnByValue: true
  });

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

  // Get captured response
  const captured = await send('Runtime.evaluate', {
    expression: `JSON.stringify(window.__karlinCapture || [])`,
    returnByValue: true,
    timeout: 5000
  });
  console.log('\nCaptured preview_premium_stream responses:');
  const capData = captured.result?.result?.value;
  if (capData && capData !== '[]') {
    try { console.log(JSON.stringify(JSON.parse(capData), null, 2)); }
    catch { console.log(capData); }
  } else {
    console.log('(none captured)');
  }

  // Also check store data
  const storeData = await send('Runtime.evaluate', {
    expression: `(function() {
      try {
        const p = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
        const s = p?._s?.get('discover');
        const items = s?.items || [];
        if (!items.length) return 'no items';
        return JSON.stringify({
          count: items.length,
          first: {
            is_private: items[0].is_private,
            is_premium: items[0].is_premium,
            disallowed_reason: items[0].disallowed_reason,
            is_allowed: items[0].is_allowed,
            stream_status: items[0].stream_details?.status,
            preview_allowed: items[0].stream_details?.preview_allowed,
            title_image_url: items[0].stream_details?.title_image_url
          }
        }, null, 2);
      } catch(e) { return 'error: ' + e.message; }
    })()`,
    returnByValue: true,
    timeout: 5000
  });
  console.log('\nPinia store after hover:');
  console.log(storeData.result?.result?.value || 'N/A');

  // Video state
  const videoCheck = await send('Runtime.evaluate', {
    expression: `(function() {
      const v = document.querySelector("a[href*=\\\"/livestream/\\\"] video");
      if (!v) return 'no video';
      return JSON.stringify({
        paused: v.paused, muted: v.muted, hasSrc: !!v.src,
        hasSrcObject: !!v.srcObject, readyState: v.readyState,
        videoWidth: v.videoWidth, videoHeight: v.videoHeight
      });
    })()`,
    returnByValue: true,
    timeout: 5000
  });
  console.log('\nVideo state:');
  console.log(videoCheck.result?.result?.value || 'N/A');

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
