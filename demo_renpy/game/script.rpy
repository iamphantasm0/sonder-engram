# Sonder demo — NPCs that remember what you did, across sessions.
#
# Drop this file (and sonder.rpy) into a Ren'Py project's game/ folder, replacing
# the default script.rpy. Start the sidecar first (see demo_renpy/README.md).
#
# The point of the demo: every NPC greeting below is RECALLED from the Cognee
# knowledge graph via the sidecar — not a Ren'Py flag. Insult the blacksmith,
# quit, relaunch, load, and he is still cold. That is the whole thesis.

define gethin = Character("Gethin")
define mara = Character("Mara")

label start:
    $ ensure_player_id()

    "A small town. Two people here have a memory now — and it survives you closing the game."

    "You step up to the forge. Gethin looks up and studies you..."
    # Recall runs an LLM via the sidecar (~a few seconds). First visit: he won't know you.
    $ mood = sonder_recall("gethin", "In one short sentence, in character as a gruff blacksmith, how does Gethin feel about this player and why? If nothing is known about them, say he doesn't recognize them.")
    gethin "[mood]"

    menu:
        "Praise his craftsmanship":
            $ sonder_remember("gethin", "The player warmly praised Gethin's craftsmanship and bought a fine sword.")
            gethin "Hah. A good eye. Come back anytime."
        "Insult his work and walk out":
            $ sonder_remember("gethin", "The player insulted Gethin's craftsmanship and walked out without buying anything.")
            gethin "...Don't come back."

    "By the stocks, the captured bandit Mara watches you..."
    $ mmood = sonder_recall("mara", "In one short sentence, in character as a wary captured bandit, how does Mara feel about this player and why? If nothing is known about them, say she doesn't recognize them.")
    mara "[mmood]"

    menu:
        "Cut her loose and let her run":
            $ sonder_remember("mara", "The player spared Mara and let her slip away instead of handing her to the guards.")
            mara "...I won't forget this."
        "Turn her in for the bounty":
            $ sonder_remember("mara", "The player turned Mara in to the guards for the bounty.")
            mara "You'll regret that."

    # Persist both NPCs' memories so they survive a restart.
    $ sonder_sync("gethin")
    $ sonder_sync("mara")

    "Night falls on the town."
    "To prove they truly remember: SAVE now, quit Ren'Py entirely, relaunch, and LOAD this save."
    "Then ask around — their answers come from the graph, not from a saved flag."

    jump ask_around

label ask_around:
    menu:
        "Ask Gethin how he feels about you":
            "Gethin sizes you up..."
            $ g = sonder_recall("gethin", "In one short sentence, in character, how does Gethin feel about this player and why?")
            gethin "[g]"
            jump ask_around
        "Ask Mara how she feels about you":
            "Mara narrows her eyes..."
            $ m = sonder_recall("mara", "In one short sentence, in character, how does Mara feel about this player and why?")
            mara "[m]"
            jump ask_around
        "Leave town (end demo)":
            return
