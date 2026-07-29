param (
    [string]$Account
)

$ConfigFile = Join-Path $PSScriptRoot "profiles.json"

if (-not (Test-Path $ConfigFile)) {
    Write-Host "profiles.json file is missing!" -ForegroundColor Red
    exit 1
}

$Profiles = Get-Content $ConfigFile | ConvertFrom-Json
$AccountKeys = @($Profiles.psobject.properties.Name)

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

    $Email = Read-Host "Enter email address for '$Name'"
    if ([string]::IsNullOrWhiteSpace($Email)) {
        $Email = "$Name@example.com"
    }

    $Path = "%USERPROFILE%\.claude-profiles\$Name"

    $Profiles | Add-Member -NotePropertyName $Name -NotePropertyValue @{
        email      = $Email
        path       = $Path
        last_login = $null
    } -Force

    $Profiles | ConvertTo-Json -Depth 5 | Set-Content $ConfigFile -Encoding UTF8
    Write-Host "[+] Saved new profile '$Name' to profiles.json!" -ForegroundColor Green

    return $Name
}

if (-not $Account) {
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host " Select a Claude Desktop Profile:" -ForegroundColor Green
    Write-Host "----------------------------------------" -ForegroundColor Cyan

    for ($i = 0; $i -lt $AccountKeys.Count; $i++) {
        $key = $AccountKeys[$i]
        $email = $Profiles.$key.email
        $lastLogin = $Profiles.$key.last_login
        if (-not $lastLogin) { $lastLogin = "Never" }
        Write-Host " [$($i + 1)] $key ($email) - Last Login: $lastLogin" -ForegroundColor Yellow
    }
    Write-Host " [N] Add New Profile (+)" -ForegroundColor Magenta
    Write-Host "----------------------------------------" -ForegroundColor Cyan

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
    $Email = $ProfileInfo.email
    $RawDir = $ProfileInfo.path
    $Dir = [System.Environment]::ExpandEnvironmentVariables($RawDir)

    if (-not (Test-Path $Dir)) {
        New-Item -ItemType Directory -Force -Path $Dir | Out-Null
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

    # Remove any custom registry protocol overrides so Windows uses 100% native AppX protocol handling
    try {
        $RegPath = 'HKCU:\Software\Classes\claude'
        if (Test-Path $RegPath) {
            Remove-Item -Path $RegPath -Force -Recurse -ErrorAction SilentlyContinue
        }
    } catch { }

    # Close existing running Claude processes
    $RunningClaude = Get-Process -Name "claude" -ErrorAction SilentlyContinue
    if ($RunningClaude) {
        Write-Host "Closing running Claude process(es) to switch profiles..." -ForegroundColor Yellow
        $RunningClaude | Stop-Process -Force
        Start-Sleep -Milliseconds 800
    }

    $ProfilesBaseDir = [System.Environment]::ExpandEnvironmentVariables("%USERPROFILE%\.claude-profiles")
    if (-not (Test-Path $ProfilesBaseDir)) {
        New-Item -ItemType Directory -Force -Path $ProfilesBaseDir | Out-Null
    }
    $StateFile = Join-Path $ProfilesBaseDir ".active_profile"

    # Ephemeral Chromium cache folders to exclude from sync to prevent disk cache corruptions (Error -8)
    $CacheExcludeDirs = @("Cache", "GPUCache", "Code Cache", "Script Cache", "Crashpad", "blob_storage", "DawnCache", "Cache_Data")

    # Save currently active profile session back to its storage folder
    if (Test-Path $StateFile) {
        $PrevAccount = (Get-Content $StateFile -Raw).Trim()
        if ($PrevAccount -and ($PrevAccount -ne $Account) -and (Test-Path $NativeAppDataDir)) {
            $PrevStorageDir = Join-Path $ProfilesBaseDir $PrevAccount
            if (-not (Test-Path $PrevStorageDir)) {
                New-Item -ItemType Directory -Force -Path $PrevStorageDir | Out-Null
            }
            Write-Host "[+] Saving current session data to profile '$PrevAccount'..." -ForegroundColor Gray
            & robocopy $NativeAppDataDir $PrevStorageDir /MIR /XD $CacheExcludeDirs /R:1 /W:1 /NJH /NJS /NDL /NC /NS | Out-Null
        }
    }

    # Restore target profile session into Native AppData directory
    $TargetStorageDir = $Dir
    if (-not (Test-Path $TargetStorageDir)) {
        New-Item -ItemType Directory -Force -Path $TargetStorageDir | Out-Null
    }

    if (-not (Test-Path $NativeAppDataDir)) {
        New-Item -ItemType Directory -Force -Path $NativeAppDataDir | Out-Null
    }

    $TargetFiles = Get-ChildItem -Path $TargetStorageDir -ErrorAction SilentlyContinue
    if ($TargetFiles) {
        Write-Host "[+] Restoring session data for profile '$Account'..." -ForegroundColor Cyan
        & robocopy $TargetStorageDir $NativeAppDataDir /MIR /XD $CacheExcludeDirs /R:1 /W:1 /NJH /NJS /NDL /NC /NS | Out-Null
    }
    else {
        Write-Host "[+] Initializing fresh profile storage for '$Account'..." -ForegroundColor Cyan
        Get-ChildItem -Path $NativeAppDataDir -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }

    # Clear stale Chromium disk cache files to force clean initialization (prevents Error -8)
    foreach ($cDir in $CacheExcludeDirs) {
        $cPath = Join-Path $NativeAppDataDir $cDir
        if (Test-Path $cPath) {
            Remove-Item -Path $cPath -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    # Update active profile tracker file
    $Account | Set-Content $StateFile -Encoding UTF8

    # Update last login timestamp in profile and save to profiles.json
    $CurrentTimestamp = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    $ProfileInfo | Add-Member -NotePropertyName "last_login" -NotePropertyValue $CurrentTimestamp -Force
    $Profiles | ConvertTo-Json -Depth 5 | Set-Content $ConfigFile -Encoding UTF8

    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host " Launching Claude Desktop (Native)" -ForegroundColor Green
    Write-Host " Profile    : $Account" -ForegroundColor Yellow
    Write-Host " Email      : $Email" -ForegroundColor Yellow
    Write-Host " Last Login : $CurrentTimestamp" -ForegroundColor Yellow
    Write-Host " Active     : $NativeAppDataDir" -ForegroundColor Gray
    Write-Host " Storage    : $TargetStorageDir" -ForegroundColor Gray
    Write-Host " Exe        : $ClaudeExe" -ForegroundColor Gray
    Write-Host "----------------------------------------" -ForegroundColor Cyan

    # Redirect stdout/stderr to temp logs to suppress internal Electron/Node.js deprecation warnings (DEP0169)
    $OutLog = Join-Path $env:TEMP "claude_out.log"
    $ErrLog = Join-Path $env:TEMP "claude_err.log"
    Start-Process $ClaudeExe -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
}
else {
    Write-Host "Account '$Account' not found in profiles.json" -ForegroundColor Red
    exit 1
}