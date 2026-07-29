# git-workflow

- **Minor / Routine Changes**: Use `.\sync.ps1` without arguments. It auto-generates a conventional commit message (`feat`/`refactor`/`chore` + hunk context + churn stats) from staged diff.
- **Major Changes** (new profile schema field, launcher exe-resolution logic, sync pipeline order): Execute `.\sync.ps1 -m "type(scope): detailed commit summary"` with a descriptive message to ensure rich historical context is preserved.
