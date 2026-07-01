"""A tiny localhost HTTP sidecar that exposes the Sonder SDK over JSON.

Why this exists: engines like Ren'Py bundle their own Python interpreter, which
can't host Cognee's native dependencies (kuzu / lancedb / onnxruntime). Run this
sidecar in your SDK venv and let the game talk to it over HTTP. It's also the
seam that a future web build / non-Python engine uses.

Run (in the venv that has cognee + your .env):
    python -m sonder_engram.service          # binds 127.0.0.1:8765 (SONDER_PORT to change)

Endpoints (JSON in, JSON out):
    GET  /health                                     -> {"ok": true}
    POST /remember {npc_id, player_id, event}        -> {"ok": true}
    POST /recall   {npc_id, player_id, question}     -> {"answer": "..."}
    POST /sync     {npc_id, player_id}               -> {"ok": true}
    POST /forget   {npc_id, player_id}               -> {"ok": true}

Localhost, single-machine use. NOT hardened for public exposure (see issue #8).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .npc import NPC

_log = logging.getLogger("sonder_engram")

# One NPC object per (npc_id, player_id). They all share the SDK's single
# background worker + serialization lock, so concurrent HTTP requests are safely
# serialized onto one Cognee loop.
_npcs: dict = {}
_npcs_lock = threading.Lock()


def _get_npc(npc_id: str, player_id: str) -> NPC:
    key = (npc_id, player_id)
    with _npcs_lock:
        npc = _npcs.get(key)
        if npc is None:
            npc = NPC(npc_id, player_id)
            _npcs[key] = npc
        return npc


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"ok": True})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception as exc:
            return self._send(400, {"error": f"bad json: {exc}"})

        npc_id = data.get("npc_id")
        player_id = data.get("player_id")
        if not npc_id or not player_id:
            return self._send(400, {"error": "npc_id and player_id are required"})

        npc = _get_npc(npc_id, player_id)
        try:
            if self.path == "/remember":
                npc.remember(data.get("event", ""))
                return self._send(200, {"ok": True})
            if self.path == "/recall":
                return self._send(200, {"answer": npc.recall(data.get("question", ""))})
            if self.path == "/sync":
                npc.sync()
                return self._send(200, {"ok": True})
            if self.path == "/forget":
                npc.forget()
                return self._send(200, {"ok": True})
        except Exception as exc:
            _log.error("sidecar %s failed: %s", self.path, exc)
            return self._send(500, {"error": str(exc)})
        self._send(404, {"error": "not found"})

    def log_message(self, *args):  # keep the console clean
        pass


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), _Handler)
    print(f"sonder sidecar listening on http://{host}:{port}")
    _log.info("sonder sidecar on http://%s:%d", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    serve(port=int(os.environ.get("SONDER_PORT", "8765")))
