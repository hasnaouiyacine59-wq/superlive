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

  // Re-inject with capture:true on mouseenter and use bubbling mouseover
  const fixCode = `
(function() {
  if (window.__karlinFixed) return;
  window.__karlinFixed = true;

  // Remove old overlay listeners by replacing with new approach
  // Use mouseover/mouseout on document (capture) because mouseenter doesn't bubble
  // and the video element covers the anchor

  document.addEventListener('mouseover', function(e) {
    var a = e.target.closest('a[href*="/livestream/"]');
    if (!a) return;
    var o = a.querySelector('.__karlin-overlay');
    if (o && o.style.opacity !== '1') {
      // Reposition
      var r = a.getBoundingClientRect();
      o.style.left = r.x + 'px';
      o.style.top = r.y + 'px';
      o.style.width = r.width + 'px';
      o.style.height = r.height + 'px';
      var c = o.querySelector('canvas');
      if (c && (c.width !== Math.round(r.width) || c.height !== Math.round(r.height))) {
        c.width = Math.round(r.width);
        c.height = Math.round(r.height);
      }
      o.style.opacity = '1';
      // Start animation if not started
      if (!o._animId) {
        var ca = o.querySelector('canvas');
        if (ca) {
          var x = ca.getContext('2d');
          var w = ca.width, h = ca.height;
          var idx = Array.from(document.querySelectorAll('.__karlin-overlay')).indexOf(o);
          var profileImg = o._profileImg || null;
          (function draw() {
            if (!x || o.style.opacity === '0') { o._animId = null; return; }
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
            x.fillStyle = 'rgba(0,0,0,0.5)'; x.beginPath(); x.roundRect(w-110,10,96,26,13); x.fill();
            x.fillStyle = '#aaa'; x.font = Math.round(h*0.026) + 'px Arial'; x.textAlign = 'center';
            x.fillText('\\uD83D\\uDC65 '+viewers, w-62, 23);
            x.fillStyle = '#ff4444'; x.beginPath(); x.roundRect(10,10,50,22,4); x.fill();
            var pulse = 0.8+0.2*Math.sin(t*3);
            x.fillStyle = 'rgba(255,255,255,'+(0.3*pulse)+')'; x.beginPath(); x.roundRect(10,10,50,22,4); x.fill();
            x.fillStyle = 'white'; x.font = 'bold ' + Math.round(h*0.026) + 'px Arial'; x.textAlign = 'center';
            x.fillText('LIVE', 35, 24);
            o._animId = requestAnimationFrame(draw);
          })();
        }
      }
    }
  }, true);

  document.addEventListener('mouseout', function(e) {
    var a = e.target.closest('a[href*="/livestream/"]');
    if (!a) return;
    // Only hide if mouse actually left the anchor entirely
    var related = e.relatedTarget;
    if (related && a.contains(related)) return; // still inside
    var o = a.querySelector('.__karlin-overlay');
    if (o) {
      o.style.opacity = '0';
      if (o._animId) { cancelAnimationFrame(o._animId); o._animId = null; }
    }
  }, true);

  // Make video elements non-interactive so events pass through to anchor
  document.querySelectorAll('a[href*="/livestream/"] video').forEach(function(v) {
    v.style.pointerEvents = 'none';
  });

  // Also watch for new videos
  new MutationObserver(function() {
    document.querySelectorAll('a[href*="/livestream/"] video').forEach(function(v) {
      v.style.pointerEvents = 'none';
    });
  }).observe(document.body || document.documentElement, { childList: true, subtree: true });

  console.log('Overlay fix applied - using bubbling mouseover');
})();
`;

  await send('Runtime.evaluate', {
    expression: fixCode,
    returnByValue: true,
    timeout: 15000
  });
  console.log('Fix injected');

  // Verify: test with CDP mouse move
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
  if (p) {
    console.log('Testing hover at', p.x, p.y);
    for (let i = 0; i < 5; i++) {
      await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: p.x, y: p.y, button: 'none', buttons: 0 });
    }
    await new Promise(r => setTimeout(r, 1000));
    const check = await send('Runtime.evaluate', {
      expression: `(function(){
        var o=document.querySelector('.__karlin-overlay');
        return JSON.stringify({opacity:o?o.style.opacity:'none', animRunning:o?!!o._animId:false});
      })()`,
      returnByValue: true
    });
    console.log('After hover:', check.result?.result?.value);
  }

  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
