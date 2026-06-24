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

  // Check overlay count and first overlay details
  const info = await send('Runtime.evaluate', {
    expression: `(function() {
      var os = document.querySelectorAll('.__karlin-overlay');
      var o = os[0];
      if (!o) return JSON.stringify({count:0});
      var a = document.querySelector('a[href*="/livestream/"]');
      var ar = a ? a.getBoundingClientRect() : null;
      return JSON.stringify({
        count: os.length,
        overlayLeft: o.style.left,
        overlayTop: o.style.top,
        overlayW: o.style.width,
        overlayH: o.style.height,
        linkRect: ar ? ar.x+','+ar.y+' '+ar.width+'x'+ar.height : null
      });
    })()`,
    returnByValue: true
  });
  console.log('Overlay positions:', info.result?.result?.value);

  // Trigger mouseenter via JS dispatch
  console.log('\nTriggering mouseenter via dispatchEvent...');
  await send('Runtime.evaluate', {
    expression: `(function() {
      var a = document.querySelector('a[href*="/livestream/"]');
      if (a) a.dispatchEvent(new MouseEvent('mouseenter', {bubbles:true}));
      return 'dispatched';
    })()`,
    returnByValue: true
  });
  await new Promise(r => setTimeout(r, 500));

  const afterJS = await send('Runtime.evaluate', {
    expression: `(function() {
      var o = document.querySelector('.__karlin-overlay');
      return JSON.stringify({
        opacity: o ? o.style.opacity : 'none',
        canvasActive: o ? !!o.querySelector('canvas') : false,
        canvasPixels: o ? (function(){var c=o.querySelector('canvas');var ctx=c.getContext('2d');var d=ctx.getImageData(~~c.width/2,~~c.height/2,1,1).data; return Array.from(d)})() : null
      });
    })()`,
    returnByValue: true
  });
  console.log('After JS mouseenter:', afterJS.result?.result?.value);

  // Now trigger mouseleave
  console.log('\nTriggering mouseleave...');
  await send('Runtime.evaluate', {
    expression: `(function() {
      var a = document.querySelector('a[href*="/livestream/"]');
      if (a) a.dispatchEvent(new MouseEvent('mouseleave', {bubbles:true}));
      return 'dispatched';
    })()`,
    returnByValue: true
  });
  await new Promise(r => setTimeout(r, 500));

  const afterLeave = await send('Runtime.evaluate', {
    expression: `(function() {
      var o = document.querySelector('.__karlin-overlay');
      return JSON.stringify({ opacity: o ? o.style.opacity : 'none' });
    })()`,
    returnByValue: true
  });
  console.log('After mouseleave:', afterLeave.result?.result?.value);

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
