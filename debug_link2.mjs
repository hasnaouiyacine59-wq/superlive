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

  // Simple check: what is at the center of the first link?
  const r1 = await send('Runtime.evaluate', {
    expression: `(function() {
      var a = document.querySelector('a[href*="/livestream/"]');
      if (!a) return 'no a';
      var r = a.getBoundingClientRect();
      var cx = r.x + r.width/2, cy = r.y + r.height/2;
      var el = document.elementFromPoint(cx, cy);
      return 'center=' + ~~cx + ',' + ~~cy + ' el=' + el.tagName + (el.className ? ' .' + el.className.substring(0,60) : '') + ' sameAsA=' + (el === a);
    })()`,
    returnByValue: true
  });
  console.log('elementFromPoint:', r1.result?.result?.value);

  // Does the link have pointer-events?
  const r2 = await send('Runtime.evaluate', {
    expression: `(function() {
      var a = document.querySelector('a[href*="/livestream/"]');
      if (!a) return 'no a';
      return 'pe=' + window.getComputedStyle(a).pointerEvents;
    })()`,
    returnByValue: true
  });
  console.log(r2.result?.result?.value);

  // What's the z-index of the overlay vs link?
  const r3 = await send('Runtime.evaluate', {
    expression: `(function() {
      var o = document.querySelector('.__karlin-overlay');
      var a = document.querySelector('a[href*="/livestream/"]');
      if (!o || !a) return 'missing';
      return 'overlay.z=' + o.style.zIndex + ' a.z=' + window.getComputedStyle(a).zIndex + ' o.opacity=' + o.style.opacity;
    })()`,
    returnByValue: true
  });
  console.log(r3.result?.result?.value);

  // Check if the link has any ancestor with overflow hidden that clips
  const r4 = await send('Runtime.evaluate', {
    expression: `(function() {
      var a = document.querySelector('a[href*="/livestream/"]');
      if (!a) return 'no a';
      var el = a.parentElement;
      while (el) {
        var cs = window.getComputedStyle(el);
        if (cs.overflow === 'hidden' || cs.overflowX === 'hidden' || cs.overflowY === 'hidden') {
          return 'overflow:hidden on ' + el.tagName + (el.className ? ' .' + el.className.substring(0,50) : '');
        }
        el = el.parentElement;
      }
      return 'no overflow:hidden ancestor';
    })()`,
    returnByValue: true
  });
  console.log(r4.result?.result?.value);

  // Check if page has scrolled and overlay positions match
  const r5 = await send('Runtime.evaluate', {
    expression: `(function() {
      var a = document.querySelector('a[href*="/livestream/"]');
      var o = document.querySelector('.__karlin-overlay');
      if (!a || !o) return 'missing';
      var ar = a.getBoundingClientRect();
      return JSON.stringify({
        scrollY: window.scrollY,
        scrollX: window.scrollX,
        aRect: ar.x+','+ar.y+' '+ar.width+'x'+ar.height,
        overlayCSS: o.style.left+' '+o.style.top+' '+o.style.width+'x'+o.style.height
      });
    })()`,
    returnByValue: true
  });
  console.log('Position check:', r5.result?.result?.value);

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
