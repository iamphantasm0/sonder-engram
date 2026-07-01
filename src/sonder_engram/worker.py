"""AsyncMemoryWorker — run Cognee's async, LLM-backed work off the game loop.

Cognee's writes (and the graph build) call an LLM and take seconds; a game can't
block a frame on that. This worker owns an asyncio loop in a daemon thread so
synchronous game code can `submit(...)` a write (non-blocking) or `run(...)` and
block for a result (recall / flush).

Background write failures are logged (not silently swallowed) and recorded on
`last_error`, so a lost write is observable.
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import threading
from concurrent.futures import TimeoutError as _FutureTimeout
from typing import Any, Awaitable, Callable, Optional

_log = logging.getLogger("sonder_engram")


class AsyncMemoryWorker:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="sonder-memory", daemon=True)
        self._thread.start()
        self._pending: set = set()
        self._closed = False
        self.last_error: Optional[BaseException] = None
        atexit.register(self.close)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _on_done(self, future) -> None:
        self._pending.discard(future)
        try:
            exc = future.exception()
        except Exception:
            return
        if exc is not None:
            self.last_error = exc
            _log.error("sonder: background memory write failed: %s: %s", type(exc).__name__, exc)

    def submit(self, coro_factory: Callable[[], Awaitable[Any]]):
        """Schedule a coroutine on the background loop and return immediately.

        Failures are logged via `_on_done` and recorded on `last_error`.
        """
        future = asyncio.run_coroutine_threadsafe(coro_factory(), self._loop)
        self._pending.add(future)
        future.add_done_callback(self._on_done)
        return future

    def run(self, coro_factory: Callable[[], Awaitable[Any]], timeout: Optional[float] = None) -> Any:
        """Schedule a coroutine and block until it returns (used for recall / flush).

        Raises concurrent.futures.TimeoutError if it exceeds `timeout`. On timeout the
        underlying task is cancelled so a slow/rate-limited LLM call stops instead of
        running to completion unseen (avoids leaked "Task was destroyed" work).
        """
        future = asyncio.run_coroutine_threadsafe(coro_factory(), self._loop)
        try:
            return future.result(timeout)
        except _FutureTimeout:
            future.cancel()
            raise

    def drain(self, timeout: Optional[float] = None) -> None:
        """Wait for all in-flight writes to finish (call before flush/save)."""
        for future in list(self._pending):
            try:
                future.result(timeout)
            except Exception as exc:
                # Already logged in _on_done; keep draining the rest.
                self.last_error = exc

    def close(self) -> None:
        """Best-effort graceful shutdown: drain, stop the loop, join the thread."""
        if self._closed:
            return
        self._closed = True
        # Give in-flight writes a moment to finish (don't drop them)...
        try:
            self.drain(timeout=5)
        except Exception:
            pass
        # ...then cancel any stragglers so we don't leak running tasks on shutdown.
        for future in list(self._pending):
            future.cancel()
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass
        try:
            self._thread.join(timeout=5)
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
