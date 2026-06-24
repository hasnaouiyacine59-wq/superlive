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

  // Check what the page currently looks like
  const info = await send('Runtime.evaluate', {
    expression: `(function() {
      var links = document.querySelectorAll("a[href*=\\"/livestream/\\\"]");
      var first = links[0];
      if (!first) return JSON.stringify({error: 'no links found', url: location.href});
      var v = first.querySelector('video');
      var style = document.getElementById('ok');
      var viewport = document.querySelector('meta[name=viewport]');
      var computed = v ? window.getComputedStyle(v) : null;
      return JSON.stringify({
        url: location.href.substring(0, 100),
        linkCount: links.length,
        viewport: viewport ? viewport.content : 'none',
        hasCustomStyle: !!style,
        videoExists: !!v,
        videoInjected: v ? !!v.__karlin : false,
        videoPaused: v ? v.paused : null,
        videoSrcObject: v ? !!v.srcObject : null,
        videoOpacity: computed ? computed.opacity : null,
        linkOpacity: first ? window.getComputedStyle(first).opacity : null,
        linkDisplay: first ? window.getComputedStyle(first).display : null,
        firstLinkHTML: first ? first.innerHTML.substring(0, 300) : null
      });
    })()`,
    returnByValue: true
  });

  console.log('Page state:');
  console.log(info.result?.result?.value || 'N/A');

  // Try to force-inject the first video manually
  const forceInject = await send('Runtime.evaluate', {
    expression: `(function() {
      var a = document.querySelector("a[href*=\\"/livestream/\\\"]");
      if (!a) return 'no anchor';
      var v = a.querySelector('video');
      if (!v) return 'no video in anchor';
      if (v.__karlin) return 'already injected';
      var img = a.querySelector('img');
      var imgUrl = img ? img.src : '';
      window.__karlinInject(v, imgUrl, 0);
      return 'injected now. paused=' + v.paused + ' srcObject=' + !!v.srcObject;
    })()`,
    returnByValue: true
  });
  console.log('Force inject result:', forceInject.result?.result?.value);

  // After injection, check video
  const after = await send('Runtime.evaluate', {
    expression: `(function() {
      var v = document.querySelector("a[href*=\\"/livestream/\\\"] video");
      if (!v) return 'no video';
      return JSON.stringify({
        paused: v.paused,
        muted: v.muted,
        readyState: v.readyState,
        hasSrcObject: !!v.srcObject,
        hasKarlin: !!v.__karlin,
        videoWidth: v.videoWidth,
        videoHeight: v.videoHeight,
        style: (v.getAttribute('style') || '') + ' | ' + window.getComputedStyle(v).opacity + ' ' + window.getComputedStyle(v).visibility
      });
    })()`,
    returnByValue: true
  });
  console.log('After injection:', after.result?.result?.value);

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
