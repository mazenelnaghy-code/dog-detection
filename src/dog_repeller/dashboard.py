"""Tiny web dashboard: live annotated video + status + arm / disarm / test buttons.

Open http://<pi-ip>:8000 from a phone on the same Wi-Fi. When ``dashboard.token`` is set, every
endpoint (including the video, which may show children) needs ``?token=...`` or ``X-Token``.
"""

from __future__ import annotations

import hmac
import logging
import threading

from flask import Flask, Response, abort, jsonify, request

from .config import DashboardConfig

log = logging.getLogger(__name__)

COMMANDS = {"arm", "disarm", "test"}


class DashboardState:
    """Thread-safe mailbox between the detection loop and the web server."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._jpeg: bytes | None = None
        self._seq = 0
        self._status: dict = {}
        self._commands: list[str] = []
        self.viewers = 0  # open /stream.mjpg connections

    def update(self, jpeg: bytes | None, status: dict) -> None:
        with self._cond:
            if jpeg is not None:
                self._jpeg, self._seq = jpeg, self._seq + 1
            self._status = dict(status)
            self._cond.notify_all()

    def status(self) -> dict:
        with self._cond:
            return dict(self._status)

    def wait_frame(self, last_seq: int, timeout: float = 5.0) -> tuple[int, bytes | None]:
        with self._cond:
            self._cond.wait_for(lambda: self._seq != last_seq, timeout)
            return self._seq, (self._jpeg if self._seq != last_seq else None)

    def push_command(self, command: str) -> None:
        with self._cond:
            self._commands.append(command)

    def pop_commands(self) -> list[str]:
        with self._cond:
            commands, self._commands = self._commands, []
            return commands


def create_app(state: DashboardState, token: str = "") -> Flask:
    app = Flask(__name__)

    @app.before_request
    def check_token():
        if token and request.path != "/":
            given = request.headers.get("X-Token") or request.args.get("token", "")
            if not hmac.compare_digest(given.encode(), token.encode()):
                abort(401)

    @app.get("/")
    def index():
        return Response(PAGE, mimetype="text/html")

    @app.get("/api/status")
    def status():
        return jsonify(state.status())

    @app.post("/api/<command>")
    def command(command: str):
        if command not in COMMANDS:
            abort(404)
        state.push_command(command)
        log.info("Dashboard command: %s", command)
        return jsonify({"ok": True, "command": command}), 202

    @app.get("/stream.mjpg")
    def stream():
        def frames():
            seq = -1
            state.viewers += 1
            try:
                while True:
                    seq, jpeg = state.wait_frame(seq)
                    if jpeg is not None:
                        yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                               + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
            finally:
                state.viewers -= 1

        return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    return app


def start_dashboard(state: DashboardState, cfg: DashboardConfig):
    """Start the server in a daemon thread. Returns the server (call ``.shutdown()``)."""
    from werkzeug.serving import make_server

    server = make_server(cfg.host, cfg.port, create_app(state, cfg.token), threaded=True)
    threading.Thread(target=server.serve_forever, name="dashboard", daemon=True).start()
    log.info("Dashboard on http://%s:%d", cfg.host, cfg.port)
    return server


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dog Repeller</title>
<style>
  :root { --bg:#0f172a; --card:#1e293b; --text:#e2e8f0; --muted:#94a3b8;
          --ok:#22c55e; --warn:#eab308; --bad:#ef4444; --accent:#3b82f6; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, sans-serif; background:var(--bg); color:var(--text); }
  main { max-width: 900px; margin: 0 auto; padding: 16px; }
  h1 { font-size: 1.25rem; margin: 0 0 12px; }
  img { width:100%; border-radius:12px; background:#000; aspect-ratio: 4/3; object-fit: contain; }
  .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:8px;
          margin: 12px 0; }
  .card { background:var(--card); border-radius:10px; padding:10px 12px; }
  .label { color:var(--muted); font-size:.75rem; text-transform:uppercase; letter-spacing:.05em; }
  .value { font-size:1.15rem; font-weight:600; margin-top:2px; }
  .CLEAR { color:var(--ok); } .DETECTED { color:var(--warn); } .DANGER { color:var(--bad); }
  .buttons { display:flex; gap:8px; flex-wrap:wrap; }
  button { flex:1; min-width:110px; padding:12px; border:0; border-radius:10px; font-size:1rem;
           font-weight:600; color:white; background:var(--accent); cursor:pointer; }
  button.off { background:#475569; } button.test { background:#a855f7; }
  #msg { color:var(--muted); min-height:1.2em; margin-top:8px; }
</style></head>
<body><main>
  <h1>AI Dog Detection &amp; Repellent System</h1>
  <img id="video" alt="Live camera">
  <div class="grid">
    <div class="card"><div class="label">Threat</div><div class="value" id="level">-</div></div>
    <div class="card"><div class="label">State</div><div class="value" id="state">-</div></div>
    <div class="card"><div class="label">System</div><div class="value" id="armed">-</div></div>
    <div class="card"><div class="label">Dogs</div><div class="value" id="dogs">-</div></div>
    <div class="card"><div class="label">Repels</div><div class="value" id="bursts">-</div></div>
    <div class="card"><div class="label">FPS</div><div class="value" id="fps">-</div></div>
  </div>
  <div class="buttons">
    <button onclick="send('arm')">Arm</button>
    <button class="off" onclick="send('disarm')">Disarm</button>
    <button class="test" onclick="send('test')">Test repeller</button>
  </div>
  <div id="msg"></div>
</main>
<script>
  const token = new URLSearchParams(location.search).get('token') || '';
  const q = token ? '?token=' + encodeURIComponent(token) : '';
  document.getElementById('video').src = '/stream.mjpg' + q;
  const $ = id => document.getElementById(id);
  async function refresh() {
    try {
      const s = await (await fetch('/api/status' + q)).json();
      $('level').textContent = s.level || '-'; $('level').className = 'value ' + (s.level || '');
      $('state').textContent = (s.state || '-') + (s.seconds_left ? ' (' + s.seconds_left + 's)' : '');
      $('armed').textContent = s.armed ? 'ARMED' : 'DISARMED';
      $('dogs').textContent = s.dogs ?? '-'; $('bursts').textContent = s.total_bursts ?? '-';
      $('fps').textContent = s.fps ?? '-';
    } catch (e) { $('msg').textContent = 'Connection lost - retrying...'; }
  }
  async function send(cmd) {
    const r = await fetch('/api/' + cmd + q, { method: 'POST' });
    $('msg').textContent = r.ok ? 'Sent: ' + cmd : 'Error ' + r.status;
  }
  setInterval(refresh, 1000); refresh();
</script></body></html>
"""
