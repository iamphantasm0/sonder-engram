"""Memory backends for Sonder.

The `NPC` never calls Cognee directly — it talks to a `MemoryBackend`. That seam
is the "open door": `LocalCogneeBackend` runs Cognee in-process today; an
`HttpCogneeBackend` (for the web build and non-Python engines) can slot in later
with zero change to NPC / ontology / gossip logic.

All calls map onto the Cognee v1.0 API confirmed in docs/PINNED_API.md.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Sequence

from .config import Settings

_log = logging.getLogger("sonder_engram")

# Cognee keeps global state (one embedded DB), so only one operation may touch it
# at a time or concurrent writes corrupt each other (one NPC's graph came back
# empty). Locks are per-event-loop; with the shared default worker there is a
# single loop, so this serializes every NPC's memory operations.
#
# LIMITATION: this is per-loop. The synchronous API (via the shared worker) is
# always safe. The async API (aremember/arecall) runs on the CALLER's loop; if
# you mix it with the sync worker or run NPCs on multiple loops, operations on
# different loops take different locks and can still race. See NPC async docstrings.
_locks: dict = {}


def _serialize() -> "asyncio.Lock":
    loop = asyncio.get_running_loop()
    lock = _locks.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _locks[loop] = lock
    return lock


# Substrings that mean "this NPC simply has no memory yet" (expected) rather than
# an operational failure (auth / rate limit / network / Cognee internal error).
_NO_MEMORY_HINTS = (
    "precondition",
    "not been created",
    "no database",
    "usernotfound",
    "empty knowledge graph",
    "empty graph",
)


class MemoryBackend(ABC):
    """The contract the NPC depends on. Keep it tiny."""

    @abstractmethod
    async def remember(self, text: str, *, dataset: str, node_set: Sequence[str], session_id: str) -> None: ...

    @abstractmethod
    async def recall(self, query: str, *, dataset: str, node_set: Sequence[str], session_id: str) -> str: ...

    @abstractmethod
    async def flush(self, *, dataset: str, session_id: str) -> None: ...

    @abstractmethod
    async def forget(self, *, dataset: str) -> None: ...


def _first_text(results) -> str:
    """Pull the answer text out of Cognee's discriminated recall entries.

    GRAPH_COMPLETION answers arrive as a ResponseQAEntry (.answer) or, as seen in
    the Day-0.5 run, a ResponseGraphEntry (.text); context entries carry .content.
    NOTE: this is duck-typed; a Cognee response-shape change could make it return
    "" silently. Tracked as a hardening issue.
    """
    for r in results or []:
        for attr in ("answer", "content", "text"):
            value = getattr(r, attr, None)
            if value:
                return str(value)
        if isinstance(r, dict):
            for key in ("answer", "content", "text"):
                if r.get(key):
                    return str(r[key])
    return ""


class LocalCogneeBackend(MemoryBackend):
    """In-process Cognee. Provider/model come from the environment (.env.example)."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()

    async def remember(self, text, *, dataset, node_set, session_id) -> None:
        import cognee

        text = (text or "")[: self.settings.max_event_chars]

        kwargs = {}
        if self.settings.use_custom_ontology:
            from .ontology import npc_graph_model, ONTOLOGY_PROMPT

            kwargs["graph_model"] = npc_graph_model()
            kwargs["custom_prompt"] = ONTOLOGY_PROMPT

        # Permanent write (no session_id): Cognee runs add() + cognify(), which
        # BUILDS the per-NPC knowledge graph and materializes the dataset. The
        # session-cache + improve() path does NOT create the dataset on a clean
        # install, leaving the graph empty (see docs/PINNED_API.md). Cognify cost
        # is absorbed by AsyncMemoryWorker so the game loop never blocks.
        # `session_id` is accepted for API symmetry but intentionally unused here.
        async with _serialize():
            await cognee.remember(
                text,
                dataset_name=dataset,
                node_set=list(node_set),
                **kwargs,
            )

    async def recall(self, query, *, dataset, node_set, session_id) -> str:
        import cognee
        from cognee import SearchType

        recall_kwargs = {}
        if self.settings.ground_strict:
            recall_kwargs["system_prompt"] = (
                "Answer only from the retrieved memory. If the memory does not say "
                "something, do not invent it. Stay in character and be concise."
            )

        try:
            async with _serialize():
                results = await cognee.recall(
                    query_text=query,
                    datasets=[dataset],
                    node_name=list(node_set),
                    query_type=getattr(SearchType, self.settings.search_type),
                    top_k=self.settings.top_k,
                    # Match ALL tags (this NPC AND this player) — isolates memories
                    # across NPCs and across players.
                    node_name_filter_operator="AND",
                    # Honor the requested search type; else Cognee may reroute (COT).
                    auto_route=False,
                    **recall_kwargs,
                )
        except Exception as exc:
            name = type(exc).__name__
            msg = str(exc).lower()
            if any(h in msg or h in name.lower() for h in _NO_MEMORY_HINTS):
                # Expected: a brand-new NPC has nothing to recall yet.
                _log.debug("recall: no memory yet for %s (%s)", dataset, name)
                return ""
            # Real operational failure (auth / rate limit / network / internal).
            # Do NOT masquerade it as "no memory": log it, and re-raise if asked.
            _log.error("recall failed for %s: %s: %s", dataset, name, exc)
            if self.settings.raise_on_error:
                raise
            return ""
        return _first_text(results)

    async def flush(self, *, dataset, session_id) -> None:
        # No-op: the graph is built at remember() time (permanent write), so there
        # is nothing to bridge. Durability is handled by NPC.sync() draining the
        # background worker. Kept as a hook so a future batched-write backend can
        # implement a real flush here.
        return None

    async def forget(self, *, dataset) -> None:
        import cognee

        async with _serialize():
            await cognee.forget(dataset=dataset)


class FakeBackend(MemoryBackend):
    """In-memory backend for tests and offline dev — no LLM, no Cognee, no key."""

    def __init__(self) -> None:
        self._store: dict[str, list[tuple[tuple[str, ...], str]]] = {}

    async def remember(self, text, *, dataset, node_set, session_id) -> None:
        self._store.setdefault(dataset, []).append((tuple(node_set), text))

    async def recall(self, query, *, dataset, node_set, session_id) -> str:
        wanted = set(node_set)
        # AND semantics, mirroring LocalCogneeBackend's node_name_filter_operator.
        hits = [
            text
            for tags, text in self._store.get(dataset, [])
            if not wanted or wanted.issubset(set(tags))
        ]
        return hits[-1] if hits else ""

    async def flush(self, *, dataset, session_id) -> None:
        return None

    async def forget(self, *, dataset) -> None:
        self._store.pop(dataset, None)
