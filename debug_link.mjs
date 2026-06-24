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

  const info = await send('Runtime.evaluate', {
    expression: `(function() {
      var a = document.querySelector('a[href*="/livestream/"]');
      if (!a) return 'no link';
      var cs = window.getComputedStyle(a);
      // Check what's inside the link
      var children = [];
      a.querySelectorAll('*').forEach(function(el, i) {
        if (i < 20) {
          var ecs = window.getComputedStyle(el);
          children.push({
            tag: el.tagName,
            classes: el.className.substring(0, 60),
            pe: ecs.pointerEvents,
            zIndex: ecs.zIndex,
            position: ecs.position,
            opacity: ecs.opacity
          });
        }
      });
      // Also check if there's an element that covers the link
      var aRect = a.getBoundingClientRect();
      var centerEl = document.elementFromPoint(aRect.x + aRect.width/2, aRect.y + aRect.height/2);
      return JSON.stringify({
        aPointerEvents: cs.pointerEvents,
        aPosition: cs.position,
        aZIndex: cs.zIndex,
        aOverflow: cs.overflow,
        childCount: a.querySelectorAll('*').length,
        videoCount: a.querySelectorAll('video').length,
        imgCount: a.querySelectorAll('img').length,
        centerElement: centerEl ? centerEl.tagName + (centerEl.className ? '.' + centerEl.className.substring(0,40) : '') : 'none',
        centerElementIsLink: centerEl === a,
        firstChildren: children.slice(0, 5)
      });
    })()`,
    returnByValue: true
  });
  console.log('Link analysis:');
  console.log(JSON.stringify(info.result?.result?.value, null, 2));

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
