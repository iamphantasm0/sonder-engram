"""AsyncMemoryWorker — run Cognee's async, LLM-backed work off the game loop.

Cognee's writes (and especially the graph build on sync) call an LLM and take
seconds. A game can't block a frame on that. This worker owns an asyncio loop in
a daemon thread, so synchronous game code can:

- `submit(...)`  fire a write and return immediately (non-blocking), and
- `run(...)`     block for a result when it actually needs one (recall / sync).

This keeps the SDK usable from plain synchronous engines like Ren'Py.
"""

from __future__ import annotations

import asyncio
import atexit
import threading
from typing import Any, Awaitable, Callable, Optional


class AsyncMemoryWorker:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="sonder-memory", daemon=True)
        self._thread.start()
        self._pending: set = set()
        atexit.register(self.close)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submit(self, coro_factory: Callable[[], Awaitable[Any]]):
        """Schedule a coroutine on the background loop and return immediately."""
        future = asyncio.run_coroutine_threadsafe(coro_factory(), self._loop)
        self._pending.add(future)
        future.add_done_callback(self._pending.discard)
        return future

    def run(self, coro_factory: Callable[[], Awaitable[Any]], timeout: Optional[float] = None) -> Any:
        """Schedule a coroutine and block until it returns (used for recall / sync)."""
        return asyncio.run_coroutine_threadsafe(coro_factory(), self._loop).result(timeout)

    def drain(self, timeout: Optional[float] = None) -> None:
        """Wait for all in-flight writes to finish (call before sync)."""
        for future in list(self._pending):
            try:
                future.result(timeout)
            except Exception:
                # A failed background write should not crash the game; it's logged
                # by the backend. Surface via monitoring later.
                pass

    def close(self) -> None:
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass


_DEFAULT_WORKER: "AsyncMemoryWorker | None" = None


def get_default_worker() -> "AsyncMemoryWorker":
    """Return a process-wide shared worker.

    Cognee keeps global state (one embedded DB and default user), so every NPC
    must run its memory operations on a SINGLE background loop. Combined with the
    serialization lock in backend.py, this prevents concurrent-write corruption —
    which showed up as one of two NPCs' memory coming back empty.
    """
    global _DEFAULT_WORKER
    if _DEFAULT_WORKER is None:
        _DEFAULT_WORKER = AsyncMemoryWorker()
    return _DEFAULT_WORKER
