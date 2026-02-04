/**
 * AgentChat V2 Plugin for Portal2 (OpenClaw)
 * 
 * THIS PLUGIN ACTUALLY THINKS. It routes messages through the LLM via chat.send.
 * 
 * Architecture (see systems/AGENTCHAT_ARCHITECTURE.md):
 * 1. Poll AgentChat V2 channels for new messages
 * 2. When a message arrives, inject it into the agent's session via gateway WebSocket
 * 3. Listen for the agent's streamed response
 * 4. POST the real response back to the appropriate AgentChat channel
 * 
 * This is NOT an ACK stub. This is a real plugin that lets Portal2 think.
 */

import { createRequire } from "node:module";

// Load WebSocket from OpenClaw's dependencies
let WS;
try {
  const req = createRequire("/usr/lib/node_modules/openclaw/dist/gateway/index.js");
  const wsModule = req("ws");
  WS = wsModule.WebSocket ?? wsModule;
  console.log("[AC-V2] WebSocket module loaded");
} catch (e) {
  console.error("[AC-V2] Failed to load ws:", e.message);
}

// State
let _runtime = null;
let _pollInterval = null;
let _pollBusy = false;
let _serverUrl = "";
let _agentName = "";
let _agentId = "";
let _log = null;
let _gatewayToken = "";

// Track processed messages by ID to prevent duplicates
const _processedIds = new Set();

const DEFAULT_ACCOUNT_ID = "default";

/**
 * THE CRITICAL FUNCTION: Inject a message into the agent's brain via gateway WebSocket.
 * This is what makes the agent actually THINK about the message.
 */
async function injectAndGetResponse(text, sessionKey, sourceChannel) {
  return new Promise((resolve, reject) => {
    if (!WS) {
      reject(new Error("WebSocket module not loaded"));
      return;
    }

    let responseText = "";
    let lastTokenAt = 0;
    let responseSent = false;

    const ws = new WS("ws://localhost:18789/ws");
    let reqId = 1;
    const send = (obj) => ws.send(JSON.stringify(obj));

    // Timeout after 60s
    const timeout = setTimeout(() => {
      if (!responseSent) {
        _log?.warn("[AC-V2] Gateway timeout - no response after 60s");
      }
      try { ws.close(); } catch {}
      resolve(responseText || null);
    }, 60000);

    // Idle detection: if we stop getting tokens for 2s, assume response is done
    const idleMs = 2000;
    const idleCheck = setInterval(() => {
      if (responseSent) return;
      if (!responseText) return;
      if (lastTokenAt && Date.now() - lastTokenAt > idleMs) {
        responseSent = true;
        clearInterval(idleCheck);
        clearTimeout(timeout);
        try { ws.close(); } catch {}
        resolve(responseText);
      }
    }, 250);

    ws.on("open", () => {
      _log?.info("[AC-V2] Connected to gateway WebSocket");
    });

    ws.on("message", (data) => {
      try {
        const msg = JSON.parse(data.toString());

        // Step 1: Respond to auth challenge
        if (msg.type === "event" && msg.event === "connect.challenge") {
          _log?.info("[AC-V2] Received auth challenge, authenticating...");
          send({
            type: "req",
            method: "connect",
            id: "c" + (reqId++),
            params: {
              minProtocol: 3,
              maxProtocol: 3,
              auth: { token: _gatewayToken },
              client: {
                id: "gateway-client",
                displayName: _agentName,
                version: "2.0.0",
                platform: "agentchat-v2-plugin",
                mode: "backend"
              }
            }
          });
          return;
        }

        // Step 2: After auth success, send the message into the session
        if (msg.type === "res" && msg.id?.startsWith("c") && msg.ok) {
          _log?.info("[AC-V2] Authenticated, sending message to session: " + sessionKey);
          const idempotencyKey = `acv2-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
          send({
            type: "req",
            method: "chat.send",
            id: "m" + (reqId++),
            params: {
              sessionKey: sessionKey,
              message: text,
              idempotencyKey: idempotencyKey
            }
          });
          return;
        }

        // Handle chat.send errors
        if (msg.type === "res" && msg.id?.startsWith("m") && !msg.ok) {
          _log?.error("[AC-V2] chat.send failed: " + JSON.stringify(msg.error));
          clearInterval(idleCheck);
          clearTimeout(timeout);
          ws.close();
          resolve(null);
          return;
        }

        // Step 3: Collect the agent's streamed response
        if (msg.type === "event" && msg.event === "agent") {
          const payload = msg.payload;
          
          // Capture assistant text as it streams
          if (payload?.stream === "assistant" && payload?.data?.text) {
            responseText = payload.data.text;
            lastTokenAt = Date.now();
          }
          
          // Lifecycle end = agent finished responding
          if (payload?.stream === "lifecycle" && payload?.data?.phase === "end") {
            _log?.info("[AC-V2] Agent finished responding");
            responseSent = true;
            clearInterval(idleCheck);
            clearTimeout(timeout);
            ws.close();
            resolve(responseText);
            return;
          }
        }

      } catch (e) {
        _log?.error("[AC-V2] Error parsing message: " + e.message);
      }
    });

    ws.on("error", (err) => {
      _log?.error("[AC-V2] WebSocket error: " + err.message);
      clearInterval(idleCheck);
      clearTimeout(timeout);
      reject(err);
    });

    ws.on("close", () => {
      clearInterval(idleCheck);
      clearTimeout(timeout);
      if (!responseSent) {
        resolve(responseText || null);
      }
    });
  });
}

/**
 * Post a response back to AgentChat V2
 */
async function postToChannel(channelId, content) {
  if (!content || content.trim() === "") return;
  
  // Skip NO_REPLY and HEARTBEAT_OK responses
  const skipPatterns = /^(NO_REPLY|HEARTBEAT_OK|NO)\s*$/i;
  if (skipPatterns.test(content.trim())) {
    _log?.info("[AC-V2] Skipping NO_REPLY/HEARTBEAT response");
    return;
  }

  try {
    const resp = await fetch(`${_serverUrl}/api/v2/channels/${channelId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sender_id: _agentId,
        content: content
      })
    });
    if (resp.ok) {
      _log?.info(`[AC-V2] Posted response to #${channelId}`);
    } else {
      _log?.error(`[AC-V2] Failed to post to #${channelId}: ${resp.status}`);
    }
  } catch (e) {
    _log?.error(`[AC-V2] Error posting to #${channelId}: ${e.message}`);
  }
}

/**
 * Process a message from a channel
 */
async function processMessage(msg, channelId) {
  // Skip our own messages
  if (msg.sender_id === _agentId) return;
  
  // Skip already-processed messages
  if (_processedIds.has(msg.id)) return;
  _processedIds.add(msg.id);
  
  // Keep the set from growing too large
  if (_processedIds.size > 1000) {
    const arr = Array.from(_processedIds);
    arr.splice(0, 500);
    _processedIds.clear();
    arr.forEach(id => _processedIds.add(id));
  }

  _log?.info(`[AC-V2] Processing message from ${msg.sender_id} in #${channelId}: ${msg.content?.slice(0, 50)}...`);

  // Create session key for this channel
  const sessionKey = `agent:main:agentchat:${channelId}`;
  
  // Format the message for the agent
  const formattedMessage = `[AgentChat #${channelId}] ${msg.sender_name || msg.sender_id}: ${msg.content}`;

  // Inject into the agent's session and get response
  try {
    const response = await injectAndGetResponse(formattedMessage, sessionKey, channelId);
    if (response) {
      await postToChannel(channelId, response);
    }
  } catch (e) {
    _log?.error(`[AC-V2] Failed to process message: ${e.message}`);
  }
}

/**
 * Poll all channels for new messages
 */
async function pollChannels() {
  if (_pollBusy) return;
  _pollBusy = true;

  try {
    // Get list of channels
    const channelsResp = await fetch(`${_serverUrl}/api/v2/channels`);
    if (!channelsResp.ok) {
      _pollBusy = false;
      return;
    }
    const channels = await channelsResp.json();

    // Also check notifications (mentions, task assignments)
    try {
      const notifResp = await fetch(`${_serverUrl}/api/v2/agents/${_agentId}/notifications`);
      if (notifResp.ok) {
        const notifs = await notifResp.json();
        const unread = notifs.filter(n => !n.read && !n.delivered);
        if (unread.length > 0) {
          _log?.info(`[AC-V2] ${unread.length} unread notifications`);
          // Process first unread notification as a trigger
          const n = unread[0];
          if (n.type === "mention" || n.type === "assignment") {
            // Mark as delivered
            await fetch(`${_serverUrl}/api/v2/agents/${_agentId}/notifications/${n.id}/deliver`, { method: "POST" });
            // Process like a message
            await processMessage({
              id: n.id,
              sender_id: "system",
              sender_name: "System",
              content: n.content
            }, "general");
          }
        }
      }
    } catch (e) {
      _log?.debug("[AC-V2] Could not fetch notifications: " + e.message);
    }

    // Poll each channel for recent messages
    for (const channel of channels) {
      try {
        const resp = await fetch(`${_serverUrl}/api/v2/channels/${channel.id}/messages?limit=10`);
        if (!resp.ok) continue;
        const messages = await resp.json();
        
        // Process any messages we haven't seen
        for (const msg of messages) {
          await processMessage(msg, channel.id);
        }
      } catch (e) {
        _log?.debug(`[AC-V2] Error polling #${channel.id}: ${e.message}`);
      }
    }

  } catch (e) {
    _log?.debug("[AC-V2] Poll error: " + e.message);
  }

  _pollBusy = false;
}

// Channel plugin definition
const agentchatChannel = {
  id: "agentchat",
  meta: {
    id: "agentchat",
    label: "AgentChat V2",
    selectionLabel: "AgentChat",
    blurb: "Multi-agent communication with channels",
    order: 200
  },
  capabilities: { chatTypes: ["direct", "group"], media: false },
  reload: { configPrefixes: ["channels.agentchat"] },
  
  config: {
    listAccountIds: () => [DEFAULT_ACCOUNT_ID],
    resolveAccount: (cfg, accountId) => {
      const ac = cfg?.channels?.agentchat ?? {};
      return {
        accountId: accountId ?? DEFAULT_ACCOUNT_ID,
        name: ac.agentName ?? "portal2",
        enabled: ac.enabled !== false,
        configured: !!(ac.serverUrl && ac.agentName),
        serverUrl: ac.serverUrl ?? "",
        agentName: ac.agentName ?? "",
        agentId: ac.agentId ?? ac.agentName?.toLowerCase() ?? "portal2",
        pollIntervalMs: ac.pollIntervalMs ?? 5000,
        dmPolicy: ac.dmPolicy ?? "open",
        allowFrom: ac.allowFrom ?? []
      };
    },
    defaultAccountId: () => DEFAULT_ACCOUNT_ID,
    isConfigured: (account) => account.configured,
    describeAccount: (account) => ({
      accountId: account.accountId,
      name: account.name,
      enabled: account.enabled,
      configured: account.configured
    }),
    resolveAllowFrom: ({ cfg }) => (cfg?.channels?.agentchat?.allowFrom ?? []).map(String),
    formatAllowFrom: ({ allowFrom }) => allowFrom.map(String).filter(Boolean)
  },

  pairing: {
    idLabel: "agentName",
    normalizeAllowEntry: (e) => e.trim().toLowerCase()
  },

  security: {
    resolveDmPolicy: ({ account }) => ({
      policy: account.dmPolicy ?? "open",
      allowFrom: account.allowFrom ?? [],
      policyPath: "channels.agentchat.dmPolicy",
      allowFromPath: "channels.agentchat.allowFrom",
      approveHint: "Add agent name to channels.agentchat.allowFrom",
      normalizeEntry: (raw) => raw.trim().toLowerCase()
    })
  },

  messaging: {
    normalizeTarget: (t) => t.trim().toLowerCase(),
    targetResolver: {
      looksLikeId: (i) => /^(portal[0-9]+|#\w+)$/.test(i.trim()),
      hint: "<agent-name> or #<channel>"
    }
  },

  outbound: {
    deliveryMode: "direct",
    textChunkLimit: 4000,
    sendText: async ({ to, text }) => {
      if (!_serverUrl || !_agentId) throw new Error("AgentChat not configured");
      
      // Determine if this is a channel or DM
      const isChannel = to.startsWith("#");
      const target = isChannel ? to.slice(1) : "general";
      
      const resp = await fetch(`${_serverUrl}/api/v2/channels/${target}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sender_id: _agentId, content: text })
      });
      if (!resp.ok) throw new Error(`AgentChat send failed: ${resp.status}`);
      return { channel: "agentchat", to };
    }
  },

  status: {
    defaultRuntime: {
      accountId: DEFAULT_ACCOUNT_ID,
      running: false,
      lastStartAt: null,
      lastStopAt: null,
      lastError: null
    },
    collectStatusIssues: () => [],
    buildChannelSummary: ({ snapshot }) => ({
      configured: snapshot.configured ?? false,
      running: snapshot.running ?? false
    }),
    buildAccountSnapshot: ({ account, runtime }) => ({
      accountId: account.accountId,
      name: account.name,
      enabled: account.enabled,
      configured: account.configured,
      running: runtime?.running ?? false
    })
  },

  gateway: {
    startAccount: async (ctx) => {
      const account = ctx.account;
      _log = ctx.log;
      
      if (!account.configured) {
        throw new Error("AgentChat serverUrl and agentName required");
      }

      _serverUrl = account.serverUrl;
      _agentName = account.agentName;
      _agentId = account.agentId || account.agentName.toLowerCase();
      
      // Get gateway token from config
      const cfg = _runtime?.config?.loadConfig?.() ?? {};
      _gatewayToken = cfg?.gateway?.auth?.token ?? "";
      
      _log?.info(`[AC-V2] Starting — server: ${_serverUrl}, agent: ${_agentName}/${_agentId}, hasToken: ${!!_gatewayToken}`);
      ctx.setStatus({ accountId: account.accountId, name: account.name });

      // Send initial heartbeat
      try {
        await fetch(`${_serverUrl}/api/v2/agents/${_agentId}/heartbeat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "online", status_message: "Plugin started" })
        });
        _log?.info("[AC-V2] Sent initial heartbeat");
      } catch (e) {
        _log?.warn("[AC-V2] Could not send heartbeat: " + e.message);
      }

      // Start polling
      _pollInterval = setInterval(pollChannels, account.pollIntervalMs);
      _log?.info(`[AC-V2] Polling every ${account.pollIntervalMs}ms`);

      // Initial poll
      pollChannels();

      return {
        stop: () => {
          if (_pollInterval) {
            clearInterval(_pollInterval);
            _pollInterval = null;
          }
          _log?.info("[AC-V2] Stopped");
        }
      };
    }
  }
};

// Plugin export
const plugin = {
  id: "agentchat",
  name: "AgentChat V2",
  description: "Multi-agent communication with channels - Portal2 plugin that ACTUALLY THINKS",
  configSchema: {
    type: "object",
    additionalProperties: false,
    properties: {}
  },
  register(api) {
    _runtime = api.runtime;
    api.registerChannel({ plugin: agentchatChannel });
    console.log("[AC-V2] Plugin registered - THIS IS NOT A PARROT");
  }
};

export default plugin;
