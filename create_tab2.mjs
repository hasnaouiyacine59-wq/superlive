import WebSocket from 'ws';

const BASE = 'http://localhost:9222';

async function main() {
  const ver = await (await fetch(`${BASE}/json/version`)).json();
  const ws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0, pending = {};
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.id && pending[d.id]) { pending[d.id](d); delete pending[d.id]; }
  };
  const send = (m, p) => new Promise(r => { const i = ++id; pending[i] = r; ws.send(JSON.stringify({id: i, method: m, params: p})); });
  const result = await send('Target.createTarget', { url: 'about:blank', type: 'page' });
  console.log(result.result?.targetId);
  ws.close();
}

main().catch(e => { console.error('Error:', e.message); process.exit(1); });
