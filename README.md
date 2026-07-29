# Claude Desktop Multi-Profile & Sync Utilities

PowerShell scripts to manage multiple isolated user profiles for the Claude Desktop application on Windows and automate Git repository synchronization with smart commit messaging.

## Features

- **Multi-Profile Management**: Launch distinct Claude Desktop sessions using dedicated data directories.
- **Smart Git Synchronization**: Automatically stage, commit, pull (with rebase/autostash), and push workspace changes.
- **Intelligent Commit Messages**: Dynamically generates conventional commit messages (`feat`, `refactor`, `chore`) based on git diffs, hunk context, and line churn.

## Files

- **`user_n.ps1`**: Profile launcher script. Reads profile definitions and launches `Claude.exe` with `--user-data-dir`.
- **`profiles.json`**: Configuration mapping profile names to email addresses and user data paths.
- **`sync.ps1`**: Git repository synchronization tool.

## Usage

### Launching Claude Desktop Profiles

Launch a specific profile configured in `profiles.json` (defaults to `user1`):

```powershell
.\user_n.ps1 -Account user1
.\user_n.ps1 -Account work
```

### Syncing Git Repository

Run full sync (pull rebase, auto-commit changes, and push):

```powershell
.\sync.ps1
```

Supply a custom commit message:

```powershell
.\sync.ps1 -Message "feat: customize profile settings"
```

Perform pull-only:

```powershell
.\sync.ps1 -PullOnly
```