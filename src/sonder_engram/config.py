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


def _slug(value: str) -> str:
    """Make an id safe to use inside a dataset / node_set name."""
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(value)).strip("_")


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
    """A fresh session id for one play session (used with Cognee's session cache)."""
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")
    return f"sess__{stamp}__{uuid.uuid4().hex[:8]}"


@dataclass
class Settings:
    """Runtime knobs for the SDK. Provider/model config lives in the environment
    (see .env.example), not here — the SDK is provider-agnostic."""

    # Cognee SearchType name used for recall (GRAPH_COMPLETION = graph+vector answer).
    search_type: str = "GRAPH_COMPLETION"
    top_k: int = 8

    # Opt-in: constrain graph extraction to the minimal NPC ontology (see ontology.py).
    # Default False — Cognee's built-in KnowledgeGraph model is proven working (Day 0.5).
    use_custom_ontology: bool = False

    # Opt-in: bias recall toward stored facts instead of letting the LLM embellish.
    # (Day-0.5 note: recall adds plausible detail by default; fine for flavor.)
    ground_strict: bool = False
