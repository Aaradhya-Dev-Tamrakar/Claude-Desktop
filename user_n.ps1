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

if (-not $Account) {
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host " Select a Claude Desktop Profile:" -ForegroundColor Green
    Write-Host "----------------------------------------" -ForegroundColor Cyan

    for ($i = 0; $i -lt $AccountKeys.Count; $i++) {
        $key = $AccountKeys[$i]
        $email = $Profiles.$key.email
        Write-Host " [$($i + 1)] $key ($email)" -ForegroundColor Yellow
    }
    Write-Host "----------------------------------------" -ForegroundColor Cyan

    $selection = Read-Host "Select profile [1-$($AccountKeys.Count)] (Default: 1)"
    if ([string]::IsNullOrWhiteSpace($selection)) {
        $selectionIndex = 0
    }
    else {
        $selectionIndex = [int]$selection - 1
    }

    if ($selectionIndex -ge 0 -and $selectionIndex -lt $AccountKeys.Count) {
        $Account = $AccountKeys[$selectionIndex]
    }
    else {
        Write-Host "Invalid selection '$selection'" -ForegroundColor Red
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

    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host " Launching Claude Desktop" -ForegroundColor Green
    Write-Host " Profile : $Account" -ForegroundColor Yellow
    Write-Host " Email   : $Email" -ForegroundColor Yellow
    Write-Host " Path    : $Dir" -ForegroundColor Gray
    Write-Host " Exe     : $ClaudeExe" -ForegroundColor Gray
    Write-Host "----------------------------------------" -ForegroundColor Cyan

    Start-Process $ClaudeExe -ArgumentList "--user-data-dir=`"$Dir`""
}
else {
    Write-Host "Account '$Account' not found in profiles.json" -ForegroundColor Red
    exit 1
}