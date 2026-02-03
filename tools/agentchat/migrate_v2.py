#!/usr/bin/env python3
"""Migrate AgentChat from v1 to v2 schema."""

import sqlite3
import uuid
import time
import json

DB_PATH = '/home/clawd/tools/agentchat/chat.db'
SCHEMA_PATH = '/home/clawd/tools/agentchat/schema_v2.sql'

def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Run schema
    print("📦 Creating V2 tables...")
    with open(SCHEMA_PATH) as f:
        cursor.executescript(f.read())
    conn.commit()
    
    # Check if already migrated
    cursor.execute("SELECT COUNT(*) FROM agents")
    if cursor.fetchone()[0] > 0:
        print("⚠️  Already migrated (agents exist). Skipping.")
        return
    
    # Create default agents
    print("🤖 Creating agents...")
    agents = [
        ('portal1', 'Portal1', 'Media Librarian', 'agent:main:main', 
         json.dumps(['camera', 'media', 'catalog']), 'online'),
        ('portal2', 'Portal2', 'Research Agent', 'agent:research:main',
         json.dumps(['research', 'code', 'analysis']), 'offline'),
    ]
    for agent in agents:
        cursor.execute("""
            INSERT INTO agents (id, name, role, session_key, capabilities, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (*agent, int(time.time())))
    
    # Create default channels
    print("📢 Creating channels...")
    channels = [
        ('general', 'general', 'public', 'General discussion'),
        ('builds', 'builds', 'public', 'Build coordination and updates'),
    ]
    for ch in channels:
        cursor.execute("""
            INSERT INTO channels (id, name, type, topic, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (*ch, int(time.time())))
    
    # Add agents to channels
    print("👥 Adding agents to channels...")
    for ch_id in ['general', 'builds']:
        for agent_id in ['portal1', 'portal2']:
            cursor.execute("""
                INSERT INTO channel_members (channel_id, agent_id, subscribed, joined_at)
                VALUES (?, ?, 1, ?)
            """, (ch_id, agent_id, int(time.time())))
    
    # Migrate old messages to #general
    print("💬 Migrating messages...")
    cursor.execute("SELECT * FROM messages ORDER BY ts")
    old_messages = cursor.fetchall()
    
    for msg in old_messages:
        sender = msg['sender'].lower()
        sender_id = 'portal1' if sender == 'portal1' else 'portal2'
        msg_id = f"msg-{uuid.uuid4().hex[:8]}"
        created_at = int(msg['ts'])
        
        cursor.execute("""
            INSERT INTO messages_v2 (id, channel_id, sender_id, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (msg_id, 'general', sender_id, msg['text'], created_at))
    
    conn.commit()
    
    # Stats
    cursor.execute("SELECT COUNT(*) FROM messages_v2")
    msg_count = cursor.fetchone()[0]
    
    print(f"""
✅ Migration complete!

Stats:
  - Agents: 2 (Portal1, Portal2)
  - Channels: 2 (#general, #builds)
  - Messages migrated: {msg_count}
  - Old table preserved: messages (v1 backup)
""")
    
    conn.close()

if __name__ == '__main__':
    migrate()
