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
    [switch]$NoTUI,
    # Disable automatic window snapping / grid arrangement for concurrent launches
    [switch]$NoSnap,
    # Explicitly force window snapping / grid arrangement
    [switch]$Snap,
    # Skip the two-step confirmation before isolated mode closes concurrent
    # profile instances. This is unsafe by design.
    [switch]$ForceIsolated
)

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch { }

function Get-VisibleTextWidth {
    param([string]$Text)

    if ([string]::IsNullOrEmpty($Text)) { return 0 }

    $width = 0
    $i = 0
    while ($i -lt $Text.Length) {
        $current = [char]$Text[$i]

        if ([char]::IsHighSurrogate($current) -and ($i + 1) -lt $Text.Length -and [char]::IsLowSurrogate([char]$Text[$i + 1])) {
            $width += 2
            $i += 2
            continue
        }

        $code = [int][char]$Text[$i]
        $isWide = (
            ($code -ge 0x1100 -and (
                $code -le 0x115F -or
                $code -ge 0x2329 -and $code -le 0x232A -or
                $code -ge 0x2E80 -and $code -le 0xA4CF -or
                $code -ge 0xAC00 -and $code -le 0xD7A3 -or
                $code -ge 0xF900 -and $code -le 0xFAFF -or
                $code -ge 0xFE10 -and $code -le 0xFE19 -or
                $code -ge 0xFE30 -and $code -le 0xFE6F -or
                $code -ge 0xFF00 -and $code -le 0xFF60 -or
                $code -ge 0xFFE0 -and $code -le 0xFFE6
            )) -or $code -eq 0x3000
        )

        $width += if ($isWide) { 2 } else { 1 }
        $i++
    }

    return $width
}

function Format-VisibleRight {
    param(
        [string]$Text,
        [int]$Width
    )

    $rawWidth = Get-VisibleTextWidth $Text
    if ($rawWidth -ge $Width) { return $Text }
    return $Text + (' ' * ($Width - $rawWidth))
}

function Format-VisibleText {
    param(
        [string]$Text,
        [int]$MaxWidth
    )

    if ([string]::IsNullOrEmpty($Text)) { return $Text }
    if (Get-VisibleTextWidth $Text -le $MaxWidth) { return $Text }

    $result = ""
    $currentWidth = 0
    $i = 0

    while ($i -lt $Text.Length -and $currentWidth + 1 -le $MaxWidth - 3) {
        $current = [char]$Text[$i]
        if ([char]::IsHighSurrogate($current) -and ($i + 1) -lt $Text.Length -and [char]::IsLowSurrogate([char]$Text[$i + 1])) {
            $segmentWidth = 2
            if ($currentWidth + $segmentWidth -le $MaxWidth - 3) {
                $result += $Text.Substring($i, 2)
                $currentWidth += $segmentWidth
                $i += 2
                continue
            }
        }

        $segmentWidth = 1
        if ($currentWidth + $segmentWidth -le $MaxWidth - 3) {
            $result += $current
            $currentWidth += $segmentWidth
            $i++
            continue
        }

        break
    }

    return $result + "..."
}

function Format-CardRow([string]$Label, [string]$Value, [int]$BoxWidth = 98) {
    $val = if ($null -ne $Value) { [string]$Value } else { "" }
    $prefix = "  * " + $Label.PadRight(13, ' ') + ": "
    $contentWidth = $BoxWidth - 2

    if (($prefix + $val).Length -le $contentWidth) {
        $content = ($prefix + $val).PadRight($contentWidth, ' ')
        return "│$content│"
    }

    $prefixWidth = $prefix.Length
    $maxVisible = [Math]::Max(0, $contentWidth - $prefixWidth)
    $splitAt = -1
    $candidate = $val.Substring(0, [Math]::Min($val.Length, $maxVisible))

    if ($candidate.Contains("\")) {
        $splitAt = $candidate.LastIndexOf("\")
    }
    if ($splitAt -lt 0 -and $val.Length -gt $maxVisible) {
        $splitAt = $maxVisible
    }

    if ($splitAt -lt 0) {
        $firstValue = $candidate
        $secondValue = ""
    }
    else {
        $firstValue = $val.Substring(0, [Math]::Min($val.Length, $splitAt + 1))
        $secondValue = $val.Substring([Math]::Min($val.Length, $splitAt + 1))
    }

    $firstLine = ($prefix + $firstValue).PadRight($contentWidth, ' ')
    $secondLine = ("  " + $secondValue).PadRight($contentWidth, ' ')
    return "│$firstLine│`n│$secondLine│"
}

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

function Write-LaunchBanner {
    param(
        [string]$Title,
        [string]$Subtitle = ""
    )
    Write-Host "" 
    Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║ $($Title.PadRight(52, ' ')) ║" -ForegroundColor Green
    if ($Subtitle) {
        Write-Host "║ $($Subtitle.Substring(0, [Math]::Min($Subtitle.Length, 52)).PadRight(52, ' ')) ║" -ForegroundColor DarkGray
    }
    Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host "" 
}

Write-LaunchBanner -Title "Claude Desktop Launcher" -Subtitle "Mode: $(if ($Concurrent) { 'Concurrent' } else { 'Isolated' })"

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

function Get-ConcurrentClaudeInstances {
    param(
        [Parameter(Mandatory = $true)]$Processes,
        [Parameter(Mandatory = $true)][string]$ProfilesBaseDir
    )

    $normalizedBaseDir = [System.IO.Path]::GetFullPath($ProfilesBaseDir).TrimEnd('\')
    return @($Processes | Where-Object {
        $_.CommandLine -and
        $_.CommandLine -match '(?i)--user-data-dir(?:=|\s+)' -and
        $_.CommandLine -match [regex]::Escape($normalizedBaseDir) + '\\'
    })
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

    # Cloud orchestration is paused; remove stale active registrations while
    # preserving the disabled definition in the shared config for later reuse.
    $Merged.mcpServers.PSObject.Properties.Remove("cloud-orchestrator-mcp")
    $Merged.mcpServers.PSObject.Properties.Remove("site-mcp")

    foreach ($serverName in $Merged.mcpServers.PSObject.Properties.Name) {
        $server = $Merged.mcpServers.$serverName
        if ($server.PSObject.Properties.Name -contains "args") {
            $server.args = @($server.args)
        }
    }

    if ($Merged.PSObject.Properties.Name -contains "preferences" -and $Merged.preferences) {
        foreach ($preferenceName in @("launchPreviewPersistedWorkspaces", "launchPreviewSessionScopedSessions")) {
            if ($Merged.preferences.PSObject.Properties.Name -contains $preferenceName) {
                if ($null -eq $Merged.preferences.$preferenceName) {
                    $Merged.preferences.$preferenceName = [System.Collections.ArrayList]::new()
                }
                else {
                    $Merged.preferences.$preferenceName = @($Merged.preferences.$preferenceName)
                }
            }
        }
    }

    return $Merged
}

function Write-JsonConfigSafely {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Config
    )

    $directory = Split-Path $Path -Parent
    $tempPath = Join-Path $directory (".$([IO.Path]::GetFileName($Path)).$([guid]::NewGuid().ToString('N')).tmp")
    try {
        $Config | ConvertTo-Json -Depth 10 | Set-Content $tempPath -Encoding UTF8
        if (Test-Path $Path) {
            Copy-Item $Path "$Path.bak" -Force
        }
        Move-Item $tempPath $Path -Force
    }
    finally {
        if (Test-Path $tempPath) {
            Remove-Item $tempPath -Force -ErrorAction SilentlyContinue
        }
    }
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
            $server.args = @($server.args)
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
    # Force-syncs shared MCP servers from team-mcp.json across all profiles
    # in %USERPROFILE%\.claude-profiles and the active native AppData dir.
    # Runs once per launch execution unless explicitly forced.
    # Best-effort — matches the script's philosophy: a broken or missing team-mcp.json,
    # or a malformed existing config file, must never block the actual launch.
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [string]$TargetConfigDir,
        [switch]$WhatIf,
        [switch]$Force
    )

    if ($script:TeamMcpSyncCompleted -and -not $Force) {
        return
    }

    $SharedConfigPath = Join-Path $RepoRoot "team-mcp.json"
    if (-not (Test-Path $SharedConfigPath)) {
        return
    }

    try {
        $SharedConfig = Get-Content $SharedConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        Write-Warning "team-mcp.json is not valid JSON ($_). Skipping team MCP sync this launch."
        return
    }

    if (-not ($SharedConfig.PSObject.Properties.Name -contains "mcpServers")) {
        return
    }

    try {
        $SharedConfig = Expand-TeamMcpPlaceholders -SharedConfig $SharedConfig -RepoRoot $RepoRoot
    }
    catch {
        Write-Warning "Failed to expand {{REPO_ROOT}} placeholders in team-mcp.json ($_). Team MCP sync skipped this launch."
        return
    }

    $sharedServerNames = @($SharedConfig.mcpServers.PSObject.Properties.Name)
    $sharedCount = $sharedServerNames.Count

    # Locate all target profile directories
    $ProfilesRoot = [System.Environment]::ExpandEnvironmentVariables("%USERPROFILE%\.claude-profiles")
    $Targets = @()

    if ($TargetConfigDir) {
        $Targets += [PSCustomObject]@{ Name = (Split-Path $TargetConfigDir -Leaf); Path = $TargetConfigDir }
    }
    else {
        if (Test-Path $ProfilesRoot) {
            $profileDirs = Get-ChildItem -Path $ProfilesRoot -Directory | Where-Object { $_.Name -match '^user\d+$' }
            foreach ($p in $profileDirs) {
                $Targets += [PSCustomObject]@{ Name = $p.Name; Path = $p.FullName }
            }
        }

        # Also include active native AppData dir
        $NativeAppDataDir = "$env:LOCALAPPDATA\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude"
        if (-not (Test-Path (Split-Path $NativeAppDataDir -Parent))) {
            $NativeAppDataDir = "$env:APPDATA\Claude"
        }
        if (Test-Path $NativeAppDataDir) {
            $Targets += [PSCustomObject]@{ Name = "NativeAppData"; Path = $NativeAppDataDir }
        }
    }

    if ($WhatIf) {
        Write-Host "  🔄 [WhatIf] Would sync $sharedCount shared MCP server(s) ($($sharedServerNames -join ', ')) into $($Targets.Count) profile(s)/target(s)." -ForegroundColor DarkCyan
    }
    else {
        Write-Host "  🔄 Syncing MCP Servers ($sharedCount) across $($Targets.Count) profile config(s):" -ForegroundColor Cyan
        foreach ($srv in $sharedServerNames) {
            Write-Host "     ● $srv" -ForegroundColor Green
        }

        $syncedCount = 0
        foreach ($tgt in $Targets) {
            $ProfileConfigPath = Join-Path $tgt.Path "claude_desktop_config.json"
            $ProfileConfig = [PSCustomObject]@{}
            if (Test-Path $ProfileConfigPath) {
                try {
                    $ProfileConfig = Get-Content $ProfileConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
                }
                catch {
                    $ProfileConfig = [PSCustomObject]@{}
                }
            }

            try {
                $Merged = Merge-McpServers -ProfileConfig $ProfileConfig -SharedConfig $SharedConfig
                if (-not (Test-Path $tgt.Path)) {
                    New-Item -ItemType Directory -Force -Path $tgt.Path | Out-Null
                }
                Write-JsonConfigSafely -Path $ProfileConfigPath -Config $Merged
                $syncedCount++
            }
            catch {
                Write-Warning "Failed to write merged claude_desktop_config.json for '$($tgt.Name)' ($_)."
            }
        }
        Write-Host "     ✓ Successfully synced $syncedCount config file(s)." -ForegroundColor DarkGray
    }

    $script:TeamMcpSyncCompleted = $true
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
        Add-NewProfile | Out-Null
        $script:Profiles = Get-Content $script:ConfigFile | ConvertFrom-Json
        $script:AccountKeys = @($script:Profiles.psobject.properties.Name)
        $allRows = Get-EnrichedProfileRows -Profiles $script:Profiles -AccountKeys $script:AccountKeys
    }

    # Initial console clear
    try { [Console]::Clear() } catch { }

    $cols = @(6, 13, 16, 10, 10, 10, 11)
    $tblTop = "╭" + (($cols | ForEach-Object { "─" * ($_ + 2) }) -join "┬") + "╮"
    $tblMid = "├" + (($cols | ForEach-Object { "─" * ($_ + 2) }) -join "┼") + "┤"
    $tblBot = "╰" + (($cols | ForEach-Object { "─" * ($_ + 2) }) -join "┴") + "╯"

    $bannerTop = "╭" + ("─" * 96) + "╮"
    $bannerMid = "│" + "                    🚀  CLAUDE DESKTOP PROFILE LAUNCHER".PadRight(96) + "│"
    $bannerBot = "╰" + ("─" * 96) + "╯"

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
            $modeLine = " Mode: [ $modeLabel ]".PadRight(42) + "◄ Press [Tab] or [M] to toggle"
            Write-Host $modeLine.PadRight(98) -ForegroundColor $modeColor
            $currentLines++
            
            if ($isConcurrent) {
                $selCount = $selectedSet.Count
                $multiLine = " Multi-Launch: $selCount profile(s) selected".PadRight(42) + "([Space] to toggle, [A] select/clear all)"
                Write-Host $multiLine.PadRight(98) -ForegroundColor Yellow
            } else {
                Write-Host (" " * 98)
            }
            $currentLines++

            if (-not [string]::IsNullOrEmpty($filterText)) {
                $filterLine = " 🔍 Filter: $filterText (Press [Esc] to clear, matches: $($filteredRows.Count))"
                Write-Host $filterLine.PadRight(98) -ForegroundColor Yellow
            } else {
                $filterLine = " 🔍 Filter: [Type to search by name/role/number...]"
                Write-Host $filterLine.PadRight(98) -ForegroundColor DarkGray
            }
            $currentLines++

            Write-Host (" " * 98)
            $currentLines++

            # Table Header
            $headers = @("Sel   ", "Nickname     ", "Role            ", "Last Time ", "Last Date ", "Today Rank", "Status     ")
            $hdrRow = "│" + (($headers | ForEach-Object { " " + $_ + " " }) -join "│") + "│"

            Write-Host $tblTop -ForegroundColor Cyan
            Write-Host $hdrRow -ForegroundColor Cyan
            Write-Host $tblMid -ForegroundColor Cyan
            $currentLines += 3

            if ($filteredRows.Count -eq 0) {
                $emptyMsg = "  (No matching profiles found for '$filterText')".PadRight(96)
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
                    
                    $roleCell = $row.Role.PadRight(16)
                    if ($roleCell.Length -gt 16) { $roleCell = $roleCell.Substring(0, 13) + "..." }
                    
                    $timeCell = $row.LastTime.PadRight(10)
                    $dateCell = $row.LastDate.PadRight(10)
                    
                    $rankStr = if ($row.TodayRank -ne "-") { "#$($row.TodayRank)" } else { "-" }
                    $rankCell = $rankStr.PadRight(10)

                    $statusStr = if ($row.IsActive -and $row.IsRunning) { "* Active" } elseif ($row.IsRunning) { "> Live" } elseif ($row.IsActive) { "* Active" } else { "" }
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
                Write-Host $scrollInfo.PadRight(98) -ForegroundColor DarkGray
            } else {
                Write-Host (" " * 98)
            }
            $currentLines++

            $footerLine = " [↑/↓] Move │ [Space] Select │ [Tab] Mode │ [Enter] Launch │ [/] Search │ [N] New │ [Q] Exit"
            Write-Host $footerLine.PadRight(98) -ForegroundColor DarkCyan
            $currentLines++

            # Clear trailing lines if viewport shrank
            if ($lastRenderLineCount -gt $currentLines) {
                for ($cl = $currentLines; $cl -lt $lastRenderLineCount; $cl++) {
                    Write-Host (" " * 98)
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
                            Add-NewProfile | Out-Null
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

function Start-LocalOrchestratorServer {
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

function Get-DesktopBatchAllocation {
    <#
    .SYNOPSIS
        Distributes N accounts across virtual desktops with a maximum limit per desktop (default 4).
    .DESCRIPTION
        Returns an array of PSCustomObject detailing for each item:
          - AccountIndex: 0-based overall index
          - DesktopIndex: 0-based virtual desktop index (Desktop 1 is index 0)
          - DesktopSlot:  1-based slot on that virtual desktop (1..4)
          - DesktopTotal: total number of windows placed on that virtual desktop
    #>
    param(
        [Parameter(Mandatory = $true)][int]$TotalCount,
        [int]$MaxPerDesktop = 4
    )

    if ($TotalCount -le 0 -or $MaxPerDesktop -le 0) {
        return @()
    }

    $numDesktops = [int][Math]::Ceiling($TotalCount / [double]$MaxPerDesktop)
    $allocations = [System.Collections.Generic.List[PSCustomObject]]::new()

    for ($d = 0; $d -lt $numDesktops; $d++) {
        $startIdx = $d * $MaxPerDesktop
        $countOnThisDesktop = [Math]::Min($MaxPerDesktop, $TotalCount - $startIdx)

        for ($s = 0; $s -lt $countOnThisDesktop; $s++) {
            $overallIdx = $startIdx + $s
            $allocations.Add([PSCustomObject]@{
                AccountIndex = $overallIdx
                DesktopIndex = $d
                DesktopSlot  = ($s + 1)
                DesktopTotal = $countOnThisDesktop
            })
        }
    }

    return $allocations
}

function Initialize-VirtualDesktopTool {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $toolsDir = Join-Path $RepoRoot "tools"
    $exePath = Join-Path $toolsDir "VirtualDesktop.exe"
    $csPath = Join-Path $toolsDir "VirtualDesktop11-24H2.cs"

    if (Test-Path $exePath) {
        return $exePath
    }

    if (Test-Path $csPath) {
        $cscPaths = @(
            "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
            "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
        )
        $csc = $cscPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($csc) {
            try {
                if (-not (Test-Path $toolsDir)) {
                    New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
                }
                & $csc /nologo /target:exe /out:$exePath $csPath | Out-Null
                if (Test-Path $exePath) {
                    return $exePath
                }
            }
            catch { }
        }
    }

    return $null
}

function Get-WindowGridLayout {
    <#
    .SYNOPSIS
        Calculates grid rectangles for arranging N windows within a bounding rectangle.
    .DESCRIPTION
        Returns an array of PSCustomObject rectangles with X, Y, Width, Height, and Slot index (1-based).
        Layout logic (per desktop with max 4 windows):
          - Count <= 1: 1 col, 1 row (full work area)
          - Count == 2: 2 cols, 1 row (left 50%, right 50%)
          - Count == 3..4: 2 cols, 2 rows (quad grid: top-left, top-right, bottom-left, bottom-right)
          - Count > 4: 2 cols, Ceil(N/2) rows
    #>
    param(
        [Parameter(Mandatory = $true)]$Bounds,
        [Parameter(Mandatory = $true)][int]$Count
    )

    if ($Count -le 0) {
        return @()
    }

    $bX = [int]$Bounds.X
    $bY = [int]$Bounds.Y
    $bW = [int]$Bounds.Width
    $bH = [int]$Bounds.Height

    if ($Count -eq 1) {
        return @([PSCustomObject]@{
            Slot   = 1
            X      = $bX
            Y      = $bY
            Width  = $bW
            Height = $bH
        })
    }

    $cols = 2
    $rows = if ($Count -eq 2) { 1 } elseif ($Count -le 4) { 2 } else { [int][Math]::Ceiling($Count / 2.0) }

    $baseColW = [int][Math]::Floor($bW / $cols)
    $baseRowH = [int][Math]::Floor($bH / $rows)

    $slots = for ($i = 0; $i -lt $Count; $i++) {
        $c = $i % $cols
        $r = [int][Math]::Floor($i / $cols)

        $x = $bX + ($c * $baseColW)
        $y = $bY + ($r * $baseRowH)

        $w = if ($c -eq ($cols - 1)) { $bW - ($c * $baseColW) } else { $baseColW }
        $h = if ($r -eq ($rows - 1)) { $bH - ($r * $baseRowH) } else { $baseRowH }

        [PSCustomObject]@{
            Slot   = ($i + 1)
            X      = $x
            Y      = $y
            Width  = $w
            Height = $h
        }
    }

    return $slots
}

function Initialize-WindowHelperType {
    if (-not ([System.Management.Automation.PSTypeName]'ClaudeDesktopWindowHelper').Type) {
        $typeDef = @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;

public class ClaudeDesktopWindowHelper {
    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);

    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SystemParametersInfo(uint uiAction, uint uiParam, out RECT pvParam, uint fWinIni);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    public const uint SPI_GETWORKAREA = 0x0030;
    public const int SW_RESTORE = 9;
    public const uint SWP_NOZORDER = 0x0004;
    public const uint SWP_NOACTIVATE = 0x0010;
    public const uint SWP_SHOWWINDOW = 0x0040;

    public static RECT GetPrimaryWorkArea() {
        RECT rect = new RECT();
        SystemParametersInfo(SPI_GETWORKAREA, 0, out rect, 0);
        return rect;
    }

    public static List<IntPtr> GetProcessWindows(uint processId) {
        var result = new List<IntPtr>();
        EnumWindows((hWnd, lParam) => {
            if (IsWindowVisible(hWnd)) {
                uint pid;
                GetWindowThreadProcessId(hWnd, out pid);
                if (pid == processId) {
                    StringBuilder className = new StringBuilder(256);
                    GetClassName(hWnd, className, 256);
                    string cls = className.ToString();
                    RECT r;
                    GetWindowRect(hWnd, out r);
                    int w = r.Right - r.Left;
                    int h = r.Bottom - r.Top;
                    if (w > 150 && h > 150) {
                        result.Add(hWnd);
                    }
                }
            }
            return true;
        }, IntPtr.Zero);
        return result;
    }

    public static void SnapWindow(IntPtr hWnd, int x, int y, int width, int height) {
        ShowWindowAsync(hWnd, SW_RESTORE);
        SetWindowPos(hWnd, IntPtr.Zero, x, y, width, height, SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW);
    }
}
"@
        try {
            Add-Type -TypeDefinition $typeDef -Language CSharp
        }
        catch { }
    }
}

function Set-ClaudeWindowsLayout {
    param(
        [Parameter(Mandatory = $false)][string[]]$Accounts = @(),
        [int]$MaxPerDesktop = 4,
        [switch]$WhatIf
    )

    try {
        Initialize-WindowHelperType
        if (-not ([System.Management.Automation.PSTypeName]'ClaudeDesktopWindowHelper').Type) {
            Write-Warning "Window helper could not be initialized. Skipping auto-snap."
            return
        }

        $workArea = [ClaudeDesktopWindowHelper]::GetPrimaryWorkArea()
        $bounds = [PSCustomObject]@{
            X      = [int]$workArea.Left
            Y      = [int]$workArea.Top
            Width  = [int]($workArea.Right - $workArea.Left)
            Height = [int]($workArea.Bottom - $workArea.Top)
        }

        if ($bounds.Width -le 0 -or $bounds.Height -le 0) {
            return
        }

        $orderedProfiles = [System.Collections.Generic.List[string]]::new()
        foreach ($acc in $Accounts) {
            if ($acc -and -not $orderedProfiles.Contains($acc)) {
                $orderedProfiles.Add($acc)
            }
        }

        $allKnownAccounts = if ($script:AccountKeys) { @($script:AccountKeys) } else { @() }
        foreach ($acc in $allKnownAccounts) {
            if (-not $orderedProfiles.Contains($acc)) {
                $orderedProfiles.Add($acc)
            }
        }

        $targets = [System.Collections.Generic.List[PSCustomObject]]::new()

        # Wait up to ~3.5s for launched windows to be created and visible
        $maxAttempts = 7
        for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
            $targets.Clear()
            $runningProcs = @(Get-CimInstance Win32_Process -Filter "Name = 'claude.exe'" -ErrorAction SilentlyContinue)

            foreach ($acc in $orderedProfiles) {
                $pInfo = $script:Profiles.$acc
                $rawPath = if ($pInfo -and $pInfo.path) { [string]$pInfo.path } else { "%USERPROFILE%\.claude-profiles\$acc" }
                $expPath = [System.Environment]::ExpandEnvironmentVariables($rawPath)

                $matchedProcs = @($runningProcs | Where-Object { $_.CommandLine -and $_.CommandLine.IndexOf($expPath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 })
                if ($matchedProcs.Count -gt 0) {
                    $mainPids = @($matchedProcs | Select-Object -ExpandProperty ProcessId)
                    $allProfilePids = @($runningProcs | Where-Object { $mainPids -contains $_.ProcessId -or $mainPids -contains $_.ParentProcessId } | Select-Object -ExpandProperty ProcessId)

                    $foundHwnd = $null
                    foreach ($procId in $allProfilePids) {
                        $hwnds = [ClaudeDesktopWindowHelper]::GetProcessWindows($procId)
                        if ($hwnds.Count -gt 0) {
                            $foundHwnd = $hwnds[0]
                            break
                        }
                    }

                    if ($foundHwnd) {
                        $targets.Add([PSCustomObject]@{
                            Account = $acc
                            Hwnd    = $foundHwnd
                        })
                    }
                }
            }

            # Check if all requested accounts have visible windows
            $allRequestedFound = $true
            if ($Accounts.Count -gt 0) {
                foreach ($req in $Accounts) {
                    $found = $false
                    foreach ($t in $targets) {
                        if ($t.Account -eq $req) { $found = $true; break }
                    }
                    if (-not $found) {
                        $allRequestedFound = $false
                        break
                    }
                }
            }

            if ($allRequestedFound -and $targets.Count -ge 2) {
                break
            }
            Start-Sleep -Milliseconds 500
        }

        # 1 user / profile stays normal (no forced snapping)
        if ($targets.Count -le 1) {
            return
        }

        # Multi-desktop allocation (max 4 per desktop)
        $allocations = Get-DesktopBatchAllocation -TotalCount $targets.Count -MaxPerDesktop $MaxPerDesktop
        $vdExe = Initialize-VirtualDesktopTool -RepoRoot $PSScriptRoot

        $numDesktops = [int][Math]::Ceiling($targets.Count / [double]$MaxPerDesktop)

        if ($numDesktops -gt 1 -and $vdExe) {
            try {
                $countStr = & $vdExe /Quiet /Count 2>$null
                $currentDesktopCount = 1
                if ($countStr -match '(\d+)') {
                    $currentDesktopCount = [int]$Matches[1]
                }
                while ($currentDesktopCount -lt $numDesktops) {
                    if ($WhatIf) {
                        Write-Host "[WhatIf] Would create Virtual Desktop $($currentDesktopCount + 1)." -ForegroundColor DarkCyan
                    } else {
                        & $vdExe /Quiet /New | Out-Null
                    }
                    $currentDesktopCount++
                }
            }
            catch {
                Write-Warning "Failed to ensure virtual desktops ($_)."
            }
        }

        # Group targets by virtual desktop and apply per-desktop grid arrangement
        for ($d = 0; $d -lt $numDesktops; $d++) {
            $desktopItems = @($allocations | Where-Object { $_.DesktopIndex -eq $d })
            $countOnThisDesktop = $desktopItems.Count
            $desktopSlots = Get-WindowGridLayout -Bounds $bounds -Count $countOnThisDesktop

            for ($k = 0; $k -lt $desktopItems.Count; $k++) {
                $alloc = $desktopItems[$k]
                $target = $targets[$alloc.AccountIndex]
                $slot = $desktopSlots[$k]

                if ($WhatIf) {
                    $moveDesc = if ($d -gt 0) { " -> Desktop $($d + 1)" } else { " (Desktop 1)" }
                    Write-Host "[WhatIf] Profile '$($target.Account)'${moveDesc}: Slot $($slot.Slot) at (X=$($slot.X), Y=$($slot.Y), W=$($slot.Width), H=$($slot.Height))" -ForegroundColor DarkCyan
                }
                else {
                    # Move to virtual desktop if index > 0
                    if ($d -gt 0 -and $vdExe) {
                        try {
                            & $vdExe /Quiet "/GetDesktop:$d" "/MoveWindowHandle:$($target.Hwnd)" | Out-Null
                        }
                        catch { }
                    }

                    # Snap window to slot (only snap if > 1 window on this desktop)
                    if ($countOnThisDesktop -gt 1) {
                        [ClaudeDesktopWindowHelper]::SnapWindow($target.Hwnd, $slot.X, $slot.Y, $slot.Width, $slot.Height)
                    }
                }
            }
        }

        if (-not $WhatIf) {
            if ($numDesktops -gt 1) {
                Write-Host "[+] Arranged $($targets.Count) profiles across $numDesktops virtual desktops (max $MaxPerDesktop per desktop)." -ForegroundColor Green
            } else {
                Write-Host "[+] Snapped $($targets.Count) Claude profile window(s) into desktop grid (Slots 1-$($targets.Count))." -ForegroundColor Green
            }
        }
    }
    catch {
        Write-Warning "Auto-snap grid arrangement failed: $_"
    }
}

if ($TestHook) {
    return
}

function Invoke-NlmLogin {
    param(
        [switch]$WhatIf
    )

    $NlmCommand = Get-Command nlm -ErrorAction SilentlyContinue
    if (-not $NlmCommand) {
        Write-Warning "NotebookLM CLI 'nlm' was not found on PATH. Skipping automatic nlm login."
        return
    }

    if ($WhatIf) {
        Write-Host "[WhatIf] Would run 'nlm login' in this terminal." -ForegroundColor DarkCyan
        return
    }

    Write-Host "[+] Running NotebookLM login..." -ForegroundColor Cyan
    & $NlmCommand.Source login
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "'nlm login' exited with code $LASTEXITCODE. Continuing with Claude launch."
    }
}

Invoke-NlmLogin -WhatIf:$WhatIf

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

            if ($RunningClaude -and -not $ForceIsolated -and -not $WhatIf) {
                $ConcurrentInstances = @(Get-ConcurrentClaudeInstances -Processes @(Get-CimInstance Win32_Process -Filter "Name = 'claude.exe'" -ErrorAction SilentlyContinue) -ProfilesBaseDir $ProfilesBaseDir)
                if ($ConcurrentInstances.Count -gt 0) {
                    Write-Host "[!] $($ConcurrentInstances.Count) concurrent Claude instance(s) are running." -ForegroundColor Red
                    Write-Host "    Isolated mode will close all Claude instances and mirror shared native storage." -ForegroundColor Yellow
                    $firstConfirmation = Read-Host "Proceed with isolated mode and close them? [y/N]"
                    if ($firstConfirmation -notmatch '^[Yy]$') {
                        Write-Host "Launch cancelled; concurrent work was left untouched." -ForegroundColor Green
                        return
                    }
                    Write-Host "[i] Confirmed. Closing Claude instances for isolated profile '$Account'." -ForegroundColor Yellow
                }
            }

            if ($RunningClaude -and ($ActiveAccount -eq $Account) -and -not $WhatIf) {
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
        Start-LocalOrchestratorServer -RepoRoot $PSScriptRoot -WhatIf:$WhatIf

        # Team interlink: force-merge shared MCP servers into all profiles
        # (and active native AppData) claude_desktop_config.json. Opt out with -NoTeamSync.
        if (-not $NoTeamSync) {
            if ($script:DeferTeamSync) {
                Write-Host "[i] Deferring team MCP sync until the concurrent launch batch is complete." -ForegroundColor DarkGray
            }
            else {
                Sync-TeamMcpConfig -RepoRoot $PSScriptRoot -WhatIf:$WhatIf
            }
        }

        $Role = if ($ProfileInfo.role) { [string]$ProfileInfo.role } else { "-" }
        $modeDesc = if ($Concurrent) { "Concurrent (Side-by-Side)" } else { "Isolated (Session Swap)" }

        $bannerWidth = 98
        $innerBannerWidth = $bannerWidth - 2
        $bannerTitle = "  Launching Claude Desktop (Native)"
        $bannerLine = "│" + $bannerTitle.PadRight($innerBannerWidth, ' ') + "│"
        Write-Host ("╭" + ("─" * $innerBannerWidth) + "╮") -ForegroundColor Cyan
        Write-Host $bannerLine -ForegroundColor Green
        Write-Host ("├" + ("─" * $innerBannerWidth) + "┤") -ForegroundColor Cyan
        Write-Host (Format-CardRow -Label "Profile" -Value $Account -BoxWidth $bannerWidth) -ForegroundColor Yellow
        Write-Host (Format-CardRow -Label "Nickname" -Value $Nickname -BoxWidth $bannerWidth) -ForegroundColor Yellow
        Write-Host (Format-CardRow -Label "Role" -Value $Role -BoxWidth $bannerWidth) -ForegroundColor Cyan
        Write-Host (Format-CardRow -Label "Mode" -Value $modeDesc -BoxWidth $bannerWidth) -ForegroundColor Gray
        Write-Host (Format-CardRow -Label "Last Login" -Value "$CurrentDate $CurrentTime" -BoxWidth $bannerWidth) -ForegroundColor Gray
        Write-Host (Format-CardRow -Label "Storage" -Value $TargetStorageDir -BoxWidth $bannerWidth) -ForegroundColor DarkGray
        Write-Host (Format-CardRow -Label "Executable" -Value $ClaudeExe -BoxWidth $bannerWidth) -ForegroundColor DarkGray
        Write-Host ("╰" + ("─" * $innerBannerWidth) + "╯") -ForegroundColor Cyan

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
        elseif ($script:DeferRepoSync) {
            Write-Host "[i] Deferring repository sync until the concurrent launch batch is complete." -ForegroundColor DarkGray
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

function Sync-RepositoryAfterLaunchBatch {
    param(
        [Parameter(Mandatory = $true)][string[]]$Accounts
    )

    if ($WhatIf -or $Accounts.Count -le 1) { return }

    Write-Host "[+] Auto-syncing repository once for the $($Accounts.Count)-profile launch batch..." -ForegroundColor Cyan
    & pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "sync.ps1") -Message "chore(sync): auto-sync after concurrent profile batch ($($Accounts -join ', '))"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] Batch auto-sync via sync.ps1 exited with code $LASTEXITCODE. Repo may be out of sync." -ForegroundColor Yellow
    }
}

function Sync-TeamConfigAfterLaunchBatch {
    param(
        [Parameter(Mandatory = $true)][int]$AccountCount
    )

    if ($NoTeamSync -or $AccountCount -le 1) { return }

    Sync-TeamMcpConfig -RepoRoot $PSScriptRoot -WhatIf:$WhatIf
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
    $script:DeferRepoSync = $Concurrent -and $tuiChoice.Accounts.Count -gt 1
    $script:DeferTeamSync = $script:DeferRepoSync
    foreach ($acc in $tuiChoice.Accounts) {
        Invoke-ProfileLaunch -Account $acc
    }
    Sync-RepositoryAfterLaunchBatch -Accounts $tuiChoice.Accounts
    Sync-TeamConfigAfterLaunchBatch -AccountCount $tuiChoice.Accounts.Count
    if (($Concurrent -or $Snap) -and -not $NoSnap) {
        Set-ClaudeWindowsLayout -Accounts $tuiChoice.Accounts -WhatIf:$WhatIf
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
    $script:DeferRepoSync = $Concurrent -and $Users.Count -gt 1
    $script:DeferTeamSync = $script:DeferRepoSync
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
    Sync-RepositoryAfterLaunchBatch -Accounts $ResolvedAccounts
    Sync-TeamConfigAfterLaunchBatch -AccountCount $ResolvedAccounts.Count
    if (($Concurrent -or $Snap) -and -not $NoSnap) {
        Set-ClaudeWindowsLayout -Accounts $ResolvedAccounts -WhatIf:$WhatIf
    }
}
else {
    $tableAlreadyShown = -not $Mode -and -not $Concurrent
    $singleAccount = Resolve-SingleAccount -PresetAccount $Account -SkipTableDisplay:$tableAlreadyShown
    Invoke-ProfileLaunch -Account $singleAccount
    if (($Concurrent -or $Snap) -and -not $NoSnap) {
        Set-ClaudeWindowsLayout -Accounts @($singleAccount) -WhatIf:$WhatIf
    }
}

if (-not $WhatIf) {
    Read-Host "Press Enter to close this window"
}