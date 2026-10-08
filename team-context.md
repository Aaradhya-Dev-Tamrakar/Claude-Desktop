# Team Context & Ecosystem Invariants

Bootstrap your session in a single tool call using orchestrator-mcp:
`get_context_bundle(account="<account>", memory_limit=5, memory_hours=24)`
This returns team context, recent durable memory, caller's assigned tasks, pending task count, and active worker heartbeats in one round-trip, saving substantial startup tokens compared to individual queries. Edit this file directly to adjust durable context across all profiles.

Because it's pasted identically into every profile (IEEE, personal, gaming,
family, project accounts alike), keep anything account-specific out of here
and use per-account Custom Instructions for that instead. Put only what you
actually want repeated everywhere: durable facts about you, how you want
Claude to behave, standing project context.

If you're reading this pasted into a chat and it still looks like this
paragraph, it means the file was never filled in — edit
`team-context.md` at the repo root.

## SPARK project

Repo: github.com/AaradhyaDT/SPARK (main). Tracker: dev_logs/SPARK_TRACKER.md — dense, versioned, authoritative; read §0/§1/§2 before acting. sync.ps1 present — mandatory workflow for any commit once a repo/sync.ps1 is touched this session (see repo-conventions).
Deep-research board: parent task_2026-08-21_001, 19 child tracks task_2026-08-21_002–\_020 (see orch memory for full context: NLM notebook 2c00f5a4 already has 6 core academic sources loaded — check before searching cold; 3b67fc33 is now proposal/deck reference only, not tracker-current).
