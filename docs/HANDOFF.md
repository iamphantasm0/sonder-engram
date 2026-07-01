sonder-engram — Technical Handoff
Last updated: 2026-07-01. Written for another agent/developer picking this up cold.

0. TL;DR for whoever's reading this
sonder-engram is an open-source Python SDK that gives game NPCs persistent, per-player memory using Cognee (a knowledge-graph memory engine) as the whole memory brain. An NPC remembers what a specific player did to it, across full game restarts.

The SDK and an HTTP sidecar are done, merged to main, and verified on real hardware (DeepSeek LLM + local fastembed embeddings — no OpenAI, no cost).
There's a Ren'Py dialogue demo merged but not yet run visually.
What's most likely left for you: build a richer game layer (e.g. a Godot/Pygame overworld) that talks to the sidecar over HTTP, and/or produce the demo video. The memory backend is solved — don't rebuild it. See §12.
Repo: github.com/iamphantasm0/sonder-engram. Everything is on main. No open PRs. Deferred hardening is filed as issues #3–#9.
Built for the WeMakeDevs × Cognee hackathon ("Best Use of Open Source"). The judged thing is the use of Cognee for memory, not game production values.

1. What it is & the core thesis
Normal game NPCs are stateless — they forget you the moment a scene ends, or track relationships with hand-coded flags. sonder-engram makes an NPC's memory a real knowledge graph:

remember(event) — the NPC ingests something the player did (builds/updates its graph).
recall(question) — the NPC answers in character, grounded in that graph.
Memory is isolated per (NPC, player) and survives process restarts.
The demo beat: insult the blacksmith → quit the whole game → relaunch → he's still cold, from the graph, not a flag.

2. Current status (2026-07-01)
Merged to main & working:

SDK: NPC + MemoryBackend/LocalCogneeBackend/FakeBackend, background worker, minimal ontology, config, 6 passing unit tests.
Correctness: permanent-write graph build, single-worker+lock concurrency, per-NPC/per-player node_set isolation.
Two rounds of code-review fixes (observable errors, timeouts, input bounds, timeout cancellation, safe async API).
HTTP sidecar (sonder_engram.service) + Ren'Py demo (demo_renpy/).
Verified on the founder's Ubuntu box via the sidecar: recall returned a correct, grounded answer.
Not done yet:

CI workflow (.github/workflows/ci.yml) is written but not in the repo — the GitHub API integration lacks the workflows permission, so it must be committed by a human/local tool. Content is in this repo's history/handoff (§11).
Ren'Py demo never launched in Ren'Py (authored only).
90-second demo video.
PyPI publish + hackathon submission.
Deferred hardening: issues #3–#9.

3. Repo map
sonder-engram/
  pyproject.toml            # hatchling; name "sonder-engram"; dep: cognee>=1.2.2; extras [fastembed],[dev]
  README.md                 # origin story + quickstart
  LICENSE                   # Apache-2.0 (matches Cognee)
  .env.example              # DeepSeek + fastembed defaults; commented OpenAI switch
  .gitignore                # ignores .env, .cognee/, venvs
  docs/
    PINNED_API.md           # VERIFIED Cognee 1.2.2 API surface + the corrected recipe. Source of truth.
    HANDOFF.md              # this file
  src/sonder_engram/
    __init__.py             # exports NPC, backends, worker, Settings, helpers; __version__
    npc.py                  # NPC — the public API (sync + async methods)
    backend.py              # MemoryBackend ABC + LocalCogneeBackend + FakeBackend + _serialize() lock
    worker.py               # AsyncMemoryWorker (bg loop) + get_default_worker() singleton
    ontology.py             # minimal NPC ontology (opt-in via Settings.use_custom_ontology)
    config.py               # Settings + naming helpers (npc_dataset, player_tag, new_session_id)
    service.py              # the HTTP sidecar (python -m sonder_engram.service)
  examples/terminal_demo.py # MVP: two NPCs remember across runs (no engine)
  demo_renpy/               # Ren'Py visual-novel demo (game/script.rpy, game/sonder.rpy, README.md)
  tests/test_npc_unit.py    # FakeBackend + pure-function tests (no key needed)

4. Architecture
flowchart TD
  subgraph Game["Game layer (Ren'Py today; Godot/Pygame next)"]
    A[dialogue / choices] --> B[HTTP client]
  end
  B -- "POST /remember /recall /sync" --> S[sonder_engram.service<br/>localhost:8765]
  subgraph SDK["sonder-engram SDK (runs in a normal venv)"]
    S --> C[NPC: remember/recall/sync/forget]
    C --> W[AsyncMemoryWorker<br/>single bg loop]
    C --> E[MemoryBackend]
    E --> L[LocalCogneeBackend]
  end
  L --> COG[(Cognee: graph + vector + embedded DBs)]
Why the sidecar exists: Ren'Py (and some other engines) bundle their own Python interpreter that can't host Cognee's native deps (kuzu / lancedb / onnxruntime). So the SDK runs in a normal venv and the game talks to it over localhost HTTP. This is also the seam a web build would use.

Concurrency invariant (important): Cognee has global state (one embedded DB). Concurrent writes from different event loops corrupt each other. So all memory ops funnel onto ONE shared background loop (get_default_worker()), serialized by a per-loop asyncio.Lock (backend._serialize()). The async API (aremember/arecall) routes through that same worker via asyncio.wrap_future, so it's safe to mix with the sync API. Do not call LocalCogneeBackend methods directly from your own loop — go through NPC (or the sidecar).

5. The SDK API (Python)
from sonder_engram import NPC, Settings, FakeBackend

npc = NPC("gethin_the_blacksmith", player_id="player_42")   # stable player_id!
npc.remember("The player insulted Gethin's craftsmanship.") # non-blocking (bg worker)
npc.sync()                                                   # flush pending writes (on save/quit)
mood = npc.recall("How do you feel about this player?")      # blocks ~5-7s; returns "" if unknown
npc.forget()                                                 # wipe this NPC's memory

# async variants (route through the same worker): aremember / arecall / async_sync / aforget
# tests / offline: NPC(..., backend=FakeBackend()) — no LLM, no cognee, no key
Settings (pass NPC(..., settings=Settings(...))):

search_type="GRAPH_COMPLETION", top_k=8
use_custom_ontology=False (opt-in minimal ontology)
ground_strict=False (True biases recall to stored facts, less LLM embellishment)
default_timeout=45.0 (blocking-call cap; recall returns "" + logs on timeout)
max_event_chars=4000 (truncates oversized writes)
raise_on_error=False (True → recall re-raises real errors instead of returning "")
Observability: background write failures are logged and stored on worker.last_error.

6. The sidecar HTTP contract (what the game layer uses)
Run it (in the venv with .env loaded):

python -m sonder_engram.service        # 127.0.0.1:8765 ; SONDER_PORT to change
Method	Path	Body	Returns
GET	/health	—	{"ok": true}
POST	/remember	{"npc_id","player_id","event"}	{"ok": true}
POST	/recall	{"npc_id","player_id","question"}	{"answer": "..."} (may be "")
POST	/sync	{"npc_id","player_id"}	{"ok": true}
POST	/forget	{"npc_id","player_id"}	{"ok": true}
The sidecar keeps one server-side NPC per (npc_id, player_id), all on the shared worker → concurrent HTTP requests are safely serialized. Localhost/single-machine only; not hardened for public exposure (issue #8).

Verified example (real): remember an insult → sync → recall → {"answer": "I view this player negatively because they mocked Gethin and left without buying."}. An untaught NPC returns {"answer": ""}.

7. How Cognee is used (the recipe — details in docs/PINNED_API.md)
These are hard-won; changing them tends to break things:

Write = permanent, not session-cache. remember calls cognee.remember(text, dataset_name=npc__<id>, node_set=[npc__<id>, player__<id>]) with no session_id, which runs add() + cognify() and actually builds the graph. The session-cache + improve() distillation path does not create the dataset on a clean install (fails with "dataset not found"), leaving the graph empty.
Isolation = node_set, not datasets. With ENABLE_BACKEND_ACCESS_CONTROL=false, datasets=[name] does NOT scope retrieval (everything pools), and GRAPH_COMPLETION bridges NPCs via the shared player node. So we tag every write with [npc__<id>, player__<id>] and recall with node_name=[npc__<id>, player__<id>], node_name_filter_operator="AND".
Recall: cognee.recall(query_text=..., datasets=[npc__<id>], node_name=[...], query_type=SearchType.GRAPH_COMPLETION, node_name_filter_operator="AND", auto_route=False). auto_route=False stops Cognee rerouting to a different search type.
Reset: await cognee.prune.prune_data(); await cognee.prune.prune_system(metadata=True).
BAML is not used (framework defaults to instructor); ignore baml_llm_*.

8. Environment / config
Python 3.10–3.14 (the sandbox's system 3.9 is too old; we use 3.12). Cognee pinned at 1.2.2.
Default provider stack (no OpenAI): DeepSeek LLM + local fastembed embeddings. See .env.example:
LLM_PROVIDER=custom
LLM_MODEL=openai/deepseek-chat
LLM_ENDPOINT=https://api.deepseek.com/v1
LLM_API_KEY=...                 # DeepSeek key (rotate; never commit)
EMBEDDING_PROVIDER=fastembed
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384
ENABLE_BACKEND_ACCESS_CONTROL=false
Switching to OpenAI later is a two-line change (LLM + embeddings) but requires re-embedding existing memories (different vector space/dimension → prune + re-ingest). Documented in .env.example.

9. Run & test
# from repo root, in a Python 3.12 venv
pip install -e ".[fastembed,dev]"
cp .env.example .env      # fill LLM_API_KEY
set -a; source .env; set +a

pytest -q                                   # 6 tests, FakeBackend, NO key
python examples/terminal_demo.py write      # then, in a fresh process:
python examples/terminal_demo.py recall     # each NPC recalls only its own event
python -m sonder_engram.service             # the sidecar on :8765
Ren'Py demo: see demo_renpy/README.md (start sidecar → drop game/*.rpy into a Ren'Py project → play → save → quit → relaunch → load → ask).

10. Gotchas (read before you touch anything)
Test from a CLEAN Cognee dir. Leftover state (~/.cognee, <venv>/.../cognee/.cognee_system) masks bugs — a "pass" on dirty state was a false positive earlier. Wipe both between real tests.
Cognee daemon threads exit noisily ("Task was destroyed", "Unclosed client session") at interpreter shutdown — cosmetic, non-fatal, from litellm/aiohttp. Don't chase it (low-priority).
The integration can't push .github/workflows/* — needs the workflows permission. Commit CI files with a human/local git session.
Recall is slow (~5–7s) — it's an LLM call. Never block a game frame on it; precompute at scene/interaction entry and show a beat. See §12.
player_id must be stable across sessions, or the NPC "forgets" the player. Store it in the save.
Don't call LocalCogneeBackend directly across loops — use NPC/sidecar (concurrency invariant, §4).
DeepSeek has no embeddings — that's why embeddings are local fastembed. Don't point embeddings at DeepSeek.
Secret hygiene: .env is gitignored and NOT in history; keep real keys local, rotate anything exposed.

11. What's left / next tasks
Add CI — create .github/workflows/ci.yml (human commit; integration can't):

name: CI
on: { push: { branches: [main] }, pull_request: {} }
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: |
          python -m pip install --upgrade pip
          pip install -e . --no-deps
          pip install "pytest>=8"
      - run: python -c "import sonder_engram; print(sonder_engram.__version__)"
      - run: pytest -q

Pick a demo surface & record the 90-second video (the submission artifact): insult → quit → relaunch → still-remembers.
PyPI publish (python -m build + twine upload; TestPyPI first) + hackathon submission.
Game layer (see §12) — the biggest open build.
Deferred hardening: issues #3–#9.

12. Building the game layer (for a local agent)
Recommended engine: Godot or Pygame (Ren'Py is a visual-novel engine — fine for dialogue, wrong for a Pokémon-style overworld). A local agent that can launch the engine and iterate visually is the right tool here; the SDK/sidecar is stable and headless-verified, so you only integrate over HTTP.

Integration pattern:

Start the sidecar in the SDK venv (python -m sonder_engram.service). Ship a launcher that boots it alongside the game (or document "run the sidecar first").
On new game, mint a player_id (UUID) and store it in the engine's save (Godot user://, etc.). Reuse it forever for that save.
When the player does something meaningful to an NPC → POST /remember {npc_id, player_id, event} (fire-and-forget; the sidecar returns immediately).
At interaction/scene entry (not every frame) → POST /recall {npc_id, player_id, question}; it takes a few seconds, so do it async / off the main thread and show a "…" beat, then render the answer as dialogue.
At save points / quit → POST /sync {npc_id, player_id} for each active NPC so memory is durable.
Godot (GDScript) sketch — HTTPRequest is async, perfect for not blocking:

const SONDER := "http://127.0.0.1:8765"
func sonder_recall(npc_id, question, on_answer):
    var http := HTTPRequest.new(); add_child(http)
    http.request_completed.connect(func(_r,_c,_h,body):
        on_answer(JSON.parse_string(body.get_string_from_utf8()).get("answer","")), CONNECT_ONE_SHOT)
    http.request("%s/recall" % SONDER, ["Content-Type: application/json"],
        HTTPClient.METHOD_POST, JSON.stringify({"npc_id":npc_id,"player_id":player_id,"question":question}))
Pygame: use requests/urllib on a worker thread; kick off recall when the player enters an NPC's tile, store the result, and open the dialogue box once it's back.

Do not reimplement memory, isolation, or Cognee wiring in the game — it's all behind the sidecar. If you need a new capability (e.g. batched writes, gossip), add it to the SDK/sidecar and keep the game thin.

13. Deferred backlog (GitHub issues)
#3 per-event cognify cost — batch/debounce/importance-filter writes.
#4 concurrency — replace global lock + single loop with a serialized executor / bounded pool; concurrent reads.
#5 cross-loop async safety — proper serialized executor so direct-backend async use is safe.
#6 typed error model + structured logging (session/npc/player correlation).
#7 durability & Cognee coupling — backup/migration/integrity; robust recall-response parsing; version pinning.
#8 prompt-injection / memory-poisoning hardening for event/question.
#9 secret-scan pre-commit + CI check.

14. Key decisions & rationale (don't re-litigate)
Name: brand "Sonder", package sonder-engram, import sonder_engram.
Python + Cognee self-hosted (open-source track). DeepSeek + fastembed so it runs with no OpenAI budget.
Permanent writes over session-cache distillation (the distillation path leaves the graph empty on clean installs).
node_set AND-isolation because datasets don't scope retrieval with access control off.
Sidecar because Ren'Py/native engines can't host Cognee's deps.
Dialogue demo for the submission, not a Pokémon-style game — the hackathon scores memory/Cognee use, and a full game is scope creep. A richer overworld is a post-submission "vision" build (this section + §12 is your starting point).
Prior reviews took the SDK from 3/10 → "ready after minor fixes (5.5)"; the named blockers (silent errors, no timeouts, broken shutdown, async footgun, committed secret) are all addressed. Remaining items are the deferred backlog, not correctness holes.
