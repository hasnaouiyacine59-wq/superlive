import WebSocket from 'ws';

const BASE = 'http://localhost:9222';
const TARGET_URL = 'https://superlive.chat/fr/discover';

async function createTab() {
  // Create a FRESH tab via browser websocket (no pre-registered scripts)
  const ver = await (await fetch(`${BASE}/json/version`)).json();
  const bws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res, rej) => { bws.onopen = res; bws.onerror = rej; });
  let id = 0, pending = {};
  bws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; }
  };
  const send = (m, p) => new Promise(r => { const msgId = ++id; pending[msgId] = r; bws.send(JSON.stringify({id: msgId, method: m, params: p})); });
  
  const result = await send('Target.createTarget', { url: 'about:blank', type: 'page' });
  const tid = result.result?.targetId;
  bws.close();
  await new Promise(r => setTimeout(r, 1500));
  
  // Get WebSocket URL for this tab
  const tabs = await (await fetch(`${BASE}/json`)).json();
  const tab = tabs.find(t => t.id === tid);
  if (!tab) throw new Error('Created tab not found');
  return tab;
}

async function main() {
  console.log('Creating fresh tab (no hooks)...');
  const tab = await createTab();

  const ws = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0, pending = {};
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; }
  };
  const send = (m, p) => new Promise(r => { const msgId = ++id; pending[msgId] = r; ws.send(JSON.stringify({id: msgId, method: m, params: p})); });

  // Enable Network + Page
  await send('Network.enable');
  await send('Page.enable');

  // Track network
  const requests = [];
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.method === 'Network.requestWillBeSent') {
      const req = d.params.request;
      requests.push({ id: d.params.requestId, url: req.url, method: req.method, type: req.type });
    }
    if (d.method === 'Network.responseReceived') {
      const resp = d.params.response;
      const r = requests.find(x => x.id === d.params.requestId);
      if (r) { r.status = resp.status; r.mimeType = resp.mimeType; }
    }
    if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; }
  };

  // Navigate
  console.log('Navigating to', TARGET_URL);
  await send('Page.navigate', { url: TARGET_URL });

  // Wait for page
  for (let i = 0; i < 90; i++) {
    const r = await send('Runtime.evaluate', {
      expression: 'document.readyState',
      returnByValue: true,
      timeout: 3000
    });
    const state = r.result?.result?.value;
    if (state === 'complete') break;
    await new Promise(r => setTimeout(r, 1000));
  }
  console.log('Page loaded');

  // Wait for livestream links
  for (let i = 0; i < 60; i++) {
    const r = await send('Runtime.evaluate', {
      expression: 'document.querySelectorAll("a[href*=\\\\\"/livestream/\\\\\"]").length',
      returnByValue: true,
      timeout: 3000
    });
    const count = r.result?.result?.value || 0;
    if (count > 0) { console.log('Found', count, 'livestream links'); break; }
    await new Promise(r => setTimeout(r, 1000));
  }

  // Examine cards for premium indicators
  const cardInfo = await send('Runtime.evaluate', {
    expression: `(function() {
      const links = document.querySelectorAll("a[href*=\\\"/livestream/\\\"]");
      const results = [];
      for (let i = 0; i < Math.min(links.length, 15); i++) {
        const a = links[i];
        const rect = a.getBoundingClientRect();
        const classes = a.className;
        const imgs = a.querySelectorAll('img');
        const videos = a.querySelectorAll('video');
        // Check for premium/private indicators
        const innerText = a.textContent.toLowerCase();
        const indicators = [];
        if (innerText.includes('premium')) indicators.push('premium');
        if (innerText.includes('private')) indicators.push('private');
        if (innerText.includes('vip')) indicators.push('vip');
        if (innerText.includes('lock')) indicators.push('lock');
        if (innerText.includes('member')) indicators.push('member');
        // Check data attributes
        const dataAttrs = {};
        for (const attr of a.attributes) {
          if (attr.name.startsWith('data-')) dataAttrs[attr.name] = attr.value.substring(0, 80);
        }
        results.push({
          idx: i,
          href: a.href,
          rect: { x: ~~rect.x, y: ~~rect.y, w: ~~rect.width, h: ~~rect.height },
          classes: classes.substring(0, 150),
          imgCount: imgs.length,
          videoCount: videos.length,
          indicators,
          dataAttrs,
          text: (a.textContent || '').substring(0, 100).replace(/\\s+/g, ' ').trim()
        });
      }
      return JSON.stringify(results, null, 2);
    })()`,
    returnByValue: true,
    timeout: 10000
  });
  console.log('\n=== Card analysis ===');
  console.log(cardInfo.result?.result?.value || 'N/A');

  // Clear request log
  requests.length = 0;

  // Pick the first visible card and hover
  console.log('\n=== Hovering over first card ===');
  
  // First get the Pinia store data for this card to see if it's premium
  const storeData = await send('Runtime.evaluate', {
    expression: `(function() {
      try {
        const p = document.getElementById('__nuxt')?.__vue_app__?.config?.globalProperties?.$pinia;
        const s = p?._s?.get('discover');
        if (!s || !s.items) return 'no store';
        const items = s.items;
        return JSON.stringify(items.slice(0, 3).map(i => ({
          id: i.id,
          user: i.user?.username,
          isPrivate: i.is_private,
          isPremium: i.is_premium,
          status: i.stream_details?.status,
          is_allowed: i.stream_details?.is_allowed,
          allowed: i.is_allowed,
          disallowed_reason: i.disallowed_reason,
          preview_allowed: i.stream_details?.preview_allowed,
          hasTitleImg: !!i.stream_details?.title_image_url
        })), null, 2);
      } catch(e) { return 'error: ' + e.message; }
    })()`,
    returnByValue: true,
    timeout: 10000
  });
  console.log('\n=== Pinia store data for first 3 items ===');
  console.log(storeData.result?.result?.value || 'N/A');

  // Now hover
  await send('Runtime.evaluate', {
    expression: `(function() {
      const a = document.querySelector("a[href*=\\\"/livestream/\\\"]");
      if (!a) return 'no link found';
      const enter = new MouseEvent('mouseenter', { bubbles: true, cancelable: true, view: window, clientX: 100, clientY: 100 });
      const over = new MouseEvent('mouseover', { bubbles: true, cancelable: true, view: window, clientX: 100, clientY: 100 });
      a.dispatchEvent(enter);
      a.dispatchEvent(over);
      return 'HOVER on: ' + a.href;
    })()`,
    returnByValue: true
  });

  // Wait for network
  await new Promise(r => setTimeout(r, 5000));

  // Print hover-triggered requests
  console.log('\n=== Network requests during hover ===');
  const seen = new Set();
  for (const req of requests) {
    if (!seen.has(req.url)) {
      seen.add(req.url);
      console.log(`  ${req.method} ${req.url} [${req.status || 'pending'}] [${req.type || '?'}]`);
    }
  }
  if (requests.length === 0) console.log('  (no new network requests)');

  // Inspect DOM after hover — what changes?
  const domAfter = await send('Runtime.evaluate', {
    expression: `(function() {
      const a = document.querySelector("a[href*=\\\"/livestream/\\\"]");
      if (!a) return 'no link';
      const v = a.querySelector('video');
      const imgs = a.querySelectorAll('img');
      const style = window.getComputedStyle(a.querySelector('video,img,div') || a);
      return JSON.stringify({
        hasVideo: !!v,
        videoPaused: v ? v.paused : null,
        videoSrc: v ? (v.src || v.srcObject ? '[set]' : 'none') : null,
        imgSrcs: Array.from(imgs).map(x => (x.src || '').substring(0, 80)),
        aStyle: a.getAttribute('style'),
        opacity: style.opacity,
        transform: style.transform,
        pointerEvents: style.pointerEvents,
        classes: a.className.substring(0, 150)
      }, null, 2);
    })()`,
    returnByValue: true,
    timeout: 5000
  });
  console.log('\n=== DOM after hover ===');
  console.log(domAfter.result?.result?.value || 'N/A');

  // Check for any XHR/fetch activity in console
  const consoleCheck = await send('Runtime.evaluate', {
    expression: `(function() {
      // Check what API calls were made
      const entries = performance.getEntriesByType('resource');
      const apiCalls = entries
        .filter(e => e.name.includes('api'))
        .map(e => ({ url: e.name.substring(0, 120), dur: ~~e.duration, type: e.initiatorType }));
      return JSON.stringify(apiCalls.slice(0, 15), null, 2);
    })()`,
    returnByValue: true,
    timeout: 5000
  });
  console.log('\n=== Performance API calls ===');
  console.log(consoleCheck.result?.result?.value || 'N/A');

  ws.close();
  console.log('\nDone. The tab is still open if you want to inspect manually.');
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
