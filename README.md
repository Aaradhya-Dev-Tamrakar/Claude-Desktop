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

## Files

- **`launch_user_n.ps1`**: Profile launcher script. Two modes: **Isolated** (default) resolves the executable path and swaps a single profile's session data into the native AppData install; **Concurrent** (`-Mode Concurrent` / `-Concurrent`, optionally with `-Users <name1,name2,...>`) launches one or more profiles as independent windows via `--user-data-dir`, with no swap/mirror and no shared `claude://` handler changes. With no `-Mode`/`-Concurrent`/`-Users` given, prompts once for a mode. Unless `-NoTeamSync`, force-merges `team-mcp.json` into each launching profile's `claude_desktop_config.json` and stages `team-context.md` + `team-memory.md` (concatenated) on the clipboard.
- **`launch.bat`**: Double-click launcher for Windows File Explorer.
- **`profiles.json`**: Configuration file mapping account profile names to display nicknames, user data storage paths, and last logged-in timestamps.
- **`team-mcp.json`**: Shared MCP server config, force-merged into every profile's `claude_desktop_config.json` on launch (shared entries win on name collision; a profile's own extra servers are never removed). Currently wires in `notebooklm-mcp` (see `mcp-servers/notebooklm-mcp/`) — add further entries here to roll them out to every profile at once.
- **`mcp-servers/notebooklm-mcp/run_server.py`**: `uvx` launcher for the NotebookLM MCP server, referenced by `team-mcp.json`. Falls back through common per-platform `uvx` install locations when it's missing from `PATH` (Claude Desktop launches with a restricted `PATH`). Auth is shared across all profiles via `%USERPROFILE%\.notebooklm-mcp-cli\` (every profile runs as the same Windows user) — run `nlm login` once, no per-profile setup needed.
- **`team-context.md`**: Static identity/context scaffold. Its full content is copied to the clipboard on every launch for pasting as a first message or into Custom Instructions. Edit it directly with what you actually want repeated into every profile — it ships as a plain-text placeholder, so if it still reads like a template when pasted, that's the signal it hasn't been filled in yet.
- **`team-memory.md`**: Growing, hand-appended memory log — same clipboard/Custom-Instructions delivery as `team-context.md`, concatenated with it. Distributed via `sync.ps1` like everything else, so an entry added from one profile reaches every other profile's clipboard on its next launch. Nothing is written to it automatically; it only grows when you add a line.
- **`sync.ps1`**: Automated Git repository synchronization tool.
- **`cooldown-reminder.ps1`**: Auto-invoked by `launch_user_n.ps1` after every non-`-WhatIf` login. Tracks each profile's `first_login_time`, anchors a 5-hour cooldown to it, and registers a local Windows toast alarm for when the cooldown expires.
- **`reset_profiles.ps1`**: Wipes all profile storage, logs, session state, and the `claude://` registry override, then resets `profiles.json` to `{}`. Prompts for a typed `RESET` confirmation unless `-WhatIf`.
- **`tests/launch_user_n.Tests.ps1`**: Pester specs for `launch_user_n.ps1`'s pure/mockable logic (path-traversal guard, profile table formatting, shared-MCP-server merge). Run via `Invoke-Pester -Path .\tests\launch_user_n.Tests.ps1`.

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
pwsh -File .\launch_user_n.ps1 -Mode Concurrent -Users tisha,shreejan
```

Or one at a time:

```powershell
pwsh -File .\launch_user_n.ps1 -Concurrent -Account tisha
pwsh -File .\launch_user_n.ps1 -Concurrent -Account shreejan
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
