"""Unit tests for the SDK wiring, using FakeBackend (no LLM, no Cognee, no key).

    pip install -e ".[dev]"
    pytest
"""

import asyncio

from sonder_engram import NPC, FakeBackend
from sonder_engram.backend import _first_text
from sonder_engram.config import _slug


def test_remember_recall_roundtrip():
    npc = NPC("gethin", "p1", backend=FakeBackend())
    npc.remember("the player was rude about the sword")
    npc.sync()
    assert "rude" in npc.recall("how do you feel?", timeout=5)


def test_memory_is_isolated_per_npc():
    shared = FakeBackend()
    smith = NPC("smith", "p1", backend=shared)
    baker = NPC("baker", "p1", backend=shared)

    smith.remember("smith-only memory")
    smith.sync()

    assert baker.recall("anything?", timeout=5) == ""
    assert "smith-only" in smith.recall("what happened?", timeout=5)


def test_memory_is_scoped_per_player():
    shared = FakeBackend()
    npc_p1 = NPC("gethin", "player_1", backend=shared)
    npc_p2 = NPC("gethin", "player_2", backend=shared)

    npc_p1.remember("player_1 broke the display case")
    npc_p1.sync()

    # Same NPC, different player -> different scoped memory (AND-matched tags).
    assert npc_p2.recall("what did I do?", timeout=5) == ""
    assert "display case" in npc_p1.recall("what did I do?", timeout=5)


def test_slug_sanitizes_and_bounds():
    assert _slug("Gethin the Blacksmith!") == "Gethin_the_Blacksmith"
    assert len(_slug("x" * 500)) <= 96
    assert _slug("") == "unknown"


def test_first_text_reads_known_response_shapes():
    class QA:
        answer, content, text = "the answer", None, None

    class GraphEntry:
        answer, content, text = None, None, "graph text"

    assert _first_text([QA()]) == "the answer"
    assert _first_text([GraphEntry()]) == "graph text"
    assert _first_text([{"content": "ctx"}]) == "ctx"
    assert _first_text([]) == ""
    assert _first_text(None) == ""


def test_async_api_routes_through_worker():
    # aremember/arecall run on a fresh asyncio loop but route through the shared
    # worker loop (via wrap_future), so this exercises the cross-loop bridge.
    async def go():
        npc = NPC("gethin", "p1", backend=FakeBackend())
        await npc.aremember("the player smashed a display vase")
        return await npc.arecall("what happened?")

    assert "vase" in asyncio.run(go())
