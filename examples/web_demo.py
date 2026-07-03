#!/usr/bin/env python3
"""
Sonder Web Demo — An easy-to-launch playable demo of persistent NPC memory.

Run it:

    pip install -e ".[fastembed,web]"
    cp .env.example .env     # add your LLM key (DeepSeek recommended)
    python examples/web_demo.py

Then open http://127.0.0.1:8000 in your browser.

This demo now behaves more like a real game:
- Traveling to a location prefetches NPC memories in the background.
- Oracle and NPC reactions use client-side cache for instant responses on repeat questions.
- Multiple NPC calls run in parallel instead of one-by-one.

Environment:
- SONDER_WEB_PORT / PORT — port to listen on (Railway etc. set PORT)
- SONDER_WEB_HOST — override bind host (e.g. 0.0.0.0 for containers)

This uses the SDK directly (no sidecar needed). All memory is powered by
Cognee knowledge graphs so NPCs actually remember what you did across "sessions".
"""

from __future__ import annotations

import os
import time
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn

from sonder_engram import NPC, Settings

# -----------------------------------------------------------------------------
# Demo configuration
# -----------------------------------------------------------------------------
DEFAULT_PLAYER_ID = "curious_traveler"

# Support standard $PORT (Railway, Render, etc.) and our override.
# Default host: 127.0.0.1 locally, 0.0.0.0 when running in a platform that sets $PORT.
PORT = int(os.environ.get("PORT") or os.environ.get("SONDER_WEB_PORT", "8000"))
HOST = os.environ.get("SONDER_WEB_HOST") or ("0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")

# In-memory cache of NPCs per player (so different player_ids have isolated memories)
_player_npcs: Dict[str, Dict[str, NPC]] = {}

# Tiny server-side short cache for recalls (helps across browser refreshes while server runs)
# Key: (player_id, npc_id, question) -> (answer, timestamp)
_recall_cache: Dict[Tuple[str, str, str], Tuple[str, float]] = {}
RECALL_CACHE_TTL = 180.0  # 3 minutes — short and demo-friendly

# Keep strong references to fire-and-forget background tasks. The event loop
# only holds WEAK refs to Tasks, so an unreferenced create_task() can be
# garbage-collected mid-flight and the memory write silently dropped (RUF006).
_background_tasks: set = set()


def _spawn(coro) -> None:
    """create_task + retain a reference until the task completes."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def get_npcs(player_id: str) -> Dict[str, NPC]:
    """Get or create the demo NPCs for a given player."""
    if player_id not in _player_npcs:
        # ground_strict: lean toward stored facts. top_k=12: chat-exchange engrams
        # multiply fast and can crowd deed memories out of the candidate set at the
        # default 8 — a few extra chunks keeps betrayals surfacing next to banter.
        settings = Settings(ground_strict=True, top_k=12)
        _player_npcs[player_id] = {
            "gethin": NPC("gethin_the_blacksmith", player_id=player_id, settings=settings),
            "mara": NPC("mara_the_bandit", player_id=player_id, settings=settings),
            "elara": NPC("elara_the_seer", player_id=player_id, settings=settings),
        }
    return _player_npcs[player_id]


# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up message
    print("Sonder Web Demo ready.")
    display_host = "127.0.0.1" if HOST in ("0.0.0.0", "::") else HOST
    print(f"Open http://{display_host}:{PORT} in your browser.")
    yield


app = FastAPI(title="Sonder Demo", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve a self-contained playable demo."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sonder • Text RPG</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: ui-monospace, monospace; background:#0a0a0a; color:#c9a25f; }
        .torn { background:#111; border:2px solid #4a3f2e; }
        .link { 
            color:#c9a25f; text-decoration:none; display:block; padding:4px 8px; 
            background: #1a1815; border: 1px solid #4a3f2e; font: inherit; text-align: left; cursor: pointer;
            margin: 1px 0;
        }
        .link:hover { background:#1f180f; color:#f0d8a8; border-color:#c9a25f; }
        .scene { background:#0a0a0a; border:1px solid #4a3f2e; padding:10px; line-height:1.3; }
        .log { font-size:13px; }
        .oracle { background:#1a140f; border:2px solid #5c4a2e; }
    </style>
</head>
<body class="p-4 max-w-[780px] mx-auto">
    <!-- Landing / Explainer (shown first, like a real game title screen) -->
    <div id="landing">
      <div class="text-center mb-4">
        <h1 class="text-4xl font-bold tracking-wider">SONDER</h1>
        <p class="text-sm opacity-80">Persistent memory for NPCs • Powered by Cognee knowledge graphs</p>
      </div>

      <div class="torn p-4 text-sm leading-relaxed space-y-3 mb-4">
        <p><strong>Why this exists:</strong> Every NPC you've ever met in a game was faking it. A looped smile. One line of dialogue. They forget your face the moment you turn around. Props wearing people.</p>
        
        <p><strong>Sonder changes that.</strong> It gives NPCs a real <em>engram</em> — a trace of what you did — stored in a knowledge graph. Insult the blacksmith on Monday. Quit the game. Come back on Thursday (or restart the server). He's still cold to you. Not because of a flag. Because the graph remembers.</p>

        <p><strong>How the demo works (real-game style):</strong></p>
        <ul class="list-disc pl-5 text-xs space-y-0.5">
          <li>Travel between locations — this prefetches memories in the background (exactly what a game engine does on scene load)</li>
          <li>Take actions → they are written to the NPC's permanent memory via the sonder-engram SDK</li>
          <li>Click [restart server] → fresh process, same player_id → NPCs still remember (the graph survived)</li>
          <li>The Oracle lets you query what NPCs actually recall about you</li>
          <li>Post in the village group chat — every NPC remembers it. They react automatically with @mentions</li>
          <li>Word travels: deeds at the forge or tavern reach Elara the seer as gossip — visit the grove and she'll hint at what you did elsewhere</li>
          <li>Your name is your save — return with the same name and the town still remembers you (it stays logged in on this browser too)</li>
          <li>Visible timing + caches show you the real cost and how games hide it</li>
        </ul>

        <p class="text-[10px] opacity-70">All memory is <strong>real</strong>. No scripts, no fake responses. Powered by the open-source <a href="https://github.com/iamphantasm0/sonder-engram" class="underline">sonder-engram</a> SDK + Cognee.</p>
      </div>

      <div class="text-center">
        <button onclick="startPlaying()" 
                class="link text-base px-8 py-2 font-bold">PLAY THE GAME →</button>
        <div class="text-[10px] mt-2 opacity-60">All memory is real. Powered by sonder-engram + Cognee.</div>
      </div>
    </div>

    <!-- The actual game UI (hidden until you click Play) -->
    <div id="game-ui" style="display: none;">
    <div class="torn p-3">
        <div class="flex justify-between text-sm mb-2 border-b border-[#4a3f2e] pb-1">
            <div><strong>SONDER</strong> <span class="text-xs">text rpg</span></div>
            <div>
                Player:
                <input id="pid-input" class="bg-transparent border-b border-[#4a3f2e] px-1 w-40" title="Your name is your save — return with the same name and the town remembers you." onchange="setPlayerId(this.value)">
                <button onclick="newLife()" class="text-xs">[new life]</button>
                <button onclick="restartServer()" class="text-xs">[restart server]</button>
            </div>
        </div>

        <div class="scene mb-3">
            <div id="loc-name" class="font-bold text-lg"></div>
            <div id="loc-desc" class="text-sm"></div>
        </div>

        <div class="mb-2">
            <div class="text-xs">TRAVEL</div>
            <div id="travel" class="text-sm"></div>
        </div>

        <div class="mb-2">
            <div class="text-xs">ACTIONS HERE (click the lines below):</div>
            <div id="actions" class="text-sm"></div>
        </div>

        <div id="oracle" class="oracle p-2 mb-2 hidden">
            <div class="font-bold text-sm">Elara the Seer</div>
            <div id="oracle-actions" class="text-sm"></div>
            <div id="oracle-result" class="mt-1 text-sm hidden p-1 border-l-2 border-[#5c4a2e]"></div>
        </div>

        <div>
            <div class="text-xs flex justify-between"><span>DEEDS</span> <button onclick="clearLog()" class="text-[10px]">[clear]</button></div>
            <div id="log" class="log max-h-28 overflow-auto"></div>
        </div>

        <div class="mt-3 border-t border-[#4a3f2e] pt-2">
            <div class="text-xs">VILLAGE GROUP CHAT <span class="text-[10px]">(press Enter or Post; @gethin/@mara/@elara to target specific NPCs — they react automatically)</span></div>
            <div id="chat-log" class="log max-h-24 overflow-auto mb-1 text-xs"></div>
            <div class="flex gap-1">
                <input id="chat-input" class="flex-1 bg-[#111] border border-[#4a3f2e] px-1 text-xs" placeholder="Say something... (Enter to post, @gethin etc)">
                <button onclick="postToChat()" class="text-xs px-2 border border-[#4a3f2e]">Post</button>
            </div>
        </div>
    </div>

    </div> <!-- /#game-ui -->

    <script>
        // Username login, game-style: the name you type IS your save — return
        // with the same name (any device) and the town remembers you. It's also
        // persisted in this browser so refreshes and restarts keep you logged in.
        function mintPlayerId() {
            // placeholder identity for fresh visitors until they claim a name
            return "stranger_" + Math.random().toString(36).slice(2, 6);
        }
        function ensureIdentity() {
            let id = null;
            try { id = localStorage.getItem("sonder_player_id"); } catch (e) {}
            if (!id) {
                id = mintPlayerId();
                try { localStorage.setItem("sonder_player_id", id); } catch (e) {}
            }
            return id;
        }
        let player = ensureIdentity();
        let loc = "square";
        let logs = [];
        let chatEntries = [];

        // Client-side memory cache — like a real game pre-loading NPC state when you enter an area.
        // Keyed by "player:npc:question" → answer string.
        // This makes repeated Oracle questions and "NPCs react" instant on cache hit.
        const memoryCache = {};

        function cacheKey(npc, question) {
            return `${player}:${npc}:${question}`;
        }

        function getCached(npc, question) {
            return memoryCache[cacheKey(npc, question)];
        }

        function setCached(npc, question, answer) {
            memoryCache[cacheKey(npc, question)] = answer || "";
        }

        // A write changes what an NPC knows — drop every cached answer for that
        // NPC so the next recall re-fetches instead of showing the pre-deed reply.
        function invalidateCached(npc) {
            const prefix = `${player}:${npc}:`;
            Object.keys(memoryCache).forEach(k => { if (k.startsWith(prefix)) delete memoryCache[k]; });
        }

        // Prefetch like a real game would: when you travel to a location, kick off
        // recall(s) in the background so the info is ready when the player asks.
        async function prefetchMemory(npc, question) {
            const key = cacheKey(npc, question);
            if (memoryCache[key] !== undefined) return; // already have it
            try {
                const res = await fetch("/api/recall", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ player_id: player, npc_id: npc, question })
                });
                const d = await res.json();
                setCached(npc, question, d.answer);
            } catch (e) {}
        }

        function prefetchForLocation(key) {
            if (key === "forge") {
                prefetchMemory("gethin", "You are Gethin the blacksmith. Speaking only from your own firsthand memory, in first person: what has this player done to you?");
            } else if (key === "tavern") {
                prefetchMemory("mara", "You are Mara the bandit. Speaking only from your own firsthand memory, in first person: what has this player done to you?");
            } else if (key === "grove") {
                // Only prefetch Elara here — Gethin & Mara are already cached from forge/tavern visits.
                prefetchMemory("elara", "What rumors have reached you about this traveler?");
            }
        }

        function formatTiming(ms, fromCache) {
            const secs = (ms / 1000).toFixed(1);
            return fromCache ? `${secs}s (from cache)` : `${secs}s`;
        }

        function startPlaying() {
            const landing = document.getElementById('landing');
            const game = document.getElementById('game-ui');
            if (landing) landing.style.display = 'none';
            if (game) game.style.display = 'block';

            // Initialize the game UI now that elements are visible
            initGameUI();
        }

        function initGameUI() {
            const inp = document.getElementById("pid-input");
            if (inp) {
                inp.value = player;
                inp.onchange = () => setPlayerId(inp.value);
            }
            // The status was already called in onload; just set up the world
            logs = ["08:01 You arrive in Eldridge. No one knows you."];
            chatEntries = [];
            renderLog();
            renderChat();
            setLoc("square");

            // Enter posts chat message (real chat feel)
            const chatInput = document.getElementById("chat-input");
            if (chatInput) {
                chatInput.onkeydown = (e) => {
                    if (e.key === "Enter") {
                        e.preventDefault();
                        postToChat();
                    }
                };
            }
            // Prefetches happen on travel (setLoc). No need to warm up here.
        }

        function getMentionedNpcs(msg) {
            const m = (msg || "").toLowerCase();
            const targets = [];
            if (m.includes("@gethin")) targets.push("gethin");
            if (m.includes("@mara")) targets.push("mara");
            if (m.includes("@elara")) targets.push("elara");
            return targets.length > 0 ? targets : ["gethin", "mara", "elara"];
        }

        // Per-NPC voice for chat reactions. Elara's persona sells the gossip
        // mechanic: what she "sees" is the village whispers written to her graph.
        const PERSONA = {
            gethin: "You are Gethin, the gruff blacksmith of Eldridge. Plain words, short sentences, no patience for flattery.",
            mara: "You are Mara, a wary bandit who trusts almost no one. Guarded, dry, streetwise — but genuine charm gets under her skin: if this player has been kind to you or flirted with you, let a reluctant warmth and playful teasing show through (never gush; she'd deny it if asked).",
            elara: "You are Elara, the village seer of Eldridge. You hear every whisper in town and speak in calm, knowing tones — if gossip about this player has reached you, hint that you know what they did elsewhere."
        };

        async function triggerAutoReactions(message, targets, rememberSet = []) {
            const el = document.getElementById("chat-log");
            const thinking = document.createElement("div");
            const typingText = targets.length === 1 
                ? `${targets[0] === "gethin" ? "Gethin" : targets[0] === "mara" ? "Mara" : "Elara"} is typing...`
                : "NPCs are typing...";
            thinking.textContent = typingText;
            thinking.style.fontStyle = "italic";
            thinking.style.opacity = "0.6";
            el.appendChild(thinking);

            let question = `The player said in the village group chat: "${message}".

As yourself, reply naturally and briefly in the group chat. If you have any memories of this specific player, let them shape your tone and what you say. Keep it conversational.`;
            if (targets.length === 1) {
                question = `The player addressed you directly: "${message}".

As yourself, reply naturally in character. Use any memories you have of this player.`;
            }

            const results = await Promise.all(targets.map(async (npc) => {
                const q = (PERSONA[npc] ? PERSONA[npc] + "\\n\\n" : "") + question;
                const clientCached = getCached(npc, q);
                if (clientCached !== undefined) {
                    return { npc, answer: clientCached, duration: 0, cached: true };
                }
                const fetchStart = performance.now();
                try {
                    const res = await fetch("/api/recall", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ player_id: player, npc_id: npc, question: q })
                    });
                    const d = await res.json();
                    const ans = d.answer || "";
                    setCached(npc, q, ans);
                    return { npc, answer: ans, duration: performance.now() - fetchStart, cached: d.cached === true };
                } catch (e) {
                    return { npc, answer: "", duration: performance.now() - fetchStart, cached: false };
                }
            }));

            thinking.remove();

            results.forEach(({ npc, answer, duration, cached }) => {
                const name = npc === "gethin" ? "Gethin" : npc === "mara" ? "Mara" : "Elara";
                const tstr = duration > 10 ? ` (${formatTiming(duration, cached)})` : (cached ? ' (cached)' : '');
                const finalAnswer = answer || "*thinks for a moment*";
                chatEntries.push(`${name}: ${finalAnswer}${tstr}`);

                // Commit the EXCHANGE (player line + this NPC's reply) to memory for
                // the targeted NPCs — after the reply, so recalls never queue behind
                // the write, and the NPC remembers both sides of the conversation.
                if (rememberSet.includes(npc)) {
                    const exchange = answer
                        ? `In the village group chat, the player said: "${message}" and ${name} replied: "${answer}"`
                        : `In the village group chat, the player said: "${message}"`;
                    invalidateCached(npc);
                    fetch("/api/remember", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ player_id: player, npc_id: npc, event: exchange })
                    }).catch(() => {});
                }
            });

            renderChat();
        }

        const data = {
            square: {
                n: "Village Square",
                d: "Muddy crossroads. Smoke from the forge, laughter from the tavern, mist from the grove.",
                acts: [
                    {t: "Watch the villagers", e: "You watched the slow rhythm of village life."},
                    {t: "Help carry firewood", e: "You helped an old man with his wood."}
                ],
                go: ["forge", "tavern", "grove"]
            },
            forge: {
                n: "The Forge",
                d: "Heat and hammer strikes. Gethin works iron with intense focus.",
                acts: [
                    {t: "Praise his craft and buy a blade", e: "You praised Gethin's craftsmanship and bought a sword.", m: "The player praised Gethin's craftsmanship and bought a sword from him."},
                    {t: "Commission a custom hunting dagger", e: "The player commissioned a custom hunting dagger from Gethin and paid half up front."},
                    {t: "Insult his work", e: "You mocked Gethin's craftsmanship and left empty-handed.", m: "The player mocked Gethin's craftsmanship to his face and left without buying anything."}
                ],
                go: ["square", "tavern"]
            },
            tavern: {
                n: "The Drunken Boar",
                d: "Dim light, wary eyes. Mara sits in the corner, watching.",
                acts: [
                    {t: "Buy her a drink and talk", e: "You bought Mara a drink and heard her story.", m: "The player bought Mara a drink and listened to her story."},
                    {t: "Flirt with her over the rim of your cup", e: "The player flirted with Mara, complimenting her sharp eyes; she smirked despite herself and let them sit a little closer."},
                    {t: "Ask about the scar on her hand", e: "The player asked Mara about the scar on her hand; she shared a guarded story about the road that gave it to her."},
                    {t: "Slip the guards her location", e: "You betrayed Mara's location to the town guard.", m: "The player betrayed Mara by slipping her location to the town guard."}
                ],
                go: ["square", "forge"]
            },
            grove: {
                n: "The Oracle's Grove",
                d: "Ancient stones in the mist. Elara the seer waits, eyes clouded with visions. They say she hears every whisper in Eldridge.",
                acts: [
                    {t: "Cross her palm with silver for a reading", e: "The player paid Elara for a reading and listened to her visions with respect."},
                    {t: "Scoff and call her visions a fraud", e: "The player mocked Elara's visions and called her a fraud to her face."}
                ],
                go: ["square"]
            }
        };

        function setLoc(key) {
            loc = key;
            const L = data[key];
            document.getElementById("loc-name").textContent = L.n;
            document.getElementById("loc-desc").textContent = L.d;

            const actEl = document.getElementById("actions");
            actEl.innerHTML = "";
            const o = document.getElementById("oracle");

            if (key === "grove") {
                o.classList.remove("hidden");
                const oact = document.getElementById("oracle-actions");
                oact.innerHTML = "";
                const qs = [
                    {l:"Ask what Gethin remembers", n:"gethin", q:"You are Gethin the blacksmith. Speaking only from your own firsthand memory, in first person: what has this player done to you?"},
                    {l:"Ask what Mara remembers", n:"mara", q:"You are Mara the bandit. Speaking only from your own firsthand memory, in first person: what has this player done to you?"},
                    {l:"Ask Elara what the whispers say", n:"elara", q:"What rumors have reached you about this traveler?"},
                    {l:"Ask for the full truth", special:true}
                ];
                qs.forEach(q => {
                    const btn = document.createElement("button");
                    btn.className = "link oracle-link";
                    btn.textContent = "> " + q.l;
                    btn.onclick = async (e) => {
                        e.preventDefault();
                        const orig = btn.textContent;
                        btn.textContent = orig + " [loading...]";
                        btn.disabled = true;
                        try {
                            const r = document.getElementById("oracle-result");
                            r.classList.remove("hidden");

                            if (q.special) {
                                // Full truth: parallel + cache (real game would have pre-warmed these)
                                r.innerHTML = "The Oracle consults the memories...";
                                const t0 = performance.now();
                                const fullQ = "What exactly do you remember the player doing?";
                                const recalls = await Promise.all(["gethin","mara","elara"].map(async (nn) => {
                                    const cached = getCached(nn, fullQ);
                                    if (cached !== undefined) {
                                        return { nn, answer: cached, dt: 0, cached: true };
                                    }
                                    const res = await fetch("/api/recall", {
                                        method:"POST", headers:{"Content-Type":"application/json"},
                                        body:JSON.stringify({player_id:player, npc_id:nn, question:fullQ})
                                    });
                                    const d = await res.json();
                                    const ans = d.answer || "silence";
                                    setCached(nn, fullQ, ans);
                                    return { nn, answer: ans, dt: null, cached: d.cached === true };
                                }));
                                const totalDt = performance.now() - t0;
                                r.innerHTML = recalls.map(({nn, answer, dt, cached}) => {
                                    const timeStr = dt !== null ? formatTiming(dt, cached) : formatTiming(totalDt / 3, cached);
                                    return `<div><strong>${nn}:</strong> ${answer} <span class="text-[10px] opacity-60">(${timeStr})</span></div>`;
                                }).join("");
                            } else {
                                // Single NPC query – check cache first (prefetched on travel!)
                                const cached = getCached(q.n, q.q);
                                if (cached !== undefined) {
                                    r.innerHTML = `${cached || "The mists stay silent."} <span class="text-[10px] opacity-60">(cached)</span>`;
                                    btn.textContent = orig;
                                    btn.disabled = false;
                                    return;
                                }

                                r.innerHTML = "Querying memory (real Cognee recall + LLM — a few seconds the first time for a location)...";
                                const fetchStart = performance.now();
                                const res = await fetch("/api/recall", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({player_id:player, npc_id:q.n, question:q.q})});
                                const d = await res.json();
                                const dt = performance.now() - fetchStart;
                                const answer = d.answer || "The mists stay silent.";
                                setCached(q.n, q.q, answer);
                                const isServerCached = d.cached === true;
                                r.innerHTML = `${answer} <span class="text-[10px] opacity-60">(${formatTiming(dt, isServerCached)})</span>`;
                            }
                        } finally {
                            btn.textContent = orig;
                            btn.disabled = false;
                        }
                    };
                    oact.appendChild(btn);
                });
            } else {
                o.classList.add("hidden");
            }

            // Render location actions for EVERY location — the grove now has
            // Elara's own actions alongside her seer panel.
            L.acts.forEach(act => {
                const btn = document.createElement("button");
                btn.className = "link action-link";
                btn.textContent = "> " + act.t;
                btn.onclick = (e) => {
                    e.preventDefault();
                    const orig = btn.textContent;
                    btn.textContent = orig + " [sent]";
                    btn.disabled = true;
                    addLog(act.e);  // show the deed immediately (real-game feel)
                    // The deed changes what NPCs know — drop stale client-cached
                    // answers for the acting NPC (and Elara, who hears public deeds).
                    invalidateCached(getNpc(key));
                    if (key === "forge" || key === "tavern") invalidateCached("elara");
                    // Fire remember; restore button when the request acknowledges.
                    // Forge/tavern deeds are PUBLIC — the server also whispers them
                    // to Elara (town gossip). Her own grove deeds stay hers alone.
                    fetch("/api/remember", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        // act.m = memory-clear phrasing ("The player ...") so extraction
                        // links every deed to a stable player entity; act.e stays as the
                        // friendly second-person deeds-log line.
                        body: JSON.stringify({ player_id: player, npc_id: getNpc(key), event: act.m || act.e, gossip: (key === "forge" || key === "tavern") })
                    }).finally(() => {
                        btn.textContent = orig;
                        btn.disabled = false;
                    }).catch(() => {});
                };
                actEl.appendChild(btn);
            });

            const t = document.getElementById("travel");
            t.innerHTML = "";
            L.go.forEach(g => {
                const btn = document.createElement("button");
                btn.className = "link travel-link";
                btn.textContent = "→ " + data[g].n;
                btn.onclick = (e) => {
                    e.preventDefault();
                    setLoc(g);
                };
                t.appendChild(btn);
            });

            // Real-game pattern: prefetch memories for this location in the background.
            // Next time you talk to the Oracle or ask NPCs to react, answers can come from cache.
            prefetchForLocation(key);
        }

        function getNpc(l) {
            if (l==="forge") return "gethin";
            if (l==="tavern") return "mara";
            if (l==="grove") return "elara";
            return null;
        }

        // doAction removed — actions log immediately and fire remember in background from the click handler


        function addLog(m) {
            const d = new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
            logs.unshift(d + " " + m);
            if (logs.length > 9) logs.length = 9;
            renderLog();
        }

        function renderLog() {
            const el = document.getElementById("log");
            if (!logs.length) {
                el.innerHTML = `<div class="text-[#6b5f4f]">No deeds yet.</div>`;
                return;
            }
            el.innerHTML = logs.map(l => `<div class="log-entry">${l}</div>`).join("");
        }

        function clearLog() { logs = []; renderLog(); }

        function renderChat() {
            const el = document.getElementById("chat-log");
            if (!chatEntries.length) {
                el.innerHTML = `<div class="text-[#6b5f4f]">The village is quiet...</div>`;
                return;
            }
            el.innerHTML = chatEntries.map(c => `<div>${c}</div>`).join("");
        }

        async function postToChat() {
            const inp = document.getElementById("chat-input");
            const msg = (inp.value || "").trim();
            if (!msg) return;
            const entry = "You: " + msg;
            chatEntries.push(entry);
            renderChat();
            inp.value = "";

            // Only @mentioned NPCs commit chat to memory (unaddressed "hey" -> just
            // Gethin) — writing to all 3 queues 3 cognee pipelines on the single
            // worker and starves recalls (the 160s-bottleneck fix).
            const targets = getMentionedNpcs(msg);
            const rememberSet = targets.length >= 3 ? ["gethin"] : targets;

            addLog("Posted to village chat: " + msg);

            // Reactions FIRST: the reply prompt already contains the message, so
            // recalls don't need the write to land. (Writing first made every reply
            // queue behind its own cognify on the serialized worker — the 39s
            // first-reply lag.) The full exchange (message + reply) is written to
            // memory inside triggerAutoReactions once each reply arrives.
            triggerAutoReactions(msg, targets, rememberSet);
        }

        // npcsReactToChat removed — reactions now happen automatically after every chat post (with @ support)

        async function newLife() {
            player = mintPlayerId();
            try { localStorage.setItem("sonder_player_id", player); } catch (e) {}
            renderPlayerInput();
            logs = [];
            chatEntries = [];
            // Clear client cache when starting over
            Object.keys(memoryCache).forEach(k => delete memoryCache[k]);
            await fetch("/api/forget", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({player_id:player})});
            addLog("A new life begins. The town does not know you.");
            renderChat();
            setLoc("square");
        }

        function renderPlayerInput() {
            const inp = document.getElementById("pid-input");
            if (inp) inp.value = player;
        }

        function setPlayerId(val) {
            if (!val) return;
            // Clear previous player's cached memories
            Object.keys(memoryCache).forEach(k => delete memoryCache[k]);
            player = val.trim();
            try { localStorage.setItem("sonder_player_id", player); } catch (e) {}
            renderPlayerInput();
            addLog("Identity set to " + player + ". The town will remember this name.");
            fetch("/api/status", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({player_id:player})});
        }

        async function restartServer() {
            const btns = document.querySelectorAll('button');
            // Visual feedback
            const origTexts = [];
            btns.forEach((b, i) => { origTexts[i] = b.textContent; b.textContent = '[restarting...]'; });

            try {
                const res = await fetch("/api/restart", {method:"POST"});
                const data = await res.json();

                // Clear client state to simulate fresh launch
                Object.keys(memoryCache).forEach(k => delete memoryCache[k]);
                logs = [];
                chatEntries = [];
                renderLog();
                renderChat();

                addLog("*** SERVER RESTARTED *** " + (data.message || ""));
                addLog("Fresh NPC objects created, but the Cognee knowledge graph persists.");

                // Re-init the current location with same player (memories should still be there)
                await fetch("/api/status", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({player_id:player})});
                setLoc(loc);  // re-render current scene + trigger prefetches
            } finally {
                btns.forEach((b, i) => b.textContent = origTexts[i]);
            }
        }

        window.onload = async () => {
            // Only do the non-UI work on initial load (landing is shown)
            await fetch("/api/status", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({player_id:player})});

            // Warm common memories early so when player clicks "Play" things are ready
            prefetchForLocation("forge");
            prefetchForLocation("tavern");
            prefetchForLocation("grove");
        };
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)


# -----------------------------------------------------------------------------
# API Endpoints (used by the frontend)
# -----------------------------------------------------------------------------
@app.post("/api/remember")
async def api_remember(request: Request):
    data = await request.json()
    player_id = data.get("player_id", DEFAULT_PLAYER_ID)
    npc_id = data.get("npc_id")
    event = data.get("event", "")
    
    npcs = get_npcs(player_id)
    npc = npcs.get(npc_id)

    if not npc or not event:
        return {"ok": False, "error": "invalid request"}

    # Fire-and-forget the remember so the HTTP response returns immediately.
    # The actual work (cognify etc) happens on the shared background worker.
    async def _background_remember():
        try:
            await npc.aremember(event)
        except Exception as e:
            print("remember background error:", e)

    _spawn(_background_remember())

    # Town gossip: public deeds done to Gethin/Mara also reach Elara the seer —
    # written as HER OWN engram (per-NPC isolation stays intact; gossip is an
    # explicit second write, not a backdoor read). Only when the frontend flags
    # a deed as public (location actions), never for chat spam — that keeps the
    # write volume at deed-pace, per the 160s-bottleneck fix.
    if data.get("gossip") and npc_id != "elara":
        elara = npcs.get("elara")
        if elara:
            whisper = f"Village whispers reached Elara the seer: {event}"

            async def _background_gossip():
                try:
                    await elara.aremember(whisper)
                except Exception as e:
                    print("gossip background error:", e)

            _spawn(_background_gossip())
            # Elara's cached answers are now stale too
            to_delete = [k for k in _recall_cache if k[0] == player_id and k[1] == "elara"]
            for k in to_delete:
                _recall_cache.pop(k, None)
    
    # Optimistically invalidate short recall cache (the write is in flight)
    to_delete = [k for k in _recall_cache if k[0] == player_id and k[1] == npc_id]
    for k in to_delete:
        _recall_cache.pop(k, None)
    
    return {"ok": True}


@app.post("/api/recall")
async def api_recall(request: Request):
    data = await request.json()
    player_id = data.get("player_id", DEFAULT_PLAYER_ID)
    npc_id = data.get("npc_id")
    question = data.get("question", "How do you feel about this player?")
    
    npcs = get_npcs(player_id)
    npc = npcs.get(npc_id)
    
    if not npc:
        return {"answer": ""}
    
    # Check tiny server cache first
    cache_key = (player_id, npc_id, question)
    now = time.time()
    if cache_key in _recall_cache:
        ans, ts = _recall_cache[cache_key]
        if now - ts < RECALL_CACHE_TTL:
            return {"answer": ans, "cached": True}
    
    try:
        answer = await npc.arecall(question) or ""
    except Exception:
        # Graceful for missing datasets (no remembers yet for this NPC/player)
        answer = ""
    
    # Store in short cache
    _recall_cache[cache_key] = (answer, now)
    
    return {"answer": answer, "cached": False}


@app.post("/api/forget")
async def api_forget(request: Request):
    data = await request.json()
    player_id = data.get("player_id", DEFAULT_PLAYER_ID)
    
    npcs = get_npcs(player_id)
    for npc in npcs.values():
        await npc.aforget()
    
    # Clear NPC instance cache + short recall cache for this player
    if player_id in _player_npcs:
        del _player_npcs[player_id]
    
    to_delete = [k for k in _recall_cache if k[0] == player_id]
    for k in to_delete:
        _recall_cache.pop(k, None)
    
    return {"ok": True}


@app.post("/api/status")
async def api_status(request: Request):
    data = await request.json()
    player_id = data.get("player_id", DEFAULT_PLAYER_ID)
    get_npcs(player_id)  # touch / create
    return {"ok": True, "player_id": player_id}


@app.post("/api/restart")
async def api_restart(request: Request):
    """Simulate a full server restart for the demo.
    Clears the in-process NPC cache (fresh objects) but leaves
    the underlying Cognee graph data intact → memories survive.
    """
    global _player_npcs, _recall_cache
    _player_npcs.clear()
    _recall_cache.clear()
    return {
        "ok": True,
        "message": "Server cache cleared. Persistent Cognee graph data survives the 'restart'."
    }


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SONDER WEB DEMO")
    print("="*60)
    print("Starting local web server...")
    display_host = "127.0.0.1" if HOST in ("0.0.0.0", "::") else HOST
    print(f"→ Open http://{display_host}:{PORT} in your browser")
    print("→ Click 'Play the Game', travel around, take actions (logs instantly), chat + Enter (auto reactions with typing indicator)")
    print("="*60 + "\n")
    
    # Use the app object directly (not a string import path).
    # This makes `python examples/web_demo.py` work reliably from the project root
    # without ModuleNotFoundError for 'examples'.
    uvicorn.run(app, host=HOST, port=PORT, reload=False)
