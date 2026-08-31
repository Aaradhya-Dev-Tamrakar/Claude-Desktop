param (
    [string]$Account,
    # Non-interactive mode selection. "Isolated" = single-profile swap (the
    # historical default behavior); "Concurrent" = one or more profiles as
    # independent side-by-side windows. Equivalent to passing -Concurrent,
    # but explicit and pairable with -Users for scripted multi-launch.
    [ValidateSet("Isolated", "Concurrent")]
    [string]$Mode,
    # One or more profile names for Concurrent mode, e.g.
    # -Users tisha,shreejan or -Users @("tisha","shreejan"). Isolated mode
    # is inherently single-profile (session-swap semantics don't compose
    # across multiple windows) — use -Account for that instead.
    [string[]]$Users,
    [switch]$WhatIf,
    [switch]$Concurrent,
    [switch]$NoCooldownAlarm,
    [switch]$GCalReminder,
    # Skip syncing team-mcp.json into this launch. Use for a one-off launch
    # you don't want the shared MCP config force-merged into.
    [switch]$NoTeamSync,
    # Port to enable Chrome DevTools Protocol (CDP) for headless/unattended automation.
    # When > 0, passes --remote-debugging-port=<Port> to Claude.exe.
    [int]$RemoteDebuggingPort = 0,
    # Dot-source-and-return-early hook for Pester: stops after function
    # definitions, before any interactive prompt or side-effecting logic.
    # Never set by real launches (launch.bat / manual pwsh invocation).
    [switch]$TestHook,
    # Bypass interactive TUI mode and use classic terminal prompts
    [switch]$NoTUI
)

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch { }

if ($GCalReminder) {
    Write-Warning "GCalReminder: Google Calendar integration is currently paused. This switch has no effect until re-enabled in cooldown-reminder.ps1."
}

# -Mode is sugar over -Concurrent (kept as the single source of truth
# downstream, since it's already threaded through every launch-time check).
# Conflicting explicit combinations are rejected rather than silently
# picking one, so a scripted call with a typo fails loudly instead of
# launching the wrong mode.
if ($Mode -eq "Concurrent") { $Concurrent = $true }
elseif ($Mode -eq "Isolated" -and $Concurrent) {
    Write-Host "Conflicting flags: -Mode Isolated with -Concurrent." -ForegroundColor Red
    Read-Host "Press Enter to close this window"
    exit 1
}

if ($Users -and $Users.Count -gt 0) {
    $Users = @($Users | ForEach-Object { $_ -split '[, ]+' } | Where-Object { $_ })
    if ($Mode -eq "Isolated") {
        Write-Host "-Users requires Concurrent mode (Isolated is single-profile only)." -ForegroundColor Red
        Read-Host "Press Enter to close this window"
        exit 1
    }
    if ($Account) {
        Write-Host "-Users and -Account are mutually exclusive." -ForegroundColor Red
        Read-Host "Press Enter to close this window"
        exit 1
    }
    $Concurrent = $true
}

$ConfigFile = Join-Path $PSScriptRoot "profiles.json"

if (-not (Test-Path $ConfigFile)) {
    Write-Host "profiles.json file is missing!" -ForegroundColor Red
    Read-Host "Press Enter to close this window"
    exit 1
}

$Profiles = Get-Content $ConfigFile | ConvertFrom-Json
$AccountKeys = @($Profiles.psobject.properties.Name)

function Test-ProfilePathWithinBase {
    # Pure predicate: does $RawPath resolve inside the approved
    # .claude-profiles base directory? No side effects (no Write-Host,
    # Read-Host, or exit), so this is the unit under test for the
    # path-traversal guard; Get-ValidatedProfilePath below is just this
    # plus the exit-on-reject wrapper.
    param(
        [Parameter(Mandatory = $true)][string]$RawPath
    )

    $BaseDir = [System.Environment]::ExpandEnvironmentVariables("%USERPROFILE%\.claude-profiles")
    $BaseFull = [System.IO.Path]::GetFullPath($BaseDir).TrimEnd('\') + '\'

    $Expanded = [System.Environment]::ExpandEnvironmentVariables($RawPath)
    $ExpandedFull = [System.IO.Path]::GetFullPath($Expanded)

    return [PSCustomObject]@{
        IsValid      = $ExpandedFull.StartsWith($BaseFull, [System.StringComparison]::OrdinalIgnoreCase)
        BaseFull     = $BaseFull
        ExpandedFull = $ExpandedFull
    }
}

function Get-ValidatedProfilePath {
    param(
        [Parameter(Mandatory = $true)][string]$RawPath,
        [Parameter(Mandatory = $true)][string]$ProfileName
    )

    $Check = Test-ProfilePathWithinBase -RawPath $RawPath

    if (-not $Check.IsValid) {
        Write-Host "[!] Profile '$ProfileName' path resolves outside the approved base directory." -ForegroundColor Red
        Write-Host "    Base    : $($Check.BaseFull)" -ForegroundColor Gray
        Write-Host "    Resolved: $($Check.ExpandedFull)" -ForegroundColor Gray
        Write-Host "    Refusing to use this path. Fix 'path' for '$ProfileName' in profiles.json." -ForegroundColor Red
        Read-Host "Press Enter to close this window"
        exit 1
    }

    return $Check.ExpandedFull
}

function Merge-McpServers {
    # Pure merge: union of $Shared.mcpServers into $Profile.mcpServers, with
    # $Shared entries taking precedence on key collision. Everything else in
    # $Profile (any keys not named "mcpServers", and any profile-only server
    # entries not present in $Shared) passes through untouched — this is a
    # deliberate union-with-precedence, not a replace, so a profile's own
    # extra/private MCP connectors are never silently deleted by a team sync.
    # No file I/O, no side effects: takes two already-parsed PSCustomObjects
    # (as ConvertFrom-Json would produce), returns a new merged PSCustomObject.
    param(
        [Parameter(Mandatory = $true)]$ProfileConfig,
        [Parameter(Mandatory = $true)]$SharedConfig
    )

    # Clone so the caller's original $ProfileConfig is never mutated —
    # ConvertTo-Json/ConvertFrom-Json round-trip is the simplest deep clone
    # available without extra dependencies.
    $Merged = $ProfileConfig | ConvertTo-Json -Depth 10 | ConvertFrom-Json

    if (-not ($Merged.PSObject.Properties.Name -contains "mcpServers")) {
        $Merged | Add-Member -NotePropertyName "mcpServers" -NotePropertyValue ([PSCustomObject]@{}) -Force
    }

    if ($SharedConfig -and ($SharedConfig.PSObject.Properties.Name -contains "mcpServers")) {
        foreach ($serverName in $SharedConfig.mcpServers.PSObject.Properties.Name) {
            $Merged.mcpServers | Add-Member -NotePropertyName $serverName -NotePropertyValue $SharedConfig.mcpServers.$serverName -Force
        }
    }

    return $Merged
}

function Expand-TeamMcpPlaceholders {
    # Rewrites the literal "{{REPO_ROOT}}" token in every mcpServers entry's
    # command/args/env string values to $RepoRoot (this machine's actual
    # launch_user_n.ps1 location, i.e. $PSScriptRoot). Lets team-mcp.json
    # reference paths inside the repo without hardcoding one contributor's
    # absolute clone path (e.g. "D:\Aaradhya-Dev-Tamrakar\Claude-Desktop\..."
    # — breaks for every profile whose clone isn't at that exact drive/path).
    # Runs on the already-parsed $SharedConfig, before Merge-McpServers, so
    # claude_desktop_config.json never sees the placeholder itself.
    # Deep-clones first (same ConvertTo-Json/ConvertFrom-Json round-trip as
    # Merge-McpServers) so the caller's original $SharedConfig is untouched —
    # matches Merge-McpServers' purity contract rather than mutating in place.
    param(
        [Parameter(Mandatory = $true)]$SharedConfig,
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $Expanded = $SharedConfig | ConvertTo-Json -Depth 10 | ConvertFrom-Json

    if (-not ($Expanded.PSObject.Properties.Name -contains "mcpServers")) {
        return $Expanded
    }

    $Placeholder = "{{REPO_ROOT}}"

    foreach ($serverName in $Expanded.mcpServers.PSObject.Properties.Name) {
        $server = $Expanded.mcpServers.$serverName

        if ($server.PSObject.Properties.Name -contains "command" -and $server.command -is [string]) {
            $server.command = $server.command.Replace($Placeholder, $RepoRoot)
        }

        if ($server.PSObject.Properties.Name -contains "args" -and $server.args) {
            for ($i = 0; $i -lt $server.args.Count; $i++) {
                if ($server.args[$i] -is [string]) {
                    $server.args[$i] = $server.args[$i].Replace($Placeholder, $RepoRoot)
                }
            }
        }

        if ($server.PSObject.Properties.Name -contains "env" -and $server.env) {
            foreach ($envKey in $server.env.PSObject.Properties.Name) {
                if ($server.env.$envKey -is [string]) {
                    $server.env.$envKey = $server.env.$envKey.Replace($Placeholder, $RepoRoot)
                }
            }
        }
    }

    return $Expanded
}

function Sync-TeamMcpConfig {
    # I/O wrapper around Merge-McpServers: reads team-mcp.json from the repo
    # and the profile's own claude_desktop_config.json, merges, writes back.
    # Best-effort — matches the rest of this script's philosophy (see
    # cooldown-reminder.ps1's doc comment): a broken or missing team-mcp.json,
    # or a malformed existing config file, must never block the actual launch.
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$TargetConfigDir,
        [switch]$WhatIf
    )

    $SharedConfigPath = Join-Path $RepoRoot "team-mcp.json"
    if (-not (Test-Path $SharedConfigPath)) {
        return  # No team-mcp.json checked in yet — nothing to sync, silently skip.
    }

    try {
        $SharedConfig = Get-Content $SharedConfigPath -Raw | ConvertFrom-Json
    }
    catch {
        Write-Warning "team-mcp.json is not valid JSON ($_). Skipping team MCP sync this launch."
        return
    }

    try {
        $SharedConfig = Expand-TeamMcpPlaceholders -SharedConfig $SharedConfig -RepoRoot $RepoRoot
    }
    catch {
        Write-Warning "Failed to expand {{REPO_ROOT}} placeholders in team-mcp.json ($_). Team MCP sync skipped this launch."
        return
    }

    $ProfileConfigPath = Join-Path $TargetConfigDir "claude_desktop_config.json"
    $ProfileConfig = [PSCustomObject]@{}
    if (Test-Path $ProfileConfigPath) {
        try {
            $ProfileConfig = Get-Content $ProfileConfigPath -Raw | ConvertFrom-Json
        }
        catch {
            Write-Warning "Existing claude_desktop_config.json is not valid JSON ($_). Treating as empty for this merge rather than overwriting blind."
            $ProfileConfig = [PSCustomObject]@{}
        }
    }

    try {
        $Merged = Merge-McpServers -ProfileConfig $ProfileConfig -SharedConfig $SharedConfig
    }
    catch {
        Write-Warning "Failed to merge shared MCP servers ($_). Team MCP sync skipped this launch."
        return
    }

    if ($WhatIf) {
        $sharedCount = ($SharedConfig.mcpServers.PSObject.Properties | Measure-Object).Count
        Write-Host "[WhatIf] Would merge $sharedCount shared MCP server(s) from team-mcp.json into '$ProfileConfigPath'." -ForegroundColor DarkCyan
    }
    else {
        try {
            if (-not (Test-Path $TargetConfigDir)) {
                New-Item -ItemType Directory -Force -Path $TargetConfigDir | Out-Null
            }
            $Merged | ConvertTo-Json -Depth 10 | Set-Content $ProfileConfigPath -Encoding UTF8
            Write-Host "[+] Synced shared MCP config into '$ProfileConfigPath'." -ForegroundColor Gray
        }
        catch {
            Write-Warning "Failed to write merged claude_desktop_config.json ($_). Team MCP sync skipped this launch."
        }
    }
}

function Add-NewProfile {
    param(
        [string]$SuggestedName = ""
    )

    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host " Add New Claude Desktop Profile" -ForegroundColor Green
    Write-Host "----------------------------------------" -ForegroundColor Cyan

    $Name = $SuggestedName
    if (-not $Name) {
        $NextUserNum = 1
        while ($Profiles.psobject.properties.Name -contains "user$NextUserNum") {
            $NextUserNum++
        }
        $DefaultName = "user$NextUserNum"
        $Name = Read-Host "Enter profile name (e.g. personal, client) [Enter for '$DefaultName']"
        if ([string]::IsNullOrWhiteSpace($Name)) {
            $Name = $DefaultName
        }
    }

    if ([string]::IsNullOrWhiteSpace($Name)) {
        Write-Host "Profile name cannot be empty." -ForegroundColor Red
        Read-Host "Press Enter to close this window"
        exit 1
    }

    $Name = $Name.Trim().ToLower() -replace '[^a-z0-9_-]', ''

    if ($Profiles.psobject.properties.Name -contains $Name) {
        Write-Host "Profile '$Name' already exists!" -ForegroundColor Yellow
        return $Name
    }

    $Nickname = Read-Host "Enter a nickname for '$Name' (e.g. work, personal, ieee)"
    if ([string]::IsNullOrWhiteSpace($Nickname)) {
        $Nickname = $Name
    }

    $Path = "%USERPROFILE%\.claude-profiles\$Name"

    $Profiles | Add-Member -NotePropertyName $Name -NotePropertyValue @{
        nickname        = $Nickname
        path            = $Path
        last_login_date = $null
        last_login_time = $null
    } -Force

    $Profiles | ConvertTo-Json -Depth 5 | Set-Content $ConfigFile -Encoding UTF8
    Write-Host "[+] Saved new profile '$Name' to profiles.json!" -ForegroundColor Green

    return $Name
}

function Get-EnrichedProfileRows {
    param($Profiles, $AccountKeys)

    if (-not $AccountKeys -or $AccountKeys.Count -eq 0) {
        return @()
    }

    $TodayStr = (Get-Date).ToString("yyyy-MM-dd")
    $ProfilesBaseDir = [System.Environment]::ExpandEnvironmentVariables("%USERPROFILE%\.claude-profiles")
    $StateFile = Join-Path $ProfilesBaseDir ".active_profile"
    $ActiveAccount = $null
    if (Test-Path $StateFile) {
        try {
            $ActiveAccount = (Get-Content $StateFile -Raw -ErrorAction SilentlyContinue)
            if ($ActiveAccount) { $ActiveAccount = $ActiveAccount.Trim() }
        } catch { }
    }

    $RunningProcesses = @()
    try {
        $RunningProcesses = @(Get-CimInstance Win32_Process -Filter "Name = 'claude.exe'" -ErrorAction SilentlyContinue)
    } catch { }

    $rows = for ($i = 0; $i -lt $AccountKeys.Count; $i++) {
        $key = $AccountKeys[$i]
        $p = $Profiles.$key
        $lastLoginDate = if ($p -and $p.last_login_date) { $p.last_login_date } else { "Never" }
        $lastLoginTime = if ($p -and $p.last_login_time) { $p.last_login_time } else { "-" }
        $role = if ($p -and $p.role) { [string]$p.role } else { "-" }
        $nickname = if ($p -and $p.nickname) { [string]$p.nickname } else { $key }
        $rawPath = if ($p -and $p.path) { [string]$p.path } else { "%USERPROFILE%\.claude-profiles\$key" }
        $expandedPath = [System.Environment]::ExpandEnvironmentVariables($rawPath)

        $isRunning = $false
        foreach ($proc in $RunningProcesses) {
            if ($proc.CommandLine -and $proc.CommandLine.IndexOf($expandedPath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                $isRunning = $true
                break
            }
        }
        $isActive = ($key -eq $ActiveAccount)

        [PSCustomObject]@{
            Index     = ($i + 1)
            Profile   = $key
            Nickname  = $nickname
            Role      = $role
            LastTime  = $lastLoginTime
            LastDate  = $lastLoginDate
            IsToday   = ($lastLoginDate -eq $TodayStr)
            IsActive  = $isActive
            IsRunning = $isRunning
            Path      = $expandedPath
        }
    }

    # Rank today's logins by Last Time descending (most recent = 1).
    $todayRanked = $rows | Where-Object { $_.IsToday } | Sort-Object -Property LastTime -Descending
    $rankMap = @{}
    for ($r = 0; $r -lt $todayRanked.Count; $r++) {
        $rankMap[$todayRanked[$r].Profile] = ($r + 1)
    }
    foreach ($row in $rows) {
        $rankVal = if ($rankMap.ContainsKey($row.Profile)) { [string]$rankMap[$row.Profile] } else { "-" }
        $row | Add-Member -NotePropertyName "TodayRank" -NotePropertyValue $rankVal -Force
    }

    return $rows
}

function Show-ProfileTable {
    param($Profiles, $AccountKeys)

    if ($AccountKeys.Count -eq 0) {
        Write-Host "(No profiles yet. Press N to add your first profile.)" -ForegroundColor DarkGray
        return
    }

    $rows = Get-EnrichedProfileRows -Profiles $Profiles -AccountKeys $AccountKeys

    $profW = [Math]::Max(5, ([string]$rows.Count).Length)
    $nickW = [Math]::Max(8, ($rows.Nickname | Measure-Object -Property Length -Maximum).Maximum)
    $timeW = [Math]::Max(10, ($rows.LastTime | Measure-Object -Property Length -Maximum).Maximum)
    $dateW = [Math]::Max(10, ($rows.LastDate | Measure-Object -Property Length -Maximum).Maximum)
    $rankW = [Math]::Max(10, ($rows.TodayRank | Measure-Object -Property Length -Maximum).Maximum)
    $widths = @($profW, $nickW, $timeW, $dateW, $rankW)

    function New-Border($L, $C, $R) {
        $L + (($widths | ForEach-Object { "-" * ($_ + 2) }) -join $C) + $R
    }
    function New-Row([string[]]$Cells) {
        $padded = for ($c = 0; $c -lt $Cells.Count; $c++) {
            $cell = if ($null -ne $Cells[$c]) { [string]$Cells[$c] } else { "" }
            " " + $cell.PadRight($widths[$c]) + " "
        }
        "|" + ($padded -join "|") + "|"
    }

    $innerWidth = (New-Border "+" "+" "+").Length - 2

    Write-Host (New-Border "+" "+" "+") -ForegroundColor Cyan
    Write-Host (New-Row @("User#", "Nickname", "Last Time", "Last Date", "Today Rank")) -ForegroundColor Cyan
    Write-Host (New-Border "+" "+" "+") -ForegroundColor Cyan
    $displayNum = 0
    foreach ($r in $rows) {
        $displayNum++
        Write-Host (New-Row @([string]$displayNum, $r.Nickname, $r.LastTime, $r.LastDate, $r.TodayRank)) -ForegroundColor Yellow
    }
    Write-Host (New-Border "+" "+" "+") -ForegroundColor Cyan
    Write-Host ("| " + "[N] Add New Profile (+)".PadRight($innerWidth - 2) + " |") -ForegroundColor Magenta
    Write-Host (New-Border "+" "+" "+") -ForegroundColor Cyan
}

function Select-ProfileInteractive {
    param(
        [string]$InitialMode = "Isolated"
    )

    $isConcurrent = ($InitialMode -eq "Concurrent")
    $selectedIndex = 0
    $filterText = ""
    $selectedSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

    # Save initial cursor visibility
    $origCursorVisible = $true
    try { $origCursorVisible = [Console]::CursorVisible } catch { }

    try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
    try { [Console]::CursorVisible = $false } catch { }

    # Load enriched profiles once in memory (no repeated WMI queries in loop)
    $allRows = Get-EnrichedProfileRows -Profiles $script:Profiles -AccountKeys $script:AccountKeys
    if ($allRows.Count -eq 0) {
        Write-Host "No profiles found in profiles.json." -ForegroundColor Yellow
        $new = Add-NewProfile
        $script:Profiles = Get-Content $script:ConfigFile | ConvertFrom-Json
        $script:AccountKeys = @($script:Profiles.psobject.properties.Name)
        $allRows = Get-EnrichedProfileRows -Profiles $script:Profiles -AccountKeys $script:AccountKeys
    }

    # Initial console clear
    try { [Console]::Clear() } catch { }

    $cols = @(6, 13, 14, 10, 10, 10, 11)
    $tblTop = "╭" + (($cols | ForEach-Object { "─" * ($_ + 2) }) -join "┬") + "╮"
    $tblMid = "├" + (($cols | ForEach-Object { "─" * ($_ + 2) }) -join "┼") + "┤"
    $tblBot = "╰" + (($cols | ForEach-Object { "─" * ($_ + 2) }) -join "┴") + "╯"

    $bannerTop = "╭" + ("─" * 94) + "╮"
    $bannerMid = "│" + "                    🚀  CLAUDE DESKTOP PROFILE LAUNCHER".PadRight(94) + "│"
    $bannerBot = "╰" + ("─" * 94) + "╯"

    $lastRenderLineCount = 0

    try {
        while ($true) {
            # Filter rows by query in-memory
            $filteredRows = if ([string]::IsNullOrWhiteSpace($filterText)) {
                $allRows
            } else {
                $q = $filterText.Trim().ToLower()
                @($allRows | Where-Object {
                    ([string]$_.Index) -eq $q -or
                    $_.Nickname.ToLower().Contains($q) -or
                    $_.Role.ToLower().Contains($q) -or
                    $_.Profile.ToLower().Contains($q)
                })
            }

            if ($selectedIndex -ge $filteredRows.Count) {
                $selectedIndex = [Math]::Max(0, $filteredRows.Count - 1)
            }

            # Adaptive viewport calculation
            $windowHeight = 25
            try { $windowHeight = [Console]::WindowHeight } catch { }
            $maxVisible = [Math]::Max(5, [Math]::Min(14, $windowHeight - 12))
            
            $viewportStart = 0
            if ($filteredRows.Count -gt $maxVisible) {
                $viewportStart = [Math]::Max(0, [Math]::Min($selectedIndex - [Math]::Floor($maxVisible / 2), $filteredRows.Count - $maxVisible))
            }
            $visibleRows = if ($filteredRows.Count -eq 0) {
                @()
            } elseif ($filteredRows.Count -le $maxVisible) {
                $filteredRows
            } else {
                @($filteredRows[$viewportStart .. ($viewportStart + $maxVisible - 1)])
            }

            # Flicker-free render via cursor repositioning
            try { [Console]::SetCursorPosition(0, 0) } catch { [Console]::Clear() }

            $currentLines = 0

            Write-Host $bannerTop -ForegroundColor Cyan
            Write-Host $bannerMid -ForegroundColor Green
            Write-Host $bannerBot -ForegroundColor Cyan
            $currentLines += 3
            
            $modeLabel = if ($isConcurrent) { "Concurrent (Side-by-Side)" } else { "Isolated (Session Swap)" }
            $modeColor = if ($isConcurrent) { "Magenta" } else { "Cyan" }
            $modeLine = " Mode: [ $modeLabel ]".PadRight(40) + "◄ Press [Tab] or [M] to toggle"
            Write-Host $modeLine.PadRight(96) -ForegroundColor $modeColor
            $currentLines++
            
            if ($isConcurrent) {
                $selCount = $selectedSet.Count
                $multiLine = " Multi-Launch: $selCount profile(s) selected".PadRight(40) + "([Space] to toggle, [A] select/clear all)"
                Write-Host $multiLine.PadRight(96) -ForegroundColor Yellow
            } else {
                Write-Host (" " * 96)
            }
            $currentLines++

            if (-not [string]::IsNullOrEmpty($filterText)) {
                $filterLine = " 🔍 Filter: $filterText (Press [Esc] to clear, matches: $($filteredRows.Count))"
                Write-Host $filterLine.PadRight(96) -ForegroundColor Yellow
            } else {
                $filterLine = " 🔍 Filter: [Type to search by name/role/number...]"
                Write-Host $filterLine.PadRight(96) -ForegroundColor DarkGray
            }
            $currentLines++

            Write-Host (" " * 96)
            $currentLines++

            # Table Header
            $headers = @("Sel   ", "Nickname     ", "Role          ", "Last Time ", "Last Date ", "Today Rank", "Status     ")
            $hdrRow = "│" + (($headers | ForEach-Object { " " + $_ + " " }) -join "│") + "│"

            Write-Host $tblTop -ForegroundColor Cyan
            Write-Host $hdrRow -ForegroundColor Cyan
            Write-Host $tblMid -ForegroundColor Cyan
            $currentLines += 3

            if ($filteredRows.Count -eq 0) {
                $emptyMsg = "  (No matching profiles found for '$filterText')".PadRight(94)
                Write-Host "│$emptyMsg│" -ForegroundColor Yellow
                $currentLines++
            } else {
                for ($v = 0; $v -lt $visibleRows.Count; $v++) {
                    $row = $visibleRows[$v]
                    $actualIdx = $viewportStart + $v
                    $isHighlighted = ($actualIdx -eq $selectedIndex)
                    $isChecked = $selectedSet.Contains($row.Profile)

                    $cursorMark = if ($isHighlighted) { "❯" } else { " " }
                    $checkMark = if ($isChecked) { "x" } else { " " }
                    $selCell = "$cursorMark[$checkMark]" + ([string]$row.Index).PadLeft(2)
                    
                    $nickCell = $row.Nickname.PadRight(13)
                    if ($nickCell.Length -gt 13) { $nickCell = $nickCell.Substring(0, 10) + "..." }
                    
                    $roleCell = $row.Role.PadRight(14)
                    if ($roleCell.Length -gt 14) { $roleCell = $roleCell.Substring(0, 11) + "..." }
                    
                    $timeCell = $row.LastTime.PadRight(10)
                    $dateCell = $row.LastDate.PadRight(10)
                    
                    $rankStr = if ($row.TodayRank -ne "-") { "#$($row.TodayRank)" } else { "-" }
                    $rankCell = $rankStr.PadRight(10)

                    $statusStr = if ($row.IsActive -and $row.IsRunning) { "🟢 Active" } elseif ($row.IsRunning) { "⚡ Live" } elseif ($row.IsActive) { "● Active" } else { "" }
                    $statusCell = $statusStr.PadRight(11)

                    $cells = @($selCell, $nickCell, $roleCell, $timeCell, $dateCell, $rankCell, $statusCell)
                    $line = "│" + (($cells | ForEach-Object { " " + $_ + " " }) -join "│") + "│"

                    if ($isHighlighted) {
                        Write-Host $line -ForegroundColor Black -BackgroundColor Cyan
                    } elseif ($isChecked) {
                        Write-Host $line -ForegroundColor Green -BackgroundColor DarkGray
                    } elseif ($row.IsToday) {
                        Write-Host $line -ForegroundColor Yellow
                    } else {
                        Write-Host $line -ForegroundColor Gray
                    }
                    $currentLines++
                }
            }

            Write-Host $tblBot -ForegroundColor Cyan
            $currentLines++

            if ($filteredRows.Count -gt $maxVisible) {
                $scrollInfo = " (Showing items $($viewportStart + 1)-$($viewportStart + $visibleRows.Count) of $($filteredRows.Count) — use ↑/↓ to scroll)"
                Write-Host $scrollInfo.PadRight(96) -ForegroundColor DarkGray
            } else {
                Write-Host (" " * 96)
            }
            $currentLines++

            $footerLine = " [↑/↓] Move │ [Space] Select │ [Tab] Mode │ [Enter] Launch │ [/] Search │ [N] New │ [Q] Exit"
            Write-Host $footerLine.PadRight(96) -ForegroundColor DarkCyan
            $currentLines++

            # Clear trailing lines if viewport shrank
            if ($lastRenderLineCount -gt $currentLines) {
                for ($cl = $currentLines; $cl -lt $lastRenderLineCount; $cl++) {
                    Write-Host (" " * 96)
                }
            }
            $lastRenderLineCount = $currentLines

            # Fast responsive input handling with key drain for held keys
            $keyInfo = [Console]::ReadKey($true)
            $key = $keyInfo.Key

            if ($key -eq [ConsoleKey]::DownArrow) {
                $delta = 1
                while ([Console]::KeyAvailable) {
                    $next = [Console]::ReadKey($true)
                    if ($next.Key -eq [ConsoleKey]::DownArrow) {
                        $delta++
                    } else {
                        $keyInfo = $next
                        $key = $next.Key
                        break
                    }
                }
                if ($filteredRows.Count -gt 0) {
                    $selectedIndex = ($selectedIndex + $delta) % $filteredRows.Count
                }
                continue
            }
            elseif ($key -eq [ConsoleKey]::UpArrow) {
                $delta = 1
                while ([Console]::KeyAvailable) {
                    $next = [Console]::ReadKey($true)
                    if ($next.Key -eq [ConsoleKey]::UpArrow) {
                        $delta++
                    } else {
                        $keyInfo = $next
                        $key = $next.Key
                        break
                    }
                }
                if ($filteredRows.Count -gt 0) {
                    $selectedIndex = ($selectedIndex - $delta) % $filteredRows.Count
                    if ($selectedIndex -lt 0) { $selectedIndex += $filteredRows.Count }
                }
                continue
            }

            switch ($key) {
                ([ConsoleKey]::PageUp) {
                    $selectedIndex = [Math]::Max(0, $selectedIndex - $maxVisible)
                }
                ([ConsoleKey]::PageDown) {
                    $selectedIndex = [Math]::Min([Math]::Max(0, $filteredRows.Count - 1), $selectedIndex + $maxVisible)
                }
                ([ConsoleKey]::Home) {
                    $selectedIndex = 0
                }
                ([ConsoleKey]::End) {
                    $selectedIndex = [Math]::Max(0, $filteredRows.Count - 1)
                }
                ([ConsoleKey]::Tab) {
                    $isConcurrent = -not $isConcurrent
                }
                ([ConsoleKey]::Spacebar) {
                    if ($filteredRows.Count -gt 0) {
                        $targetProfile = $filteredRows[$selectedIndex].Profile
                        if ($selectedSet.Contains($targetProfile)) {
                            $selectedSet.Remove($targetProfile) | Out-Null
                        } else {
                            $selectedSet.Add($targetProfile) | Out-Null
                            if ($selectedSet.Count -gt 1) {
                                $isConcurrent = $true
                            }
                        }
                    }
                }
                ([ConsoleKey]::Enter) {
                    if ($filteredRows.Count -eq 0) {
                        continue
                    }
                    if ($isConcurrent -and $selectedSet.Count -gt 0) {
                        try { [Console]::Clear() } catch { }
                        return [PSCustomObject]@{
                            Mode      = "Concurrent"
                            Accounts  = @($selectedSet)
                            Cancelled = $false
                        }
                    } else {
                        $chosen = $filteredRows[$selectedIndex].Profile
                        try { [Console]::Clear() } catch { }
                        return [PSCustomObject]@{
                            Mode      = if ($isConcurrent) { "Concurrent" } else { "Isolated" }
                            Accounts  = @($chosen)
                            Cancelled = $false
                        }
                    }
                }
                ([ConsoleKey]::Escape) {
                    if ($filterText.Length -gt 0) {
                        $filterText = ""
                        $selectedIndex = 0
                    } else {
                        try { [Console]::Clear() } catch { }
                        return [PSCustomObject]@{ Cancelled = $true }
                    }
                }
                ([ConsoleKey]::Backspace) {
                    if ($filterText.Length -gt 0) {
                        $filterText = $filterText.Substring(0, $filterText.Length - 1)
                        $selectedIndex = 0
                    }
                }
                default {
                    $c = $keyInfo.KeyChar
                    if ($c -eq 'q' -or $c -eq 'Q') {
                        if ($filterText.Length -eq 0) {
                            try { [Console]::Clear() } catch { }
                            return [PSCustomObject]@{ Cancelled = $true }
                        } else {
                            $filterText += $c
                            $selectedIndex = 0
                        }
                    }
                    elseif ($c -eq 'm' -or $c -eq 'M') {
                        if ($filterText.Length -eq 0) {
                            $isConcurrent = -not $isConcurrent
                        } else {
                            $filterText += $c
                            $selectedIndex = 0
                        }
                    }
                    elseif ($c -eq 'n' -or $c -eq 'N' -or $c -eq '+') {
                        if ($filterText.Length -eq 0) {
                            try { [Console]::Clear() } catch { }
                            try { [Console]::CursorVisible = $true } catch { }
                            $newAccount = Add-NewProfile
                            try { [Console]::CursorVisible = $false } catch { }
                            $script:Profiles = Get-Content $script:ConfigFile | ConvertFrom-Json
                            $script:AccountKeys = @($script:Profiles.psobject.properties.Name)
                            $filterText = ""
                            $allRows = Get-EnrichedProfileRows -Profiles $script:Profiles -AccountKeys $script:AccountKeys
                            $selectedIndex = [Math]::Max(0, $allRows.Count - 1)
                            try { [Console]::Clear() } catch { }
                        } else {
                            $filterText += $c
                            $selectedIndex = 0
                        }
                    }
                    elseif ($c -eq 'a' -or $c -eq 'A') {
                        if ($filterText.Length -eq 0) {
                            $isConcurrent = $true
                            if ($selectedSet.Count -eq $filteredRows.Count) {
                                $selectedSet.Clear()
                            } else {
                                foreach ($r in $filteredRows) {
                                    $selectedSet.Add($r.Profile) | Out-Null
                                }
                            }
                        } else {
                            $filterText += $c
                            $selectedIndex = 0
                        }
                    }
                    elseif ($c -eq '/' -or [char]::IsLetterOrDigit($c) -or $c -eq '-' -or $c -eq '_' -or $c -eq '.') {
                        if ($c -ne '/') {
                            $filterText += $c
                        }
                        $selectedIndex = 0
                    }
                }
            }
        }
    }
    finally {
        try { [Console]::CursorVisible = $origCursorVisible } catch { }
    }
}

function Ensure-LocalOrchestratorServer {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [switch]$WhatIf
    )

    $HealthUrl = "http://127.0.0.1:8000/health"
    $IsRunning = $false

    try {
        $response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 1 -ErrorAction Stop
        if ($response -and $response.status -eq "ok") {
            $IsRunning = $true
        }
    }
    catch {
        $IsRunning = $false
    }

    if ($IsRunning) {
        Write-Host "[+] Local Orchestrator server is active on http://127.0.0.1:8000." -ForegroundColor Gray
        return
    }

    if ($WhatIf) {
        Write-Host "[WhatIf] Would spawn background Orchestrator server on http://127.0.0.1:8000." -ForegroundColor DarkCyan
        return
    }

    $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $PythonExe = if (Test-Path $VenvPython) { $VenvPython } else { "python" }
    
    $ProfilesBaseDir = [System.Environment]::ExpandEnvironmentVariables("%USERPROFILE%\.claude-profiles")
    $ServerLogsDir = Join-Path $ProfilesBaseDir "Logs\server"
    if (-not (Test-Path $ServerLogsDir)) {
        New-Item -ItemType Directory -Force -Path $ServerLogsDir | Out-Null
    }
    $ServerOutLog = Join-Path $ServerLogsDir "server_out.log"
    $ServerErrLog = Join-Path $ServerLogsDir "server_err.log"

    Write-Host "[+] Starting background Orchestrator server on http://127.0.0.1:8000..." -ForegroundColor Cyan
    Start-Process -FilePath $PythonExe -ArgumentList "-m uvicorn server.main:app --host 127.0.0.1 --port 8000" -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput $ServerOutLog -RedirectStandardError $ServerErrLog

    # Wait up to 3 seconds for health check
    $retries = 6
    while ($retries -gt 0) {
        Start-Sleep -Milliseconds 500
        try {
            $check = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 1 -ErrorAction Stop
            if ($check -and $check.status -eq "ok") {
                Write-Host "[+] Local Orchestrator server is ready." -ForegroundColor Green
                return
            }
        }
        catch { }
        $retries--
    }
}

if ($TestHook) {
    return
}

function Resolve-SingleAccount {
    # Interactive picker for one account: shows the table, accepts a number
    # or N (add new), or validates a pre-supplied name (offering to add it
    # if unknown). Identical logic to the original single-launch picker —
    # extracted verbatim so both the Isolated flow and the Concurrent
    # multi-select loop (which calls this once per requested seat) share
    # one implementation. Mutates $script:Profiles/$script:AccountKeys on
    # add so subsequent calls in the same process see the new profile.
    # A rejected/failed resolution here is fatal to the whole process (exit 1)
    # even inside a multi-select loop, since it happens before any account
    # commits to launching — unlike failures inside Invoke-ProfileLaunch,
    # there is no partial launch to protect by continuing past this.
    param(
        [string]$PresetAccount,
        [switch]$SkipTableDisplay
    )

    $Result = $PresetAccount

    if (-not $Result) {
        if (-not $SkipTableDisplay) {
            Write-Host "----------------------------------------" -ForegroundColor Cyan
            Write-Host " Select a Claude Desktop Profile:" -ForegroundColor Green
            Write-Host "----------------------------------------" -ForegroundColor Cyan

            Show-ProfileTable -Profiles $script:Profiles -AccountKeys $script:AccountKeys
        }

        if ($script:AccountKeys.Count -eq 0) {
            $selection = Read-Host "No profiles yet. Press N (or Enter) to add your first profile"
            $Result = Add-NewProfile
            $script:Profiles = Get-Content $script:ConfigFile | ConvertFrom-Json
            $script:AccountKeys = @($script:Profiles.psobject.properties.Name)
        }
        else {
            $selection = Read-Host "Select profile [1-$($script:AccountKeys.Count) or N] (Default: 1)"
            if ($selection -match '^[Nn]$|^\+$') {
                $Result = Add-NewProfile
                $script:Profiles = Get-Content $script:ConfigFile | ConvertFrom-Json
                $script:AccountKeys = @($script:Profiles.psobject.properties.Name)
            }
            elseif ([string]::IsNullOrWhiteSpace($selection)) {
                $Result = $script:AccountKeys[0]
            }
            else {
                $selectionIndex = [int]$selection - 1
                if ($selectionIndex -ge 0 -and $selectionIndex -lt $script:AccountKeys.Count) {
                    $Result = $script:AccountKeys[$selectionIndex]
                }
                else {
                    Write-Host "Invalid selection '$selection'" -ForegroundColor Red
                    Read-Host "Press Enter to exit..."
                    exit 1
                }
            }
        }
    }
    elseif (-not ($script:Profiles.psobject.properties.Name -contains $Result)) {
        Write-Host "Account '$Result' not found in profiles.json." -ForegroundColor Yellow
        $response = Read-Host "Would you like to add '$Result' as a new profile? [Y/n]"
        if ([string]::IsNullOrWhiteSpace($response) -or $response -match '^[Yy]') {
            $Result = Add-NewProfile -SuggestedName $Result
            $script:Profiles = Get-Content $script:ConfigFile | ConvertFrom-Json
            $script:AccountKeys = @($script:Profiles.psobject.properties.Name)
        }
        else {
            Read-Host "Press Enter to close this window"
            exit 1
        }
    }

    return $Result
}

function Invoke-ProfileLaunch {
    # The full single-profile launch pipeline (session-info lookup, exe
    # resolution, swap/mirror or direct concurrent launch, tracker update,
    # team sync, sync.ps1). Verbatim body of the original script's
    # $ProfileInfo-gated launch logic, extracted so it can run once per
    # account in either single-account (-Account) or multi-account
    # (-Users, Concurrent only) invocation without duplicating ~400 lines.
    #
    # Per-account failure isolation: in a multi-account run, one profile's
    # failure (bad path, exe not found, missing profiles.json entry) must
    # not prevent the remaining requested profiles from launching. Every
    # exit 0/1 and blocking "press enter" from the original single-launch
    # body is therefore replaced here with Write-Host + return — except the
    # profiles.json-vanished / lock-timeout warnings inside the mutex block,
    # which were already non-fatal (Write-Warning, no exit) and are
    # unchanged.
    param(
        [Parameter(Mandatory = $true)][string]$Account
    )

    $ProfileInfo = $script:Profiles.$Account

    if ($ProfileInfo) {
        $Nickname = $ProfileInfo.nickname
        $RawDir = $ProfileInfo.path
        $Dir = Get-ValidatedProfilePath -RawPath $RawDir -ProfileName $Account
        $TargetStorageDir = $Dir

        $ProfilesBaseDir = [System.Environment]::ExpandEnvironmentVariables("%USERPROFILE%\.claude-profiles")

        if ($Concurrent) {
            # Concurrent mode has no single "active profile" - .active_profile is never
            # written to in this mode (see the tracker-update block below), so check
            # per-instance instead: is a claude.exe already running with THIS profile's
            # --user-data-dir on its command line?
            $ExistingConcurrent = Get-CimInstance Win32_Process -Filter "Name = 'claude.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -and $_.CommandLine.Contains($Dir) }
            if ($ExistingConcurrent) {
                Write-Host "----------------------------------------" -ForegroundColor Cyan
                Write-Host " Profile '$Account' ($Nickname) is already running as a concurrent instance." -ForegroundColor Green
                Write-Host " No action taken." -ForegroundColor Gray
                Write-Host "----------------------------------------" -ForegroundColor Cyan
                return
            }
        }
        else {
            # Same-profile short-circuit: if the requested account is already the active
            # profile AND Claude is currently running, this is not a switch - do nothing
            # rather than closing and relaunching the same session.
            $StateFile = Join-Path $ProfilesBaseDir ".active_profile"
            $ActiveAccount = $null
            if (Test-Path $StateFile) {
                $ActiveAccount = (Get-Content $StateFile -Raw).Trim()
            }
            $RunningClaude = Get-Process -Name "claude" -ErrorAction SilentlyContinue

            if ($RunningClaude -and ($ActiveAccount -eq $Account)) {
                Write-Host "----------------------------------------" -ForegroundColor Cyan
                Write-Host " Profile '$Account' ($Nickname) is already open." -ForegroundColor Green
                Write-Host " No action taken." -ForegroundColor Gray
                Write-Host "----------------------------------------" -ForegroundColor Cyan
                return
            }
        }

        if (-not (Test-Path $Dir)) {
            if ($WhatIf) {
                Write-Host "[WhatIf] Would create profile storage dir '$Dir'." -ForegroundColor DarkCyan
            }
            else {
                New-Item -ItemType Directory -Force -Path $Dir | Out-Null
            }
        }

        $ExecutablePaths = [System.Collections.Generic.List[string]]::new()

        try {
            $AppxPkg = Get-AppxPackage *claude* -ErrorAction SilentlyContinue
            if ($AppxPkg -and $AppxPkg.InstallLocation) {
                $ExecutablePaths.Add((Join-Path $AppxPkg.InstallLocation "app\claude.exe"))
                $ExecutablePaths.Add((Join-Path $AppxPkg.InstallLocation "Claude.exe"))
            }
        }
        catch { }

        $ExecutablePaths.Add("$env:LOCALAPPDATA\Programs\Claude\Claude.exe")
        $ExecutablePaths.Add("$env:LOCALAPPDATA\Microsoft\WindowsApps\Claude.exe")

        $ClaudeExe = $null
        foreach ($exePath in $ExecutablePaths) {
            if ($exePath -and (Test-Path $exePath)) {
                $ClaudeExe = $exePath
                break
            }
        }

        if (-not $ClaudeExe) {
            Write-Host "Claude Desktop executable (Claude.exe) not found!" -ForegroundColor Red
            Write-Host "Checked locations:" -ForegroundColor Yellow
            foreach ($exePath in $ExecutablePaths) {
                if ($exePath) { Write-Host "  - $exePath" -ForegroundColor Gray }
            }
            return
        }

        # Native AppData directory used by Claude Desktop MSIX / Desktop installer
        $NativeAppDataDir = "$env:LOCALAPPDATA\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude"
        if (-not (Test-Path (Split-Path $NativeAppDataDir -Parent))) {
            $NativeAppDataDir = "$env:APPDATA\Claude"
        }

        if (-not (Test-Path $ProfilesBaseDir)) {
            New-Item -ItemType Directory -Force -Path $ProfilesBaseDir | Out-Null
        }

        # Only strip custom registry protocol overrides when the AppX package owns native protocol
        # handling. If Claude was installed via the non-Store installer (LOCALAPPDATA\Programs\Claude),
        # there is no AppX URI activation to fall back on — removing the override here leaves
        # claude:// with NO handler at all, breaking OAuth/quick-signin callback routing.
        # Skipped entirely in Concurrent mode: claude:// is a single OS-wide handler, so flipping
        # it per concurrent launch would fight with whatever other instances are already running.
        if ($Concurrent) {
            # The warning only matters once a second claude.exe is about to come up
            # alongside a first — with zero instances running, this launch can't
            # collide with anything, so the generic "sign in one at a time" advice
            # is noise. Check actual state instead of firing unconditionally.
            #
            # Printed once per Invoke-ProfileLaunch call in a single-account run,
            # but a multi-account Concurrent list would otherwise repeat this
            # identical warning once per profile — dedupe via a script-scoped flag.
            if (-not $script:ConcurrentSignInWarningShown) {
                $OtherRunningClaude = @(Get-CimInstance Win32_Process -Filter "Name = 'claude.exe'" -ErrorAction SilentlyContinue)
                if ($OtherRunningClaude.Count -gt 0) {
                    Write-Host "[!] Concurrent mode: $($OtherRunningClaude.Count) other Claude instance(s) already running. 'claude://' sign-in is a single OS-wide handler and will route to whichever instance last had focus — if '$Account' ($Nickname) still needs sign-in, close the other instances first, sign in, then relaunch both." -ForegroundColor Yellow
                }
                else {
                    Write-Host "[i] Concurrent mode: no other Claude instances running yet. If '$Account' ($Nickname) needs sign-in, do it now while it's the only instance open — once you add more profiles side by side, 'claude://' sign-in will route to whichever instance last had focus." -ForegroundColor Cyan
                }
                $script:ConcurrentSignInWarningShown = $true
            }
        }
        else {
            try {
                $RegPath = 'HKCU:\Software\Classes\claude'
                if ($AppxPkg -and (Test-Path $RegPath)) {
                    if ($WhatIf) {
                        Write-Host "[WhatIf] Would export '$RegPath' to RegistryBackups\ then remove it (AppX present)." -ForegroundColor DarkCyan
                    }
                    else {
                        $RegBackupDir = Join-Path $ProfilesBaseDir "RegistryBackups"
                        if (-not (Test-Path $RegBackupDir)) {
                            New-Item -ItemType Directory -Force -Path $RegBackupDir | Out-Null
                        }
                        $RegBackupFile = Join-Path $RegBackupDir "claude-protocol-$(Get-Date -Format 'yyyyMMdd-HHmmss').reg"
                        & reg.exe export "HKCU\Software\Classes\claude" $RegBackupFile /y 2>$null | Out-Null
                        Remove-Item -Path $RegPath -Force -Recurse -ErrorAction SilentlyContinue
                    }
                }
                elseif (-not $AppxPkg -and -not (Test-Path $RegPath)) {
                    Write-Host "[!] No AppX package and no 'claude://' registry handler found — quick sign-in callback may not route back to the app." -ForegroundColor Yellow
                }
            }
            catch { }
        }

        # Close existing running Claude processes (skipped in Concurrent mode by design)
        if (-not $Concurrent -and $RunningClaude) {
            if ($WhatIf) {
                Write-Host "[WhatIf] Would stop $($RunningClaude.Count) running Claude process(es)." -ForegroundColor DarkCyan
            }
            else {
                Write-Host "Closing running Claude process(es) to switch profiles..." -ForegroundColor Yellow
                $RunningClaude | Stop-Process -Force
                Start-Sleep -Milliseconds 800
            }
        }

        if (-not $Concurrent) {
            # Ephemeral Chromium cache folders to exclude from sync to prevent disk cache corruptions (Error -8)
            $CacheExcludeDirs = @("Cache", "GPUCache", "Code Cache", "Script Cache", "Crashpad", "blob_storage", "DawnCache", "Cache_Data")

            # Save currently active profile session back to its storage folder
            if (Test-Path $StateFile) {
                $PrevAccount = (Get-Content $StateFile -Raw).Trim()
                if ($PrevAccount -and ($PrevAccount -ne $Account) -and (Test-Path $NativeAppDataDir)) {
                    $PrevStorageDir = Join-Path $ProfilesBaseDir $PrevAccount
                    if ($WhatIf) {
                        Write-Host "[WhatIf] Would mirror '$NativeAppDataDir' -> '$PrevStorageDir' (backup for '$PrevAccount')." -ForegroundColor DarkCyan
                    }
                    else {
                        if (-not (Test-Path $PrevStorageDir)) {
                            New-Item -ItemType Directory -Force -Path $PrevStorageDir | Out-Null
                        }
                        Write-Host "[+] Saving current session data to profile '$PrevAccount'..." -ForegroundColor Gray
                        & robocopy $NativeAppDataDir $PrevStorageDir /MIR /XD $CacheExcludeDirs /R:1 /W:1 /NJH /NJS /NDL /NC /NS | Out-Null
                    }
                }
            }

            # Restore target profile session into Native AppData directory
            if (-not (Test-Path $TargetStorageDir)) {
                if (-not $WhatIf) {
                    New-Item -ItemType Directory -Force -Path $TargetStorageDir | Out-Null
                }
            }

            if (-not (Test-Path $NativeAppDataDir)) {
                if (-not $WhatIf) {
                    New-Item -ItemType Directory -Force -Path $NativeAppDataDir | Out-Null
                }
            }

            $TargetFiles = Get-ChildItem -Path $TargetStorageDir -ErrorAction SilentlyContinue
            if ($TargetFiles) {
                if ($WhatIf) {
                    Write-Host "[WhatIf] Would mirror '$TargetStorageDir' -> '$NativeAppDataDir' (restore for '$Account')." -ForegroundColor DarkCyan
                }
                else {
                    Write-Host "[+] Restoring session data for profile '$Account'..." -ForegroundColor Cyan
                    & robocopy $TargetStorageDir $NativeAppDataDir /MIR /XD $CacheExcludeDirs /R:1 /W:1 /NJH /NJS /NDL /NC /NS | Out-Null
                }
            }
            else {
                if ($WhatIf) {
                    Write-Host "[WhatIf] Would clear '$NativeAppDataDir' to initialize fresh profile storage for '$Account'." -ForegroundColor DarkCyan
                }
                else {
                    Write-Host "[+] Initializing fresh profile storage for '$Account'..." -ForegroundColor Cyan
                    Get-ChildItem -Path $NativeAppDataDir -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
                }
            }

            # Clear stale Chromium disk cache files to force clean initialization (prevents Error -8)
            foreach ($cDir in $CacheExcludeDirs) {
                $cPath = Join-Path $NativeAppDataDir $cDir
                if (Test-Path $cPath) {
                    if ($WhatIf) {
                        Write-Host "[WhatIf] Would remove cache dir '$cPath'." -ForegroundColor DarkCyan
                    }
                    else {
                        Remove-Item -Path $cPath -Recurse -Force -ErrorAction SilentlyContinue
                    }
                }
            }
        }
        else {
            # Concurrent mode: no shared directory to swap - Claude launches directly against
            # $Dir via --user-data-dir further down, so there is nothing to mirror here. Reusing
            # $Dir as both the swap-mode backup target and the concurrent live data dir is
            # intentional (one naming scheme, no third directory layout) - but do not run a
            # non-Concurrent switch INTO this same profile while a concurrent instance of it is
            # still live, since that would robocopy /MIR over a directory the running instance
            # has open file handles on.
            if ($WhatIf) {
                Write-Host "[WhatIf] Concurrent mode: would launch directly against '$Dir' (no swap/mirror)." -ForegroundColor DarkCyan
            }
            else {
                Write-Host "[+] Concurrent mode: launching directly against '$Dir' (no swap/mirror needed)." -ForegroundColor Gray
            }
        }

        # Update last-login timestamp (both modes). The single-slot .active_profile tracker
        # is swap-mode only — Concurrent mode intentionally never claims it, since "one active
        # profile" doesn't apply when several may be running, and claiming it here would corrupt
        # a later non-concurrent switch's backup-save logic (see the "no shared directory" note above).
        $Now = Get-Date
        $CurrentDate = $Now.ToString("yyyy-MM-dd")
        $CurrentTime = $Now.ToString("HH:mm:ss")
        if ($WhatIf) {
            if ($Concurrent) {
                Write-Host "[WhatIf] Would update last_login to '$CurrentDate $CurrentTime' for '$Account' (active-profile tracker left untouched in Concurrent mode)." -ForegroundColor DarkCyan
            }
            else {
                Write-Host "[WhatIf] Would set active profile to '$Account' and update last_login to '$CurrentDate $CurrentTime'." -ForegroundColor DarkCyan
            }
        }
        else {
            if (-not $Concurrent) {
                $Account | Set-Content $StateFile -Encoding UTF8
            }

            # Same named Mutex as cooldown-reminder.ps1's Update-FirstLoginDate:
            # serializes profiles.json access across processes. -Concurrent mode
            # runs multiple independent PowerShell processes against this file,
            # so we re-read fresh under the lock (rather than reusing the $Profiles
            # loaded at script start) to avoid clobbering another process's
            # concurrent write — its own last_login update, or a first_login_time
            # write from its cooldown-reminder.ps1 invocation.
            $MutexName = "Global\ClaudeDesktopProfilesJsonLock"
            $Mutex = $null
            $AcquiredLock = $false
            $LockError = $null
            try {
                $Mutex = New-Object System.Threading.Mutex($false, $MutexName)
                try {
                    $AcquiredLock = $Mutex.WaitOne([TimeSpan]::FromSeconds(10))
                }
                catch [System.Threading.AbandonedMutexException] {
                    # Previous holder crashed while holding the lock. .NET still
                    # grants ownership despite the exception — treat as acquired.
                    $AcquiredLock = $true
                }
            }
            catch {
                # Any other failure constructing the mutex or waiting on it (e.g.
                # Global namespace creation denied under session isolation).
                # Captured explicitly rather than inferred from $Mutex being
                # non-null, so a genuine timeout can never be conflated with this.
                $LockError = $_
            }

            if ($AcquiredLock) {
                try {
                    $FreshProfiles = Get-Content $ConfigFile -Raw | ConvertFrom-Json
                    $FreshProfileInfo = $FreshProfiles.$Account
                    if ($FreshProfileInfo) {
                        $FreshProfileInfo | Add-Member -NotePropertyName "last_login_date" -NotePropertyValue $CurrentDate -Force
                        $FreshProfileInfo | Add-Member -NotePropertyName "last_login_time" -NotePropertyValue $CurrentTime -Force

                        $TempConfigPath = "$ConfigFile.tmp"
                        $FreshProfiles | ConvertTo-Json -Depth 5 | Set-Content $TempConfigPath -Encoding UTF8
                        Move-Item -Path $TempConfigPath -Destination $ConfigFile -Force
                    }
                    else {
                        Write-Warning "Profile '$Account' vanished from profiles.json between load and write. last_login not updated this run."
                    }
                }
                catch {
                    # Failure while HOLDING a successfully-acquired lock — the lock was
                    # never the issue, so falling back to a stale unlocked write here
                    # wouldn't help and would misattribute the cause. Log and skip;
                    # next launch will pick this profile's last_login up correctly.
                    Write-Warning "Write to profiles.json failed while holding lock ($_). last_login not updated this run."
                }
                finally {
                    $Mutex.ReleaseMutex()
                }
            }
            elseif ($LockError) {
                # Mutex itself could not be constructed/acquired — genuinely no lock
                # available. Fall back to the pre-hardening behavior (best-effort
                # unlocked write) rather than silently dropping the update, since
                # this write previously never failed and callers may depend on it.
                Write-Warning "profiles.json lock unavailable ($LockError). Falling back to unlocked write."
                try {
                    $ProfileInfo | Add-Member -NotePropertyName "last_login_date" -NotePropertyValue $CurrentDate -Force
                    $ProfileInfo | Add-Member -NotePropertyName "last_login_time" -NotePropertyValue $CurrentTime -Force
                    $Profiles | ConvertTo-Json -Depth 5 | Set-Content $ConfigFile -Encoding UTF8
                }
                catch {
                    Write-Warning "Unlocked fallback write also failed ($_). last_login not updated this run."
                }
            }
            else {
                # $Mutex constructed fine and WaitOne definitively returned $false —
                # a genuine 10s timeout, lock is healthy but contended by another
                # process. Skip rather than write stale data underneath a real lock.
                Write-Warning "Timed out waiting for profiles.json lock (10s). last_login not updated this run."
            }

            if ($Mutex) {
                $Mutex.Dispose()
            }

            # Cooldown reminders (toast + cooldown tracking) are best-effort and must
            # never block or fail the launch itself.
            try {
                $ReminderScript = Join-Path $PSScriptRoot "cooldown-reminder.ps1"
                if (Test-Path $ReminderScript) {
                    & $ReminderScript -LoginTime $Now -Nickname $Nickname -ProfileName $Account -ConfigFile $ConfigFile -DisableToast:$NoCooldownAlarm -EnableGCal:$GCalReminder
                }
            }
            catch {
                Write-Warning "Cooldown reminder setup failed: $_"
            }
        }

        # Ensure local background orchestrator server is running for MCP endpoints
        Ensure-LocalOrchestratorServer -RepoRoot $PSScriptRoot -WhatIf:$WhatIf

        # Team interlink: force-merge shared MCP servers into this profile's
        # claude_desktop_config.json. Opt out with -NoTeamSync. Best-effort
        # no-op if team-mcp.json isn't checked in yet. Runs for both modes:
        # $NativeAppDataDir is what swap-mode Claude reads (already restored
        # by the mirror step above); $Dir is what Concurrent mode reads
        # directly via --user-data-dir.
        if (-not $NoTeamSync) {
            $TeamConfigDir = if ($Concurrent) { $Dir } else { $NativeAppDataDir }
            Sync-TeamMcpConfig -RepoRoot $PSScriptRoot -TargetConfigDir $TeamConfigDir -WhatIf:$WhatIf
        }

        $Role = if ($ProfileInfo.role) { [string]$ProfileInfo.role } else { "-" }
        $modeDesc = if ($Concurrent) { "Concurrent (Side-by-Side)" } else { "Isolated (Session Swap)" }

        function Format-CardRow([string]$Label, [string]$Value) {
            $val = if ($null -ne $Value) { [string]$Value } else { "" }
            if ($val.Length -gt 74) {
                $val = $val.Substring(0, 71) + "..."
            }
            "│  ● " + $Label.PadRight(13) + ": " + $val.PadRight(74) + " │"
        }

        Write-Host ("╭" + ("─" * 94) + "╮") -ForegroundColor Cyan
        Write-Host ("│" + "  🚀 Launching Claude Desktop (Native)".PadRight(94) + "│") -ForegroundColor Green
        Write-Host ("├" + ("─" * 94) + "┤") -ForegroundColor Cyan
        Write-Host (Format-CardRow "Profile" $Account) -ForegroundColor Yellow
        Write-Host (Format-CardRow "Nickname" $Nickname) -ForegroundColor Yellow
        Write-Host (Format-CardRow "Role" $Role) -ForegroundColor Cyan
        Write-Host (Format-CardRow "Mode" $modeDesc) -ForegroundColor Gray
        Write-Host (Format-CardRow "Last Login" "$CurrentDate $CurrentTime") -ForegroundColor Gray
        Write-Host (Format-CardRow "Storage" $TargetStorageDir) -ForegroundColor DarkGray
        Write-Host (Format-CardRow "Executable" $ClaudeExe) -ForegroundColor DarkGray
        Write-Host ("╰" + ("─" * 94) + "╯") -ForegroundColor Cyan

        # Redirect stdout/stderr to per-profile logs to suppress internal Electron/Node.js deprecation warnings (DEP0169)
        $LogsDir = Join-Path $ProfilesBaseDir "Logs\$Account"
        if ($WhatIf) {
            Write-Host "[WhatIf] Would launch '$ClaudeExe' with logs under '$LogsDir'." -ForegroundColor DarkCyan
            Write-Host "[WhatIf] Dry run complete. No files, registry, or processes were modified." -ForegroundColor Green
        }
        else {
            if (-not (Test-Path $LogsDir)) {
                New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
            }
            $OutLog = Join-Path $LogsDir "claude_out.log"
            $ErrLog = Join-Path $LogsDir "claude_err.log"
            $ProcessArgs = @()
            if ($Concurrent) {
                $ProcessArgs += "--user-data-dir=`"$Dir`""
            }
            if ($RemoteDebuggingPort -gt 0) {
                $ProcessArgs += "--remote-debugging-port=$RemoteDebuggingPort"
            }

            if ($ProcessArgs.Count -gt 0) {
                Start-Process $ClaudeExe -ArgumentList ($ProcessArgs -join " ") -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
            }
            else {
                Start-Process $ClaudeExe -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
            }
        }

        # Auto-sync repo (profiles.json last_login, etc.) via sync.ps1 on every launch.
        # Spawned as a separate pwsh process (not dot-sourced/called in-process) so that
        # sync.ps1's internal `exit` calls (e.g. secret-scan abort) cannot terminate this
        # launcher's own session.
        if ($WhatIf) {
            Write-Host "[WhatIf] Would auto-sync repository via sync.ps1 (pull, commit, push)." -ForegroundColor DarkCyan
        }
        else {
            Write-Host "[+] Auto-syncing repository via sync.ps1..." -ForegroundColor Cyan
            & pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "sync.ps1") -Message "chore(sync): auto-sync after launching profile '$Account' ($Nickname)"
            if ($LASTEXITCODE -ne 0) {
                Write-Host "[!] Auto-sync via sync.ps1 exited with code $LASTEXITCODE. Repo may be out of sync." -ForegroundColor Yellow
            }
        }
    }
    else {
        Write-Host "Account '$Account' not found in profiles.json" -ForegroundColor Red
        return
    }
}

# ----------------------------------------------------------------------
# Mode dispatch
# ----------------------------------------------------------------------

$isInteractive = [Environment]::UserInteractive -and -not [Console]::IsInputRedirected -and -not $NoTUI

# Interactive TUI mode for interactive terminal runs with no CLI targets
if ($isInteractive -and -not $Users -and -not $Account) {
    $initialMode = if ($Concurrent -or $Mode -eq "Concurrent") { "Concurrent" } else { "Isolated" }
    $tuiChoice = Select-ProfileInteractive -InitialMode $initialMode
    
    if ($tuiChoice.Cancelled) {
        Write-Host "Launch cancelled." -ForegroundColor Yellow
        exit 0
    }

    $Concurrent = ($tuiChoice.Mode -eq "Concurrent")
    foreach ($acc in $tuiChoice.Accounts) {
        Invoke-ProfileLaunch -Account $acc
    }
    
    if (-not $WhatIf) {
        Read-Host "Press Enter to close this window"
    }
    exit 0
}

# Classic Fallback Mode (non-interactive / redirected / explicit CLI parameters)
if (-not $Mode -and -not $Concurrent -and -not $Users -and -not $Account) {
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host " Select a Claude Desktop Profile:" -ForegroundColor Green
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Show-ProfileTable -Profiles $script:Profiles -AccountKeys $script:AccountKeys

    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host " Run mode:" -ForegroundColor Green
    Write-Host "   [1] Isolated  - one profile, swaps into the shared native install (default)" -ForegroundColor Gray
    Write-Host "   [2] Concurrent - one or more profiles, each its own independent window" -ForegroundColor Gray
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    $modeSelection = Read-Host "Select mode [1-2] (Default: 1)"
    if ($modeSelection -eq "2") {
        $Concurrent = $true
    }
}

if ($Concurrent -and -not $Users) {
    Show-ProfileTable -Profiles $script:Profiles -AccountKeys $script:AccountKeys
    $usersInput = Read-Host "Profile(s) for Concurrent mode - number(s) or name(s), comma-separated (blank to pick one from the list)"
    if (-not [string]::IsNullOrWhiteSpace($usersInput)) {
        $Users = @($usersInput -split '[,\s]+' | Where-Object { $_ })
    }
}

if ($Users -and $Users.Count -gt 0) {
    $ResolvedAccounts = foreach ($u in $Users) {
        if ($u -match '^\d+$') {
            $idx = [int]$u - 1
            if ($idx -ge 0 -and $idx -lt $script:AccountKeys.Count) {
                Resolve-SingleAccount -PresetAccount $script:AccountKeys[$idx]
            }
            else {
                Write-Host "Invalid profile number '$u' (have $($script:AccountKeys.Count) profile(s))." -ForegroundColor Red
                Read-Host "Press Enter to close this window"
                exit 1
            }
        }
        else {
            Resolve-SingleAccount -PresetAccount $u
        }
    }
    foreach ($resolvedAccount in $ResolvedAccounts) {
        Invoke-ProfileLaunch -Account $resolvedAccount
    }
}
else {
    $tableAlreadyShown = -not $Mode -and -not $Concurrent
    $singleAccount = Resolve-SingleAccount -PresetAccount $Account -SkipTableDisplay:$tableAlreadyShown
    Invoke-ProfileLaunch -Account $singleAccount
}

if (-not $WhatIf) {
    Read-Host "Press Enter to close this window"
}