"""Naming conventions and tunable settings for Sonder.

The isolation model (verified in docs/PINNED_API.md):
- one Cognee dataset per NPC:            npc__<npc_id>
- one node_set tag per player:           player__<player_id>
- one shared dataset for town gossip:    town__gossip   (Day-2 stretch)
"""

from __future__ import annotations

import datetime as _dt
import uuid
from dataclasses import dataclass

DATASET_PREFIX = "npc__"
PLAYER_PREFIX = "player__"
GOSSIP_DATASET = "town__gossip"

# Keep derived dataset / node_set names well within the underlying stores' limits
# (Kuzu / LanceDB / SQLite). ids come from game/user input, so bound them.
_MAX_ID_LEN = 96


def _slug(value: str) -> str:
    """Make an id safe (and bounded) for use in a dataset / node_set name."""
    s = "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(value)).strip("_")
    if len(s) > _MAX_ID_LEN:
        s = s[:_MAX_ID_LEN].rstrip("_")
    return s or "unknown"


def npc_dataset(npc_id: str) -> str:
    """Dataset name that isolates a single NPC's memory."""
    return f"{DATASET_PREFIX}{_slug(npc_id)}"


def player_tag(player_id: str) -> str:
    """node_set tag that scopes memories to a specific player.

    IMPORTANT: player_id must be stable across sessions (see README / the demo).
    In Ren'Py, mint it once at new-game and store it in the save slot.
    """
    return f"{PLAYER_PREFIX}{_slug(player_id)}"


def new_session_id() -> str:
    """A fresh session id for one play session."""
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")
    return f"sess__{stamp}__{uuid.uuid4().hex[:8]}"


@dataclass
class Settings:
    """Runtime knobs for the SDK. Provider/model config lives in the environment
    (see .env.example), not here — the SDK is provider-agnostic."""

    # --- retrieval ---
    search_type: str = "GRAPH_COMPLETION"  # Cognee SearchType name used for recall
    top_k: int = 8

    # Opt-in: constrain graph extraction to the minimal NPC ontology (see ontology.py).
    use_custom_ontology: bool = False
    # Opt-in: bias recall toward stored facts instead of letting the LLM embellish.
    ground_strict: bool = False

    # --- operational ---
    # Blocking recall/sync/forget cap so a stalled LLM call can't hang the game
    # thread (Ren'Py included) forever. On timeout, recall returns "" and logs.
    default_timeout: float = 45.0
    # Oversized memory writes are truncated to this many characters.
    max_event_chars: int = 4000
    # If True, recall re-raises genuine operational errors (auth/rate/network)
    # instead of returning "". "No memory yet" always returns "" regardless.
    raise_on_error: bool = False
