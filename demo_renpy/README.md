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
`.env` filled in (DeepSeek + local fastembed — see `../.env.example`).

### Easy launchers (recommended)

```bash
# Linux / macOS
cd demo_renpy
chmod +x launch_sidecar.sh
./launch_sidecar.sh
```

```bat
:: Windows
cd demo_renpy
launch_sidecar.bat
```

These scripts:
- Load your `.env`
- Start the sidecar using the installed `sonder-sidecar` command (or `python -m`)
- Print the next steps

You can also start it manually:

```bash
set -a; source .env; set +a
python -m sonder_engram.service
# or after pip install: sonder-sidecar
```

`SONDER_PORT` can be used to change the port (default 8765). Leave the sidecar running.

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

## Making it more runnable (exe + .sh)

### Option A — Sidecar as a standalone binary (recommended for distribution)

You can bundle just the memory sidecar into a single executable so players don't
need Python or a venv.

```bash
pip install pyinstaller
pyinstaller --onefile --name sonder-sidecar src/sonder_engram/service.py
```

- On Windows you get `dist/sonder-sidecar.exe`
- On Linux you get `dist/sonder-sidecar`

Then a player can run:

```bash
# Linux
./sonder-sidecar

# Windows
sonder-sidecar.exe
```

(They still need to put their LLM keys in the environment or you can embed a
default .env at build time — not recommended for secrets.)

### Option B — Full Ren'Py game as .exe / .sh

1. Copy the two `.rpy` files into a real Ren'Py project (as described above).
2. In the **Ren'Py launcher**, choose **"Build Distributions"**.
3. Ren'Py will generate platform packages, including:
   - `YourGame-1.0-pc.zip` → contains `YourGame.exe` + `lib/` folder
   - `YourGame-1.0-linux.tar.bz2` → contains `YourGame.sh`

Users then run the generated `YourGame.exe` or `YourGame.sh`.  
They must still start the sidecar separately (or you ship the sidecar exe next to it
and document "run sonder-sidecar.exe first, then YourGame.exe").

### Option C — Combined launcher (advanced)

You can write a small wrapper (Python or shell) that:
- Starts the sidecar as a subprocess (in the background)
- Then launches the Ren'Py game executable
- Kills the sidecar on exit

This is possible but out of scope for the basic demo. See issues for future work.
