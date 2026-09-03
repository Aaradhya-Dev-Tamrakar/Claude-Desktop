param(
    [string[]]$Profiles = @("user1", "user2", "user3", "user4"),
    [ValidateRange(1, 20)][int]$Iterations = 3,
    [switch]$IncludeProcessSnapshot
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$Launcher = Join-Path $RepoRoot "launch_user_n.ps1"
$McpSync = Join-Path $RepoRoot "sync-mcp.ps1"
$ProfileArgument = $Profiles -join ","

function Measure-Milliseconds {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    $measurement = Measure-Command { & $Action }
    return [math]::Round($measurement.TotalMilliseconds, 1)
}

function Get-Statistics {
    param(
        [Parameter(Mandatory = $true)][double[]]$Values
    )

    $summary = $Values | Measure-Object -Average -Minimum -Maximum
    return [pscustomobject]@{
        AverageMs = [math]::Round($summary.Average, 1)
        MinimumMs = [math]::Round($summary.Minimum, 1)
        MaximumMs = [math]::Round($summary.Maximum, 1)
    }
}

if (-not (Test-Path $Launcher) -or -not (Test-Path $McpSync)) {
    throw "Run this script from the repository containing launch_user_n.ps1 and sync-mcp.ps1."
}

Write-Host "Efficiency benchmark" -ForegroundColor Cyan
Write-Host "Profiles: $ProfileArgument | Iterations: $Iterations"
Write-Host "All measurements are side-effect-free dry runs." -ForegroundColor DarkGray
Write-Host ""

$launcherTimes = @(
    1..$Iterations | ForEach-Object {
        Measure-Milliseconds {
            & pwsh -NoProfile -File $Launcher -Mode Concurrent -Users $ProfileArgument -WhatIf -NoTUI -NoTeamSync -NoSnap *> $null
        }
    }
)
$launcherStats = Get-Statistics -Values $launcherTimes
[pscustomobject]@{
    Benchmark = "Concurrent launcher dry run"
    Iterations = $Iterations
    AverageMs = $launcherStats.AverageMs
    MinimumMs = $launcherStats.MinimumMs
    MaximumMs = $launcherStats.MaximumMs
} | Format-Table -AutoSize

$singleSyncTimes = @(
    1..$Iterations | ForEach-Object {
        Measure-Milliseconds {
            & pwsh -NoProfile -File $McpSync -WhatIf *> $null
        }
    }
)
$repeatedSyncTimes = @(
    1..$Iterations | ForEach-Object {
        Measure-Milliseconds {
            1..$Profiles.Count | ForEach-Object {
                & pwsh -NoProfile -File $McpSync -WhatIf *> $null
            }
        }
    }
)
$singleSyncStats = Get-Statistics -Values $singleSyncTimes
$repeatedSyncStats = Get-Statistics -Values $repeatedSyncTimes
$syncReduction = [math]::Round((1 - ($singleSyncStats.AverageMs / $repeatedSyncStats.AverageMs)) * 100, 1)

[pscustomobject]@{
    Benchmark = "One MCP sync"
    Iterations = $Iterations
    AverageMs = $singleSyncStats.AverageMs
    MinimumMs = $singleSyncStats.MinimumMs
    MaximumMs = $singleSyncStats.MaximumMs
} | Format-Table -AutoSize
[pscustomobject]@{
    Benchmark = "$($Profiles.Count) repeated MCP syncs"
    Iterations = $Iterations
    AverageMs = $repeatedSyncStats.AverageMs
    MinimumMs = $repeatedSyncStats.MinimumMs
    MaximumMs = $repeatedSyncStats.MaximumMs
} | Format-Table -AutoSize
Write-Host "Batch sync avoids approximately $syncReduction% of repeated sync-run time." -ForegroundColor Green

if ($IncludeProcessSnapshot) {
    Write-Host ""
    Write-Host "Current Claude process snapshot" -ForegroundColor Cyan
    $processes = @(Get-Process -Name "claude" -ErrorAction SilentlyContinue)
    if ($processes.Count -eq 0) {
        Write-Host "No Claude processes are currently running."
    }
    else {
        $processes |
            Select-Object Id, CPU, @{Name = "WorkingSetMB"; Expression = { [math]::Round($_.WorkingSet64 / 1MB, 1) }}, StartTime |
            Format-Table -AutoSize
        $totalMemory = ($processes | Measure-Object -Property WorkingSet64 -Sum).Sum
        Write-Host "Total Claude working set: $([math]::Round($totalMemory / 1GB, 2)) GB" -ForegroundColor Yellow
    }
}