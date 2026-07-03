# Sonder

**Give game NPCs real, persistent memory with Cognee knowledge graphs.**

> Insult the blacksmith on Monday.  
> Full server restart.  
> Come back Thursday with the same character.  
> He's still cold to you — not because of a flag, but because a knowledge graph remembers.

**Sonder** is the feeling that every NPC has an inner life as complex as yours. This project makes it real.

🎮 **Live demo:** [sonder-engram.up.railway.app](https://sonder-engram.up.railway.app) — no setup, click and play.

Built for the [WeMakeDevs × Cognee hackathon](https://www.wemakedevs.org/hackathons/cognee) ("Best Use of Open Source" track).

---

## The 60-Second Demo (try it now)

Use the [live demo](https://sonder-engram.up.railway.app), or run it yourself:

```bash
pip install -e ".[fastembed,web]"
cp .env.example .env   # add any OpenAI-compatible LLM key (see Providers below)
python examples/web_demo.py
# open http://127.0.0.1:8000
```

<!-- Once published to PyPI, installing the SDK alone is just: pip install sonder-engram -->

1. Click **Play the Game** — type a name; it's your save, and it stays logged in on this browser
2. Go to the Forge → insult or praise the blacksmith
3. Go to the Drunken Boar → buy Mara a drink… or sell her out to the guards (or flirt — she has opinions either way)
4. Visit the Oracle's Grove → **Elara already knows what you did across town** (word travels as gossip)
5. Click **[restart server]** (top right)
6. Come back as the *same player* → the NPCs still remember you perfectly
7. Try a new name → clean slate

Real per-player, cross-"session" memory. No scripts. No flags. Pure Cognee graphs.

---

## How it works (deep Cognee usage)

```python
from sonder_engram import NPC, Settings

npc = NPC("gethin_the_blacksmith", player_id="player_42", settings=Settings(ground_strict=True))

# Fire-and-forget write (non-blocking for the game; the graph is built here)
npc.remember("The player insulted Gethin's craftsmanship and walked out.")

# On save/quit — flush pending background writes so memory is durable
npc.sync()

# On scene entry (never mid-conversation)
mood = npc.recall("How do you feel about this player?")
```

**What makes this real Cognee usage** (judges: look here):
- Permanent writes (`remember` without `session_id` → `add()` + `cognify()` builds the graph per event)
- Strong per-player + per-NPC isolation using `node_set` + `AND` filter
- **Cross-NPC "gossip"** — public deeds also reach Elara the seer as an explicit second engram written to *her* graph; isolation stays honest, and word still travels
- **NPCs remember conversations** — chat exchanges (your line + their reply) are committed to the targeted NPC's graph
- Single background worker + lock (Cognee's global embedded state is dangerous)
- `recall` always goes through the hybrid graph + vector layer
- Works across full process restarts when storage is persisted

Full recipe and verified API surface: [`docs/PINNED_API.md`](docs/PINNED_API.md) and [`docs/HANDOFF.md`](docs/HANDOFF.md).

## The demo world

A self-contained Torn.com-style text RPG that makes memory effects visceral:

- Locations + travel (prefetches memories like a real game engine on scene load)
- Actions that permanently change how NPCs treat you — including a full relationship arc with Mara (drinks, flirting, betrayal… and earning your way back)
- **Elara the Seer** — query what each NPC actually remembers, and hear the village gossip about you
- Village group chat with automatic NPC reactions (`@gethin` / `@mara` / `@elara` to target) — targeted NPCs remember the exchange
- **[restart server]** button — simulates a full process restart while the Cognee graph lives on
- Your player name persists in the browser, so refreshes and restarts keep you logged in

Everything is real Cognee data. No hardcoded responses.

## Providers

Any OpenAI-compatible LLM works; embeddings run **locally** via fastembed (no key, no cost). Copy `.env.example` and set your key. Two gotchas we hit so you don't have to:

- **OpenRouter:** the router strips the first prefix, so the model string needs it doubled — `LLM_MODEL="openai/openai/gpt-4o-mini"`
- **Small models (gpt-4o-mini etc.):** set `LLM_INSTRUCTOR_MODE=tool_call` — prompt-based JSON mode can echo the schema instead of an instance and trigger retry storms

DeepSeek and Gemini configs are documented in [`.env.example`](.env.example). Deploying? [`railway.toml`](railway.toml) documents the volume + `DATA_ROOT_DIRECTORY`/`SYSTEM_ROOT_DIRECTORY`/`CACHE_ROOT_DIRECTORY` env vars — Cognee's databases don't live in `~/.cognee`, and without these your memories die on redeploy.

## Why this is a strong "Best Use of Open Source" entry

- Deep, correct use of Cognee's memory primitives (permanent writes, `node_set` isolation, worker serialization) — verified from clean state and documented
- **Live, clickable proof of persistence** with the [restart server] button — and a hosted demo judges can play in ten seconds
- Cross-NPC memory (gossip) and conversation memory built on the same primitives
- Zero OpenAI dependency (any compatible provider + local embeddings)
- Solves a real, long-standing game design problem — and ships as a reusable SDK, not just an app

## License

Apache-2.0. Built on [Cognee](https://github.com/topoteretes/cognee).

---

**For the hackathon**: The most important thing in this repo is the web demo. Restart the server, do something memorable, come back with the same player. That's the thesis.
