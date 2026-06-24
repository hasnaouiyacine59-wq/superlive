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
    const timer = setTimeout(() => { delete pending[msgId]; rej(new Error(`Timeout ${m}`)); }, 15000);
    pending[msgId] = (d) => { clearTimeout(timer); r(d); };
    ws.send(JSON.stringify({id: msgId, method: m, params: p}));
  });

  const r = await send('Runtime.evaluate', {
    expression: `(function() {
      var overlays = document.querySelectorAll('.__karlin-overlay');
      var links = document.querySelectorAll('a[href*="/livestream/"]');
      var firstLink = links[0];
      var firstOverlay = overlays[0];
      return JSON.stringify({
        linkCount: links.length,
        overlayCount: overlays.length,
        firstLinkHref: firstLink ? firstLink.href.substring(0,60) : null,
        firstOverlayExists: !!firstOverlay,
        firstOverlayOpacity: firstOverlay ? firstOverlay.style.opacity : null,
        firstOverlayPos: firstOverlay ? firstOverlay.style.left + ',' + firstOverlay.style.top : null,
        firstOverlaySize: firstOverlay ? firstOverlay.style.width + 'x' + firstOverlay.style.height : null,
        firstLinkRect: firstLink ? (function(){var r=firstLink.getBoundingClientRect(); return r.x+','+r.y+' '+r.width+'x'+r.height})() : null
      });
    })()`,
    returnByValue: true
  });
  console.log('Overlay state:');
  console.log(r.result?.result?.value || 'N/A');

  // Now hover over first card and check if overlay becomes visible
  const pos = await send('Runtime.evaluate', {
    expression: `(function() {
      var a = document.querySelector('a[href*="/livestream/"]');
      if (!a) return null;
      var r = a.getBoundingClientRect();
      return { x: ~~(r.x + r.width/2), y: ~~(r.y + r.height/2) };
    })()`,
    returnByValue: true
  });

  if (pos.result?.result?.value) {
    const p = pos.result.result.value;
    console.log('\nHovering at (' + p.x + ', ' + p.y + ')');

    for (let i = 1; i <= 15; i++) {
      await send('Input.dispatchMouseEvent', {
        type: 'mouseMoved', x: Math.round(p.x * i / 15), y: Math.round(p.y * i / 15), button: 'none', buttons: 0
      });
    }
    await new Promise(r => setTimeout(r, 1500));

    const after = await send('Runtime.evaluate', {
      expression: `(function() {
        var o = document.querySelector('.__karlin-overlay');
        return JSON.stringify({
          opacity: o ? o.style.opacity : 'no overlay',
          canvasActive: o ? !!o.querySelector('canvas') : false
        });
      })()`,
      returnByValue: true
    });
    console.log('After hover:', after.result?.result?.value);
  }

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
