# PINNED_API.md — Cognee API, verified for `sonder-engram`

> Day 0.5 gate output. The SDK codes against **this file**, not the live docs (which drift).
> Verified 2026-07-01 by installing cognee and introspecting signatures. Items needing a live LLM run are flagged PENDING.

## Pinned environment

- **cognee == 1.2.2**, **Python 3.12.13**, Linux (x86_64).
- The sandbox's system Python was **3.9**, which is too old — cognee needs **3.10–3.14**. Provisioned 3.12 via `uv`.
- Install used:
  ```bash
  uv venv .venv-cognee --python 3.12
  uv pip install "cognee==1.2.2"
  ```
- Default local stack: **embedded SQLite + LanceDB + Kuzu, no servers**. LLM + embeddings default to **OpenAI** (needs `LLM_API_KEY`).

## Runtime defaults (from the import banner — confirmed)

- New API: `remember` / `recall` / `forget` / `improve`. Legacy `add` / `cognify` / `search` still work.
- **Session memory is ON by default** (`CACHING=false` to disable).
- **Multi-tenant access control is ON by default** (`ENABLE_BACKEND_ACCESS_CONTROL=false` to disable).
  - Implication: `datasets=["name"]` resolves only within the **current user's** datasets. Cross-user shared datasets must be queried by `dataset_ids=[...]`.
  - For our single-user local demo this is fine. Recommend setting `ENABLE_BACKEND_ACCESS_CONTROL=false` in the demo `.env` to keep dataset-name lookups simple.
- `@cognee.agent` functions are auto-verified on registration.

## Confirmed signatures (verbatim, types trimmed for readability)

```python
remember(data, dataset_name='main_dataset', *, session_id=None, chunk_size=None,
         chunker=None, custom_prompt=None, run_in_background=False,
         self_improvement=True, session_ids=None, **kwargs) -> RememberResult

recall(query_text, query_type=None, *, datasets=None, dataset_ids=None, top_k=15,
       auto_route=True, scope=None, system_prompt=None,
       system_prompt_path='answer_simple_question.txt', node_name=None,
       node_name_filter_operator='OR', only_context=False, session_id=None,
       context_profile='qa', wide_search_top_k=100, triplet_distance_penalty=6.5,
       feedback_influence=0.0, verbose=False, retriever_specific_config=None,
       neighborhood_depth=None, neighborhood_seed_top_k=None,
       include_references=False, user=None, llm_config=None,
       embedding_config=None) -> list[RecallResponse...]

improve(dataset='main_dataset', *, run_in_background=False, node_name=None,
        session_ids=None, build_global_context_index=False,
        build_truth_subspace=False, **kwargs)

forget(*, data_id=None, dataset=None, dataset_id=None, everything=False,
       memory_only=False, user=None) -> dict

add(data, dataset_name='main_dataset', user=None, node_set=None, vector_db_config=None,
    graph_db_config=None, dataset_id=None, preferred_loaders=None,
    incremental_loading=True, data_per_batch=20, importance_weight=0.5,
    run_in_background=False, llm_config=None, embedding_config=None, **kwargs)

cognify(datasets=None, user=None, graph_model=KnowledgeGraph, chunker=TextChunker,
        chunk_size=None, chunks_per_batch=None, config=None, vector_db_config=None,
        graph_db_config=None, run_in_background=False, incremental_loading=True,
        custom_prompt=None, temporal_cognify=False, data_per_batch=20,
        llm_config=None, embedding_config=None, **kwargs)

search(query_text, query_type=SearchType.GRAPH_COMPLETION, user=None, datasets=None,
       dataset_ids=None, system_prompt_path='answer_simple_question.txt',
       system_prompt=None, top_k=15, node_type=NodeSet, node_name=None,
       node_name_filter_operator='OR', only_context=False, session_id=None, ...)
       -> List[SearchResult]

prune.prune_data()
prune.prune_system(graph=True, vector=True, metadata=False, cache=True)
```

## Behavior notes (from docstrings — confirmed)

- **`remember`**: no `session_id` → permanent (runs `add` + `cognify`). With `session_id` → session cache. `self_improvement=True` (default) also bridges the session into the permanent graph.
- **`recall`**: `session_id` **without** `datasets`/`query_type` → direct session-cache keyword lookup, falling through to the graph if nothing matches. With `datasets` + `query_type=GRAPH_COMPLETION` → graph search. Returns a list of discriminated entries.
- **`improve`**: with `session_ids=[...]` it bridges those sessions into the permanent graph and applies feedback weights. **This is our `sync()`.**
- **`forget`**: `dataset=` deletes that dataset's data + graph + vectors; `everything=True` nukes; `memory_only=True` drops graph memory but keeps raw data.

## SearchType members (real, from the enum)

`AGENTIC_COMPLETION, CHUNKS, CHUNKS_LEXICAL, CODING_RULES, CYPHER, FEELING_LUCKY,`
**`GRAPH_COMPLETION`** (default — what we use)`, GRAPH_COMPLETION_CONTEXT_EXTENSION, GRAPH_COMPLETION_COT, GRAPH_COMPLETION_DECOMPOSITION, GRAPH_SUMMARY_COMPLETION, HYBRID_COMPLETION, NATURAL_LANGUAGE, RAG_COMPLETION, SUMMARIES, TEMPORAL, TRIPLET_COMPLETION`

## NodeSet

`from cognee.modules.engine.models.node_set import NodeSet` — importable.
- `search()` filters with `node_type=NodeSet` + `node_name=[...]`.
- `recall()` filters with `node_name=[...]` only (no `node_type` param).

## Recall return shape (confirmed)

`recall()` returns a list of entries discriminated by a `source` field:

| Entry type | Key fields | Use |
|---|---|---|
| `ResponseQAEntry` | `answer`, `question`, `context`, `qa_id`, `feedback_score`, `used_graph_element_ids` | **The completion answer is in `.answer`** |
| `ResponseGraphEntry` | `text`, `score`, `dataset_name`, `metadata` | Raw graph hits |
| `ResponseGraphContextEntry` | `content` | Context block |
| `ResponseSessionContextEntry` | `content`, `context_profile` | Session context |
| `ResponseAgentTraceEntry` | trace fields | Agent traces |

SDK `first_answer(res)`: return the `ResponseQAEntry`'s `.answer`; fall back to `.content` / `.text`.

## `remember` kwargs (confirmed via RememberKwargs)

`node_set`, `graph_model`, `dataset_id`, `preferred_loaders`, `incremental_loading`, `data_per_batch`, `chunks_per_batch`, `user`, `vector_db_config`, `graph_db_config`, `content_type`, `llm_config`, `embedding_config`, ...

So `remember(text, dataset_name=..., session_id=..., node_set=[...], graph_model=<ontology>, self_improvement=...)` are all valid. `graph_model` is how we pass the minimal NPC ontology.

## `sonder-engram` → cognee call mapping (LocalCogneeBackend)

```python
from cognee import SearchType
NPC_DS   = f"npc__{npc_id}"
PLAYER   = [f"player__{player_id}"]

# during play (fast, session cache, no graph build yet)
await cognee.remember(event_text, dataset_name=NPC_DS, session_id=sess,
                      node_set=PLAYER, self_improvement=False)

# on save/quit (bridge the session into the permanent per-NPC graph)
await cognee.improve(dataset=NPC_DS, session_ids=[sess])

# at scene entry (graph-grounded answer, scoped to this NPC + player)
res = await cognee.recall(query_text=q, datasets=[NPC_DS], node_name=PLAYER,
                          query_type=SearchType.GRAPH_COMPLETION, session_id=sess)

# wipe this NPC's memory
await cognee.forget(dataset=NPC_DS)

# reset (tests / demo seeding)
await cognee.prune.prune_data(); await cognee.prune.prune_system(metadata=True)
```

## Status

**VERIFIED offline (no key needed):** install + import on py3.12; all core signatures; `prune` signatures; full `SearchType` list; `NodeSet` import path; recall return shape; `remember` kwargs incl. `node_set` + `graph_model`.

**PENDING — needs `LLM_API_KEY` (run `day05_smoke.py`):**
1. `node_set` tags on session writes survive the `improve()` bridge, so `recall(node_name=...)` filters correctly. *If not:* tag at permanent-write time, or use a dataset per (npc, player).
2. `recall(datasets + node_name + session_id + GRAPH_COMPLETION)` returns a populated `ResponseQAEntry.answer`.
3. **Cross-process persistence:** write + improve in run A, then `recall` in a fresh process (run B) returns the memory. (The whole demo rests on this.)
4. Per-call latency with `gpt-5-mini` (`remember`, `improve`, `recall`) to size the scene-entry "…" beat.
5. `self_improvement=False` on session writes + one explicit `improve()` on sync behaves as intended (no premature graph build).

To finish these, run `day05_smoke.py write` then (fresh process) `day05_smoke.py recall` with `LLM_API_KEY` set. Do **not** paste the key into chat — see the reply for secure options.

---

## Day-1 corrected recipe (verified end-to-end from a CLEAN state)

Running the SDK against a **wiped** Cognee dir surfaced three issues the earlier dirty-state run masked. These fixes are what the SDK ships.

1. **Build the graph with a PERMANENT write.** `remember(text, dataset_name, node_set)` with **no `session_id`** → Cognee runs `add()` + `cognify()`, which builds the per-NPC graph and materializes the dataset. The session-cache + `improve()` path does **not** create the dataset on a clean install (`SessionDistillationError: dataset not found`), so the graph stays empty and recall returns nothing or hallucinates. Do not rely on session distillation.

2. **Serialize writes on ONE loop.** Cognee has global state (one embedded DB). Concurrent `cognify` runs from separate event loops corrupt each other — symptom: one of two NPCs' memory comes back empty. Use a single shared background worker + an `asyncio` lock so memory ops run one at a time.

3. **Isolation is by `node_set`, not dataset.** With `ENABLE_BACKEND_ACCESS_CONTROL=false`, `datasets=[name]` does **not** scope retrieval — even `CHUNKS` returns other datasets' text, and `GRAPH_COMPLETION` bridges across NPCs through the shared player node. Isolate with node_set tags:
   - write `node_set=["npc__<id>", "player__<id>"]`
   - recall `node_name=["npc__<id>", "player__<id>"]` with `node_name_filter_operator="AND"`
   Verified: Gethin recalls only his event, Mara only hers, across a process restart.

4. **recall:** pass `auto_route=False` so it honors `GRAPH_COMPLETION` (otherwise Cognee may reroute to `GRAPH_COMPLETION_COT`). A brand-new NPC has no memory → Cognee raises a precondition error → the SDK catches it and returns `""` so dialogue never crashes.

5. **Latency (DeepSeek + local fastembed):** permanent write ~2–3s incl. cognify; recall ~5–7s. Absorbed by the background worker so the game loop never blocks.
