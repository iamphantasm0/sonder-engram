"""Unit tests for the SDK wiring, using FakeBackend (no LLM, no Cognee, no key).

    pip install -e ".[dev]"
    pytest
"""

from sonder_engram import NPC, FakeBackend


def test_remember_recall_roundtrip():
    npc = NPC("gethin", "p1", backend=FakeBackend())
    npc.remember("the player was rude about the sword")
    npc.sync()
    assert "rude" in npc.recall("how do you feel?")


def test_memory_is_isolated_per_npc():
    shared = FakeBackend()
    smith = NPC("smith", "p1", backend=shared)
    baker = NPC("baker", "p1", backend=shared)

    smith.remember("smith-only memory")
    smith.sync()

    # The baker has its own dataset and should know nothing about the smith's events.
    assert baker.recall("anything?") == ""
    assert "smith-only" in smith.recall("what happened?")


def test_memory_is_scoped_per_player():
    shared = FakeBackend()
    npc_p1 = NPC("gethin", "player_1", backend=shared)
    npc_p2 = NPC("gethin", "player_2", backend=shared)

    npc_p1.remember("player_1 broke the display case")
    npc_p1.sync()

    # Same NPC, different player tag -> different scoped memory.
    assert npc_p2.recall("what did I do?") == ""
    assert "display case" in npc_p1.recall("what did I do?")
