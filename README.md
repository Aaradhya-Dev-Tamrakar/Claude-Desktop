# Claude Desktop Multi-Profile & Sync Utilities

PowerShell scripts to manage multiple isolated user profiles for the Claude Desktop application on Windows and automate Git repository synchronization with smart commit messaging.

## Features

- **Multi-Profile Management**: Launch distinct Claude Desktop sessions via automated profile session swapping into native AppData paths.
- **Concurrent Multi-Monitor Sessions**: `-Mode Concurrent` (or `-Concurrent`) launches one or more profiles as independent, simultaneously-running windows via `--user-data-dir`, instead of swapping the single native install — drag each to its own monitor for side-by-side team use on one machine. `-Users <name1,name2,...>` launches a whole list non-interactively; per-account failures (missing exe, unknown profile) don't stop the rest of the list.
- **Native MSIX & OAuth Compatibility**: 100% compatible with Windows MSIX packages and browser OAuth deep links (`claude://`) without dual-window or authentication loop issues.
- **Dynamic Executable Resolution**: Automatically locates `Claude.exe` across MSIX/Windows Store App packages (`Get-AppxPackage *claude*`) and traditional local installation directories (`AppData\Local\Programs\Claude` and `WindowsApps`).
- **Automatic Session Backup & Persistence**: Automatically saves and syncs cookies, tokens, and local storage per profile on every switch.
- **Smart Git Synchronization**: Automatically stages, commits, pulls (with `--rebase` & `--autostash`), and pushes repository changes.
- **Auto-Sync on Launch & Reset**: `launch_user_n.ps1` and `reset_profiles.ps1` each auto-invoke `sync.ps1` (with a verbose, context-specific commit message) as their final step, skipped entirely under `-WhatIf`.
- **Intelligent Commit Messaging**: Dynamically generates conventional commit messages (`feat`, `refactor`, `chore`) derived from staged git diffs, hunk context headers, and line churn statistics (`+ins/-del`).
- **PowerShell 7 (`pwsh`) Compatible**: Fully compatible with PowerShell 7 (`pwsh`) and Windows PowerShell 5.1.

## Repo Structure

```Claude-Desktop/
├── launch_user_n.ps1              # Profile launcher (Isolated / Concurrent)
├── launch.bat                     # Double-click entry point for File Explorer
├── sync.ps1                       # Git sync: pull --rebase --autostash, commit, push
├── cooldown-reminder.ps1          # Post-login 5h cooldown toast, invoked by launch_user_n.ps1
├── reset_profiles.ps1             # Wipes all profile state, resets profiles.json to {}
├── bypass-all-profiles.ps1        # Sets bypassPermissionsGateByAccount=true across all profile configs
├── profiles.json                  # Account name -> nickname/paths/last-login map
├── team-mcp.json                  # Shared MCP config, force-merged into every profile
├── team-context.md                # Static identity scaffold, clipboard-delivered on launch
├── team-memory.md                 # Hand-appended memory log, clipboard-delivered on launch
├── gcal-credentials.json.example  # Google Calendar OAuth credential template
├── gcal-token.json.example        # Google Calendar token template
├── AGENTS.md                      # Repo conventions for agent contributors
├── README.md
├── LICENSE
├── .gitattributes
├── .gitignore
│
├── mcp-servers/
│   ├── notebooklm-mcp/
│   │   └── run_server.py          # uvx-shim launcher for the published NotebookLM CLI
│   └── orchestrator-mcp/
│       └── run_server.py          # Hand-written MCP server, 13 tools, requires `pip install mcp`
│
├── orchestrator-state/
│   ├── SCHEMA.md                  # File contract for tasks/live-status/checkpoints/memory
│   ├── tasks/.gitkeep
│   ├── live-status/.gitkeep
│   ├── checkpoints/.gitkeep
│   └── memory/.gitkeep
│
└── tests/
    ├── launch_user_n.Tests.ps1        # Pester specs (path guard, profile table, MCP merge, placeholder expansion)
    └── orchestrator_mcp_test.py       # pytest specs, 22 cases, each against a throwaway git repo
```

## Files

- **`launch_user_n.ps1`**: Profile launcher script. Two modes: **Isolated** (default) resolves the executable path and swaps a single profile's session data into the native AppData install; **Concurrent** (`-Mode Concurrent` / `-Concurrent`, optionally with `-Users <name1,name2,...>`) launches one or more profiles as independent windows via `--user-data-dir`, with no swap/mirror and no shared `claude://` handler changes. With no `-Mode`/`-Concurrent`/`-Users` given, prompts once for a mode. Unless `-NoTeamSync`, force-merges `team-mcp.json` into each launching profile's `claude_desktop_config.json` and stages `team-context.md` + `team-memory.md` (concatenated) on the clipboard.
- **`launch.bat`**: Double-click launcher for Windows File Explorer.
- **`profiles.json`**: Configuration file mapping account profile names to display nicknames, user data storage paths, and last logged-in timestamps.
- **`team-mcp.json`**: Shared MCP server config, force-merged into every profile's `claude_desktop_config.json` on launch (shared entries win on name collision; a profile's own extra servers are never removed). Currently wires in `notebooklm-mcp` and `orchestrator-mcp` (see `mcp-servers/`) — add further entries here to roll them out to every profile at once. Use the literal token `{{REPO_ROOT}}` anywhere a `command`/`args`/`env` value needs to reference a path inside the repo; `Expand-TeamMcpPlaceholders` resolves it to each machine's actual clone path at sync time, so no entry should ever hardcode one contributor's absolute path.
- **`mcp-servers/notebooklm-mcp/run_server.py`**: `uvx` launcher for the NotebookLM MCP server, referenced by `team-mcp.json`. Falls back through common per-platform `uvx` install locations when it's missing from `PATH` (Claude Desktop launches with a restricted `PATH`). Auth is shared across all profiles via `%USERPROFILE%\.notebooklm-mcp-cli\` (every profile runs as the same Windows user) — run `nlm login` once, no per-profile setup needed.
- **`mcp-servers/orchestrator-mcp/run_server.py`**: Hand-written MCP server (not a `uvx` shim — requires `pip install mcp` locally, unlike `notebooklm-mcp`) coordinating orchestrator/divider/executor roles across profiles. Tools: `create_task`/`decompose_task` (orchestrator/divider), `claim_task`/`release_task`/`mark_blocked`/`unblock_task`/`submit_checkpoint` (executor), `push_live_status`/`read_all_live_status` (cheap frequent status, no history), `push_memory_entry`/`read_team_memory` (MCP-native cross-profile memory sync — chat-callable replacement for pasting `team-memory.md`/`team-context.md` via `Send-TeamContextAndMemoryToClipboard`; one file per entry under `orchestrator-state/memory/`, never per-account, so pushes never read-modify-write a shared file), `list_tasks`/`merge_results` (orchestrator — text tasks return findings for the orchestrator's own LLM to synthesize, code tasks get `git merge --no-ff`'d with a clean `git merge --abort` on the first conflict). State is plain JSON under `orchestrator-state/`, synced by `sync.ps1` like every other file — see `orchestrator-state/SCHEMA.md` for the full file contract and why every entity is its own file rather than one shared file multiple accounts write to.
- **`team-context.md`**: Static identity/context scaffold. Its full content is copied to the clipboard on every launch for pasting as a first message or into Custom Instructions. Edit it directly with what you actually want repeated into every profile — it ships as a plain-text placeholder, so if it still reads like a template when pasted, that's the signal it hasn't been filled in yet.
- **`team-memory.md`**: Growing, hand-appended memory log — same clipboard/Custom-Instructions delivery as `team-context.md`, concatenated with it. Distributed via `sync.ps1` like everything else, so an entry added from one profile reaches every other profile's clipboard on its next launch. Nothing is written to it automatically; it only grows when you add a line.
- **`sync.ps1`**: Automated Git repository synchronization tool.
- **`cooldown-reminder.ps1`**: Auto-invoked by `launch_user_n.ps1` after every non-`-WhatIf` login. Tracks each profile's `first_login_time`, anchors a 5-hour cooldown to it, and registers a local Windows toast alarm for when the cooldown expires.
- **`reset_profiles.ps1`**: Wipes all profile storage, logs, session state, and the `claude://` registry override, then resets `profiles.json` to `{}`. Prompts for a typed `RESET` confirmation unless `-WhatIf`.
- **`bypass-all-profiles.ps1`**: Sets `preferences.bypassPermissionsGateByAccount` to `true` for every account UUID found across all `%USERPROFILE%\.claude-profiles\userN\claude_desktop_config.json` files — applies to every MCP server merged in from `team-mcp.json` (both `notebooklm-mcp` and `orchestrator-mcp`), since the gate is account-scoped, not per-server. Backs up each config to `.bak` before writing. `-WhatIf` reports per-profile status (`already true` / `would update` / `no bypassPermissionsGateByAccount key` / `config not found`) without writing. Skips profiles whose config file doesn't exist yet rather than creating one.
- **`tests/launch_user_n.Tests.ps1`**: Pester specs for `launch_user_n.ps1`'s pure/mockable logic (path-traversal guard, profile table formatting, shared-MCP-server merge, `{{REPO_ROOT}}` placeholder expansion). Run via `Invoke-Pester -Path .\tests\launch_user_n.Tests.ps1`.
- **`tests/orchestrator_mcp_test.py`**: pytest specs for `orchestrator-mcp/run_server.py` — text- and code-task lifecycles, a deliberate merge conflict (asserting the repo is left clean, never mid-merge), blocked/unblock, claim-race rejection, live-status independence, team-memory push/read (round-trip, chronological sort across accounts, `since` filter, same-account repeat-push with no id collision), and input validation. Each test runs against its own throwaway git repo, never this repo's actual state. Run via `pip install pytest mcp --break-system-packages && pytest tests/orchestrator_mcp_test.py -v`.

## Usage

### Launching Claude Desktop Profiles

Double-click **`launch.bat`** in Windows File Explorer, or run via PowerShell:

```powershell
pwsh -File .\launch_user_n.ps1 -Account user1
pwsh -File .\launch_user_n.ps1 -Account user2
```

With no arguments, the script prompts once for a mode (Isolated or Concurrent), then walks the normal profile picker.

### Concurrent Mode (Multiple Windows, Multiple Monitors)

Launch two or more profiles side by side, each its own independent window — each keeps its own `--user-data-dir`, so nothing is swapped or mirrored:

```powershell
pwsh -File .\launch_user_n.ps1 -Mode Concurrent -Users aaradhya,bei79001
```

Or one at a time:

```powershell
pwsh -File .\launch_user_n.ps1 -Concurrent -Account aaradhya
pwsh -File .\launch_user_n.ps1 -Concurrent -Account bei79001
```

`claude://` sign-in is a single OS-wide handler shared by every window — sign in to each profile one at a time (others closed) before running them concurrently. A profile that fails to launch (missing exe, unknown name) doesn't block the rest of the `-Users` list.

Preview what a profile switch would do without touching any files, the registry, or running processes:

```powershell
pwsh -File .\launch_user_n.ps1 -Account user1 -WhatIf
```

Every non-`-WhatIf` launch auto-runs `sync.ps1` as its last step (pull, commit, push), with a commit message describing the profile switch. `reset_profiles.ps1` does the same after clearing all profiles. `-WhatIf` skips this entirely — no git operations occur during a dry run.

### Syncing Git Repository

Run full sync (pull rebase, auto-commit changes, and push):

```powershell
pwsh -File .\sync.ps1
```

Supply a custom commit message:

```powershell
pwsh -File .\sync.ps1 -Message "docs: update readme with pwsh usage and appx resolution details"
```

Perform pull-only:

```powershell
pwsh -File .\sync.ps1 -PullOnly
```
