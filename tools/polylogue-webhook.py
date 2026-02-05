#!/usr/bin/env python3
"""Polylogue webhook receiver - triggers OpenClaw on @mentions"""
import json
import hmac
import hashlib
import subprocess
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

WEBHOOK_SECRET = "e2aaedb645db4c5c5f9a29dbe2974c4d516397792112c7dc45793c0131d8730e"
PORT = 5095
LOG_FILE = "/home/clawd/tools/polylogue-webhook.log"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

class WebhookHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(501)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Webhook endpoint - POST only')
    
    def do_POST(self):
        log(f"Received POST from {self.client_address[0]}")
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        # Verify signature
        signature = self.headers.get('X-Polylogue-Signature', '')
        expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        
        log(f"Signature: {signature[:20]}... Expected: {expected[:20]}...")
        
        if not hmac.compare_digest(signature, expected):
            log(f"INVALID SIGNATURE")
            self.send_response(401)
            self.end_headers()
            return
        
        try:
            data = json.loads(body)
            event = data.get('event', '')
            comment = data.get('comment', {})
            document = data.get('document', {})
            author = comment.get('author', {}).get('name', 'unknown')
            
            log(f"OK: {event} from {author} on '{document.get('title', '?')}'")
            log(f"Body: {comment.get('body', '')[:200]}")
            
            # Trigger OpenClaw system event
            msg = f"Polylogue @mention from {author} on doc '{document.get('title','')}': {comment.get('body','')}"
            result = subprocess.run([
                "/home/dcarmitage/.npm-global/bin/openclaw", "system", "event", "--mode", "now", "--text", msg
            ], capture_output=True, timeout=10, text=True)
            log(f"OpenClaw triggered: {result.returncode}")
            
        except Exception as e:
            log(f"ERROR: {e}")
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"ok":true}')
    
    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    log(f"Starting webhook server on :{PORT}")
    HTTPServer(('127.0.0.1', PORT), WebhookHandler).serve_forever()
