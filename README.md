# Claude Desktop Multi-Profile & Sync Utilities

PowerShell scripts to manage multiple isolated user profiles for the Claude Desktop application on Windows and automate Git repository synchronization with smart commit messaging.

## Features

- **Multi-Profile Management**: Launch distinct Claude Desktop sessions via automated profile session swapping into native AppData paths.
- **Native MSIX & OAuth Compatibility**: 100% compatible with Windows MSIX packages and browser OAuth deep links (`claude://`) without dual-window or authentication loop issues.
- **Dynamic Executable Resolution**: Automatically locates `Claude.exe` across MSIX/Windows Store App packages (`Get-AppxPackage *claude*`) and traditional local installation directories (`AppData\Local\Programs\Claude` and `WindowsApps`).
- **Automatic Session Backup & Persistence**: Automatically saves and syncs cookies, tokens, and local storage per profile on every switch.
- **Smart Git Synchronization**: Automatically stages, commits, pulls (with `--rebase` & `--autostash`), and pushes repository changes.
- **Auto-Sync on Launch & Reset**: `launch_user_n.ps1` and `reset_profiles.ps1` each auto-invoke `sync.ps1` (with a verbose, context-specific commit message) as their final step, skipped entirely under `-WhatIf`.
- **Intelligent Commit Messaging**: Dynamically generates conventional commit messages (`feat`, `refactor`, `chore`) derived from staged git diffs, hunk context headers, and line churn statistics (`+ins/-del`).
- **PowerShell 7 (`pwsh`) Compatible**: Fully compatible with PowerShell 7 (`pwsh`) and Windows PowerShell 5.1.

## Files

- **`launch_user_n.ps1`**: Profile launcher script. Resolves executable paths, swaps profile session data, launches Claude Desktop natively, and (unless `-NoTeamSync`) force-merges `team-mcp.json` into the launching profile's `claude_desktop_config.json` and stages `team-context.md` on the clipboard.
- **`launch.bat`**: Double-click launcher for Windows File Explorer.
- **`profiles.json`**: Configuration file mapping account profile names to display nicknames, user data storage paths, and last logged-in timestamps.
- **`team-mcp.json`**: Shared MCP server config, force-merged into every profile's `claude_desktop_config.json` on launch (shared entries win on name collision; a profile's own extra servers are never removed). Ships as an empty `{"mcpServers": {}}` stub — add entries here to roll them out to every profile at once.
- **`team-context.md`** _(not shipped — create it yourself)_: If present, its full content is copied to the clipboard on every launch for pasting as a first message or into Custom Instructions. No stub is checked in, since a placeholder file here would get pasted into Custom Instructions verbatim.
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
