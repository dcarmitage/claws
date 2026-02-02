/**
 * AgentChat Channel Plugin for Clawdbot/OpenClaw
 * 
 * Connects to an AgentChat HTTP server and treats it as a real messaging channel.
 * Messages from other agents arrive as proper chat turns with full context.
 */

let _runtime = null;
let _pollInterval = null;
let _lastTs = 0;
let _serverUrl = "";
let _agentName = "";
let _log = null;

const DEFAULT_ACCOUNT_ID = "default";

const agentchatChannel = {
  id: "agentchat",
  meta: {
    id: "agentchat",
    label: "AgentChat",
    selectionLabel: "AgentChat",
    docsPath: "/channels/agentchat",
    docsLabel: "agentchat",
    blurb: "Bot-to-bot messaging via AgentChat server",
    order: 200,
  },
  capabilities: {
    chatTypes: ["direct"],
    media: false,
  },
  reload: { configPrefixes: ["channels.agentchat"] },

  config: {
    listAccountIds: () => [DEFAULT_ACCOUNT_ID],
    resolveAccount: (cfg, accountId) => {
      const ac = cfg?.channels?.agentchat ?? {};
      return {
        accountId: accountId ?? DEFAULT_ACCOUNT_ID,
        name: ac.agentName ?? "portal1",
        enabled: ac.enabled !== false,
        configured: !!(ac.serverUrl && ac.agentName),
        serverUrl: ac.serverUrl ?? "",
        agentName: ac.agentName ?? "",
        pollIntervalMs: ac.pollIntervalMs ?? 3000,
        dmPolicy: ac.dmPolicy ?? "open",
        allowFrom: ac.allowFrom ?? [],
      };
    },
    defaultAccountId: () => DEFAULT_ACCOUNT_ID,
    isConfigured: (account) => account.configured,
    describeAccount: (account) => ({
      accountId: account.accountId,
      name: account.name,
      enabled: account.enabled,
      configured: account.configured,
    }),
    resolveAllowFrom: ({ cfg, accountId }) => {
      const ac = cfg?.channels?.agentchat ?? {};
      return (ac.allowFrom ?? []).map(String);
    },
    formatAllowFrom: ({ allowFrom }) => allowFrom.map(String).filter(Boolean),
  },

  pairing: {
    idLabel: "agentName",
    normalizeAllowEntry: (entry) => entry.trim().toLowerCase(),
  },

  security: {
    resolveDmPolicy: ({ account }) => ({
      policy: account.dmPolicy ?? "open",
      allowFrom: account.allowFrom ?? [],
      policyPath: "channels.agentchat.dmPolicy",
      allowFromPath: "channels.agentchat.allowFrom",
      approveHint: "Add the agent name to channels.agentchat.allowFrom",
      normalizeEntry: (raw) => raw.trim().toLowerCase(),
    }),
  },

  messaging: {
    normalizeTarget: (target) => target.trim().toLowerCase(),
    targetResolver: {
      looksLikeId: (input) => /^portal[0-9]+$/.test(input.trim()),
      hint: "<agent-name>",
    },
  },

  outbound: {
    deliveryMode: "direct",
    textChunkLimit: 4000,
    sendText: async ({ to, text, accountId }) => {
      if (!_serverUrl || !_agentName) {
        throw new Error("AgentChat not configured");
      }
      const resp = await fetch(`${_serverUrl}/api/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sender: _agentName, text: text ?? "" }),
      });
      if (!resp.ok) {
        const err = await resp.text();
        throw new Error(`AgentChat send failed: ${resp.status} ${err}`);
      }
      _log?.info(`[agentchat] Sent message to ${to}: ${(text ?? "").slice(0, 60)}...`);
      return { channel: "agentchat", to };
    },
  },

  status: {
    defaultRuntime: {
      accountId: DEFAULT_ACCOUNT_ID,
      running: false,
      lastStartAt: null,
      lastStopAt: null,
      lastError: null,
    },
    collectStatusIssues: () => [],
    buildChannelSummary: ({ snapshot }) => ({
      configured: snapshot.configured ?? false,
      running: snapshot.running ?? false,
    }),
    buildAccountSnapshot: ({ account, runtime }) => ({
      accountId: account.accountId,
      name: account.name,
      enabled: account.enabled,
      configured: account.configured,
      running: runtime?.running ?? false,
    }),
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

      ctx.log?.info(`[agentchat] Starting — server: ${_serverUrl}, agent: ${_agentName}`);
      ctx.setStatus({ accountId: account.accountId, name: account.name });

      // Get initial timestamp (skip old messages)
      try {
        const resp = await fetch(`${_serverUrl}/api/messages?since=0&limit=1000`);
        const msgs = await resp.json();
        if (msgs.length > 0) {
          _lastTs = msgs[msgs.length - 1].ts;
          ctx.log?.info(`[agentchat] Skipping ${msgs.length} existing messages, starting from ts=${_lastTs}`);
        }
      } catch (e) {
        ctx.log?.warn(`[agentchat] Could not fetch initial messages: ${e.message}`);
      }

      // Poll for new messages
      _pollInterval = setInterval(async () => {
        try {
          const resp = await fetch(`${_serverUrl}/api/messages?since=${_lastTs}&limit=50`);
          if (!resp.ok) return;
          const msgs = await resp.json();

          for (const msg of msgs) {
            // Skip our own messages
            if (msg.sender === _agentName) {
              _lastTs = msg.ts;
              continue;
            }

            _lastTs = msg.ts;
            ctx.log?.info(`[agentchat] Inbound from ${msg.sender}: ${msg.text.slice(0, 80)}...`);

            // Inject as a real inbound message
            await _runtime.channel.reply.handleInboundMessage({
              channel: "agentchat",
              accountId: account.accountId,
              senderId: msg.sender,
              chatType: "direct",
              chatId: msg.sender,
              text: msg.text,
              reply: async (responseText) => {
                // Send reply back to AgentChat
                await fetch(`${_serverUrl}/api/send`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ sender: _agentName, text: responseText }),
                });
                ctx.log?.info(`[agentchat] Replied to ${msg.sender}: ${responseText.slice(0, 60)}...`);
              },
            });
          }
        } catch (e) {
          // Silently retry on connection errors
          ctx.log?.debug(`[agentchat] Poll error: ${e.message}`);
        }
      }, account.pollIntervalMs);

      ctx.log?.info(`[agentchat] Polling every ${account.pollIntervalMs}ms`);

      return {
        stop: () => {
          if (_pollInterval) {
            clearInterval(_pollInterval);
            _pollInterval = null;
          }
          ctx.log?.info("[agentchat] Stopped");
        },
      };
    },
  },
};

const plugin = {
  id: "agentchat",
  name: "AgentChat",
  description: "Bot-to-bot messaging via AgentChat server",
  configSchema: { type: "object", additionalProperties: false, properties: {} },
  register(api) {
    _runtime = api.runtime;
    api.registerChannel({ plugin: agentchatChannel });
  },
};

export default plugin;
