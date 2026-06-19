"""
LAN Chat -> Web Chat
A simple multi-user web chat app, deployable for free on Render.
Works from any browser - PC, iPhone, Android, anywhere with internet.
"""

import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from http.server import HTTPServer
import os

messages = []
lock = threading.Lock()
MAX_HISTORY = 200


def broadcast(text: str):
    timestamp = datetime.now().strftime("%H:%M")
    entry = {"time": timestamp, "text": text}
    with lock:
        messages.append(entry)
        if len(messages) > MAX_HISTORY:
            messages.pop(0)
    print(f"[{timestamp}] {text}")


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Chat</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #1e1e2e; --panel: #2a2a3d; --accent: #818cf8;
    --me: #4f46e5; --text: #e2e8f0; --muted: #64748b;
    --green: #4ade80; --entry: #2d2d42; --border: #3b3b52;
    --server: #6ee7b7;
  }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         height: 100dvh; display: flex; flex-direction: column; }
  #header { background: var(--panel); padding: 14px 16px;
            display: flex; align-items: center; justify-content: space-between;
            border-bottom: 1px solid var(--border); flex-shrink: 0; }
  #header h1 { font-size: 17px; font-weight: 700; }
  #status { font-size: 12px; color: var(--muted); }
  #status.on { color: var(--green); }
  #join { display: flex; flex-direction: column; align-items: center;
          justify-content: center; flex: 1; gap: 12px; padding: 24px; }
  #join input { width: 100%; max-width: 320px; padding: 14px 16px;
                background: var(--entry); border: 1px solid var(--border);
                border-radius: 12px; color: var(--text); font-size: 16px; outline: none; }
  #join button { width: 100%; max-width: 320px; padding: 14px;
                 background: var(--me); color: white; border: none;
                 border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer; }
  #chat { display: none; flex-direction: column; flex: 1; overflow: hidden; }
  #messages { flex: 1; overflow-y: auto; padding: 12px 16px; display: flex; flex-direction: column; gap: 6px; }
  .msg { max-width: 80%; padding: 8px 12px; border-radius: 16px; font-size: 15px; line-height: 1.4; word-break: break-word; }
  .msg.me { align-self: flex-end; background: var(--me); color: white; border-bottom-right-radius: 4px; }
  .msg.them { align-self: flex-start; background: var(--panel); border-bottom-left-radius: 4px; }
  .msg.server { align-self: center; background: transparent; color: var(--server);
                font-size: 12px; font-style: italic; padding: 2px 8px; }
  .msg .name { font-size: 11px; opacity: 0.7; margin-bottom: 2px; }
  .msg .time { font-size: 10px; opacity: 0.5; margin-top: 2px; text-align: right; }
  #inputbar { background: var(--panel); padding: 10px 12px;
              padding-bottom: max(10px, env(safe-area-inset-bottom));
              display: flex; gap: 8px; border-top: 1px solid var(--border); flex-shrink: 0; }
  #inputbar input { flex: 1; padding: 12px 14px; background: var(--entry);
                    border: 1px solid var(--border); border-radius: 22px;
                    color: var(--text); font-size: 16px; outline: none; }
  #inputbar button { padding: 12px 18px; background: var(--me); color: white;
                     border: none; border-radius: 22px; font-size: 15px;
                     font-weight: 600; cursor: pointer; white-space: nowrap; }
</style>
</head>
<body>
<div id="header">
  <h1>💬 Chat</h1>
  <span id="status">● Not joined</span>
</div>
<div id="join">
  <input id="nameInput" placeholder="Your name" maxlength="32" autocomplete="off">
  <button onclick="joinChat()">Join Chat</button>
</div>
<div id="chat">
  <div id="messages"></div>
  <div id="inputbar">
    <input id="msgInput" placeholder="Message…" autocomplete="off" autocorrect="off">
    <button onclick="sendMsg()">Send</button>
  </div>
</div>
<script>
let username = "";
let lastCount = 0;
let polling = false;

function joinChat() {
  const n = document.getElementById("nameInput").value.trim();
  if (!n) return;
  username = n;
  document.getElementById("join").style.display = "none";
  document.getElementById("chat").style.display = "flex";
  document.getElementById("status").textContent = "● " + username;
  document.getElementById("status").className = "on";
  document.getElementById("msgInput").focus();
  fetch("/send", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({username: "Server", text: `*** ${username} joined ***`})});
  startPolling();
}

function sendMsg() {
  const inp = document.getElementById("msgInput");
  const text = inp.value.trim();
  if (!text || !username) return;
  inp.value = "";
  fetch("/send", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({username, text})
  });
}

function startPolling() {
  if (polling) return;
  polling = true;
  poll();
}

async function poll() {
  while (polling) {
    try {
      const r = await fetch("/poll?since=" + lastCount);
      const data = await r.json();
      if (data.messages && data.messages.length > 0) {
        data.messages.forEach(addMessage);
        lastCount += data.messages.length;
      }
    } catch(e) {}
    await new Promise(r => setTimeout(r, 1000));
  }
}

function addMessage(msg) {
  const box = document.getElementById("messages");
  const div = document.createElement("div");
  const text = msg.text;
  const isServer = text.startsWith("***") || text.startsWith("[Server]");
  const colon = text.indexOf(": ");
  const sender = colon > -1 ? text.slice(0, colon) : "";
  const isMe = !isServer && sender === username;

  div.className = "msg " + (isServer ? "server" : isMe ? "me" : "them");

  if (!isServer) {
    const body = colon > -1 ? text.slice(colon + 2) : text;
    if (!isMe && sender) div.innerHTML += `<div class="name">${sender}</div>`;
    div.innerHTML += `<div></div><div class="time">${msg.time}</div>`;
    div.querySelector("div:nth-child(" + (isMe || !sender ? 1 : 2) + ")").textContent = body;
  } else {
    div.textContent = text;
  }

  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

document.getElementById("nameInput").addEventListener("keydown", e => { if (e.key === "Enter") joinChat(); });
document.getElementById("msgInput").addEventListener("keydown", e => { if (e.key === "Enter") sendMsg(); });
</script>
</body>
</html>"""


class ChatHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            self._send_html(HTML_PAGE)
        elif self.path.startswith("/poll"):
            since = 0
            if "since=" in self.path:
                try:
                    since = int(self.path.split("since=")[1])
                except ValueError:
                    pass
            with lock:
                new_msgs = messages[since:]
            self._send_json({"messages": new_msgs})
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == "/send":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            username = body.get("username", "Anon")[:32]
            text = body.get("text", "").strip()[:500]
            if text:
                if text.startswith("***"):
                    broadcast(text)
                else:
                    broadcast(f"{username}: {text}")
            self._send_json({"ok": True})
        else:
            self.send_response(404); self.end_headers()

    def _send_html(self, html):
        data = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting chat server on port {port}")
    ThreadingHTTPServer(("0.0.0.0", port), ChatHandler).serve_forever()
