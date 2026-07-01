# Sonder

**Persistent memory for game NPCs, powered by [Cognee](https://github.com/topoteretes/cognee). They remember what you did.**

> **Sonder** *(n.)* — the realization that each passerby is living a life as vivid and complex as your own.
>
> Every NPC you've ever walked past was faking it. A looped smile, one line of dialogue, no memory of your face the moment you turned around. Props wearing people.
>
> Sonder ends that. It gives a game character a real memory — an *engram*, the trace a moment leaves behind — and lets it persist. Insult the blacksmith on Monday and he's still cold on Thursday. Spare a bandit and she remembers, then warns you when the ambush comes. Nothing scripted, no flags. The character remembers because underneath it a knowledge graph is quietly laying down engrams and connecting them.
>
> That's the whole thesis. Sonder is the feeling that the people in a world have inner lives. The engram is how we finally give them one.

Built for [*The Hangover Part AI: Where's My Context?*](https://www.wemakedevs.org/hackathons/cognee) — the WeMakeDevs × Cognee hackathon.

---

## How it works

`pip install sonder-engram`, then give any character a memory in a few lines:

```python
from sonder_engram import NPC

gethin = NPC("gethin_the_blacksmith", player_id="player_42")

# during play — non-blocking, never stalls the frame
gethin.remember("The player insulted Gethin's craftsmanship and walked out.")

# on save / quit — flush + bridge the session into permanent memory
gethin.sync()

# next session, at scene entry — recall shapes the dialogue
mood = gethin.recall("How do you feel about this player, and why?")
# -> "Gethin is cold and guarded — the player mocked his work and left."
```

Under the hood, each NPC is an isolated Cognee **dataset**; each player is a `node_set` tag. During play, events go to Cognee's fast **session cache**; on `sync()` they're bridged into the NPC's permanent **knowledge graph**. A background worker keeps the LLM-backed graph build off your game loop.

## Ren'Py

Ren'Py runs on Python, so `sonder_engram` imports directly. Recall runs an LLM, so do it **at scene entry** (not mid-dialogue) and cache the result:

```python
label enter_forge:
    "You push open the forge door."
    $ gethin_mood = gethin.recall("How do you feel about this player?")   # brief "…" beat
    gethin "[gethin_mood]"      # instant; no recall mid-conversation
```

Stable identity matters: mint `player_id` once at new-game and store it in the save slot so the NPC keeps knowing *this* player across launches.

## Providers (no OpenAI required)

Sonder is provider-agnostic — all model config lives in the environment (see [`.env.example`](.env.example)). The default, verified setup needs **no OpenAI budget**:

- **LLM:** DeepSeek (`custom` OpenAI-compatible provider)
- **Embeddings:** local **fastembed** (`all-MiniLM-L6-v2`, 384-dim) — no key, no cost

Funding OpenAI later is a two-line change (LLM + embeddings), documented in `.env.example`. Full verified API reference: [`docs/PINNED_API.md`](docs/PINNED_API.md).

## Status

Day-1 scaffold. Verified end to end (see `docs/PINNED_API.md`): DeepSeek + fastembed run the full `remember → sync → recall` loop, and **memory survives a process restart** (~2s write, ~2s bridge, ~6–7s recall).

**Roadmap**
- `HttpCogneeBackend` — talk to a hosted Cognee over HTTP, which unlocks a **web-playable** demo and lets non-Python engines (Unity, Godot) reuse the same memory.
- Town gossip — a shared dataset so reputation spreads between NPCs who never met you.
- A typed ontology / stricter recall grounding.

## Install (dev)

```bash
pip install -e ".[fastembed,dev]"
cp .env.example .env      # add your key(s)
pytest                    # unit tests use a fake backend (no key)
python examples/terminal_demo.py write     # then, in a fresh process:
python examples/terminal_demo.py recall

# Easy web demo (recommended for trying it out)
pip install -e ".[fastembed,web]"
cp .env.example .env
python examples/web_demo.py
# Then open http://127.0.0.1:8000
```

## License

Apache-2.0 — see [LICENSE](LICENSE). Built on [Cognee](https://github.com/topoteretes/cognee) (Apache-2.0).
