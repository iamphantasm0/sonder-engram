"""Terminal MVP for sonder-engram: two NPCs that remember the player across runs.

This is the smallest possible proof of the whole idea — no game engine, just the
SDK. It imports `sonder_engram` exactly as a real game would.

Setup (see .env.example — DeepSeek LLM + local fastembed embeddings, no OpenAI):
    cp .env.example .env    # fill in your key
    pip install -e ".[fastembed]"

Run it in TWO separate processes to prove memory survives a restart:
    python examples/terminal_demo.py write     # NPCs learn about the player, then sync
    python examples/terminal_demo.py recall     # fresh process: they still remember

Or run the whole thing in one process:
    python examples/terminal_demo.py all
"""

import sys

from sonder_engram import NPC

PLAYER = "player_42"


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    gethin = NPC("gethin_the_blacksmith", PLAYER)
    mara = NPC("mara_the_bandit", PLAYER)

    if mode in ("write", "all"):
        gethin.remember("The player insulted Gethin's craftsmanship and walked out without buying the sword.")
        mara.remember("The player spared Mara's life instead of turning her in to the guards.")
        gethin.sync()
        mara.sync()
        print("wrote + synced memories for 2 NPCs")

    if mode in ("recall", "all"):
        print("Gethin:", gethin.recall("How do you feel about this player, and why?"))
        print("Mara:  ", mara.recall("How do you feel about this player, and why?"))


if __name__ == "__main__":
    main()
