"""The NPC object — the entire public surface most games will touch.

    from sonder_engram import NPC
    gethin = NPC("gethin_the_blacksmith", player_id="player_42")
    gethin.remember("The player insulted his craftsmanship.")   # non-blocking
    gethin.sync()                                                # on save / quit
    mood = gethin.recall("How do you feel about this player?")   # at scene entry
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import TimeoutError as _FutureTimeout
from typing import Optional

from .backend import LocalCogneeBackend, MemoryBackend
from .config import Settings, new_session_id, npc_dataset, player_tag
from .worker import AsyncMemoryWorker, get_default_worker

_log = logging.getLogger("sonder_engram")


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
        # Isolation: Cognee's graph is global and, with access control off, datasets
        # don't hard-scope retrieval. We isolate with per-NPC + per-player node_set
        # tags and AND-match on recall (this NPC AND this player). See PINNED_API.md.
        self._npc_tag = self.dataset  # reuse "npc__<id>" as a per-NPC node_set tag
        self.write_tags = [self._npc_tag, player_tag(player_id)]
        self.recall_tags = [self._npc_tag, player_tag(player_id)]
        self.session = new_session_id()

    def _timeout(self, timeout: Optional[float]) -> float:
        return self.settings.default_timeout if timeout is None else timeout

    # --- synchronous, game-friendly API (backed by the worker) ---------------

    def remember(self, event_text: str):
        """Record an engram about the player. Non-blocking (fire-and-forget).

        Failures surface via the worker's logs / `worker.last_error`, not here.
        """
        return self.worker.submit(
            lambda: self.backend.remember(
                event_text, dataset=self.dataset, node_set=self.write_tags, session_id=self.session
            )
        )

    def recall(self, question: str, timeout: Optional[float] = None) -> str:
        """Ask what this NPC knows/feels about the player. Blocks for the answer.

        Call at scene entry (not mid-dialogue) and cache the result. Returns "" if
        the NPC has no memory yet, on timeout, or on error (unless
        Settings.raise_on_error is set) — a game NPC should stay neutral, not crash.
        """
        try:
            return self.worker.run(
                lambda: self.backend.recall(
                    question, dataset=self.dataset, node_set=self.recall_tags, session_id=self.session
                ),
                timeout=self._timeout(timeout),
            )
        except _FutureTimeout:
            _log.warning("recall timed out for %s after %ss", self.dataset, self._timeout(timeout))
            return ""

    def sync(self, timeout: Optional[float] = None):
        """Flush pending writes so they're durable before save / quit.

        The graph is built at remember() time, so this just waits for in-flight
        background writes to finish. After it returns, memory survives a restart.
        """
        t = self._timeout(timeout)
        self.worker.drain(timeout=t)
        return self.worker.run(
            lambda: self.backend.flush(dataset=self.dataset, session_id=self.session),
            timeout=t,
        )

    def forget(self, timeout: Optional[float] = None):
        """Erase this NPC's memory (e.g. new game / privacy)."""
        return self.worker.run(
            lambda: self.backend.forget(dataset=self.dataset), timeout=self._timeout(timeout)
        )

    # --- async API -----------------------------------------------------------
    # These route through the SAME shared worker loop as the sync API (via
    # asyncio.wrap_future), so the actual Cognee work is serialized by the one
    # lock and is safe to mix with sync calls, regardless of which event loop you
    # await them on. (Calling a MemoryBackend directly, bypassing NPC, is still
    # your responsibility to serialize — see docs/PINNED_API.md and issue #5.)

    async def aremember(self, event_text: str) -> None:
        future = self.worker.submit(
            lambda: self.backend.remember(
                event_text, dataset=self.dataset, node_set=self.write_tags, session_id=self.session
            )
        )
        await asyncio.wrap_future(future)

    async def arecall(self, question: str) -> str:
        future = self.worker.submit(
            lambda: self.backend.recall(
                question, dataset=self.dataset, node_set=self.recall_tags, session_id=self.session
            )
        )
        return await asyncio.wrap_future(future)

    async def async_sync(self) -> None:
        future = self.worker.submit(
            lambda: self.backend.flush(dataset=self.dataset, session_id=self.session)
        )
        await asyncio.wrap_future(future)

    async def aforget(self) -> None:
        future = self.worker.submit(lambda: self.backend.forget(dataset=self.dataset))
        await asyncio.wrap_future(future)
