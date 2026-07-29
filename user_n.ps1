param (
    [string]$Account = "user1"
)

$ConfigFile = Join-Path $PSScriptRoot "profiles.json"

if (Test-Path $ConfigFile) {
    $Profiles = Get-Content $ConfigFile | ConvertFrom-Json
    $ProfileInfo = $Profiles.$Account

    if ($ProfileInfo) {
        $Email = $ProfileInfo.email
        $Dir = $ProfileInfo.path

        Write-Host "----------------------------------------" -ForegroundColor Cyan
        Write-Host " Launching Claude Desktop" -ForegroundColor Green
        Write-Host " Profile : $Account" -ForegroundColor Yellow
        Write-Host " Email   : $Email" -ForegroundColor Yellow
        Write-Host " Path    : $Dir" -ForegroundColor Gray
        Write-Host "----------------------------------------" -ForegroundColor Cyan

        Start-Process "$env:LOCALAPPDATA\Microsoft\WindowsApps\Claude.exe" `
            -ArgumentList "--user-data-dir=`"$Dir`""
    }
    else {
        Write-Host "Account '$Account' not found in profiles.json" -ForegroundColor Red
    }
}
else {
    Write-Host "profiles.json file is missing!" -ForegroundColor Red
}