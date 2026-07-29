# Claude Desktop Multi-Profile & Sync Utilities

PowerShell scripts to manage multiple isolated user profiles for the Claude Desktop application on Windows and automate Git repository synchronization with smart commit messaging.

## Features

- **Multi-Profile Management**: Launch distinct Claude Desktop sessions using dedicated data directories (`--user-data-dir`).
- **Dynamic Executable Resolution**: Automatically locates `Claude.exe` across MSIX/Windows Store App packages (`Get-AppxPackage *claude*`) and traditional local installation directories (`AppData\Local\Programs\Claude` and `WindowsApps`).
- **Portable Profile Config**: Supports environment variables like `%USERPROFILE%` in `profiles.json` and automatically creates missing profile storage directories on launch.
- **Smart Git Synchronization**: Automatically stages, commits, pulls (with `--rebase` & `--autostash`), and pushes repository changes.
- **Intelligent Commit Messaging**: Dynamically generates conventional commit messages (`feat`, `refactor`, `chore`) derived from staged git diffs, hunk context headers, and line churn statistics (`+ins/-del`).
- **PowerShell 7 (`pwsh`) Compatible**: Fully compatible with PowerShell 7 (`pwsh`) and Windows PowerShell 5.1.

## Files

- **`user_n.ps1`**: Profile launcher script. Resolves executable paths, creates profile directories, and launches `Claude.exe` with `--user-data-dir`.
- **`profiles.json`**: Configuration file mapping account profile names to email addresses and user data storage paths.
- **`sync.ps1`**: Automated Git repository synchronization tool.

## Usage

### Launching Claude Desktop Profiles

Launch a specific profile configured in `profiles.json` (defaults to `user1`):

```powershell
pwsh -File .\user_n.ps1 -Account user1
pwsh -File .\user_n.ps1 -Account work
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
