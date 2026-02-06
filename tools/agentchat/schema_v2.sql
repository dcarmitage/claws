-- AgentChat V2 Schema
-- Migration from v1

-- Agents (new)
CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  role TEXT,
  session_key TEXT,
  capabilities TEXT,  -- JSON array
  status TEXT DEFAULT 'offline',
  status_message TEXT,
  current_task_id TEXT,
  last_heartbeat INTEGER,
  created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Channels (new)
CREATE TABLE IF NOT EXISTS channels (
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  type TEXT DEFAULT 'public',
  topic TEXT,
  created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Channel Members (new)
CREATE TABLE IF NOT EXISTS channel_members (
  channel_id TEXT,
  agent_id TEXT,
  subscribed INTEGER DEFAULT 1,
  joined_at INTEGER DEFAULT (strftime('%s', 'now')),
  PRIMARY KEY (channel_id, agent_id),
  FOREIGN KEY (channel_id) REFERENCES channels(id),
  FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Messages V2 (upgrade from v1)
CREATE TABLE IF NOT EXISTS messages_v2 (
  id TEXT PRIMARY KEY,
  channel_id TEXT,
  task_id TEXT,
  thread_id TEXT,
  sender_id TEXT NOT NULL,
  content TEXT NOT NULL,
  attachments TEXT,  -- JSON array of doc IDs
  created_at INTEGER DEFAULT (strftime('%s', 'now')),
  FOREIGN KEY (channel_id) REFERENCES channels(id),
  FOREIGN KEY (task_id) REFERENCES tasks(id),
  FOREIGN KEY (sender_id) REFERENCES agents(id)
);

-- Tasks (new)
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'inbox',
  priority INTEGER DEFAULT 2,
  channel_id TEXT,
  created_by TEXT,
  created_at INTEGER DEFAULT (strftime('%s', 'now')),
  FOREIGN KEY (channel_id) REFERENCES channels(id),
  FOREIGN KEY (created_by) REFERENCES agents(id)
);

-- Task Assignees (new)
CREATE TABLE IF NOT EXISTS task_assignees (
  task_id TEXT,
  agent_id TEXT,
  assigned_at INTEGER DEFAULT (strftime('%s', 'now')),
  PRIMARY KEY (task_id, agent_id),
  FOREIGN KEY (task_id) REFERENCES tasks(id),
  FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Notifications (new)
CREATE TABLE IF NOT EXISTS notifications (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  type TEXT,
  source_type TEXT,
  source_id TEXT,
  content TEXT,
  delivered INTEGER DEFAULT 0,
  read INTEGER DEFAULT 0,
  created_at INTEGER DEFAULT (strftime('%s', 'now')),
  FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Documents (new)
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  content TEXT,
  type TEXT,
  task_id TEXT,
  created_by TEXT,
  created_at INTEGER DEFAULT (strftime('%s', 'now')),
  FOREIGN KEY (task_id) REFERENCES tasks(id),
  FOREIGN KEY (created_by) REFERENCES agents(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages_v2(channel_id);
CREATE INDEX IF NOT EXISTS idx_messages_task ON messages_v2(task_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages_v2(thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages_v2(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_notifications_agent ON notifications(agent_id);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(agent_id, read);
