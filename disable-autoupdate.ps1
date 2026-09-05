<#
.SYNOPSIS
    Disables Claude Desktop and Windows Store auto-updates to prevent
    spontaneous termination of concurrently running Claude instances.

.DESCRIPTION
    Claude Desktop's internal background updater periodically polls Anthropic's
    servers for new releases. When an update is detected, it stages the build
    and calls quitAndInstall(). On Windows (MSIX package), this triggers the
    Windows Restart Manager, which sends WM_ENDSESSION (close-app) to ALL
    running claude.exe processes regardless of profile, instantly closing every
    open concurrent window.

    This script sets the official Anthropic Enterprise Policy:
      HKLM:\SOFTWARE\Policies\Claude -> disableAutoUpdates = 1 (DWORD)
    which instructs Claude Desktop to disable background update checking,
    staging, and automatic restarts entirely.

    It also optionally configures Microsoft Store to disable automatic app
    background updates (AutoDownload = 2).

.PARAMETER EnableStoreAutoUpdate
    Leave Windows Store automatic updates untouched (only disable Claude's
    internal updater).

.EXAMPLE
    pwsh -File .\disable-autoupdate.ps1
#>

param(
    [switch]$KeepStoreAutoUpdate
)

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[!] Administrator privileges are required to configure machine-wide enterprise policies." -ForegroundColor Yellow
    Write-Host "[+] Elevating PowerShell..." -ForegroundColor Cyan
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    if ($KeepStoreAutoUpdate) {
        $argList += " -KeepStoreAutoUpdate"
    }
    Start-Process pwsh.exe -Verb RunAs -ArgumentList $argList
    exit
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Claude Desktop: Disable Auto-Update Policy Configuration" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Anthropic Enterprise Policy for Claude Desktop
$claudePolicyKey = "HKLM:\SOFTWARE\Policies\Claude"
try {
    if (-not (Test-Path $claudePolicyKey)) {
        New-Item -Path $claudePolicyKey -Force | Out-Null
    }
    Set-ItemProperty -Path $claudePolicyKey -Name "disableAutoUpdates" -Value 1 -Type DWord -Force
    Write-Host "[✓] Configured Claude policy: $claudePolicyKey\disableAutoUpdates = 1" -ForegroundColor Green
    Write-Host "    Claude Desktop will no longer poll for updates or restart running sessions." -ForegroundColor DarkGray
}
catch {
    Write-Host "[✗] Failed to set Claude policy: $_" -ForegroundColor Red
}

# 2. Windows Store Policy (prevents Microsoft Store from silently updating MSIX packages in background)
if (-not $KeepStoreAutoUpdate) {
    $storePolicyKey = "HKLM:\SOFTWARE\Policies\Microsoft\WindowsStore"
    try {
        if (-not (Test-Path $storePolicyKey)) {
            New-Item -Path $storePolicyKey -Force | Out-Null
        }
        # AutoDownload = 2 disables automatic download/install of Store updates
        Set-ItemProperty -Path $storePolicyKey -Name "AutoDownload" -Value 2 -Type DWord -Force
        Write-Host "[✓] Configured Windows Store policy: $storePolicyKey\AutoDownload = 2" -ForegroundColor Green
        Write-Host "    Windows Store will no longer update MSIX packages in the background." -ForegroundColor DarkGray
    }
    catch {
        Write-Host "[!] Windows Store policy setup skipped or failed: $_" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Done! When you want to update Claude Desktop in the future:" -ForegroundColor Cyan
Write-Host "  1. Close all Claude windows." -ForegroundColor Gray
Write-Host "  2. Open Microsoft Store -> Library -> Update Claude, or run the installer." -ForegroundColor Gray
Write-Host ""
Read-Host "Press Enter to exit"
