# Sonder bridge for Ren'Py — talks to the sonder-engram HTTP sidecar.
#
# Ren'Py ships its own Python and can't host Cognee's native deps, so the SDK
# runs in a sidecar (python -m sonder_engram.service) and we call it over HTTP.
# See demo_renpy/README.md to run it.

init python:
    import json
    import uuid
    import urllib.request

    SONDER_URL = "http://127.0.0.1:8765"

    def _sonder_post(path, payload, timeout=90):
        req = urllib.request.Request(
            SONDER_URL + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": str(e)}

    def ensure_player_id():
        # Stable across sessions: minted once, then stored IN the save slot
        # (player_uuid is a `default` var, so Ren'Py serializes it with the save).
        if not getattr(store, "player_uuid", None):
            store.player_uuid = str(uuid.uuid4())

    def sonder_remember(npc_id, event):
        _sonder_post("/remember", {"npc_id": npc_id, "player_id": store.player_uuid, "event": event})

    def sonder_sync(npc_id):
        _sonder_post("/sync", {"npc_id": npc_id, "player_id": store.player_uuid})

    def sonder_recall(npc_id, question):
        res = _sonder_post("/recall", {"npc_id": npc_id, "player_id": store.player_uuid, "question": question})
        if res.get("error"):
            return "(the town is oddly silent — is the sonder sidecar running on :8765?)"
        return res.get("answer") or "I don't think I know you."

# Saved with the slot; identifies THIS player to the NPCs' memory.
default player_uuid = None
