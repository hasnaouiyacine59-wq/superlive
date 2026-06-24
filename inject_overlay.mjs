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
    const timer = setTimeout(() => { delete pending[msgId]; rej(new Error(`Timeout ${m}`)); }, 30000);
    pending[msgId] = (d) => { clearTimeout(timer); r(d); };
    ws.send(JSON.stringify({id: msgId, method: m, params: p}));
  });

  // Inject overlay system directly - no guard needed
  const injectCode = `
(function() {
  // Clean up old hook artifacts
  try {
    // Remove old event listeners by removing the CSS style
    var oldStyle = document.getElementById('ok');
    if (oldStyle) {
      oldStyle.textContent = '.blur-xs,.blur-4xl,[class*=blur] { filter: none !important; backdrop-filter: none !important; }';
    }
  } catch(e) {}

  if (window.__karlinOverlays) return; // already injected

  window.__karlinOverlays = {};

  function karlinCreateOverlay(a, imgUrl, idx) {
    if (a.__karlinOverlay) return;
    a.__karlinOverlay = true;

    // Remove old video injection if any
    var v = a.querySelector('video.__karlin-injected');
    if (v) { try { v.pause(); v.srcObject = null; } catch(e) {} }

    var rect = a.getBoundingClientRect();
    var ov = document.createElement('div');
    ov.className = '__karlin-overlay';
    ov.style.cssText = 'position:fixed;z-index:99999;pointer-events:none;opacity:0;transition:opacity 0.15s;border-radius:12px;overflow:hidden;';
    ov.style.left = rect.x + 'px';
    ov.style.top = rect.y + 'px';
    ov.style.width = rect.width + 'px';
    ov.style.height = rect.height + 'px';

    var ca = document.createElement('canvas');
    ca.width = Math.round(rect.width);
    ca.height = Math.round(rect.height);
    ca.style.cssText = 'width:' + rect.width + 'px;height:' + rect.height + 'px;display:block;border-radius:12px;';
    ov.appendChild(ca);
    document.body.appendChild(ov);

    var x = ca.getContext('2d');
    var w = ca.width, h = ca.height;
    var animId = null;
    var profileImg = null;

    if (imgUrl) {
      (function(u) {
        var img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = function() { profileImg = img; };
        img.src = u;
      })(imgUrl);
    }

    function draw() {
      if (!x) return;
      var t = Date.now() / 1000;
      var g = x.createLinearGradient(0,0,w,h);
      g.addColorStop(0, '#1a1a2e'); g.addColorStop(1, '#0f3460');
      x.fillStyle = g; x.fillRect(0,0,w,h);
      if (profileImg) {
        var scale = Math.max(w/profileImg.width, h/profileImg.height);
        x.drawImage(profileImg, (w-profileImg.width*scale)/2, (h-profileImg.height*scale)/2, profileImg.width*scale, profileImg.height*scale);
        x.fillStyle = 'rgba(0,0,0,0.3)'; x.fillRect(0,0,w,h);
      }
      var sx = (t*200)%(w*2)-w;
      x.fillStyle = 'rgba(255,255,255,0.04)'; x.fillRect(sx-40,0,80,h);
      x.fillStyle = 'rgba(0,0,0,0.6)'; x.fillRect(0,h-55,w,55);
      x.fillStyle = 'white'; x.font = 'bold ' + Math.round(h*0.035) + 'px Arial'; x.textAlign = 'left'; x.textBaseline = 'middle';
      x.fillText('Live Stream', 14, h-28);
      var viewers = Math.floor(10 + 50*(0.5+0.5*Math.sin(t*0.3+(idx||0))));
      x.textAlign = 'right'; x.fillStyle = '#ccc'; x.font = Math.round(h*0.028) + 'px Arial';
      x.fillText(viewers+' watching', w-14, h-28);
      x.fillStyle = 'rgba(0,0,0,0.5)'; x.beginPath(); x.roundRect(Math.round(w-110),10,96,26,13); x.fill();
      x.fillStyle = '#aaa'; x.font = Math.round(h*0.026) + 'px Arial'; x.textAlign = 'center';
      x.fillText('\\uD83D\\uDC65 '+viewers, Math.round(w-62), 23);
      x.fillStyle = '#ff4444'; x.beginPath(); x.roundRect(10,10,50,22,4); x.fill();
      var pulse = 0.8+0.2*Math.sin(t*3);
      x.fillStyle = 'rgba(255,255,255,'+(0.3*pulse)+')'; x.beginPath(); x.roundRect(10,10,50,22,4); x.fill();
      x.fillStyle = 'white'; x.font = 'bold ' + Math.round(h*0.026) + 'px Arial'; x.textAlign = 'center';
      x.fillText('LIVE', 35, 24);
      animId = requestAnimationFrame(draw);
    }

    function reposition() {
      var r = a.getBoundingClientRect();
      ov.style.left = r.x + 'px';
      ov.style.top = r.y + 'px';
      ov.style.width = r.width + 'px';
      ov.style.height = r.height + 'px';
      if (ca.width !== Math.round(r.width) || ca.height !== Math.round(r.height)) {
        ca.width = Math.round(r.width);
        ca.height = Math.round(r.height);
        w = ca.width; h = ca.height;
      }
    }
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);

    a.addEventListener('mouseenter', function() {
      reposition();
      ov.style.opacity = '1';
      if (!animId) draw();
    });
    a.addEventListener('mouseleave', function() {
      ov.style.opacity = '0';
      if (animId) { cancelAnimationFrame(animId); animId = null; }
    });
  }

  // Inject into all existing links
  var items = [];
  try {
    var pinia = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
    var st = pinia?._s?.get('discover');
    items = (st && st.items) || [];
  } catch(e) {}
  var links = document.querySelectorAll('a[href*="/livestream/"]');
  links.forEach(function(a, i) {
    var item = items[i] || {};
    karlinCreateOverlay(a, item.user?.profile_image?.url || '', i);
  });

  // Poll for new links
  setInterval(function() {
    var newItems = [];
    try {
      var p = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
      var s = p?._s?.get('discover');
      newItems = (s && s.items) || [];
    } catch(e) {}
    var newLinks = document.querySelectorAll('a[href*="/livestream/"]');
    newLinks.forEach(function(a, i) {
      if (!a.__karlinOverlay) {
        karlinCreateOverlay(a, (newItems[i] || {}).user?.profile_image?.url || '', i);
      }
    });
  }, 600);

  console.log('Overlay system injected');
})();
`;

  await send('Runtime.evaluate', {
    expression: injectCode,
    returnByValue: true,
    timeout: 15000
  });
  console.log('Overlay code injected');

  // Wait and check
  await new Promise(r => setTimeout(r, 3000));

  const check = await send('Runtime.evaluate', {
    expression: `JSON.stringify({
      links: document.querySelectorAll('a[href*="/livestream/"]').length,
      overlays: document.querySelectorAll('.__karlin-overlay').length
    })`,
    returnByValue: true,
    timeout: 5000
  });
  console.log('Result:', check.result?.result?.value);

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
