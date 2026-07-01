"""Memory backends for Sonder.

The `NPC` never calls Cognee directly — it talks to a `MemoryBackend`. That seam
is the "open door": `LocalCogneeBackend` runs Cognee in-process today; an
`HttpCogneeBackend` (for the web build and non-Python engines) can slot in later
with zero change to NPC / ontology / gossip logic.

All calls map onto the Cognee v1.0 API confirmed in docs/PINNED_API.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from .config import Settings


class MemoryBackend(ABC):
    """The contract the NPC depends on. Keep it tiny."""

    @abstractmethod
    async def remember(self, text: str, *, dataset: str, node_set: Sequence[str], session_id: str) -> None: ...

    @abstractmethod
    async def recall(self, query: str, *, dataset: str, node_set: Sequence[str], session_id: str) -> str: ...

    @abstractmethod
    async def sync(self, *, dataset: str, session_id: str) -> None: ...

    @abstractmethod
    async def forget(self, *, dataset: str) -> None: ...


def _first_text(results) -> str:
    """Pull the answer text out of Cognee's discriminated recall entries.

    GRAPH_COMPLETION answers arrive as a ResponseQAEntry (.answer) or, as seen in
    the Day-0.5 run, a ResponseGraphEntry (.text); context entries carry .content.
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

        kwargs = {}
        if self.settings.use_custom_ontology:
            from .ontology import npc_graph_model, ONTOLOGY_PROMPT

            kwargs["graph_model"] = npc_graph_model()
            kwargs["custom_prompt"] = ONTOLOGY_PROMPT

        # session_id => fast session cache; self_improvement=False so we bridge
        # once on sync() rather than rebuilding the graph on every write.
        await cognee.remember(
            text,
            dataset_name=dataset,
            node_set=list(node_set),
            session_id=session_id,
            self_improvement=False,
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

        results = await cognee.recall(
            query_text=query,
            datasets=[dataset],
            node_name=list(node_set),
            session_id=session_id,
            query_type=getattr(SearchType, self.settings.search_type),
            top_k=self.settings.top_k,
            **recall_kwargs,
        )
        return _first_text(results)

    async def sync(self, *, dataset, session_id) -> None:
        import cognee

        # Bridge this session's cache into the permanent per-NPC graph.
        await cognee.improve(dataset=dataset, session_ids=[session_id])

    async def forget(self, *, dataset) -> None:
        import cognee

        await cognee.forget(dataset=dataset)


class FakeBackend(MemoryBackend):
    """In-memory backend for tests and offline dev — no LLM, no Cognee, no key.

    Good enough to exercise NPC / worker wiring and dataset isolation.
    """

    def __init__(self) -> None:
        self._store: dict[str, list[tuple[tuple[str, ...], str]]] = {}

    async def remember(self, text, *, dataset, node_set, session_id) -> None:
        self._store.setdefault(dataset, []).append((tuple(node_set), text))

    async def recall(self, query, *, dataset, node_set, session_id) -> str:
        wanted = set(node_set)
        hits = [
            text
            for tags, text in self._store.get(dataset, [])
            if not wanted or (wanted & set(tags))
        ]
        return hits[-1] if hits else ""

    async def sync(self, *, dataset, session_id) -> None:
        return None

    async def forget(self, *, dataset) -> None:
        self._store.pop(dataset, None)
