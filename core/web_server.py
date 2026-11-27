from __future__ import annotations
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

class JarvisWebServer:
    """Loopback-only HTTP bridge for the standalone HTML client."""
    def __init__(self, app_dir: Path, ai, memory, knowledge, hardware):
        self.app_dir = Path(app_dir); self.ai = ai; self.memory = memory
        self.knowledge = knowledge; self.hardware = hardware
        self.httpd = None; self.thread = None; self.port = None
    def start(self, open_browser=True):
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args): pass
            def _send(self, code, payload, content_type="application/json; charset=utf-8"):
                data = payload if isinstance(payload, bytes) else (json.dumps(payload, ensure_ascii=False).encode("utf-8") if not isinstance(payload, str) else payload.encode("utf-8"))
                self.send_response(code); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(data)))
                origin = self.headers.get("Origin", "")
                parsed_origin = urlparse(origin) if origin else None
                allowed_origin = (origin == "null" or (parsed_origin and parsed_origin.scheme == "http"
                    and parsed_origin.hostname in ("127.0.0.1", "localhost")
                    and parsed_origin.port == owner.port))
                if allowed_origin:
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                    self.send_header("Access-Control-Allow-Headers", "Content-Type")
                    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Cache-Control", "no-store")
                self.end_headers(); self.wfile.write(data)
            def do_OPTIONS(self): self._send(204, b"")
            def do_GET(self):
                path = urlparse(self.path).path
                if path in ("/", "/JARVIS.html"):
                    target = owner.app_dir / "Web" / "JARVIS.html"
                    if not target.is_file(): self._send(404, "JARVIS.html missing", "text/plain"); return
                    self._send(200, target.read_bytes(), "text/html; charset=utf-8"); return
                if path == "/api/status":
                    self._send(200, {"ok": True, "mode": "desktop-local", "model_available": __import__('core.hardware', fromlist=['choose_model']).choose_model(owner.app_dir, owner.hardware) is not None,
                        "hardware": {"ram_gb": round(owner.hardware.get("ram_gb", 0), 1), "cpu": owner.hardware.get("cpu_name", "Unknown")},
                        "knowledge": owner.knowledge.status()}); return
                self._send(404, {"error":"Not found"})
            def do_POST(self):
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length > 65536: self._send(413, {"error":"Request too large"}); return
                    body = json.loads(self.rfile.read(length) or b"{}")
                    path = urlparse(self.path).path
                    if path == "/api/search":
                        self._send(200, {"results": owner.knowledge.search(body.get("query", ""))}); return
                    if path == "/api/article":
                        self._send(200, owner.knowledge.wikipedia.article(body.get("path", ""))); return
                    if path == "/api/chat":
                        prompt = str(body.get("message", "")).strip()
                        if not prompt or len(prompt) > 8000: self._send(400, {"error":"Enter a message under 8,000 characters."}); return
                        # Do not persist a user prompt until generation succeeds.
                        # Otherwise each failed request leaves an orphan user row;
                        # the next request then violates llama.cpp's role alternation.
                        history = owner.memory.recent(12)
                        refs = owner.knowledge.context_for(prompt)
                        answer = owner.ai.reply(prompt, history, refs)
                        owner.memory.add_exchange(prompt, answer)
                        self._send(200, {"answer":answer, "sources":[x.get("title") for x in refs]}); return
                    self._send(404, {"error":"Not found"})
                except Exception as exc: self._send(500, {"error":str(exc)})
        last_error = None
        for port in range(8765, 8776):
            try:
                self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
                self.port = port
                break
            except OSError as exc:
                last_error = exc
        if self.httpd is None:
            raise RuntimeError(f"Could not start the local JARVIS web companion on ports 8765-8775: {last_error}")
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="JARVIS-Web", daemon=True); self.thread.start()
        if open_browser: webbrowser.open(f"http://127.0.0.1:{self.port}/")
        return self.httpd
    def stop(self):
        if self.httpd: self.httpd.shutdown(); self.httpd.server_close(); self.httpd = None
