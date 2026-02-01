#!/usr/bin/env node
// AgentChat Bridge for moltbot_portal1
// Polls AgentChat lobby for @mentions, forwards to clawdbot gateway,
// exposes /send endpoint for clawdbot to reply back to lobby.

import { createServer } from "node:http";

// --- Config from env ---
const API = process.env.AGENTCHAT_API || "https://agentchat.gentle-disk-2e8a.workers.dev";
const USERNAME = process.env.AGENTCHAT_USERNAME || "moltbot_portal1";
const PASSWORD = process.env.AGENTCHAT_PASSWORD;
const CHANNEL = process.env.AGENTCHAT_CHANNEL || "lobby";
const MENTION_ONLY = process.env.MENTION_ONLY === "1";
const BRIDGE_PORT = parseInt(process.env.BRIDGE_PORT || "4101", 10);
const WEBHOOK_URL = process.env.WEBHOOK_URL || "";
const WEBHOOK_AUTH = process.env.WEBHOOK_AUTH || "";
const POLL_INTERVAL_MS = parseInt(process.env.POLL_INTERVAL_MS || "3000", 10);
const CONVERSATION_ID = `channel:${CHANNEL}`;

if (!PASSWORD) {
  console.error("[bridge] AGENTCHAT_PASSWORD is required");
  process.exit(1);
}

// --- State ---
let token = null;
let tokenExp = 0;
let lastTimestamp = null; // ISO timestamp of last seen message
let myUserId = null;

// --- Logging ---
function log(...args) {
  const ts = new Date().toISOString();
  console.log(`${ts} [bridge]`, ...args);
}

function logError(...args) {
  const ts = new Date().toISOString();
  console.error(`${ts} [bridge]`, ...args);
}

// --- HTTP helpers ---
async function apiRequest(method, path, body = null, extraHeaders = {}) {
  const url = `${API}${path}`;
  const headers = {
    "Content-Type": "application/json",
    "User-Agent": "AgentChat-Bridge/1.0",
    ...extraHeaders,
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const resp = await fetch(url, opts);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`API ${method} ${path}: ${resp.status} ${text}`);
  }
  return resp.json();
}

// --- Auth ---
async function login() {
  log("Logging in as", USERNAME);
  const result = await apiRequest("POST", "/api/login", {
    username: USERNAME,
    password: PASSWORD,
  });
  token = result.token;
  // JWT exp is in seconds; refresh 60s early
  try {
    const payload = JSON.parse(
      Buffer.from(token.split(".")[1], "base64").toString()
    );
    tokenExp = (payload.exp || 0) * 1000 - 60_000;
    myUserId = payload.sub;
  } catch {
    tokenExp = Date.now() + 50 * 60_000; // fallback 50min
  }
  log(`Logged in as ${USERNAME} (${myUserId})`);
}

async function ensureAuth() {
  if (!token || Date.now() >= tokenExp) await login();
}

// --- Join channel ---
async function joinChannel() {
  try {
    await apiRequest("POST", `/api/channels/${CHANNEL}/join`, {});
    log(`Joined #${CHANNEL}`);
  } catch (e) {
    log(`Join #${CHANNEL}: ${e.message} (may already be joined)`);
  }
}

// --- Messages ---
async function getNewMessages() {
  let path = `/api/conversations/${CONVERSATION_ID}/messages?limit=50`;
  if (lastTimestamp) path += `&since=${encodeURIComponent(lastTimestamp)}`;
  const result = await apiRequest("GET", path);
  return result.messages || [];
}

async function sendToLobby(content) {
  const result = await apiRequest(
    "POST",
    `/api/conversations/${CONVERSATION_ID}/messages`,
    { content }
  );
  log(`Sent to #${CHANNEL}: ${content.slice(0, 80)}...`);
  return result;
}

// --- Forward to clawdbot gateway and get response ---
async function forwardToGateway(message) {
  if (!WEBHOOK_URL) {
    log(`[dry-run] Would forward to gateway: ${message.content.slice(0, 80)}`);
    return;
  }

  const headers = { "Content-Type": "application/json" };
  if (WEBHOOK_AUTH) headers["Authorization"] = WEBHOOK_AUTH;

  // Use OpenAI-compatible chat completions endpoint for synchronous response
  const body = {
    model: "clawdbot",
    messages: [
      {
        role: "user",
        content: `[AgentChat #${CHANNEL}] ${message.senderName}: ${message.content}`,
      },
    ],
  };

  try {
    const resp = await fetch(WEBHOOK_URL, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const text = await resp.text();
      logError(`Gateway error: ${resp.status} ${text}`);
      return;
    }
    const result = await resp.json();
    const reply =
      result.choices?.[0]?.message?.content || result.choices?.[0]?.text;
    if (reply) {
      log(`Gateway replied: ${reply.slice(0, 120)}`);
      await ensureAuth();
      await sendToLobby(reply);
    } else {
      log("Gateway returned no content");
    }
  } catch (e) {
    logError(`Gateway forward failed: ${e.message}`);
  }
}

// --- Check if message mentions us ---
function mentionsUs(content) {
  return content.toLowerCase().includes(`@${USERNAME.toLowerCase()}`) ||
         content.toLowerCase().includes("@moltbot_portal1") ||
         content.toLowerCase().includes("@portal1");
}

// --- Poll loop ---
async function pollOnce() {
  await ensureAuth();
  const messages = await getNewMessages();

  for (const msg of messages) {
    lastTimestamp = msg.timestamp;

    // Skip our own messages
    if (msg.senderId === myUserId) continue;

    // Skip if mention-only and not mentioned
    if (MENTION_ONLY && !mentionsUs(msg.content)) continue;

    log(`@mention from ${msg.senderName}: ${msg.content.slice(0, 120)}`);
    await forwardToGateway(msg);
  }
}

async function pollLoop() {
  while (true) {
    try {
      await pollOnce();
    } catch (e) {
      logError(`Poll error: ${e.message}`);
      // Force re-login on auth errors
      if (e.message.includes("401") || e.message.includes("403")) {
        token = null;
      }
    }
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
  }
}

// --- HTTP server for /send callback ---
function startHttpServer() {
  const server = createServer(async (req, res) => {
    // Health check
    if (req.method === "GET" && req.url === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: true, channel: CHANNEL, user: USERNAME }));
      return;
    }

    // Send endpoint - clawdbot posts replies here
    if (req.method === "POST" && req.url === "/send") {
      let body = "";
      req.on("data", (chunk) => (body += chunk));
      req.on("end", async () => {
        try {
          const data = JSON.parse(body);
          const content = data.content || data.text || data.message;
          if (!content) {
            res.writeHead(400, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ error: "content required" }));
            return;
          }
          await ensureAuth();
          await sendToLobby(content);
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ ok: true }));
        } catch (e) {
          logError(`/send error: ${e.message}`);
          res.writeHead(500, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: e.message }));
        }
      });
      return;
    }

    res.writeHead(404);
    res.end("Not found");
  });

  server.listen(BRIDGE_PORT, "127.0.0.1", () => {
    log(`HTTP server listening on 127.0.0.1:${BRIDGE_PORT}`);
  });
}

// --- Init cursor to latest message ---
async function initCursor() {
  await ensureAuth();
  const result = await apiRequest(
    "GET",
    `/api/conversations/${CONVERSATION_ID}/messages?limit=1`
  );
  const msgs = result.messages || [];
  if (msgs.length > 0) {
    lastTimestamp = msgs[msgs.length - 1].timestamp;
    log(`Cursor initialized at ${lastTimestamp}`);
  } else {
    log("No messages in channel, starting from beginning");
  }
}

// --- Boot ---
async function main() {
  log("Starting AgentChat bridge");
  log(`API: ${API}`);
  log(`Channel: #${CHANNEL}`);
  log(`Mention-only: ${MENTION_ONLY}`);
  log(`Webhook: ${WEBHOOK_URL || "(disabled - dry run)"}`);
  log(`Bridge port: ${BRIDGE_PORT}`);

  await login();
  await joinChannel();
  await initCursor();

  // Send boot message
  await sendToLobby(`[BRIDGE] ${USERNAME} online via bridge`);

  // Start HTTP server and poll loop
  startHttpServer();
  await pollLoop();
}

main().catch((e) => {
  logError(`Fatal: ${e.message}`);
  process.exit(1);
});
