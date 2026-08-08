<#
.SYNOPSIS
    Sets bypassPermissionsGateByAccount to true for every account UUID
    found across all Claude Desktop profile configs (user1..user20).

.USAGE
    .\bypass-all-profiles.ps1
    .\bypass-all-profiles.ps1 -WhatIf   # dry run, shows what would change
#>
param(
    [switch]$WhatIf
)

$profilesRoot = Join-Path $env:USERPROFILE ".claude-profiles"

if (-not (Test-Path $profilesRoot)) {
    Write-Error "Profiles root not found: $profilesRoot"
    exit 1
}

$profileDirs = Get-ChildItem -Path $profilesRoot -Directory | Where-Object { $_.Name -match '^user\d+$' }

if (-not $profileDirs) {
    Write-Warning "No userN profile directories found under $profilesRoot"
    exit 0
}

$summary = @()

foreach ($dir in $profileDirs) {
    $configPath = Join-Path $dir.FullName "claude_desktop_config.json"

    if (-not (Test-Path $configPath)) {
        $summary += [PSCustomObject]@{ Profile = $dir.Name; Status = "config not found"; Accounts = "" }
        continue
    }

    try {
        $raw = Get-Content -Path $configPath -Raw -Encoding UTF8
        $json = $raw | ConvertFrom-Json -Depth 100
    } catch {
        $summary += [PSCustomObject]@{ Profile = $dir.Name; Status = "parse error: $($_.Exception.Message)"; Accounts = "" }
        continue
    }

    $gate = $json.preferences.bypassPermissionsGateByAccount

    if (-not $gate) {
        $summary += [PSCustomObject]@{ Profile = $dir.Name; Status = "no bypassPermissionsGateByAccount key"; Accounts = "" }
        continue
    }

    $accountIds = ($gate | Get-Member -MemberType NoteProperty).Name
    if (-not $accountIds) {
        $summary += [PSCustomObject]@{ Profile = $dir.Name; Status = "no accounts under key"; Accounts = "" }
        continue
    }

    $changed = $false
    foreach ($id in $accountIds) {
        if ($gate.$id -ne $true) {
            $gate.$id = $true
            $changed = $true
        }
    }

    if ($WhatIf) {
        $summary += [PSCustomObject]@{ Profile = $dir.Name; Status = if ($changed) { "would update" } else { "already true" }; Accounts = ($accountIds -join ", ") }
        continue
    }

    if ($changed) {
        # backup before writing
        Copy-Item -Path $configPath -Destination "$configPath.bak" -Force
        $json | ConvertTo-Json -Depth 100 | Set-Content -Path $configPath -Encoding UTF8
        $summary += [PSCustomObject]@{ Profile = $dir.Name; Status = "updated (backup saved)"; Accounts = ($accountIds -join ", ") }
    } else {
        $summary += [PSCustomObject]@{ Profile = $dir.Name; Status = "already true"; Accounts = ($accountIds -join ", ") }
    }
}

$summary | Format-Table -AutoSize