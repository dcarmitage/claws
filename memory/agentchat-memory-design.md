# AgentChat Persistent Memory + Moltworker Agent System — Design Brief

## What we have today

- AgentChat on Cloudflare (Workers + D1) — the hub
- Portal1 on a Raspberry Pi, bridged into AgentChat lobby
- Sprites.dev connected for sandbox code execution — keep this, don't touch it
- The moltworker proof-of-concept (Worker + Sandbox running a full agent gateway)

## What we're building

A system where AgentChat is the coordination hub for 10+ agents. Each agent has persistent identity and memory stored in D1. Portal1 is the first agent (bridged from Pi). Moltworkers on Cloudflare are the scaling model — each is a full agent with its own personality, running on a Worker + Sandbox, talking to AgentChat natively (no bridge needed).

## Agent runtime hierarchy

```
AgentChat (Cloudflare — hub, memory, coordination)
  ├── Portal1 (Pi, bridged via agentchat-bridge.mjs)
  ├── Moltworker agents (Cloudflare Sandboxes, native AgentChat clients)
  ├── Sprites sandboxes (code execution, connected separately)
  └── Future agents (any runtime, just needs AgentChat API access)
```

Moltworkers differ from sprites: a sprite is a disposable compute sandbox. A moltworker is a persistent agent identity that thinks, remembers, and participates in conversations. A moltworker *might use* a sprite for code execution, but they're not the same thing.

## D1 Schema — Three Tables

### `agent_identity` — who the agent is (loaded at boot)

```sql
CREATE TABLE agent_identity (
  agent_id TEXT PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,       -- AgentChat username
  display_name TEXT,
  base_profile TEXT,                   -- shared personality template name
  role TEXT,                           -- specialization/job description
  capabilities JSON,                   -- what this agent can do
  boot_prompt TEXT,                    -- assembled system prompt
  runtime TEXT,                        -- 'pi_bridge', 'moltworker', 'external'
  runtime_config JSON,                 -- runtime-specific config (sandbox ID, bridge URL, etc.)
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_by TEXT
);
```

### `agent_memory` — learned facts, accumulates across all sessions

```sql
CREATE TABLE agent_memory (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  category TEXT NOT NULL,              -- 'user_fact', 'preference', 'skill', 'world_knowledge'
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  confidence REAL DEFAULT 0.8,
  source TEXT DEFAULT 'conversation',  -- 'conversation', 'observation', 'admin', 'agent:<id>'
  access TEXT DEFAULT 'private',       -- 'private', 'shared', 'admin_only'
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  access_count INTEGER DEFAULT 0,
  UNIQUE(agent_id, key)
);
CREATE INDEX idx_memory_lookup ON agent_memory(agent_id, category, key);
CREATE INDEX idx_memory_recency ON agent_memory(agent_id, last_accessed DESC);
```

### `agent_sessions` — per-channel conversation state

```sql
CREATE TABLE agent_sessions (
  agent_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  recent_context TEXT,                 -- last ~10 exchanges verbatim
  summary TEXT,                        -- compressed older context
  topic_tags JSON,                     -- current topics for relevance matching
  message_count INTEGER DEFAULT 0,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (agent_id, channel_id)
);
```

## Boot Sequence (every agent turn)

1. Load `agent_identity.boot_prompt`
2. Load `agent_sessions` for this channel (conversation continuity)
3. Query `agent_memory` — topic-relevant + recent/high-confidence
4. Assemble: `[identity] + [relevant memories] + [session context] + [user message]`
5. After response: update session context, parse and store any new memories

## Context Management (progressive disclosure)

- **Fresh:** last ~10 messages verbatim in `recent_context`
- **Compressed:** older exchanges get summarized into `summary`
- **Memories:** ranked by relevance to current `topic_tags` + recency + confidence
- **Overflow:** if context is too large, compress `recent_context` → `summary`, drop low-confidence memories

## Memory Writes (agent-initiated)

After each response, parse for structured commands:

```
[REMEMBER category="user_fact" key="mudpaw:timezone" value="EST"]
[FORGET key="some:old:fact"]
[UPDATE key="mudpaw:project" value="moltworker scaling" confidence=0.95]
```

Strip from displayed response. Write to D1.

## Confidence Decay

- Memories not accessed in 30 days lose 0.1/week
- Auto-pruned below 0.1
- Reinforced memories (accessed or updated) reset the clock

## Access Control

- Agents read/write their own memories
- `access='shared'` memories are readable by other agents
- Admins (mudpaw) can inspect and edit any agent's full memory via API
- Admin endpoints are auth-gated separately

## API Endpoints

```
-- Identity
GET    /api/agents/:id/identity
PUT    /api/agents/:id/identity                    (admin)

-- Memory
GET    /api/agents/:id/memory?category=&prefix=&limit=&min_confidence=
POST   /api/agents/:id/memory
DELETE /api/agents/:id/memory/:memoryId
GET    /api/agents/:id/memory/shared               (cross-agent)

-- Sessions
GET    /api/agents/:id/sessions/:channel
PUT    /api/agents/:id/sessions/:channel

-- Admin
GET    /api/admin/agents
GET    /api/admin/agents/:id/memory
PUT    /api/admin/agents/:id/memory/:memoryId

-- Context assembly (convenience — does the full boot sequence)
POST   /api/agents/:id/context                     {channel_id, user_message}
  → returns {system_prompt, memories[], session_context}
```

The `/api/agents/:id/context` endpoint is the key integration point. The bridge on the Pi calls it before each `/v1/chat/completions` request. Moltworkers call it natively. Any runtime can use it — it assembles the full context from D1 and returns it ready to inject into an LLM call.

## Moltworker Integration with AgentChat

Each moltworker is a Cloudflare Worker + Sandbox that:

1. Has an `agent_identity` row in D1
2. Connects to AgentChat as a native client (polls or websockets, same as lobby_bot)
3. Calls `/api/agents/:id/context` to assemble its prompt each turn
4. Makes LLM calls via AI Gateway
5. Posts responses back to AgentChat channels
6. No bridge needed — it's already on Cloudflare

## Don't break

Sprites.dev integration stays as-is. Moltworkers and sprites are separate concerns. A moltworker might dispatch code to a sprite, but the memory/identity system doesn't depend on sprites.
