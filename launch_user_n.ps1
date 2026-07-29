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
        email = $Email
        path  = $Path
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
        Write-Host " [$($i + 1)] $key ($email)" -ForegroundColor Yellow
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

    # Close existing running Claude processes to ensure single-instance OAuth callbacks route to the target profile
    $RunningClaude = Get-Process -Name "claude" -ErrorAction SilentlyContinue
    if ($RunningClaude) {
        Write-Host "Closing running Claude process(es) to switch profiles..." -ForegroundColor Yellow
        $RunningClaude | Stop-Process -Force
        Start-Sleep -Milliseconds 500
    }

    # Register/update Windows Registry protocol handler so OAuth deep-link callbacks (claude://) route to this profile
    try {
        $RegPath = 'HKCU:\Software\Classes\claude\shell\open\command'
        if (-not (Test-Path $RegPath)) {
            New-Item -Path $RegPath -Force | Out-Null
        }
        $ProtocolCmd = '"' + $ClaudeExe + '" --user-data-dir="' + $Dir + '" "%1"'
        Set-ItemProperty -Path $RegPath -Name '(default)' -Value $ProtocolCmd -ErrorAction SilentlyContinue
    }
    catch { }

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