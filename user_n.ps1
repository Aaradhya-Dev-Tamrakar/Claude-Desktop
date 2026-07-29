param (
    [string]$Account = "user1"
)

$ConfigFile = Join-Path $PSScriptRoot "profiles.json"

if (Test-Path $ConfigFile) {
    $Profiles = Get-Content $ConfigFile | ConvertFrom-Json
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
    }
}
else {
    Write-Host "profiles.json file is missing!" -ForegroundColor Red
}