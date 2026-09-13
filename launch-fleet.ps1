<#
.SYNOPSIS
    Convenient one-command launcher for the Claude Desktop Multi-Instance Autonomous Fleet.
.DESCRIPTION
    1. Bypasses permissions gates on all profiles.
    2. Launches concurrent instances with unique CDP ports on a dedicated virtual desktop.
    3. Auto-starts the background fleet supervisor to claim and execute tasks.
.EXAMPLE
    .\launch-fleet.ps1
    .\launch-fleet.ps1 -Users user2,user3,user6
    .\launch-fleet.ps1 -WhatIf
#>
param(
    [string[]]$Users = @("user2", "user3", "user6"),
    [int]$BaseCdpPort = 9222,
    [switch]$WhatIf
)

$RepoRoot = $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Starting Claude Desktop Autonomous Worker Fleet" -ForegroundColor Green
Write-Host "  Profiles: $($Users -join ', ')" -ForegroundColor Gray
Write-Host "  Dedicated Virtual Desktop: Active (Leaves primary desktop clean)" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Ensure permission gates are bypassed so tool execution does not block on modal prompts
Write-Host "[1/3] Ensuring tool permission gates are bypassed..." -ForegroundColor Cyan
& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "bypass-all-profiles.ps1") -WhatIf:$WhatIf

# 2. Launch concurrent Claude Desktop instances on dedicated virtual desktop with unique CDP ports
Write-Host "[2/3] Launching Claude Desktop multi-instances on dedicated virtual desktop..." -ForegroundColor Cyan
& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "launch_user_n.ps1") `
    -Mode Concurrent -Users $Users -BaseCdpPort $BaseCdpPort -FleetDesktop -AutoWorkers -WhatIf:$WhatIf

if (-not $WhatIf) {
    Write-Host ""
    Write-Host "[3/3] Fleet is active and running autonomously!" -ForegroundColor Green
    Write-Host "  - To observe instances live: Switch to Desktop 2 (Win + Ctrl + Right)" -ForegroundColor DarkGray
    Write-Host "  - To check fleet status:     python -m tools.fleet_cli status" -ForegroundColor DarkCyan
    Write-Host "  - To broadcast a prompt:     python -m tools.fleet_cli broadcast `"Your prompt`"" -ForegroundColor DarkCyan
    Write-Host "  - To submit a task pipeline: python -m tools.fleet_cli submit `"Generate spec`"" -ForegroundColor DarkCyan
}
