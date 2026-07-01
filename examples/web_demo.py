#!/usr/bin/env python3
"""
Sonder Web Demo — An easy-to-launch playable demo of persistent NPC memory.

Run it:

    pip install -e ".[fastembed,web]"
    cp .env.example .env     # add your LLM key (DeepSeek recommended)
    python examples/web_demo.py

Then open http://127.0.0.1:8000 in your browser.

This uses the SDK directly (no sidecar needed). All memory is powered by
Cognee knowledge graphs so NPCs actually remember what you did across "sessions".
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from sonder_engram import NPC, Settings

# -----------------------------------------------------------------------------
# Demo configuration
# -----------------------------------------------------------------------------
DEFAULT_PLAYER_ID = "curious_traveler"
PORT = int(os.environ.get("SONDER_WEB_PORT", "8000"))

# In-memory cache of NPCs per player (so different player_ids have isolated memories)
_player_npcs: Dict[str, Dict[str, NPC]] = {}


def get_npcs(player_id: str) -> Dict[str, NPC]:
    """Get or create the demo NPCs for a given player."""
    if player_id not in _player_npcs:
        settings = Settings(ground_strict=True)  # lean a bit toward stored facts
        _player_npcs[player_id] = {
            "gethin": NPC("gethin_the_blacksmith", player_id=player_id, settings=settings),
            "mara": NPC("mara_the_bandit", player_id=player_id, settings=settings),
        }
    return _player_npcs[player_id]


# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up message
    print("Sonder Web Demo ready.")
    print(f"Open http://127.0.0.1:{PORT} in your browser.")
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
    <title>The Town of Sonder • Memory Demo</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&amp;family=Inter:wght@400;500&amp;display=swap');
        
        body {
            font-family: 'Inter', system_ui, sans-serif;
        }
        .title-font {
            font-family: 'Playfair Display', Georgia, serif;
        }
        .npc-card {
            transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s;
        }
        .npc-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
        }
        .memory-box {
            background: linear-gradient(to bottom, #f8fafc, #f1e7d2);
            border: 1px solid #d1c4a8;
        }
        .event {
            font-size: 0.875rem;
            padding: 0.5rem 0.75rem;
            background: #f8fafc;
            border-left: 3px solid #854d0e;
        }
        .loading {
            animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
    </style>
</head>
<body class="bg-stone-950 text-stone-200">
    <div class="max-w-5xl mx-auto p-6">
        <!-- Header -->
        <div class="flex items-center justify-between mb-8">
            <div>
                <h1 class="title-font text-5xl font-bold tracking-tighter text-amber-300">The Town of Sonder</h1>
                <p class="text-stone-400 mt-1">A living memory demo powered by Cognee</p>
            </div>
            <div class="text-right text-sm">
                <div class="text-amber-300 font-medium">NPCs that actually remember you</div>
                <div class="text-stone-500">Across sessions • Across restarts</div>
            </div>
        </div>

        <!-- Player Identity -->
        <div class="mb-8 bg-stone-900 border border-stone-800 rounded-2xl p-6">
            <div class="flex items-center gap-x-3 mb-3">
                <span class="font-semibold text-amber-300">Your Identity</span>
                <span class="text-xs px-2 py-0.5 bg-stone-800 rounded-full text-stone-400">Stable across playthroughs</span>
            </div>
            
            <div class="flex gap-3 items-center">
                <input id="player-id" 
                       class="flex-1 bg-stone-950 border border-stone-700 focus:border-amber-600 rounded-xl px-4 py-2.5 text-lg font-medium outline-none"
                       value="curious_traveler" 
                       placeholder="Enter a player ID">
                <button onclick="changePlayer()"
                        class="px-6 py-2.5 bg-amber-700 hover:bg-amber-600 active:bg-amber-800 transition-colors text-white rounded-xl font-medium">
                    Change Identity
                </button>
                <button onclick="resetAllMemories()"
                        class="px-4 py-2.5 border border-red-900 hover:bg-red-950 text-red-400 rounded-xl text-sm transition-colors">
                    Reset Memories
                </button>
            </div>
            <div class="text-xs text-stone-500 mt-2">
                Changing your identity gives you a completely fresh start with the NPCs.
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            
            <!-- Gethin -->
            <div class="npc-card bg-stone-900 border border-stone-800 rounded-3xl p-6">
                <div class="flex items-start justify-between mb-4">
                    <div>
                        <div class="text-amber-300 font-semibold text-xl">Gethin</div>
                        <div class="text-stone-400 text-sm">The Blacksmith</div>
                    </div>
                    <div class="text-4xl">🔨</div>
                </div>
                
                <p class="text-stone-400 text-sm mb-5 leading-relaxed">
                    A proud craftsman who takes his work very seriously.
                </p>
                
                <div class="space-y-2 mb-6">
                    <div class="text-xs uppercase tracking-widest text-stone-500 px-1">Actions you can take</div>
                    
                    <button onclick="performAction('gethin', 'The player warmly praised Gethin\\'s craftsmanship and bought a fine sword.')"
                            class="w-full text-left px-4 py-3 bg-stone-800 hover:bg-stone-700 active:bg-stone-900 transition rounded-2xl text-sm flex items-center justify-between group">
                        <span>Praise his craftsmanship</span>
                        <span class="text-amber-400 group-active:scale-95 transition">→</span>
                    </button>
                    
                    <button onclick="performAction('gethin', 'The player insulted Gethin\\'s craftsmanship and walked out without buying anything.')"
                            class="w-full text-left px-4 py-3 bg-stone-800 hover:bg-stone-700 active:bg-stone-900 transition rounded-2xl text-sm flex items-center justify-between group">
                        <span>Insult his work and leave</span>
                        <span class="text-amber-400 group-active:scale-95 transition">→</span>
                    </button>
                </div>
                
                <button onclick="askAbout('gethin')"
                        class="w-full bg-gradient-to-r from-amber-700 to-yellow-800 hover:from-amber-600 hover:to-yellow-700 transition text-white font-medium py-3.5 rounded-2xl flex items-center justify-center gap-2">
                    <span>Ask Gethin how he feels about you</span>
                </button>
                
                <div id="gethin-memory" class="memory-box mt-4 hidden p-4 rounded-2xl text-sm text-stone-800"></div>
            </div>

            <!-- Mara -->
            <div class="npc-card bg-stone-900 border border-stone-800 rounded-3xl p-6">
                <div class="flex items-start justify-between mb-4">
                    <div>
                        <div class="text-amber-300 font-semibold text-xl">Mara</div>
                        <div class="text-stone-400 text-sm">The Bandit</div>
                    </div>
                    <div class="text-4xl">🗡️</div>
                </div>
                
                <p class="text-stone-400 text-sm mb-5 leading-relaxed">
                    A captured outlaw who watches everything carefully.
                </p>
                
                <div class="space-y-2 mb-6">
                    <div class="text-xs uppercase tracking-widest text-stone-500 px-1">Actions you can take</div>
                    
                    <button onclick="performAction('mara', 'The player spared Mara\\'s life instead of turning her in to the guards.')"
                            class="w-full text-left px-4 py-3 bg-stone-800 hover:bg-stone-700 active:bg-stone-900 transition rounded-2xl text-sm flex items-center justify-between group">
                        <span>Spare her life</span>
                        <span class="text-amber-400 group-active:scale-95 transition">→</span>
                    </button>
                    
                    <button onclick="performAction('mara', 'The player turned Mara in to the guards for the bounty.')"
                            class="w-full text-left px-4 py-3 bg-stone-800 hover:bg-stone-700 active:bg-stone-900 transition rounded-2xl text-sm flex items-center justify-between group">
                        <span>Turn her in for the bounty</span>
                        <span class="text-amber-400 group-active:scale-95 transition">→</span>
                    </button>
                </div>
                
                <button onclick="askAbout('mara')"
                        class="w-full bg-gradient-to-r from-amber-700 to-yellow-800 hover:from-amber-600 hover:to-yellow-700 transition text-white font-medium py-3.5 rounded-2xl flex items-center justify-center gap-2">
                    <span>Ask Mara how she feels about you</span>
                </button>
                
                <div id="mara-memory" class="memory-box mt-4 hidden p-4 rounded-2xl text-sm text-stone-800"></div>
            </div>
        </div>

        <!-- Event Log -->
        <div class="bg-stone-900 border border-stone-800 rounded-3xl p-6">
            <div class="flex justify-between items-center mb-3">
                <div>
                    <span class="font-semibold">Recent Events</span>
                    <span class="ml-2 text-xs text-stone-500">What the NPCs have recorded</span>
                </div>
                <button onclick="clearLog()" class="text-xs text-stone-500 hover:text-stone-300">Clear log</button>
            </div>
            <div id="event-log" class="space-y-1 text-sm max-h-48 overflow-auto pr-2"></div>
        </div>

        <div class="mt-6 text-center text-xs text-stone-500">
            Memories are stored in a real knowledge graph. 
            Try different choices, then ask the NPCs about you. 
            Change your identity to start over.
        </div>
    </div>

    <script>
        let currentPlayer = "curious_traveler";
        
        function logEvent(text) {
            const log = document.getElementById("event-log");
            const div = document.createElement("div");
            div.className = "event rounded-lg mb-1 text-stone-300";
            div.textContent = text;
            log.prepend(div);
            
            // Keep only last 8 events
            while (log.children.length > 8) {
                log.removeChild(log.lastChild);
            }
        }
        
        async function performAction(npc, eventText) {
            const res = await fetch("/api/remember", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ 
                    player_id: currentPlayer, 
                    npc_id: npc, 
                    event: eventText 
                })
            });
            
            if (res.ok) {
                logEvent(`${npc === "gethin" ? "Gethin" : "Mara"}: ${eventText}`);
                
                // Auto refresh memory after action
                setTimeout(() => askAbout(npc, true), 600);
            } else {
                alert("Failed to record memory. Is the server running?");
            }
        }
        
        async function askAbout(npc, silent = false) {
            const memoryEl = document.getElementById(npc + "-memory");
            memoryEl.classList.remove("hidden");
            memoryEl.innerHTML = `<span class="loading text-amber-700">Thinking...</span>`;
            
            const question = npc === "gethin" 
                ? "How do you feel about this player, and why?"
                : "How do you feel about this player and why?";
            
            const res = await fetch("/api/recall", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ 
                    player_id: currentPlayer, 
                    npc_id: npc, 
                    question: question 
                })
            });
            
            const data = await res.json();
            
            if (data.answer) {
                memoryEl.innerHTML = `
                    <div class="font-medium text-amber-900 mb-1">Gethin says:</div>
                    <div class="leading-snug">"${data.answer}"</div>
                `;
                if (!silent) {
                    logEvent(`You asked ${npc === "gethin" ? "Gethin" : "Mara"} about yourself.`);
                }
            } else {
                memoryEl.innerHTML = `<span class="text-stone-600">They don't seem to recognize you yet.</span>`;
            }
        }
        
        async function changePlayer() {
            const input = document.getElementById("player-id");
            const newId = input.value.trim() || "curious_traveler";
            
            if (newId === currentPlayer) return;
            
            currentPlayer = newId;
            
            // Clear displayed memories
            document.getElementById("gethin-memory").classList.add("hidden");
            document.getElementById("mara-memory").classList.add("hidden");
            
            // Clear log
            document.getElementById("event-log").innerHTML = "";
            
            logEvent(`You are now known as "${currentPlayer}". The NPCs have no memory of you.`);
            
            // Optional: fetch a status to "touch" the new player
            await fetch("/api/status", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ player_id: currentPlayer })
            });
        }
        
        async function resetAllMemories() {
            if (!confirm("Clear all memories for the current player?")) return;
            
            await fetch("/api/forget", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ player_id: currentPlayer })
            });
            
            document.getElementById("gethin-memory").classList.add("hidden");
            document.getElementById("mara-memory").classList.add("hidden");
            document.getElementById("event-log").innerHTML = "";
            
            logEvent("All memories for this playthrough have been wiped.");
        }
        
        function clearLog() {
            document.getElementById("event-log").innerHTML = "";
        }
        
        // Keyboard support
        document.addEventListener("keydown", function(e) {
            if (e.key === "Enter" && document.activeElement.id === "player-id") {
                changePlayer();
            }
        });
        
        // Initial greeting
        window.onload = function() {
            const log = document.getElementById("event-log");
            log.innerHTML = `
                <div class="event rounded-lg mb-1">You arrive in a small town. The locals have no memory of you yet.</div>
            `;
            
            // Pre-fill and set initial player
            const input = document.getElementById("player-id");
            input.value = currentPlayer;
            
            // Optional first recall after short delay
            setTimeout(() => {
                // Don't auto-ask so user can explore
            }, 1200);
        }
        
        // Expose for debugging
        window.sonderDemo = { askAbout, performAction, changePlayer };
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
    
    await npc.aremember(event)
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
    
    answer = await npc.arecall(question)
    return {"answer": answer or ""}


@app.post("/api/forget")
async def api_forget(request: Request):
    data = await request.json()
    player_id = data.get("player_id", DEFAULT_PLAYER_ID)
    
    npcs = get_npcs(player_id)
    for npc in npcs.values():
        await npc.aforget()
    
    # Also clear from cache
    if player_id in _player_npcs:
        del _player_npcs[player_id]
    
    return {"ok": True}


@app.post("/api/status")
async def api_status(request: Request):
    data = await request.json()
    player_id = data.get("player_id", DEFAULT_PLAYER_ID)
    get_npcs(player_id)  # touch / create
    return {"ok": True, "player_id": player_id}


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SONDER WEB DEMO")
    print("="*60)
    print("Starting local web server...")
    print(f"→ Open http://127.0.0.1:{PORT} in your browser")
    print("→ Make sure you have a valid .env with LLM_API_KEY")
    print("→ Use the actions, then click the 'Ask ...' buttons")
    print("="*60 + "\n")
    
    uvicorn.run("examples.web_demo:app", host="127.0.0.1", port=PORT, reload=False)
