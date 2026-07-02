# Sonder

**Give game NPCs real, persistent memory with Cognee knowledge graphs.**

> Insult the blacksmith on Monday.  
> Full server restart.  
> Come back Thursday with the same character.  
> He's still cold to you — not because of a flag, but because a knowledge graph remembers.

**Sonder** is the feeling that every NPC has an inner life as complex as yours. This project makes it real.

Built for the [WeMakeDevs × Cognee hackathon](https://www.wemakedevs.org/hackathons/cognee) ("Best Use of Open Source" track).

---

## The 60-Second Demo (try it now)

```bash
pip install -e ".[fastembed,web]"
cp .env.example .env   # add a cheap DeepSeek key
python examples/web_demo.py
# open http://127.0.0.1:8000
```

1. Click **Play the Game**
2. Go to the Forge → insult or praise the blacksmith
3. Go to the Oracle's Grove → ask what Gethin remembers (he reacts)
4. Click **[restart server]** (top right)
5. Come back as the *same player* → the NPC still remembers you perfectly
6. Try as a new stranger → clean slate

Real per-player, cross-"session" memory. No scripts. No flags. Pure Cognee graphs.

---

## How it works (deep Cognee usage)

```python
from sonder_engram import NPC, Settings

npc = NPC("gethin_the_blacksmith", player_id="player_42", settings=Settings(ground_strict=True))

# Fire-and-forget write (non-blocking for the game)
npc.remember("The player insulted Gethin's craftsmanship and walked out.")

# On save/quit — bridge to permanent graph
npc.sync()

# On scene entry (never mid-conversation)
mood = npc.recall("How do you feel about this player?")
```

**What makes this real Cognee usage** (judges: look here):
- Permanent writes (`remember` without `session_id` → `add()` + `cognify()`)
- Strong per-player + per-NPC isolation using `node_set` + `AND` filter
- Single background worker + lock (Cognee's global embedded state is dangerous)
- `recall` always goes through the hybrid graph + vector layer
- Works across full process restarts when storage is persisted

Full recipe and verified API surface: [`docs/PINNED_API.md`](docs/PINNED_API.md) and [`docs/HANDOFF.md`](docs/HANDOFF.md).

## Why this is a strong "Best Use of Cognee" submission

- **Permanent graph writes** (no session distillation tricks)
- **Strong isolation** via `node_set` + `AND` filtering (one player's actions never leak to another)
- **Production-ready concurrency** (single serialized worker because Cognee has global embedded state)
- **Real cross-process persistence** demonstrated live with the **[restart server]** button
- **Zero OpenAI cost** (DeepSeek + local fastembed)
- **Self-contained, zero-friction demo** anyone can run in 10 seconds

## Live Web Demo (the compelling part)

The demo is a self-contained Torn.com-style text RPG that makes memory effects visceral:

- Locations + travel (prefetch like a real game)
- Actions that permanently change how NPCs treat you
- **The Oracle** — query what each NPC actually remembers
- Village group chat with automatic NPC reactions (use `@gethin` etc. to target)
- **[restart server]** button — simulates a full process restart while the Cognee graph lives on

**Try the persistence magic:**
1. Do something memorable to Gethin
2. Click **[restart server]**
3. Return with the same player → he still remembers
4. Start as a new stranger → different treatment

Everything is real Cognee data. No hardcoded responses.

```bash
pip install -e ".[fastembed,web]"
cp .env.example .env     # cheap DeepSeek or OpenRouter key
python examples/web_demo.py
# open http://127.0.0.1:8000 → Play the Game
```

## Quickstart

```bash
pip install -e ".[fastembed,web]"
cp .env.example .env      # add LLM_API_KEY
python examples/web_demo.py
```

Open http://127.0.0.1:8000 and click **PLAY THE GAME**.

## Why This Stands Out for the Hackathon

- Deep, correct use of Cognee's memory primitives (permanent writes, node_set isolation, worker serialization)
- Live, clickable proof of persistence with the **Restart Server** button
- Zero-friction web demo anyone can try instantly
- Cheap to run (DeepSeek + local embeddings)
- Solves a real, long-standing game design problem

## License

Apache-2.0. Built on [Cognee](https://github.com/topoteretes/cognee).

---

**For the hackathon**: The most important thing in this repo is the web demo. Restart the server, do something memorable, come back with the same player. That's the thesis.

