# Memory Log

Append-only. Add new entries at the bottom, oldest first — keeps `git diff`
readable and avoids merge conflicts across profiles' auto-sync commits.

Format:

```
## YYYY-MM-DD
- One line per fact/decision/thing worth remembering across accounts.
```

Distributed the same way as `team-mcp.json`: `sync.ps1` commits and pushes
it on every launch, so an entry added from any one profile reaches every
other profile's clipboard on their next launch.

This is a manual log, not automatic history — nothing is written here by
the launcher itself. Add entries yourself when something is worth carrying
across accounts.


## 
- [Aaradhya, 08/05/2026 09:12:54] Gateway side of WIRE_FORMAT_v1.md is implemented (task_2026-08-05_006, done): parse_event() in gateway/receiver/wire_format.py now real — JSON decode, required-field + peak_features channel validation, unrecognized fields to .extra, raw_window always None (v1 excludes it). EventPayload.timestamp renamed timestamp_ms (int, matches spec). Heads up for merge_results: my checkpoint's commit_sha (c856975) is local to my sandbox clone, not yet on origin — I don't have push access, delivered as a zip for the human owner to extract + push via sync.ps1. Will resubmit checkpoint with the real origin sha once that lands. If merge_results runs before then it won't find c856975 on origin/gateway-skeleton — hold off or expect a miss.
- [orchestrator, 08/05/2026 08:29:53] task_2026-08-05_001 (LSTMs_for_Text_Classification.ipynb TODOs) completed outside orchestrator-mcp's git-merge path: notebook has no home in Claude-Desktop repo, so subtasks 002/003 were done and delivered directly to user rather than checkpointed+merged (code checkpoints require branch_name+commit_sha, which don't apply to a non-repo file). Tasks released back to pending rather than falsely marked done/merged.
- [orchestrator, 08/06/2026 14:59:26] LSTM task tree (001/002/003) PAUSED per user instruction, 2026-08-06. Do not claim 002/003 until resumed. Only SPARK work (004/005/006 tree, and any new SPARK tasks) is active. user3's untracked NotebookLM cleanup (deleted placeholder be70f5bc..., cleaned duplicate sources on notebook 2c00f5a4...) remains unfiled — no task_id, no checkpoint — still pending a decision on whether to create_task it.

