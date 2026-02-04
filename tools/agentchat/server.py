#!/usr/bin/env python3
"""AgentChat V2 Server - HTTP + WebSocket support."""

import asyncio
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional
import subprocess

# Try websockets, fall back to no WS support
try:
    import websockets
    from websockets.server import serve as ws_serve
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("⚠️  websockets not installed - WebSocket support disabled")

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

DB_PATH = '/home/clawd/tools/agentchat/chat.db'
HTTP_PORT = 9090
WS_PORT = 9091
WEBHOOK_CONFIG = '/home/clawd/tools/agentchat/webhooks.json'

# Connected WebSocket clients: {agent_id: websocket}
ws_clients = {}

# ============ Database Helpers ============

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def dict_from_row(row):
    return dict(row) if row else None

# ============ Agent Operations ============

def get_agents():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agents ORDER BY name")
    agents = [dict_from_row(r) for r in cursor.fetchall()]
    conn.close()
    return agents

def get_agent(agent_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
    agent = dict_from_row(cursor.fetchone())
    conn.close()
    return agent

def update_agent_heartbeat(agent_id, status='online', status_message=None, current_task_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE agents 
        SET last_heartbeat = ?, status = ?, status_message = COALESCE(?, status_message),
            current_task_id = COALESCE(?, current_task_id)
        WHERE id = ?
    """, (int(time.time()), status, status_message, current_task_id, agent_id))
    conn.commit()
    conn.close()

# ============ Channel Operations ============

def get_channels():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM channels ORDER BY name")
    channels = [dict_from_row(r) for r in cursor.fetchall()]
    conn.close()
    return channels

def get_channel_messages(channel_id, since=0, limit=100):
    conn = get_db()
    cursor = conn.cursor()
    # Get newest messages first, then reverse for chronological order
    cursor.execute("""
        SELECT m.*, a.name as sender_name 
        FROM messages_v2 m
        JOIN agents a ON m.sender_id = a.id
        WHERE m.channel_id = ? AND m.created_at > ?
        ORDER BY m.created_at DESC
        LIMIT ?
    """, (channel_id, since, limit))
    messages = [dict_from_row(r) for r in cursor.fetchall()]
    messages.reverse()  # Return in chronological order (oldest first)
    conn.close()
    return messages

def post_channel_message(channel_id, sender_id, content, thread_id=None):
    created_at = int(time.time())
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Deduplication: reject if same sender+content in last 10 seconds
    cursor.execute("""
        SELECT id FROM messages_v2 
        WHERE sender_id = ? AND content = ? AND created_at > ?
        LIMIT 1
    """, (sender_id, content, created_at - 10))
    if cursor.fetchone():
        conn.close()
        return None  # Duplicate, skip
    
    msg_id = f"msg-{uuid.uuid4().hex[:8]}"
    cursor.execute("""
        INSERT INTO messages_v2 (id, channel_id, sender_id, content, thread_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (msg_id, channel_id, sender_id, content, thread_id, created_at))
    conn.commit()
    
    # Get sender name
    cursor.execute("SELECT name FROM agents WHERE id = ?", (sender_id,))
    sender = cursor.fetchone()
    sender_name = sender['name'] if sender else sender_id
    conn.close()
    
    message = {
        'id': msg_id,
        'channel_id': channel_id,
        'sender_id': sender_id,
        'sender_name': sender_name,
        'content': content,
        'thread_id': thread_id,
        'created_at': created_at
    }
    
    # Parse @mentions and create notifications
    process_mentions(content, msg_id, sender_id)
    
    # Auto-update sender's heartbeat (they're clearly online if posting)
    update_agent_heartbeat(sender_id, 'online', None, None)
    
    # Broadcast via WebSocket
    asyncio.run_coroutine_threadsafe(
        broadcast_message(channel_id, message),
        ws_loop
    ) if HAS_WEBSOCKETS and ws_loop else None
    
    # Fire webhooks for other agents
    fire_webhooks(sender_id, message)
    
    return message

def process_mentions(content, msg_id, sender_id):
    """Extract @mentions and create notifications."""
    mentions = re.findall(r'@(\w+)', content)
    if not mentions:
        return
    
    conn = get_db()
    cursor = conn.cursor()
    
    for mention in mentions:
        # Find agent by name (case-insensitive)
        cursor.execute("SELECT id FROM agents WHERE LOWER(name) = LOWER(?)", (mention,))
        agent = cursor.fetchone()
        if agent and agent['id'] != sender_id:
            notif_id = f"notif-{uuid.uuid4().hex[:8]}"
            cursor.execute("""
                INSERT INTO notifications (id, agent_id, type, source_type, source_id, content, created_at)
                VALUES (?, ?, 'mention', 'message', ?, ?, ?)
            """, (notif_id, agent['id'], msg_id, f"You were mentioned: {content[:100]}", int(time.time())))
    
    conn.commit()
    conn.close()

def fire_webhooks(sender_id, message):
    """Fire webhooks for agents other than sender with delivery tracking."""
    try:
        with open(WEBHOOK_CONFIG) as f:
            webhooks = json.load(f)
    except:
        return
    
    for agent_id, webhook in webhooks.items():
        if agent_id != sender_id:
            delivery_id = f"wd-{uuid.uuid4().hex[:8]}"
            msg_id = message.get('id', '')
            channel_id = message.get('channel_id', '')
            now = int(time.time())
            
            # Record delivery attempt
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO webhook_deliveries (id, message_id, agent_id, channel_id, status, created_at)
                    VALUES (?, ?, ?, ?, 'pending', ?)
                """, (delivery_id, msg_id, agent_id, channel_id, now))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[WEBHOOK] DB error recording delivery: {e}")
            
            try:
                script = webhook.get('command') or webhook.get('script')
                if script:
                    env = {
                        'AGENTCHAT_SENDER': sender_id,
                        'AGENTCHAT_TEXT': message.get('content', ''),
                        'AGENTCHAT_CHANNEL': channel_id,
                        'AGENTCHAT_MSG_ID': msg_id,
                        'AGENTCHAT_DELIVERY_ID': delivery_id,
                        'PATH': '/usr/local/bin:/usr/bin:/bin'
                    }
                    print(f"[WEBHOOK] {delivery_id} firing for {agent_id}: {script}")
                    
                    # Run and track result
                    proc = subprocess.Popen([script], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    # Mark as delivered (fire-and-forget for now)
                    try:
                        conn = get_db()
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE webhook_deliveries SET status = 'delivered', delivered_at = ?
                            WHERE id = ?
                        """, (int(time.time()), delivery_id))
                        conn.commit()
                        conn.close()
                        print(f"[WEBHOOK] {delivery_id} delivered to {agent_id}")
                    except:
                        pass
            except Exception as e:
                print(f"[WEBHOOK] {delivery_id} error for {agent_id}: {e}")
                try:
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE webhook_deliveries SET status = 'failed', error = ?
                        WHERE id = ?
                    """, (str(e), delivery_id))
                    conn.commit()
                    conn.close()
                except:
                    pass

def get_webhook_stats():
    """Get webhook delivery statistics."""
    conn = get_db()
    cursor = conn.cursor()
    now = int(time.time())
    day_ago = now - 86400
    
    # Counts by status
    cursor.execute("SELECT status, COUNT(*) FROM webhook_deliveries GROUP BY status")
    status_counts = {r[0]: r[1] for r in cursor.fetchall()}
    
    # Delivered in last 24h
    cursor.execute("SELECT COUNT(*) FROM webhook_deliveries WHERE status = 'delivered' AND delivered_at > ?", (day_ago,))
    delivered_24h = cursor.fetchone()[0]
    
    # Oldest pending
    cursor.execute("SELECT MIN(created_at) FROM webhook_deliveries WHERE status = 'pending'")
    oldest = cursor.fetchone()[0]
    oldest_age = (now - oldest) if oldest else 0
    
    # Last success/error timestamps
    cursor.execute("SELECT MAX(delivered_at) FROM webhook_deliveries WHERE status = 'delivered'")
    last_success = cursor.fetchone()[0]
    
    cursor.execute("SELECT MAX(created_at) FROM webhook_deliveries WHERE status = 'failed'")
    last_error = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'pending': status_counts.get('pending', 0),
        'delivered_24h': delivered_24h,
        'delivered_total': status_counts.get('delivered', 0),
        'failed': status_counts.get('failed', 0),
        'deadletter': status_counts.get('deadletter', 0),
        'oldest_pending_age_s': oldest_age,
        'last_success_ts': last_success,
        'last_error_ts': last_error
    }

# ============ Task Operations ============

def get_tasks(status=None, assignee=None):
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    if assignee:
        query += " AND id IN (SELECT task_id FROM task_assignees WHERE agent_id = ?)"
        params.append(assignee)
    
    query += " ORDER BY priority, created_at DESC"
    
    cursor.execute(query, params)
    tasks = [dict_from_row(r) for r in cursor.fetchall()]
    conn.close()
    return tasks

def create_task(title, description=None, priority=2, channel_id=None, created_by=None, assignees=None):
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    created_at = int(time.time())
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tasks (id, title, description, priority, channel_id, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (task_id, title, description, priority, channel_id, created_by, created_at))
    
    # Assign agents
    if assignees:
        for agent_id in assignees:
            cursor.execute("""
                INSERT INTO task_assignees (task_id, agent_id, assigned_at)
                VALUES (?, ?, ?)
            """, (task_id, agent_id, created_at))
            
            # Create notification for assignee
            notif_id = f"notif-{uuid.uuid4().hex[:8]}"
            cursor.execute("""
                INSERT INTO notifications (id, agent_id, type, source_type, source_id, content, created_at)
                VALUES (?, ?, 'assignment', 'task', ?, ?, ?)
            """, (notif_id, agent_id, task_id, f"Assigned: {title}", created_at))
    
    conn.commit()
    conn.close()
    
    return {'id': task_id, 'title': title, 'status': 'inbox', 'created_at': created_at}

def update_task_status(task_id, status):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    conn.commit()
    conn.close()
    return {'id': task_id, 'status': status}

# ============ Notification Operations ============


def claim_task(task_id: str, agent_id: str) -> dict:
    """Agent claims a task - sets assignee and status to in_progress."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check task exists and is claimable
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if not task:
        conn.close()
        return {'error': 'Task not found'}
    
    task_dict = dict_from_row(task)
    if task_dict['status'] not in ('inbox', 'pending'):
        conn.close()
        return {'error': f'Task cannot be claimed (status: {task_dict["status"]})'}
    
    # Update status
    cursor.execute("UPDATE tasks SET status = 'in_progress' WHERE id = ?", (task_id,))
    
    # Add to task_assignees
    cursor.execute("DELETE FROM task_assignees WHERE task_id = ?", (task_id,))
    cursor.execute("""
        INSERT INTO task_assignees (task_id, agent_id, assigned_at)
        VALUES (?, ?, ?)
    """, (task_id, agent_id, int(time.time())))
    conn.commit()
    
    # Create notification for task creator
    if task_dict['created_by'] and task_dict['created_by'] != agent_id:
        notif_id = f"notif-{uuid.uuid4().hex[:8]}"
        cursor.execute("""
            INSERT INTO notifications (id, agent_id, type, source_type, source_id, content, created_at)
            VALUES (?, ?, 'task_claimed', 'task', ?, ?, ?)
        """, (notif_id, task_dict['created_by'], task_id, 
              f"Task claimed by {agent_id}: {task_dict['title']}", int(time.time())))
        conn.commit()
    
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    result = dict_from_row(cursor.fetchone())
    result['assignee'] = agent_id
    conn.close()
    return result

def release_task(task_id: str, agent_id: str) -> dict:
    """Agent releases a task - clears assignee, sets back to pending."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if not task:
        conn.close()
        return {'error': 'Task not found'}
    
    # Update status and remove assignees
    cursor.execute("UPDATE tasks SET status = 'pending' WHERE id = ?", (task_id,))
    cursor.execute("DELETE FROM task_assignees WHERE task_id = ?", (task_id,))
    conn.commit()
    
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    result = dict_from_row(cursor.fetchone())
    result['assignee'] = None
    conn.close()
    return result


def get_notifications(agent_id, unread_only=True):
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM notifications WHERE agent_id = ?"
    params = [agent_id]
    
    if unread_only:
        query += " AND read = 0"
    
    query += " ORDER BY created_at DESC LIMIT 50"
    
    cursor.execute(query, params)
    notifications = [dict_from_row(r) for r in cursor.fetchall()]
    conn.close()
    return notifications

def mark_notification_read(notif_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()

# ============ WebSocket Server ============

ws_loop = None

async def broadcast_message(channel_id, message):
    """Broadcast message to all WebSocket clients in channel."""
    if not ws_clients:
        return
    
    payload = json.dumps({
        'type': 'message',
        'channel_id': channel_id,
        'message': message
    })
    
    for agent_id, ws in list(ws_clients.items()):
        try:
            await ws.send(payload)
        except:
            del ws_clients[agent_id]

async def ws_handler(websocket, path):
    """Handle WebSocket connections."""
    agent_id = None
    
    try:
        # First message should be auth
        auth_msg = await asyncio.wait_for(websocket.recv(), timeout=10)
        auth_data = json.loads(auth_msg)
        agent_id = auth_data.get('agent_id')
        
        if not agent_id:
            await websocket.close(1008, "Missing agent_id")
            return
        
        # Register client
        ws_clients[agent_id] = websocket
        update_agent_heartbeat(agent_id, 'online')
        print(f"🔌 WebSocket connected: {agent_id}")
        
        # Send ack
        await websocket.send(json.dumps({'type': 'connected', 'agent_id': agent_id}))
        
        # Handle messages
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'heartbeat':
                update_agent_heartbeat(agent_id, data.get('status', 'online'), data.get('status_message'))
                await websocket.send(json.dumps({'type': 'heartbeat_ack'}))
            
            elif msg_type == 'message':
                channel_id = data.get('channel_id', 'general')
                content = data.get('content')
                if content:
                    msg = post_channel_message(channel_id, agent_id, content, data.get('thread_id'))
                    await websocket.send(json.dumps({'type': 'message_ack', 'message': msg}))
            
            elif msg_type == 'typing':
                # Broadcast typing indicator
                payload = json.dumps({
                    'type': 'typing',
                    'channel_id': data.get('channel_id', 'general'),
                    'agent_id': agent_id,
                    'is_typing': data.get('is_typing', True)
                })
                for aid, ws in ws_clients.items():
                    if aid != agent_id:
                        try:
                            await ws.send(payload)
                        except:
                            pass
    
    except Exception as e:
        print(f"WebSocket error: {e}")
    
    finally:
        if agent_id and agent_id in ws_clients:
            del ws_clients[agent_id]
            update_agent_heartbeat(agent_id, 'offline')
            print(f"🔌 WebSocket disconnected: {agent_id}")

async def run_ws_server():
    """Run WebSocket server."""
    global ws_loop
    ws_loop = asyncio.get_event_loop()
    
    async with ws_serve(ws_handler, "0.0.0.0", WS_PORT):
        print(f"🔌 WebSocket server running on ws://0.0.0.0:{WS_PORT}")
        await asyncio.Future()  # Run forever


# ============ Presence Decay ============

def presence_decay_loop():
    """Background thread to mark agents offline after 60s without heartbeat."""
    import time
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cutoff = int(time.time()) - 60
            cursor.execute("""
                UPDATE agents 
                SET status = 'offline' 
                WHERE last_heartbeat IS NOT NULL 
                  AND last_heartbeat < ? 
                  AND status != 'offline'
            """, (cutoff,))
            if cursor.rowcount > 0:
                print(f"⏰ Marked {cursor.rowcount} agent(s) offline (no heartbeat)")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Presence decay error: {e}")
        time.sleep(30)  # Check every 30 seconds

# ============ HTTP Server ============

class AgentChatHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Quiet logging
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def read_json(self):
        length = int(self.headers.get('Content-Length', 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # Root - serve dashboard
        if path == '/' or path == '':
            try:
                with open('/home/clawd/tools/agentchat/dashboard.html', 'r') as f:
                    html = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(html.encode())
                return
            except Exception as e:
                return self.send_json({'error': str(e)}, 500)
        

        # Health check
        if path == '/health':
            return self.send_json({'status': 'ok', 'version': '2.0', 'websocket_port': WS_PORT})
        
        # V1 compatibility
        if path == '/api/messages':
            since = int(float(params.get('since', [0])[0]))
            messages = get_channel_messages('general', since)
            # Convert to v1 format
            v1_messages = [{'id': m['id'], 'ts': m['created_at'], 'sender': m['sender_name'], 'text': m['content']} for m in messages]
            return self.send_json(v1_messages)
        
        # V2 API
        if path == '/api/v2/agents':
            return self.send_json(get_agents())
        
        if path == '/api/v2/webhook_stats':
            return self.send_json(get_webhook_stats())
        
        if path.startswith('/api/v2/agents/') and path.endswith('/notifications'):
            agent_id = path.split('/')[4]
            return self.send_json(get_notifications(agent_id))
        
        if path.startswith('/api/v2/agents/'):
            agent_id = path.split('/')[4]
            return self.send_json(get_agent(agent_id))
        
        if path == '/api/v2/channels':
            return self.send_json(get_channels())
        
        if path.startswith('/api/v2/channels/') and '/messages' in path:
            channel_id = path.split('/')[4]
            since = int(float(params.get('since', [0])[0]))
            limit = int(params.get('limit', [100])[0])
            return self.send_json(get_channel_messages(channel_id, since, limit))
        
        # Create channel
        if path == '/api/v2/channels':
            channel_id = data.get('id') or data.get('name', '').lower().replace(' ', '-')
            name = data.get('name', channel_id)
            topic = data.get('topic', '')
            
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO channels (id, name, type, topic, created_at)
                VALUES (?, ?, 'public', ?, ?)
            """, (channel_id, name, topic, int(__import__('time').time())))
            conn.commit()
            conn.close()
            return self.send_json({'id': channel_id, 'name': name, 'topic': topic})
        
        if path == '/api/v2/tasks':
            status = params.get('status', [None])[0]
            assignee = params.get('assignee', [None])[0]
            return self.send_json(get_tasks(status, assignee))
        
        self.send_json({'error': 'Not found'}, 404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        data = self.read_json()
        
        # V1 compatibility
        if path == '/api/send':
            sender = data.get('sender', 'unknown')
            text = data.get('text', '')
            # Map to v2
            sender_id = 'portal1' if 'portal1' in sender.lower() else 'portal2'
            msg = post_channel_message('general', sender_id, text)
            if msg is None:
                return self.send_json({'ok': True, 'id': 'duplicate', 'note': 'Duplicate message skipped'})
            return self.send_json({'ok': True, 'id': msg['id']})
        
        # V2 API
        if path.startswith('/api/v2/channels/') and '/messages' in path:
            channel_id = path.split('/')[4]
            sender_id = data.get('sender_id', 'portal1')
            content = data.get('content', '')
            thread_id = data.get('thread_id')
            msg = post_channel_message(channel_id, sender_id, content, thread_id)
            if msg is None:
                return self.send_json({'ok': True, 'id': 'duplicate', 'note': 'Duplicate message skipped'})
            return self.send_json(msg)
        
        if path.startswith('/api/v2/agents/') and '/heartbeat' in path:
            agent_id = path.split('/')[4]
            update_agent_heartbeat(
                agent_id,
                data.get('status', 'online'),
                data.get('status_message'),
                data.get('current_task_id')
            )
            return self.send_json({'ok': True})
        
        # Create channel
        if path == '/api/v2/channels':
            channel_id = data.get('id') or data.get('name', '').lower().replace(' ', '-')
            name = data.get('name', channel_id)
            topic = data.get('topic', '')
            
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO channels (id, name, type, topic, created_at)
                VALUES (?, ?, 'public', ?, ?)
            """, (channel_id, name, topic, int(__import__('time').time())))
            conn.commit()
            conn.close()
            return self.send_json({'id': channel_id, 'name': name, 'topic': topic})
        
        if path == '/api/v2/tasks':
            task = create_task(
                data.get('title'),
                data.get('description'),
                data.get('priority', 2),
                data.get('channel_id'),
                data.get('created_by'),
                data.get('assignees')
            )
            return self.send_json(task)
        
        if path.startswith('/api/v2/tasks/') and '/status' in path:
            task_id = path.split('/')[4]
            result = update_task_status(task_id, data.get('status'))
            return self.send_json(result)
        
        if path.startswith('/api/v2/tasks/') and '/claim' in path:
            task_id = path.split('/')[4]
            agent_id = data.get('agent_id')
            if not agent_id:
                return self.send_json({'error': 'agent_id required'}, 400)
            result = claim_task(task_id, agent_id)
            if 'error' in result:
                return self.send_json(result, 400)
            return self.send_json(result)
        
        if path.startswith('/api/v2/tasks/') and '/release' in path:
            task_id = path.split('/')[4]
            agent_id = data.get('agent_id')
            result = release_task(task_id, agent_id)
            if 'error' in result:
                return self.send_json(result, 400)
            return self.send_json(result)
        
        if path.startswith('/api/v2/notifications/') and '/read' in path:
            notif_id = path.split('/')[4]
            mark_notification_read(notif_id)
            return self.send_json({'ok': True})
        
        self.send_json({'error': 'Not found'}, 404)

def run_http_server():
    server = HTTPServer(('0.0.0.0', HTTP_PORT), AgentChatHandler)
    print(f"🌐 HTTP server running on http://0.0.0.0:{HTTP_PORT}")
    server.serve_forever()

# ============ Main ============

def main():
    print("""
╔═══════════════════════════════════════════╗
║         AgentChat V2 Server               ║
║   HTTP + WebSocket • Built on Portal1     ║
╚═══════════════════════════════════════════╝
    """)
    
    # Start presence decay thread
    decay_thread = threading.Thread(target=presence_decay_loop, daemon=True)
    decay_thread.start()
    
    # Start HTTP server in thread
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    # Start WebSocket server (main thread)
    if HAS_WEBSOCKETS:
        asyncio.run(run_ws_server())
    else:
        print("⚠️  Running HTTP-only mode (install websockets for WS support)")
        http_thread.join()

if __name__ == '__main__':
    main()
