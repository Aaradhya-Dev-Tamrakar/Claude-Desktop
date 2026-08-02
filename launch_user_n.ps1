param (
    [string]$Account,
    [switch]$WhatIf,
    [switch]$Concurrent,
    [switch]$NoCooldownAlarm,
    [switch]$GCalReminder,
    # Skip syncing team-mcp.json / team-context.md into this launch. Use for
    # a one-off launch you don't want the shared MCP config force-merged into.
    [switch]$NoTeamSync,
    # Dot-source-and-return-early hook for Pester: stops after function
    # definitions, before any interactive prompt or side-effecting logic.
    # Never set by real launches (launch.bat / manual pwsh invocation).
    [switch]$TestHook
)

if ($GCalReminder) {
    Write-Warning "GCalReminder: Google Calendar integration is currently paused. This switch has no effect until re-enabled in cooldown-reminder.ps1."
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

function Send-TeamContextToClipboard {
    # Copies team-context.md's content to the clipboard so it's one paste
    # away as a seed message / custom-instructions block. Not injected into
    # the app automatically: Claude Desktop's chat-side custom instructions
    # and Memory are account-level and server-side (synced via whichever
    # account is authenticated in this profile), not a local file this
    # script can write into — so clipboard-and-paste is the honest local
    # equivalent, not a guess at an unconfirmed config path.
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [switch]$WhatIf
    )

    $ContextPath = Join-Path $RepoRoot "team-context.md"
    if (-not (Test-Path $ContextPath)) {
        return  # No team-context.md checked in yet — nothing to copy, silently skip.
    }

    if ($WhatIf) {
        Write-Host "[WhatIf] Would copy 'team-context.md' to the clipboard." -ForegroundColor DarkCyan
        return
    }

    try {
        $Content = Get-Content $ContextPath -Raw
        Set-Clipboard -Value $Content
        Write-Host "[+] team-context.md copied to clipboard — paste as your first message or into Custom Instructions." -ForegroundColor Gray
    }
    catch {
        Write-Warning "Failed to copy team-context.md to clipboard ($_). Open the file manually if needed."
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

function Show-ProfileTable {
    param($Profiles, $AccountKeys)

    if ($AccountKeys.Count -eq 0) {
        Write-Host "(No profiles yet. Press N to add your first profile.)" -ForegroundColor DarkGray
        return
    }

    $TodayStr = (Get-Date).ToString("yyyy-MM-dd")

    $rows = for ($i = 0; $i -lt $AccountKeys.Count; $i++) {
        $key = $AccountKeys[$i]
        $lastLoginDate = $Profiles.$key.last_login_date
        $lastLoginTime = $Profiles.$key.last_login_time
        if (-not $lastLoginDate) { $lastLoginDate = "Never" }
        if (-not $lastLoginTime) { $lastLoginTime = "-" }
        [PSCustomObject]@{
            Profile  = $key
            Nickname = $Profiles.$key.nickname
            LastTime = $lastLoginTime
            LastDate = $lastLoginDate
            IsToday  = ($lastLoginDate -eq $TodayStr)
        }
    }

    # Rank today's logins by Last Time descending (most recent = 1). Tuple
    # position (row order) is untouched — this only assigns a rank label.
    # Profiles not logged in today (or never) get "-".
    $todayRanked = $rows | Where-Object { $_.IsToday } | Sort-Object -Property LastTime -Descending
    $rankMap = @{}
    for ($r = 0; $r -lt $todayRanked.Count; $r++) {
        $rankMap[$todayRanked[$r].Profile] = ($r + 1)
    }
    foreach ($row in $rows) {
        $row | Add-Member -NotePropertyName "TodayRank" -NotePropertyValue $(if ($rankMap.ContainsKey($row.Profile)) { [string]$rankMap[$row.Profile] } else { "-" }) -Force
    }

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

if ($TestHook) {
    return
}

if (-not $Account) {
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host " Select a Claude Desktop Profile:" -ForegroundColor Green
    Write-Host "----------------------------------------" -ForegroundColor Cyan

    Show-ProfileTable -Profiles $Profiles -AccountKeys $AccountKeys

    if ($AccountKeys.Count -eq 0) {
        $selection = Read-Host "No profiles yet. Press N (or Enter) to add your first profile"
        $Account = Add-NewProfile
        $Profiles = Get-Content $ConfigFile | ConvertFrom-Json
    }
    else {
        $selection = Read-Host "Select profile [1-$($AccountKeys.Count) or N] (Default: 1)"
        if ($selection -match '^[Nn]$|^\+$') {
            $Account = Add-NewProfile
            $Profiles = Get-Content $ConfigFile | ConvertFrom-Json
        }
        elseif ([string]::IsNullOrWhiteSpace($selection)) {
            $Account = $AccountKeys[0]
        }
        else {
            $selectionIndex = [int]$selection - 1
            if ($selectionIndex -ge 0 -and $selectionIndex -lt $AccountKeys.Count) {
                $Account = $AccountKeys[$selectionIndex]
            }
            else {
                Write-Host "Invalid selection '$selection'" -ForegroundColor Red
                Read-Host "Press Enter to exit..."
                exit 1
            }
        }
    }
}
elseif (-not ($Profiles.psobject.properties.Name -contains $Account)) {
    Write-Host "Account '$Account' not found in profiles.json." -ForegroundColor Yellow
    $response = Read-Host "Would you like to add '$Account' as a new profile? [Y/n]"
    if ([string]::IsNullOrWhiteSpace($response) -or $response -match '^[Yy]') {
        $Account = Add-NewProfile -SuggestedName $Account
        $Profiles = Get-Content $ConfigFile | ConvertFrom-Json
    }
    else {
        Read-Host "Press Enter to close this window"
        exit 1
    }
}

$ProfileInfo = $Profiles.$Account

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
            if (-not $WhatIf) {
                Read-Host "Press Enter to close this window"
            }
            exit 0
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
            if (-not $WhatIf) {
                Read-Host "Press Enter to close this window"
            }
            exit 0
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
        Read-Host "Press Enter to close this window"
        exit 1
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
        Write-Host "[!] Concurrent mode: 'claude://' sign-in is a single OS-wide handler and routes to whichever instance last had focus. Sign in to each profile one at a time (others closed) before running them side by side." -ForegroundColor Yellow
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

    # Team interlink: force-merge shared MCP servers into this profile's
    # claude_desktop_config.json, and stage team-context.md on the clipboard
    # for manual paste into Custom Instructions / first message. Both are
    # best-effort no-ops if team-mcp.json / team-context.md aren't checked in
    # yet. Runs for both modes: $NativeAppDataDir is what swap-mode Claude
    # reads (already restored by the mirror step above); $Dir is what
    # Concurrent mode reads directly via --user-data-dir.
    if (-not $NoTeamSync) {
        $TeamConfigDir = if ($Concurrent) { $Dir } else { $NativeAppDataDir }
        Sync-TeamMcpConfig -RepoRoot $PSScriptRoot -TargetConfigDir $TeamConfigDir -WhatIf:$WhatIf
        Send-TeamContextToClipboard -RepoRoot $PSScriptRoot -WhatIf:$WhatIf
    }

    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host " Launching Claude Desktop (Native)" -ForegroundColor Green
    Write-Host " Profile    : $Account" -ForegroundColor Yellow
    Write-Host " Nickname   : $Nickname" -ForegroundColor Yellow
    Write-Host " Last Login : $CurrentDate $CurrentTime" -ForegroundColor Yellow
    Write-Host " Active     : $NativeAppDataDir" -ForegroundColor Gray
    Write-Host " Storage    : $TargetStorageDir" -ForegroundColor Gray
    Write-Host " Exe        : $ClaudeExe" -ForegroundColor Gray
    Write-Host "----------------------------------------" -ForegroundColor Cyan

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
        if ($Concurrent) {
            Start-Process $ClaudeExe -ArgumentList "--user-data-dir=`"$Dir`"" -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
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
    Read-Host "Press Enter to close this window"
    exit 1
}

if (-not $WhatIf) {
    Read-Host "Press Enter to close this window"
}