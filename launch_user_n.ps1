param (
    [string]$Account,
    [switch]$WhatIf
)

$ConfigFile = Join-Path $PSScriptRoot "profiles.json"

if (-not (Test-Path $ConfigFile)) {
    Write-Host "profiles.json file is missing!" -ForegroundColor Red
    exit 1
}

$Profiles = Get-Content $ConfigFile | ConvertFrom-Json
$AccountKeys = @($Profiles.psobject.properties.Name)

function Get-ValidatedProfilePath {
    param(
        [Parameter(Mandatory = $true)][string]$RawPath,
        [Parameter(Mandatory = $true)][string]$ProfileName
    )

    $BaseDir = [System.Environment]::ExpandEnvironmentVariables("%USERPROFILE%\.claude-profiles")
    $BaseFull = [System.IO.Path]::GetFullPath($BaseDir).TrimEnd('\') + '\'

    $Expanded = [System.Environment]::ExpandEnvironmentVariables($RawPath)
    $ExpandedFull = [System.IO.Path]::GetFullPath($Expanded)

    if (-not $ExpandedFull.StartsWith($BaseFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Host "[!] Profile '$ProfileName' path resolves outside the approved base directory." -ForegroundColor Red
        Write-Host "    Base    : $BaseFull" -ForegroundColor Gray
        Write-Host "    Resolved: $ExpandedFull" -ForegroundColor Gray
        Write-Host "    Refusing to use this path. Fix 'path' for '$ProfileName' in profiles.json." -ForegroundColor Red
        exit 1
    }

    return $ExpandedFull
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
        $Name = Read-Host "Enter profile name (e.g. user3, personal, client)"
    }

    if ([string]::IsNullOrWhiteSpace($Name)) {
        Write-Host "Profile name cannot be empty." -ForegroundColor Red
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
        nickname   = $Nickname
        path       = $Path
        last_login = $null
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

    $rows = for ($i = 0; $i -lt $AccountKeys.Count; $i++) {
        $key = $AccountKeys[$i]
        $lastLogin = $Profiles.$key.last_login
        if (-not $lastLogin) { $lastLogin = "Never" }
        [PSCustomObject]@{
            Num       = "[$($i + 1)]"
            Profile   = $key
            Nickname  = $Profiles.$key.nickname
            LastLogin = $lastLogin
        }
    }

    $numW = [Math]::Max(3, ($rows.Num | Measure-Object -Property Length -Maximum).Maximum)
    $profW = [Math]::Max(7, ($rows.Profile | Measure-Object -Property Length -Maximum).Maximum)
    $nickW = [Math]::Max(8, ($rows.Nickname | Measure-Object -Property Length -Maximum).Maximum)
    $loginW = [Math]::Max(10, ($rows.LastLogin | Measure-Object -Property Length -Maximum).Maximum)
    $widths = @($numW, $profW, $nickW, $loginW)

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
    Write-Host (New-Row @("#", "Profile", "Nickname", "Last Login")) -ForegroundColor Cyan
    Write-Host (New-Border "+" "+" "+") -ForegroundColor Cyan
    foreach ($r in $rows) {
        Write-Host (New-Row @($r.Num, $r.Profile, $r.Nickname, $r.LastLogin)) -ForegroundColor Yellow
    }
    Write-Host (New-Border "+" "+" "+") -ForegroundColor Cyan
    Write-Host ("| " + "[N] Add New Profile (+)".PadRight($innerWidth - 2) + " |") -ForegroundColor Magenta
    Write-Host (New-Border "+" "+" "+") -ForegroundColor Cyan
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
        exit 1
    }
}

$ProfileInfo = $Profiles.$Account

if ($ProfileInfo) {
    $Nickname = $ProfileInfo.nickname
    $RawDir = $ProfileInfo.path
    $Dir = Get-ValidatedProfilePath -RawPath $RawDir -ProfileName $Account

    # Same-profile short-circuit: if the requested account is already the active
    # profile AND Claude is currently running, this is not a switch - do nothing
    # rather than closing and relaunching the same session.
    $ProfilesBaseDir = [System.Environment]::ExpandEnvironmentVariables("%USERPROFILE%\.claude-profiles")
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
        exit 0
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

    # Close existing running Claude processes
    if ($RunningClaude) {
        if ($WhatIf) {
            Write-Host "[WhatIf] Would stop $($RunningClaude.Count) running Claude process(es)." -ForegroundColor DarkCyan
        }
        else {
            Write-Host "Closing running Claude process(es) to switch profiles..." -ForegroundColor Yellow
            $RunningClaude | Stop-Process -Force
            Start-Sleep -Milliseconds 800
        }
    }

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
    $TargetStorageDir = $Dir
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

    # Update active profile tracker file
    $CurrentTimestamp = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    if ($WhatIf) {
        Write-Host "[WhatIf] Would set active profile to '$Account' and update last_login to '$CurrentTimestamp'." -ForegroundColor DarkCyan
    }
    else {
        $Account | Set-Content $StateFile -Encoding UTF8
        $ProfileInfo | Add-Member -NotePropertyName "last_login" -NotePropertyValue $CurrentTimestamp -Force
        $Profiles | ConvertTo-Json -Depth 5 | Set-Content $ConfigFile -Encoding UTF8
    }

    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host " Launching Claude Desktop (Native)" -ForegroundColor Green
    Write-Host " Profile    : $Account" -ForegroundColor Yellow
    Write-Host " Nickname   : $Nickname" -ForegroundColor Yellow
    Write-Host " Last Login : $CurrentTimestamp" -ForegroundColor Yellow
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
        Start-Process $ClaudeExe -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
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
    exit 1
}