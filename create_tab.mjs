import WebSocket from 'ws';

const BASE = 'http://localhost:9222';

async function main() {
  // Create fresh tab
  const ver = await (await fetch(BASE + '/json/version')).json();
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
  console.log(tid);
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
