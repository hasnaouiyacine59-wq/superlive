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

  // Check overlays before hover
  const before = await send('Runtime.evaluate', {
    expression: `(function() {
      var o = document.querySelector('.__karlin-overlay');
      return JSON.stringify({
        exists: !!o,
        opacity: o ? o.style.opacity : 'none',
        hasCanvas: o ? !!o.querySelector('canvas') : false
      });
    })()`,
    returnByValue: true
  });
  console.log('Before hover:', before.result?.result?.value);

  // Get position
  const pos = await send('Runtime.evaluate', {
    expression: `(function() {
      var a = document.querySelector('a[href*="/livestream/"]');
      if (!a) return null;
      var r = a.getBoundingClientRect();
      return { x: ~~(r.x + r.width/2), y: ~~(r.y + r.height/2) };
    })()`,
    returnByValue: true
  });
  const p = pos.result?.result?.value;
  if (!p) { console.log('No link'); ws.close(); return; }

  console.log('Hovering at', p.x, p.y);

  // Real hover
  for (let i = 1; i <= 20; i++) {
    await send('Input.dispatchMouseEvent', {
      type: 'mouseMoved',
      x: Math.round(p.x * i / 20),
      y: Math.round(p.y * i / 20),
      button: 'none', buttons: 0
    });
  }
  await new Promise(r => setTimeout(r, 2000));

  const after = await send('Runtime.evaluate', {
    expression: `(function() {
      var o = document.querySelector('.__karlin-overlay');
      return JSON.stringify({
        opacity: o ? o.style.opacity : 'none',
        hasCanvas: o ? !!o.querySelector('canvas') : false,
        canvasSize: o ? o.querySelector('canvas').width + 'x' + o.querySelector('canvas').height : 'none',
        canvasDrawn: o ? (function(){var c=o.querySelector('canvas');var ctx=c.getContext('2d');var d=ctx.getImageData(~~c.width/2,~~c.height/2,1,1).data; return Array.from(d)})() : null
      });
    })()`,
    returnByValue: true
  });
  console.log('After hover:', after.result?.result?.value);

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
