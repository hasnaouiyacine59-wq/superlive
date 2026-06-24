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

  // Fix 1: Override __karlinInject to add v.play() and class
  await send('Runtime.evaluate', {
    expression: `(function() {
      var orig = window.__karlinInject;
      window.__karlinInject = function(v, imgUrl, idx) {
        if (v.__karlin) return;
        if (orig) orig(v, imgUrl, idx);
        // Ensure play is called
        if (v.paused) v.play().catch(function(){});
        v.classList.add('__karlin-injected');
      };
    })()`,
    returnByValue: true
  });

  // Fix 2: Update CSS
  await send('Runtime.evaluate', {
    expression: `(function() {
      var s = document.getElementById('ok');
      if (s) {
        s.textContent = [
          '.blur-xs,.blur-4xl,[class*=blur] { filter: none !important; backdrop-filter: none !important; }',
          'a[href*="/livestream/"] video { opacity: 0 !important; transition: opacity 0.2s; }',
          'a[href*="/livestream/"] video.__karlin-visible { opacity: 1 !important; }',
        ].join(' ');
      }
    })()`,
    returnByValue: true
  });

  // Fix 3: Replace mouseenter/mouseleave handlers
  await send('Runtime.evaluate', {
    expression: `(function() {
      // Remove old listeners by cloning (brute force: override)
      document.addEventListener('mouseenter', function(e) {
        var a = e.target.closest('a[href*="/livestream/"]');
        if (!a) return;
        var v = a.querySelector('video');
        if (v) {
          v.classList.add('__karlin-visible');
          if (v.paused) v.play().catch(function(){});
        }
      }, true);
      document.addEventListener('mouseleave', function(e) {
        var a = e.target.closest('a[href*="/livestream/"]');
        if (!a) return;
        var v = a.querySelector('video');
        if (v) {
          v.classList.remove('__karlin-visible');
          if (!v.paused) v.pause();
        }
      }, true);
    })()`,
    returnByValue: true
  });

  // Re-inject all existing videos
  await send('Runtime.evaluate', {
    expression: `(function() {
      var vs = document.querySelectorAll('a[href*="/livestream/"] video');
      vs.forEach(function(v, i) {
        if (!v.__karlin) {
          var a = v.closest('a[href*="/livestream/"]');
          var img = a ? a.querySelector('img') : null;
          window.__karlinInject(v, img ? img.src : '', i);
        } else {
          // Re-apply: ensure playing
          if (v.paused) v.play().catch(function(){});
        }
      });
      return 're-injected ' + vs.length + ' videos';
    })()`,
    returnByValue: true
  });

  // Verify
  const check = await send('Runtime.evaluate', {
    expression: `(function() {
      var v = document.querySelector('a[href*="/livestream/"] video');
      if (!v) return 'no video';
      return JSON.stringify({
        karlin: !!v.__karlin,
        paused: v.paused,
        srcObject: !!v.srcObject,
        hasClass: v.classList.contains('__karlin-visible'),
        hasInjectedClass: v.classList.contains('__karlin-injected'),
        opacity: window.getComputedStyle(v).opacity
      });
    })()`,
    returnByValue: true
  });
  console.log('After fix:', check.result?.result?.value);

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
