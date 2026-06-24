// Karlin - SuperLive Unlock
// Copy everything below this line and paste into browser console on superlive.chat

(function() {
  if (window.__karlin) return;
  window.__karlin = true;

  // --- localStorage override ---
  var _origGetItem = Storage.prototype.getItem;
  Storage.prototype.getItem = function(k) {
    if (k === 'shown-previews-v2') return '{}';
    return _origGetItem.call(this, k);
  };
  var _origSetItem = Storage.prototype.setItem;
  Storage.prototype.setItem = function(k, v) {
    if (k === 'shown-previews-v2') return;
    return _origSetItem.call(this, k, v);
  };
  try { localStorage.removeItem('shown-previews-v2'); } catch(e) {}

  // --- Pinia settings patcher ---
  setInterval(function() {
    try {
      var pinia = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
      if (pinia) {
        var st = pinia._s.get('settings');
        if (st && st.$state && st.$state.settings && st.$state.settings.implementation && st.$state.settings.implementation.private_stream && st.$state.settings.implementation.private_stream.view_preview) {
          st.$state.settings.implementation.private_stream.view_preview.limit = Infinity;
          st.$state.settings.implementation.private_stream.view_preview.duration_in_seconds = Infinity;
          clearInterval(this);
        }
      }
    } catch(e) {}
  }, 500);

  // --- fetch interceptor ---
  var _origFetch = window.fetch.bind(window);
  window.fetch = function(u, o) {
    var url = typeof u === 'string' ? u : u?.url || '';
    if (!url.includes('api.spl-web.link/api/web/livestream/')) return _origFetch(u, o);
    var body = {};
    try { body = JSON.parse(o?.body || '{}'); } catch(e) {}
    var lsId = body.livestream_id || '';
    if (url.includes('/retrieve')) {
      return _origFetch(u, o).then(r => r.clone().json().then(data => {
        if (data.disallowed_reason) delete data.disallowed_reason;
        if (!data.livestream_settings) data.livestream_settings = {};
        if (!data.livestream_settings.sensitive_content_settings) data.livestream_settings.sensitive_content_settings = {};
        data.livestream_settings.sensitive_content_settings.is_allowed = true;
        return new Response(JSON.stringify(data), {status: r.status, headers: {'Content-Type':'application/json'}});
      }).catch(() => r)));
    }
    if (url.includes('/preview_premium_stream')) {
      return Promise.resolve(new Response(JSON.stringify({code: 0, data: {is_allowed: true, blurAccessSeconds: 999999, livestream_id: lsId, thumbnail_url: '', status: 'active'}}), {status: 200, headers: {'Content-Type':'application/json'}}));
    }
    if (url.includes('/enter')) {
      return Promise.resolve(new Response(JSON.stringify({code: 0, data: {agora_app_id: 'd8e6b8f6a7b14a6e8a9c0d1e2f3a4b5c', agora_channel_name: 'live_' + lsId, agora_channel_token: '007___' + lsId, agora_rtm_token: '008___' + lsId, agora_uid: 123456, is_live: true}}), {status: 200, headers: {'Content-Type':'application/json'}}));
    }
    return _origFetch(u, o);
  };

  // --- CSS: remove blur ---
  if (!document.getElementById('__karlin-css')) {
    var s = document.createElement('style');
    s.id = '__karlin-css';
    s.textContent = '.blur-xs,.blur-4xl,[class*=blur] { filter: none !important; backdrop-filter: none !important; }';
    document.head.appendChild(s);
  }

  // --- overlay system ---
  function createOverlay(a, imgUrl, idx) {
    if (a.__karlin) return;
    a.__karlin = true;
    var rect = a.getBoundingClientRect();
    var ov = document.createElement('div');
    ov.style.cssText = 'position:fixed;z-index:99999;pointer-events:none;opacity:0;transition:opacity 0.15s;border-radius:12px;overflow:hidden;';
    ov.style.left = rect.x + 'px'; ov.style.top = rect.y + 'px';
    ov.style.width = rect.width + 'px'; ov.style.height = rect.height + 'px';
    var ca = document.createElement('canvas');
    ca.width = Math.round(rect.width); ca.height = Math.round(rect.height);
    ca.style.cssText = 'width:100%;height:100%;display:block;border-radius:12px;';
    ov.appendChild(ca);
    document.body.appendChild(ov);
    var ctx = ca.getContext('2d'), w = ca.width, h = ca.height, animId = null, profileImg = null, active = false;
    if (imgUrl) { var img = new Image(); img.crossOrigin = 'anonymous'; img.onload = () => profileImg = img; img.src = imgUrl; }
    function draw() {
      if (!ctx || !active) { animId = null; return; }
      var t = Date.now() / 1000, g = ctx.createLinearGradient(0,0,w,h);
      g.addColorStop(0, '#1a1a2e'); g.addColorStop(1, '#0f3460');
      ctx.fillStyle = g; ctx.fillRect(0,0,w,h);
      if (profileImg) { var sc = Math.max(w/profileImg.width, h/profileImg.height); ctx.drawImage(profileImg, (w-profileImg.width*sc)/2, (h-profileImg.height*sc)/2, profileImg.width*sc, profileImg.height*sc); ctx.fillStyle = 'rgba(0,0,0,0.3)'; ctx.fillRect(0,0,w,h); }
      var sx = (t*200)%(w*2)-w;
      ctx.fillStyle = 'rgba(255,255,255,0.04)'; ctx.fillRect(sx-40,0,80,h);
      ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(0,h-55,w,55);
      ctx.fillStyle = 'white'; ctx.font = 'bold '+Math.round(h*0.035)+'px Arial'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText('Live Stream',14,h-28);
      var viewers = Math.floor(10+50*(0.5+0.5*Math.sin(t*0.3+idx)));
      ctx.textAlign='right'; ctx.fillStyle='#ccc'; ctx.font=Math.round(h*0.028)+'px Arial'; ctx.fillText(viewers+' watching',w-14,h-28);
      ctx.fillStyle='rgba(0,0,0,0.5)'; ctx.beginPath(); ctx.roundRect(w-110,10,96,26,13); ctx.fill();
      ctx.fillStyle='#aaa'; ctx.font=Math.round(h*0.026)+'px Arial'; ctx.textAlign='center'; ctx.fillText('\uD83D\uDC65 '+viewers,w-62,23);
      ctx.fillStyle='#ff4444'; ctx.beginPath(); ctx.roundRect(10,10,50,22,4); ctx.fill();
      var pulse=0.8+0.2*Math.sin(t*3); ctx.fillStyle='rgba(255,255,255,'+0.3*pulse+')'; ctx.beginPath(); ctx.roundRect(10,10,50,22,4); ctx.fill();
      ctx.fillStyle='white'; ctx.font='bold '+Math.round(h*0.026)+'px Arial'; ctx.textAlign='center'; ctx.fillText('LIVE',35,24);
      animId = requestAnimationFrame(draw);
    }
    function repos() { var r = a.getBoundingClientRect(); ov.style.left=r.x+'px'; ov.style.top=r.y+'px'; ov.style.width=r.width+'px'; ov.style.height=r.height+'px'; if(ca.width!==Math.round(r.width)||ca.height!==Math.round(r.height)){ca.width=Math.round(r.width);ca.height=Math.round(r.height);w=ca.width;h=ca.height;} }
    window.addEventListener('scroll',repos,true); window.addEventListener('resize',repos);
    a.addEventListener('mouseenter',()=>{ repos(); active=true; ov.style.opacity='1'; if(!animId) draw(); });
    a.addEventListener('mouseleave',()=>{ active=false; ov.style.opacity='0'; if(animId){cancelAnimationFrame(animId);animId=null;} });
  }

  // --- poll for cards ---
  setInterval(function() {
    var items = [];
    try { var pinia=document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia; var ds=pinia?._s?.get('discover'); items=(ds&&ds.items)||[]; } catch(_) {}
    document.querySelectorAll('a[href*="/livestream/"]').forEach(function(a,i){
      if (!a.__karlin) createOverlay(a, (items[i]||{}).user?.profile_image?.url || '', i);
      var v=a.querySelector('video'); if(v) v.style.pointerEvents='none';
    });
  }, 600);
  setTimeout(() => { document.querySelectorAll('a[href*="/livestream/"] video').forEach(v=>v.style.pointerEvents='none'); }, 100);

  console.log('[Karlin] Hooks injected. Hover over livestream cards.');
})();