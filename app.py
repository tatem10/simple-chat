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
<title>TERMINAL // CHAT</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #000000; --panel: #060a06; --accent: #2e8b3e;
    --dim: #0d1f0d; --text: #6fae6f; --muted: #2a5c2a;
    --bright: #9fd99f; --entry: #060a06; --border: #14361a;
    --server: #c9a85a; --warn: #b94b4b;
  }
  @import url('https://fonts.googleapis.com/css2?family=DotGothic16&display=swap');
  html, body { background: var(--bg); color: var(--text);
         font-family: 'DotGothic16', 'Courier New', monospace;
         height: 100dvh; width: 100%; overflow: hidden; }
  body { display: flex; flex-direction: column; position: relative; }

  /* ===== JOIN SCREEN (with code rain) ===== */
  #join { display: flex; flex-direction: column; align-items: center;
          justify-content: center; flex: 1; gap: 16px; padding: 24px;
          position: relative; overflow: hidden; }
  #matrixCanvas { position: absolute; inset: 0; width: 100%; height: 100%;
                  z-index: 0; }
  #join .overlay { position: relative; z-index: 2; display: flex;
                    flex-direction: column; align-items: center; gap: 14px;
                    background: rgba(0,0,0,0.55); padding: 32px 28px;
                    border: 1px solid var(--border); backdrop-filter: blur(1px); }
  #join .ascii { color: var(--accent); font-size: 11px; line-height: 1.3;

                 white-space: pre; text-align: center;
                 text-shadow: 0 0 8px rgba(46,139,62,0.8); }
  #join label { color: var(--muted); font-size: 18px; text-transform: uppercase;
                letter-spacing: 3px; align-self: flex-start; }
  #join input { width: 280px; padding: 12px 14px;
                background: rgba(0,0,0,0.6); border: 1px solid var(--accent);
                color: var(--bright); font-size: 22px; outline: none;
                font-family: inherit; caret-color: transparent;
                text-shadow: 0 0 4px rgba(46,139,62,0.6); }
  #join input:focus { box-shadow: 0 0 12px rgba(46,139,62,0.5); }
  #join button { width: 280px; padding: 13px;
                 background: rgba(0,20,0,0.7); color: var(--accent); border: 1px solid var(--accent);
                 font-size: 19px; font-weight: 700; cursor: pointer;
                 text-transform: uppercase; letter-spacing: 3px;
                 font-family: inherit; transition: 0.15s; }
  #join button:hover { background: var(--accent); color: #000;
                        box-shadow: 0 0 18px rgba(46,139,62,0.7); }

  /* ===== CHAT SCREEN (clean, no rain) ===== */
  #header { background: var(--panel); padding: 12px 16px;
            display: flex; align-items: center; justify-content: space-between;
            border-bottom: 1px solid var(--border); flex-shrink: 0;
            text-transform: uppercase; letter-spacing: 1px; }
  #header h1 { font-size: 20px; font-weight: 400; color: var(--accent);
               text-shadow: 0 0 6px rgba(46,139,62,0.6); }
  #header h1 .blink { animation: blink 1.2s steps(1) infinite; }
  #status { font-size: 15px; color: var(--muted); }
  #status.on { color: var(--bright); text-shadow: 0 0 6px rgba(159,217,159,0.7); }
  @keyframes blink { 50% { opacity: 0; } }

  #chat { display: none; flex-direction: column; flex: 1; overflow: hidden; background: var(--bg); }
  #messages { flex: 1; overflow-y: auto; padding: 14px 16px; display: flex;
              flex-direction: column; gap: 3px; font-size: 19px; }
  .msg { line-height: 1.5; word-break: break-word; padding: 1px 0; }
  .msg .tag { color: var(--muted); }
  .msg.me .name { color: var(--bright); font-weight: 700; }
  .msg.me .body { color: var(--text); }
  .msg.them .name { color: var(--accent); font-weight: 700; }
  .msg.them .body { color: var(--text); }
  .msg.server { color: var(--server); font-style: italic; }
  .msg .time { color: var(--muted); font-size: 15px; }

  #inputbar { background: var(--panel); padding: 10px 12px;
              padding-bottom: max(10px, env(safe-area-inset-bottom));
              display: flex; gap: 8px; border-top: 1px solid var(--border);
              flex-shrink: 0; align-items: center; }
  #inputbar .prompt { color: var(--accent); font-size: 20px; }
  #inputbar input { flex: 1; padding: 10px 8px; background: transparent;
                    border: none; color: var(--bright); font-size: 19px; outline: none;
                    font-family: inherit; caret-color: transparent; }

  /* ---- Blocky terminal-style cursor ---- */
  .input-wrap { position: relative; display: inline-flex; align-items: center; }
  .input-wrap input { width: 100%; }
  .block-cursor {
    position: absolute; top: 50%; left: 0;
    width: 0.62em; height: 1.15em;
    transform: translateY(-50%);
    background: var(--accent);
    box-shadow: 0 0 6px rgba(46,139,62,0.8);
    pointer-events: none;
    animation: cursorBlink 1s steps(1) infinite;
    display: none;
  }
  .block-cursor.active { display: block; }
  @keyframes cursorBlink { 50% { opacity: 0; } }
  #inputbar button { padding: 10px 16px; background: var(--dim); color: var(--accent);
                     border: 1px solid var(--accent); font-size: 16px;
                     text-transform: uppercase; letter-spacing: 1px;
                     cursor: pointer; white-space: nowrap; font-family: inherit; }
  #inputbar button:hover { background: var(--accent); color: #000; }

  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-thumb { background: var(--border); }
  ::-webkit-scrollbar-track { background: var(--bg); }
</style>
</head>
<body>

<div id="join">
  <canvas id="matrixCanvas"></canvas>
  <div class="overlay">
    <label>ENTER NAME</label>
    <div class="input-wrap">
      <input id="nameInput" placeholder="" maxlength="32" autocomplete="off" spellcheck="false">
      <span class="block-cursor" id="nameCursor"></span>
    </div>
    <button onclick="joinChat()">&gt; CONNECT</button>
  </div>
</div>

<div id="chat">
  <div id="header">
    <h1>[ TERMINAL // CHAT<span class="blink">_</span> ]</h1>
    <span id="status">○ OFFLINE</span>
  </div>
  <div id="messages"></div>
  <div id="inputbar">
    <span class="prompt">&gt;</span>
    <div class="input-wrap" style="flex:1;">
      <input id="msgInput" placeholder="type a message..." autocomplete="off" autocorrect="off" spellcheck="false">
      <span class="block-cursor" id="msgCursor"></span>
    </div>
    <button onclick="sendMsg()">SEND</button>
  </div>
</div>

<script>
let username = "";
let lastCount = 0;
let polling = false;
let rainAnimationId = null;

/* ---- Blocky terminal-style cursor positioning ---- */
function setupBlockCursor(inputId, cursorId) {
  const input = document.getElementById(inputId);
  const cursor = document.getElementById(cursorId);

  // Hidden span used to measure text width with the same font as the input
  const measurer = document.createElement("span");
  const cs = getComputedStyle(input);
  measurer.style.font = cs.font;
  measurer.style.letterSpacing = cs.letterSpacing;
  measurer.style.position = "absolute";
  measurer.style.visibility = "hidden";
  measurer.style.whiteSpace = "pre";
  document.body.appendChild(measurer);

  function reposition() {
    const caretPos = input.selectionStart || 0;
    measurer.textContent = input.value.slice(0, caretPos);
    const offsetX = measurer.getBoundingClientRect().width;
    const paddingLeft = parseFloat(cs.paddingLeft) || 0;
    cursor.style.left = (paddingLeft + offsetX) + "px";
  }

  input.addEventListener("input", reposition);
  input.addEventListener("keyup", reposition);
  input.addEventListener("click", reposition);
  input.addEventListener("focus", () => { cursor.classList.add("active"); reposition(); });
  input.addEventListener("blur", () => { cursor.classList.remove("active"); });

  reposition();
}

/* ---- Matrix code rain (join screen only) ---- */
function startMatrixRain() {
  const canvas = document.getElementById("matrixCanvas");
  const ctx = canvas.getContext("2d");
  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener("resize", resize);

  const chars = "アイウエオカキクケコサシスセソタチツテト0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const fontSize = 16;
  let columns = Math.floor(canvas.width / fontSize);
  // Each column gets its own starting offset and fixed speed so the
  // rain reads as a steady, continuous flow rather than a flicker.
  let drops = [];
  for (let i = 0; i < columns; i++) {
    drops.push({
      y: Math.random() * -40,                 // staggered start
      speed: 0.35 + Math.random() * 0.25,      // constant per-column speed
      glyph: chars[Math.floor(Math.random() * chars.length)],
      changeTimer: Math.random() * 20
    });
  }

  function draw() {
    ctx.fillStyle = "rgba(0, 0, 0, 0.06)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "rgba(46, 139, 62, 0.65)"; // dimmer, muted green
    ctx.font = fontSize + "px monospace";

    for (let i = 0; i < drops.length; i++) {
      const d = drops[i];
      ctx.fillText(d.glyph, i * fontSize, d.y * fontSize);

      d.y += d.speed;
      d.changeTimer -= 1;
      if (d.changeTimer <= 0) {
        d.glyph = chars[Math.floor(Math.random() * chars.length)];
        d.changeTimer = 15 + Math.random() * 15;
      }
      if (d.y * fontSize > canvas.height + 40) {
        d.y = Math.random() * -10;            // smooth wraparound, no flicker
        d.speed = 0.35 + Math.random() * 0.25;
      }
    }
    rainAnimationId = requestAnimationFrame(draw);
  }
  draw();
}

function stopMatrixRain() {
  if (rainAnimationId) {
    cancelAnimationFrame(rainAnimationId);
    rainAnimationId = null;
  }
}

startMatrixRain();

/* ---- Chat logic ---- */
function joinChat() {
  const n = document.getElementById("nameInput").value.trim();
  if (!n) return;
  username = n;

  stopMatrixRain();
  document.getElementById("join").style.display = "none";
  document.getElementById("chat").style.display = "flex";
  document.getElementById("status").textContent = "● LINK ESTABLISHED // " + username.toUpperCase();
  document.getElementById("status").className = "on";
  document.getElementById("msgInput").focus();
  fetch("/send", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({username: "Server", text: `*** ${username} has connected ***`})});
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

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
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
    div.innerHTML = `<span class="tag">[${msg.time}]</span> ` +
                    `<span class="name">${escapeHtml(sender)}:</span> ` +
                    `<span class="body">${escapeHtml(body)}</span>`;
  } else {
    div.innerHTML = `<span class="tag">[${msg.time}]</span> ${escapeHtml(text)}`;
  }

  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

document.getElementById("nameInput").addEventListener("keydown", e => { if (e.key === "Enter") joinChat(); });
document.getElementById("msgInput").addEventListener("keydown", e => { if (e.key === "Enter") sendMsg(); });

setupBlockCursor("nameInput", "nameCursor");
setupBlockCursor("msgInput", "msgCursor");
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
