"""The NPC object — the entire public surface most games will touch.

    from sonder_engram import NPC
    gethin = NPC("gethin_the_blacksmith", player_id="player_42")
    gethin.remember("The player insulted his craftsmanship.")   # non-blocking
    gethin.sync()                                                # on save / quit
    mood = gethin.recall("How do you feel about this player?")   # at scene entry
"""

from __future__ import annotations

from typing import Optional

from .backend import LocalCogneeBackend, MemoryBackend
from .config import Settings, new_session_id, npc_dataset, player_tag
from .worker import AsyncMemoryWorker, get_default_worker


class NPC:
    def __init__(
        self,
        npc_id: str,
        player_id: str,
        *,
        backend: Optional[MemoryBackend] = None,
        settings: Optional[Settings] = None,
        worker: Optional[AsyncMemoryWorker] = None,
    ) -> None:
        self.npc_id = npc_id
        self.player_id = player_id
        self.settings = settings or Settings()
        self.backend = backend or LocalCogneeBackend(self.settings)
        # All NPCs share ONE background loop by default (Cognee has global state);
        # pass an explicit worker only if you know you want an isolated one.
        self.worker = worker or get_default_worker()

        self.dataset = npc_dataset(npc_id)
        # Isolation: Cognee's graph is global and, with access control off,
        # datasets don't hard-scope retrieval — so two NPCs' memories pool together
        # and bridge through the shared player node. We isolate with a per-NPC
        # node_set tag: writes are tagged with the NPC (+ player), and recall
        # filters to this NPC's tag so it never sees another NPC's events.
        # See docs/PINNED_API.md.
        self._npc_tag = self.dataset  # reuse "npc__<id>" as a per-NPC node_set tag
        # Writes and recall both carry (NPC tag, player tag). Recall matches on ALL
        # of them (AND), so a memory must belong to THIS npc AND THIS player — that
        # isolates both across NPCs and across players/playthroughs.
        self.write_tags = [self._npc_tag, player_tag(player_id)]
        self.recall_tags = [self._npc_tag, player_tag(player_id)]
        self.session = new_session_id()

    # --- synchronous, game-friendly API (backed by the worker) ---------------

    def remember(self, event_text: str):
        """Record an engram about the player. Non-blocking (fire-and-forget)."""
        return self.worker.submit(
            lambda: self.backend.remember(
                event_text, dataset=self.dataset, node_set=self.write_tags, session_id=self.session
            )
        )

    def recall(self, question: str, timeout: Optional[float] = None) -> str:
        """Ask what this NPC knows/feels about the player. Blocks for the answer.

        Call this at scene entry (not mid-dialogue) and cache the result — see the
        Ren'Py pattern in the README.
        """
        return self.worker.run(
            lambda: self.backend.recall(
                question, dataset=self.dataset, node_set=self.recall_tags, session_id=self.session
            ),
            timeout=timeout,
        )

    def sync(self, timeout: Optional[float] = None):
        """Flush pending writes so they're durable before save / quit.

        With the permanent-write backend the graph is already built by remember(),
        so this just waits for any in-flight background writes to finish. After it
        returns, the memory survives a process restart.
        """
        self.worker.drain(timeout=timeout)
        return self.worker.run(
            lambda: self.backend.sync(dataset=self.dataset, session_id=self.session),
            timeout=timeout,
        )

    def forget(self, timeout: Optional[float] = None):
        """Erase this NPC's memory (e.g. new game / privacy)."""
        return self.worker.run(
            lambda: self.backend.forget(dataset=self.dataset), timeout=timeout
        )

    # --- async API for callers already inside an event loop ------------------

    async def aremember(self, event_text: str) -> None:
        await self.backend.remember(
            event_text, dataset=self.dataset, node_set=self.write_tags, session_id=self.session
        )

    async def arecall(self, question: str) -> str:
        return await self.backend.recall(
            question, dataset=self.dataset, node_set=self.recall_tags, session_id=self.session
        )

    async def async_sync(self) -> None:
        await self.backend.sync(dataset=self.dataset, session_id=self.session)

    async def aforget(self) -> None:
        await self.backend.forget(dataset=self.dataset)
