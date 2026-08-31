# Handoff Protocol

Formal, token-efficient format for all cross-profile communication.
Every profile must follow these conventions when pushing memory or checkpoints.

## Memory Entry Format

Default priority ("normal"): max 280 characters.

    [PROJECT_TAG] one-line fact or decision

Examples:
- `[SPARK] Chapter 3 dataset fix verified — SisFall/self-collected wording correct`
- `[BiasAperture] Track 05 checkpoint submitted, fairness metric baseline = 0.83`

## Checkpoint Summary Format (max 500 chars)

    WHAT: <one sentence>
    RESULT: <pass/fail/partial + key metric>
    NEXT: <what the next stage needs to know>
    BLOCKERS: <none | description>

## Anti-Patterns (Wastes Tokens)

- ❌ Full derivations/proofs as memory entries (use NLM notebook instead)
- ❌ Verbose narrative ("After much deliberation, we decided to...")
- ❌ Duplicating info already in team-context.md
- ❌ Calling `read_team_memory()` without `since` or `limit`
- ❌ Web searching before checking NLM notebooks in Cross-Linking Hub
- ❌ Storing multi-paragraph context that belongs in a checkpoint, not memory

## Session Bootstrap

Use ONE call: `get_context_bundle(account=<self>, memory_limit=10, memory_hours=48)`

Do NOT call `read_team_context` + `read_team_memory` + `list_tasks` separately.
