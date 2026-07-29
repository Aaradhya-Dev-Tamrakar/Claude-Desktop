# Claude Desktop Multi-Profile & Sync Utilities

PowerShell scripts to manage multiple isolated user profiles for the Claude Desktop application on Windows and automate Git repository synchronization with smart commit messaging.

## Features

- **Multi-Profile Management**: Launch distinct Claude Desktop sessions via automated profile session swapping into native AppData paths.
- **Native MSIX & OAuth Compatibility**: 100% compatible with Windows MSIX packages and browser OAuth deep links (`claude://`) without dual-window or authentication loop issues.
- **Dynamic Executable Resolution**: Automatically locates `Claude.exe` across MSIX/Windows Store App packages (`Get-AppxPackage *claude*`) and traditional local installation directories (`AppData\Local\Programs\Claude` and `WindowsApps`).
- **Automatic Session Backup & Persistence**: Automatically saves and syncs cookies, tokens, and local storage per profile on every switch.
- **Smart Git Synchronization**: Automatically stages, commits, pulls (with `--rebase` & `--autostash`), and pushes repository changes.
- **Intelligent Commit Messaging**: Dynamically generates conventional commit messages (`feat`, `refactor`, `chore`) derived from staged git diffs, hunk context headers, and line churn statistics (`+ins/-del`).
- **PowerShell 7 (`pwsh`) Compatible**: Fully compatible with PowerShell 7 (`pwsh`) and Windows PowerShell 5.1.

## Files

- **`launch_user_n.ps1`**: Profile launcher script. Resolves executable paths, creates profile directories, and launches `Claude.exe` with `--user-data-dir`.
- **`profiles.json`**: Configuration file mapping account profile names to email addresses and user data storage paths.
- **`sync.ps1`**: Automated Git repository synchronization tool.

## Usage

### Launching Claude Desktop Profiles

Launch a specific profile configured in `profiles.json` (defaults to `user1`):

```powershell
pwsh -File .\launch_user_n.ps1 -Account user1
pwsh -File .\launch_user_n.ps1 -Account work
```

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
