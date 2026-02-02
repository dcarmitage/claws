#!/usr/bin/env node
// Connect to OpenClaw gateway and send system event
const { WebSocket } = require('/usr/lib/node_modules/openclaw/node_modules/ws/index.js');
const MSG = process.argv[2] || 'AgentChat: check messages';
const ws = new WebSocket('ws://localhost:18789/ws');
let reqId = 1;

function send(obj) { ws.send(JSON.stringify(obj)); }

ws.on('open', () => {});
ws.on('message', (d) => {
  const data = JSON.parse(d.toString());
  
  if (data.type === 'event' && data.event === 'connect.challenge') {
    send({
      type: 'req',
      method: 'connect',
      id: 'c' + (reqId++),
      params: {
        minProtocol: 3, maxProtocol: 3,
        client: { id: 'gateway-client', version: '1.0', platform: 'linux', mode: 'backend' },
        caps: [],
        auth: { token: '7ca99e6d016069302ab5826f3acdd889760c7812837ba42f' },
        role: 'operator',
        scopes: ['operator.admin']
      }
    });
    return;
  }
  
  // Connected successfully
  if (data.type === 'res' && data.ok === true && data.id && data.id.startsWith('c')) {
    // Send system event
    send({
      type: 'req',
      method: 'system-event',
      id: 'se' + (reqId++),
      params: { text: MSG, mode: 'now' }
    });
    return;
  }
  
  // System event response
  if (data.type === 'res' && data.id && data.id.startsWith('se')) {
    console.log(data.ok ? 'ok' : 'error: ' + JSON.stringify(data.error));
    ws.close();
    process.exit(data.ok ? 0 : 1);
  }
});

ws.on('error', (e) => { console.error('ws:', e.message); process.exit(1); });
ws.on('close', (code, reason) => { if (code !== 1000) console.log('close:', code, reason?.toString()); });
setTimeout(() => { console.error('timeout'); process.exit(1); }, 8000);
