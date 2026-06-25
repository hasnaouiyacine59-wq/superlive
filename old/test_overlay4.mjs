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
    const timer = setTimeout(() => { delete pending[msgId]; rej(new Error(`Timeout ${m}`)); }, 10000);
    pending[msgId] = (d) => { clearTimeout(timer); r(d); };
    ws.send(JSON.stringify({id: msgId, method: m, params: p}));
  });

  // First move mouse completely away (top-left corner)
  for (let i = 0; i < 3; i++) {
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 0, y: 0, button: 'none', buttons: 0 });
  }
  await new Promise(r => setTimeout(r, 500));

  // Get card position
  const pos = await send('Runtime.evaluate', {
    expression: `(function(){
      var a=document.querySelector('a[href*="/livestream/"]');
      if(!a)return null;
      var r=a.getBoundingClientRect();
      return {x:~~(r.x+r.width/2),y:~~(r.y+r.height/2)};
    })()`,
    returnByValue: true
  });
  const p = pos.result?.result?.value;
  if (!p) { console.log('No card'); ws.close(); return; }

  console.log('Moving from (0,0) to (' + p.x + ',' + p.y + ')');

  // Move in steps to trigger mouseover on the way
  for (let i = 1; i <= 10; i++) {
    await send('Input.dispatchMouseEvent', {
      type: 'mouseMoved',
      x: Math.round(p.x * i / 10),
      y: Math.round(p.y * i / 10),
      button: 'none', buttons: 0
    });
    await new Promise(r => setTimeout(r, 50));
  }
  await new Promise(r => setTimeout(r, 2000));

  // Check overlay
  const check = await send('Runtime.evaluate', {
    expression: `(function(){
      var o=document.querySelector('.__karlin-overlay');
      if(!o)return 'no overlay';
      return JSON.stringify({
        opacity:o.style.opacity,
        animId:!!o._animId,
        canvasExists:!!o.querySelector('canvas')
      });
    })()`,
    returnByValue: true
  });
  console.log('After mouse move:', check.result?.result?.value);

  // Also check: did the listener fire at all? Add a counter
  const stats = await send('Runtime.evaluate', {
    expression: `JSON.stringify({
      links:document.querySelectorAll('a[href*="/livestream/"]').length,
      videos:document.querySelectorAll('a[href*="/livestream/"] video').length,
      videosWithPE:document.querySelectorAll('a[href*="/livestream/"] video[style*="pointer-events"]').length
    })`,
    returnByValue: true
  });
  console.log('Stats:', stats.result?.result?.value);

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
