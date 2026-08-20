# orchestrator-state schema

File-based coordination state for orchestrator-mcp. Every file here is
plain JSON, git-tracked, and moved between machines by `sync.ps1` — there
is no daemon, no lock file, and no network transport. "Real-time" sync
means "as fresh as the last `sync.ps1` pull," not literally instant.

**One file per entity, never a shared file two accounts write to.** This
is the load-bearing design constraint: `sync.ps1` does `git pull --rebase`
with zero conflict-resolution logic (see sync.ps1's push-rejection retry
at the bottom — it retries the _push_, not a rebase conflict). Two
accounts editing the same file's overlapping regions between pulls
produces a rebase conflict that halts the script with no recovery path.
Splitting every entity into its own file turns a "concurrent edit" into
a "new file added" or "file only its owner touches," which git merges
for free.

## orchestrator-state/tasks/<task_id>.json

One file per task, in the flat task tree (parent_id links form the tree,
no nested directories). Created once by whoever calls `create_task` or
`decompose_task`. After creation, only the current `owner_account` writes
to it (claiming = writing your account into `owner_account` +
`status: "claimed"` — see race note below).

```json
{
  "id": "task_2026-08-02_001",
  "parent_id": null,
  "kind": "code",
  "spec": "one-paragraph description of what this task is",
  "status": "pending",
  "owner_account": null,
  "branch_name": null,
  "blocked_reason": null,
  "created_by": "user1",
  "created_at": "2026-08-02T10:15:00Z",
  "updated_at": "2026-08-02T10:15:00Z"
}
```

- `id`: `task_<date>_<seq>`, assigned at creation, never reused.
- `parent_id`: `null` for a top-level task the orchestrator created
  directly; another task's `id` if this is a subtask produced by
  `decompose_task`. Enables reading a subtree without a separate index.
- `kind`: `"code"` or `"text"` — decided at creation, drives which
  `checkpoints/<task_id>.json` shape is expected and which merge path
  `merge_results` takes. See "kind" below.
- `status`: `pending -> claimed -> done -> merged`, with `blocked` as a
  side-branch from `claimed` (`mark_blocked` / `unblock_task` toggle
  between `claimed` and `blocked` without touching `owner_account` —
  it's a status flag on work still in progress, not a release back to
  the pool; see `release_task` for that instead).
- `owner_account`: the profile account name (`profiles.json` key or
  nickname — orchestrator-mcp doesn't care which, it's a free string
  used only for display and for the claim-race check) currently holding
  this task, `null` when `pending`.
- `branch_name`: only set for `kind: "code"` tasks, once claimed. The
  executor's own choice, recorded here so `merge_results` knows what to
  merge. `null` for `kind: "text"` tasks — they have no branch.
- `blocked_reason`: free text set by `mark_blocked`, cleared by
  `unblock_task`. `null` unless `status == "blocked"`.
- `created_by` / `created_at` / `updated_at`: audit trail, not read by
  any tool logic.

**Claim race**: `claim_task` reads the file, checks `status == "pending"`
and `owner_account == null`, then writes. Between the read and the write,
another account's claim could have already landed and been pulled in by
a `sync.ps1` that ran in between — so `claim_task` re-reads immediately
before writing and aborts if `owner_account` is no longer `null`. This
is optimistic locking, not a real lock; it narrows the race window to
"between re-read and write on one machine," which a single Python
process closes by never yielding in between.

## orchestrator-state/live-status/\<account\>.json

One file per account. Only that account's executor process ever writes
its own file — never read-modify-write across accounts, so there is no
race here at all, by construction. Cheap and frequent: no context, no
history, just "what am I doing right now."

```json
{
  "account": "user1",
  "current_task_id": "task_2026-08-02_001",
  "heartbeat_at": "2026-08-02T10:22:41Z",
  "note": "wiring claim_task, about to run the test suite"
}
```

- `current_task_id`: `null` when idle.
- `heartbeat_at`: overwritten on every `push_live_status` call. A stale
  timestamp (older than a few sync cycles) is the signal an account went
  offline mid-task — orchestrator-side staleness policy, not enforced by
  this schema.
- `note`: one line, free text, no history kept. This file is
  last-write-wins by design — it's a status light, not a log.

## orchestrator-state/checkpoints/<task_id>.json

One file per task, written once by `submit_checkpoint` when the owning
account finishes (or hits a major milestone worth recording). This is
the actual context handoff — `merge_results` reads these, not
`live-status/`.

```json
{
  "task_id": "task_2026-08-02_001",
  "kind": "code",
  "summary": "two or three sentences a human or the orchestrator's LLM can read to know what happened, without opening the diff",
  "branch_name": "task/task_2026-08-02_001",
  "commit_sha": "a1b2c3d",
  "result_text": null,
  "submitted_by": "user1",
  "submitted_at": "2026-08-02T11:40:00Z"
}
```

- `kind`: mirrors the parent task's `kind`, kept here too so a reader of
  just this file doesn't need to cross-reference `tasks/<task_id>.json`.
- For `kind: "code"`: `branch_name` + `commit_sha` are set, `result_text`
  is `null`. `merge_results` shells out to git (`git merge` or
  `git cherry-pick` against `commit_sha`) using these two fields.
- For `kind: "text"`: `branch_name` + `commit_sha` are `null`,
  `result_text` holds the actual findings/output. `merge_results` gathers
  every child task's `result_text` and hands them to the orchestrator's
  own LLM call to synthesize — the tool's job is only to gather, the
  synthesis itself isn't scriptable and isn't attempted in code.
- One task can only have one checkpoint file. A second
  `submit_checkpoint` call for the same `task_id` overwrites — there is
  no checkpoint history, only the latest.

## orchestrator-state/memory/\<account\>\_\_\<entry_id\>.json

One file per entry, never per account — an account pushes many entries
over time, so per-account-per-file would make every push a
read-modify-write on a growing shared file (the exact hazard this
schema exists to avoid). `entry_id` is a timestamp (`pushed_at` with
`:` and `-` stripped), collision-checked against the directory and
suffixed `_2`, `_3`, ... on collision — same "scan fresh, don't trust a
counter file" approach as `tasks/`' `_next_task_id`. This is the
MCP-native, automatable replacement for the old
`Send-TeamContextAndMemoryToClipboard` workflow (manually pasting
`team-memory.md` into a profile's chat): `push_memory_entry` writes,
`read_team_memory` aggregates and sorts by `pushed_at`, `sync.ps1`
carries the files between machines same as everything else here.

```json
{
  "account": "user1",
  "text": "note or context another account should see",
  "pushed_at": "2026-08-05T14:22:41Z"
}
```

- `account`: who pushed it. Free string, same validation as
  `owner_account` elsewhere.
- `text`: free text, no length limit enforced by the schema.
- `pushed_at`: set once at push time, never modified — this file is
  never edited after creation, only ever a new file added, so there is
  no write race at all, not even the narrowed one `claim_task` has.

`team-memory.md` and `team-context.md` at the repo root still exist and
are still the human-facing / static-identity path (paste manually as
needed — the old auto-clipboard-copy-on-launch has been removed) — this
directory is an additive, chat-callable path for dynamic notes, not a
replacement for those two files.

## Directory listing as the index

There is no separate `index.json` tracking "which task ids exist" — the
directory listing of `orchestrator-state/tasks/` _is_ the index.
`list_tasks` (or equivalent) just globs the directory. This avoids a
second file that would need to stay in sync with the per-task files and
would reintroduce exactly the shared-file race this schema exists to
avoid.
