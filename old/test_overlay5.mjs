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
    const timer = setTimeout(() => { delete pending[msgId]; rej(new Error(`Timeout ${m} id=${msgId}`)); }, 15000);
    pending[msgId] = (d) => { clearTimeout(timer); r(d); };
    ws.send(JSON.stringify({id: msgId, method: m, params: p}));
  });

  // Get position
  const r1 = await send('Runtime.evaluate', {
    expression: `(function(){
      var a=document.querySelector('a[href*="/livestream/"]');
      var r=a.getBoundingClientRect();
      return JSON.stringify({x:~~(r.x+r.width/2),y:~~(r.y+r.height/2),w:~~r.width,h:~~r.height});
    })()`,
    returnByValue: true
  });
  const p = JSON.parse(r1.result?.result?.value || '{}');
  console.log('Card:', p.x, p.y, p.w, 'x', p.h);

  // Move mouse to 0,0 first
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 0, y: 0, button: 'none', buttons: 0 });
  await new Promise(r => setTimeout(r, 200));

  // Move to card center in one shot
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: p.x, y: p.y, button: 'none', buttons: 0 });
  await new Promise(r => setTimeout(r, 1000));

  // Read overlay state
  const r2 = await send('Runtime.evaluate', {
    expression: `(function(){
      var o=document.querySelector('.__karlin-overlay');
      return JSON.stringify({opacity:o?o.style.opacity:'no-o', anim:o?!!o._animId:false});
    })()`,
    returnByValue: true
  });
  console.log('After move:', r2.result?.result?.value);

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
