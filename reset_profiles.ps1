param (
    [switch]$WhatIf
)

$ScriptDir = $PSScriptRoot
$ConfigFile = Join-Path $ScriptDir "profiles.json"
$ProfilesBaseDir = [System.Environment]::ExpandEnvironmentVariables("%USERPROFILE%\.claude-profiles")
$NativeAppDataDir = "$env:LOCALAPPDATA\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude"
if (-not (Test-Path (Split-Path $NativeAppDataDir -Parent))) {
    $NativeAppDataDir = "$env:APPDATA\Claude"
}

Write-Host "----------------------------------------" -ForegroundColor Cyan
Write-Host " Reset Claude Desktop Profiles" -ForegroundColor Green
Write-Host "----------------------------------------" -ForegroundColor Cyan

if (-not $WhatIf) {
    $confirm = Read-Host "This will delete ALL profiles, sessions, and logs, and reset the active Claude session. Type 'RESET' to confirm"
    if ($confirm -ne "RESET") {
        Write-Host "Aborted. Nothing was changed." -ForegroundColor Yellow
        exit 0
    }
}

# Close any running Claude process so files aren't locked
$RunningClaude = Get-Process -Name "claude" -ErrorAction SilentlyContinue
if ($RunningClaude) {
    if ($WhatIf) {
        Write-Host "[WhatIf] Would stop $($RunningClaude.Count) running Claude process(es)." -ForegroundColor DarkCyan
    }
    else {
        Write-Host "Closing running Claude process(es)..." -ForegroundColor Yellow
        $RunningClaude | Stop-Process -Force
        Start-Sleep -Milliseconds 800
    }
}

# Wipe all profile storage, logs, state, and registry backups
if (Test-Path $ProfilesBaseDir) {
    if ($WhatIf) {
        Write-Host "[WhatIf] Would delete '$ProfilesBaseDir' (all profile storage, logs, state, registry backups)." -ForegroundColor DarkCyan
    }
    else {
        Write-Host "[+] Removing '$ProfilesBaseDir'..." -ForegroundColor Gray
        Remove-Item -Path $ProfilesBaseDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Wipe the native Claude AppData directory (current live session)
if (Test-Path $NativeAppDataDir) {
    if ($WhatIf) {
        Write-Host "[WhatIf] Would clear '$NativeAppDataDir' (live Claude session data)." -ForegroundColor DarkCyan
    }
    else {
        Write-Host "[+] Clearing '$NativeAppDataDir'..." -ForegroundColor Gray
        Get-ChildItem -Path $NativeAppDataDir -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Remove any custom claude:// registry protocol override
try {
    $RegPath = 'HKCU:\Software\Classes\claude'
    if (Test-Path $RegPath) {
        if ($WhatIf) {
            Write-Host "[WhatIf] Would remove registry key '$RegPath'." -ForegroundColor DarkCyan
        }
        else {
            Write-Host "[+] Removing registry key '$RegPath'..." -ForegroundColor Gray
            Remove-Item -Path $RegPath -Force -Recurse -ErrorAction SilentlyContinue
        }
    }
}
catch { }

# Reset profiles.json to empty object (zero state, not deleted)
if ($WhatIf) {
    Write-Host "[WhatIf] Would reset '$ConfigFile' to '{}'." -ForegroundColor DarkCyan
}
else {
    Write-Host "[+] Resetting '$ConfigFile' to empty..." -ForegroundColor Gray
    "{}" | Set-Content $ConfigFile -Encoding UTF8
}

Write-Host "----------------------------------------" -ForegroundColor Cyan
if ($WhatIf) {
    Write-Host " [WhatIf] Dry run complete. No files, registry, or processes were modified." -ForegroundColor Green
}
else {
    Write-Host " Reset complete. All profiles and sessions cleared." -ForegroundColor Green
}
Write-Host "----------------------------------------" -ForegroundColor Cyan