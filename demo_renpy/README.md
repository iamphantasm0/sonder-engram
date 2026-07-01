# Sonder — Ren'Py demo

A tiny visual-novel demo where two NPCs (Gethin the blacksmith, Mara the bandit)
remember what you did **across sessions**. Every greeting is recalled from the
Cognee knowledge graph — not a Ren'Py flag.

## Why a sidecar?

Ren'Py ships its own Python interpreter, which can't host Cognee's native
dependencies (kuzu / lancedb / onnxruntime). So the SDK runs as a small local
HTTP **sidecar** (`sonder_engram.service`) in your normal venv, and Ren'Py talks
to it over `http://127.0.0.1:8765`. This is also the seam the future web build uses.

## 1. Start the sidecar (in your SDK venv)

From the repo root, with the SDK installed (`pip install -e ".[fastembed]"`) and a
`.env` filled in (DeepSeek + local fastembed — see `../.env.example`):

```bash
set -a; source .env; set +a          # load LLM_/EMBEDDING_ vars
python -m sonder_engram.service       # listens on 127.0.0.1:8765
```
Leave it running. `SONDER_PORT` overrides the port.

## 2. Add the demo to a Ren'Py project

Ren'Py projects need their launcher-generated shell (gui, options, screens), so:

1. Open the **Ren'Py launcher** → **Create New Project** (Ren'Py 8.x).
2. Copy **`game/script.rpy`** and **`game/sonder.rpy`** from here into that
   project's `game/` folder, replacing the default `script.rpy`.
3. **Launch Project**.

## 3. See the memory work

1. Play through: greet Gethin (he won't know you yet), choose praise or insult,
   then spare or turn in Mara.
2. At **"Night falls"**, open the Ren'Py menu and **Save**, then **quit Ren'Py**.
3. **Relaunch** and **Load** the save.
4. Choose **"Ask Gethin / Mara how they feel about you."** Their answers come from
   the persisted graph — insult him and he's still cold; spare her and she's still
   grateful. No flags involved.

## Notes

- Each recall calls an LLM through the sidecar, so expect a ~few-second pause. The
  demo shows a "…looks up" beat to cover it; a production game would precompute at
  scene entry off the main thread.
- If a line reads *"the town is oddly silent…"*, the sidecar isn't running on :8765.
- Player identity is `player_uuid`, minted once and stored in the save slot, so the
  NPCs keep knowing *this* playthrough across launches.
