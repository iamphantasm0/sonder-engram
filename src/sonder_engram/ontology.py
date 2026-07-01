"""Minimal NPC ontology for Sonder.

Cognee builds a knowledge graph whose nodes are `Node{id, name, type, description}`
and edges are `Edge{source_node_id, target_node_id, relationship_name, description}`
(verified in docs/PINNED_API.md). Node.type and Edge.relationship_name are free
strings, so we keep the "ontology" small and steer extraction two ways:

1. A prompt hint (ONTOLOGY_PROMPT) passed as Cognee's `custom_prompt`, listing the
   allowed types. This is the light-touch, low-risk lever.
2. Optionally, the graph_model itself (Cognee's KnowledgeGraph shape) via
   `npc_graph_model()`.

This is opt-in (Settings.use_custom_ontology). Default runs on Cognee's built-in
model, which the Day-0.5 smoke test proved works on DeepSeek.
"""

from __future__ import annotations

# Keep this MINIMAL for v1. Expand only if recall quality clearly improves (Day 2).
ENTITY_TYPES = ["Player", "Npc", "Event", "Item", "Location"]
RELATION_TYPES = [
    "LIKES",
    "DISLIKES",
    "TRUSTS",
    "OWES",
    "PROMISED",
    "BETRAYED",
    "HELPED",
    "KILLED",
]

ONTOLOGY_PROMPT = (
    "You are building a small game-world memory graph. Extract ONLY these node "
    f"types: {', '.join(ENTITY_TYPES)}. Use ONLY these relationship names between "
    f"nodes: {', '.join(RELATION_TYPES)}. Prefer a few high-signal facts over many. "
    "Do not invent details that are not in the text."
)


def npc_graph_model():
    """Return the graph model to constrain extraction.

    Currently returns Cognee's built-in KnowledgeGraph (same node/edge shape).
    Swap for a typed subclass once validated against the installed Cognee version.
    """
    from cognee.shared.data_models import KnowledgeGraph

    return KnowledgeGraph
