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

<!-- Nothing logged yet. -->
