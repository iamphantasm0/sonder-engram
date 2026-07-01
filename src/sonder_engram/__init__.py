"""Sonder — persistent memory for game NPCs, powered by Cognee.

They remember what you did.

Public API:
    from sonder_engram import NPC
    npc = NPC("gethin_the_blacksmith", player_id="player_42")
    npc.remember("The player insulted Gethin's craftsmanship.")   # non-blocking
    npc.sync()                                                     # on save/quit
    mood = npc.recall("How do you feel about this player?")        # at scene entry
"""

from .npc import NPC
from .backend import MemoryBackend, LocalCogneeBackend, FakeBackend
from .worker import AsyncMemoryWorker
from .config import Settings, npc_dataset, player_tag, new_session_id

__all__ = [
    "NPC",
    "MemoryBackend",
    "LocalCogneeBackend",
    "FakeBackend",
    "AsyncMemoryWorker",
    "Settings",
    "npc_dataset",
    "player_tag",
    "new_session_id",
]

__version__ = "0.1.0"
