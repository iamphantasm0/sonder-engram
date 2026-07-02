# Repo Session Log — 2026-07-02

**Vault counterpart:** `/home/iamphantasm0/zeros, obsidian/sonder-engram/logs/2026-07-02.md`

## Summary of work
- Created the full Obsidian vault for sonder-engram per global Claude instructions (README, STATUS, progress, decisions, logs/2026-07-02.md).
- Captured complete project narrative: senior code review of SDK, evolution to Torn-style web demo (locations, Oracle, group chat), clickability debugging saga, loading states, identity input (no prompt), Railway volume notes.
- Minor fix: ensured "elara" NPC is instantiated so all UI paths (Oracle full-truth, chat reactions) have a real memory source.
- Updated vault root to list the project.
- Added this repo-side log (as required when code-adjacent work + memory changes happen).

## Files touched
- examples/web_demo.py (small addition of elara NPC for completeness)
- docs/session-logs/2026-07-02-vault-and-memory-logs.md (new)
- (Vault files created outside repo)

## Why this matters
Logging is part of the deliverable. The vault now holds the "why", the pain points ("nothing is clickable" was a JS scoping + timing issue after string edits), the UI direction rationale (Torn + Oracle + chat makes memory visceral), and the operational notes (Railway volume). Future sessions (video recording, PRs, hardening) start with full context.

## Next steps (from vault)
1. End-to-end restart test of the web demo with a stable player_id.
2. Record the 90s demo video.
3. Hackathon submission + PyPI.

See the vault log for the full play-by-play and insights.
> See also: Obsidian — sonder-engram/logs/2026-07-02.md
