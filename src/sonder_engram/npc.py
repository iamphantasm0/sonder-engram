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
from .worker import AsyncMemoryWorker


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
        # A shared worker can be passed in so many NPCs share one background loop.
        self.worker = worker or AsyncMemoryWorker()

        self.dataset = npc_dataset(npc_id)
        self.node_set = [player_tag(player_id)]
        self.session = new_session_id()

    # --- synchronous, game-friendly API (backed by the worker) ---------------

    def remember(self, event_text: str):
        """Record an engram about the player. Non-blocking (fire-and-forget)."""
        return self.worker.submit(
            lambda: self.backend.remember(
                event_text, dataset=self.dataset, node_set=self.node_set, session_id=self.session
            )
        )

    def recall(self, question: str, timeout: Optional[float] = None) -> str:
        """Ask what this NPC knows/feels about the player. Blocks for the answer.

        Call this at scene entry (not mid-dialogue) and cache the result — see the
        Ren'Py pattern in the README.
        """
        return self.worker.run(
            lambda: self.backend.recall(
                question, dataset=self.dataset, node_set=self.node_set, session_id=self.session
            ),
            timeout=timeout,
        )

    def sync(self, timeout: Optional[float] = None):
        """Flush pending writes, then bridge this session into permanent memory.

        Call on save / quit. After this, the memory survives a process restart.
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
            event_text, dataset=self.dataset, node_set=self.node_set, session_id=self.session
        )

    async def arecall(self, question: str) -> str:
        return await self.backend.recall(
            question, dataset=self.dataset, node_set=self.node_set, session_id=self.session
        )

    async def async_sync(self) -> None:
        await self.backend.sync(dataset=self.dataset, session_id=self.session)

    async def aforget(self) -> None:
        await self.backend.forget(dataset=self.dataset)
