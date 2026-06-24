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

  // Get card position
  const r = await send('Runtime.evaluate', {
    expression: `(function() {
      const a = document.querySelector("a[href*=\\"/livestream/\\\"]");
      if (!a) return null;
      const rect = a.getBoundingClientRect();
      return { x: ~~(rect.x + rect.width/2), y: ~~(rect.y + rect.height/2) };
    })()`,
    returnByValue: true
  });
  const pos = r.result?.result?.value;
  if (!pos) { console.log('No card'); ws.close(); return; }

  // Before hover
  const before = await send('Runtime.evaluate', {
    expression: `(function() {
      var v = document.querySelector("a[href*=\\"/livestream/\\\"] video");
      return JSON.stringify({ paused: v?.paused, visible: v?.classList.contains('__karlin-visible'), opacity: v ? window.getComputedStyle(v).opacity : 'no video' });
    })()`,
    returnByValue: true
  });
  console.log('Before hover:', before.result?.result?.value);

  // Real mouse movement
  for (let i = 1; i <= 15; i++) {
    await send('Input.dispatchMouseEvent', {
      type: 'mouseMoved',
      x: Math.round(pos.x * i / 15),
      y: Math.round(pos.y * i / 15),
      button: 'none', buttons: 0
    });
  }
  await new Promise(r => setTimeout(r, 1000));

  // After hover
  const after = await send('Runtime.evaluate', {
    expression: `(function() {
      var v = document.querySelector("a[href*=\\"/livestream/\\\"] video");
      return JSON.stringify({ paused: v?.paused, visible: v?.classList.contains('__karlin-visible'), opacity: v ? window.getComputedStyle(v).opacity : 'no video' });
    })()`,
    returnByValue: true
  });
  console.log('After hover:', after.result?.result?.value);

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
