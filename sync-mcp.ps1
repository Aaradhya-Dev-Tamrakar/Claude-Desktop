<#
.SYNOPSIS
    Force-syncs shared MCP servers from team-mcp.json into all Claude Desktop profiles
    (and the active native AppData Claude configuration) without launching Claude Desktop.

.DESCRIPTION
    Reads team-mcp.json at repo root, expands {{REPO_ROOT}} placeholders to the current
    clone path, and merges the shared mcpServers into claude_desktop_config.json for:
      1. Every user profile under %USERPROFILE%\.claude-profiles (e.g. user1..userN)
      2. The active native AppData Claude directory (if present)

    Existing profile-specific MCP servers and non-MCP settings (e.g. preferences)
    are preserved. Shared MCP servers take precedence on key collision.

.USAGE
    .\sync-mcp.ps1
    .\sync-mcp.ps1 -WhatIf          # Dry run showing what would be updated
    .\sync-mcp.ps1 -Users user1,user2 # Only sync specific profile(s)
#>
param(
    [string[]]$Users,
    [switch]$WhatIf
)

$RepoRoot = $PSScriptRoot
$SharedConfigPath = Join-Path $RepoRoot "team-mcp.json"

function Write-McpBanner {
    param([string]$Title, [string]$Subtitle)
    Write-Host "" 
    Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║ $($Title.PadRight(46, ' ')) ║" -ForegroundColor Green
    Write-Host "║ $($Subtitle.Substring(0, [Math]::Min($Subtitle.Length, 46)).PadRight(46, ' ')) ║" -ForegroundColor DarkGray
    Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host "" 
}

Write-McpBanner -Title "MCP Sync" -Subtitle "Shared config -> profile configs"

if (-not (Test-Path $SharedConfigPath)) {
    Write-Host "[!] team-mcp.json not found at '$SharedConfigPath'." -ForegroundColor Red
    exit 1
}

# Parse team-mcp.json
try {
    $SharedConfig = Get-Content $SharedConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
}
catch {
    Write-Host "[!] team-mcp.json is not valid JSON ($_)." -ForegroundColor Red
    exit 1
}

if (-not ($SharedConfig.PSObject.Properties.Name -contains "mcpServers")) {
    Write-Host "[!] No 'mcpServers' object found in team-mcp.json." -ForegroundColor Yellow
    exit 0
}

# Expand {{REPO_ROOT}} placeholder
function Expand-TeamMcpPlaceholders {
    param(
        [Parameter(Mandatory = $true)]$Config,
        [Parameter(Mandatory = $true)][string]$Root
    )

    $Expanded = $Config | ConvertTo-Json -Depth 10 | ConvertFrom-Json
    if (-not ($Expanded.PSObject.Properties.Name -contains "mcpServers")) {
        return $Expanded
    }

    $Placeholder = "{{REPO_ROOT}}"

    foreach ($serverName in $Expanded.mcpServers.PSObject.Properties.Name) {
        $server = $Expanded.mcpServers.$serverName

        if ($server.PSObject.Properties.Name -contains "command" -and $server.command -is [string]) {
            $server.command = $server.command.Replace($Placeholder, $Root)
        }

        if ($server.PSObject.Properties.Name -contains "args" -and $server.args) {
            $server.args = @($server.args)
            for ($i = 0; $i -lt $server.args.Count; $i++) {
                if ($server.args[$i] -is [string]) {
                    $server.args[$i] = $server.args[$i].Replace($Placeholder, $Root)
                }
            }
        }

        if ($server.PSObject.Properties.Name -contains "env" -and $server.env) {
            foreach ($envKey in $server.env.PSObject.Properties.Name) {
                if ($server.env.$envKey -is [string]) {
                    $server.env.$envKey = $server.env.$envKey.Replace($Placeholder, $Root)
                }
            }
        }
    }

    return $Expanded
}

# Merge shared MCP servers into profile config (preserving profile custom configs)
function Merge-McpServers {
    param(
        [Parameter(Mandatory = $true)]$ProfileConfig,
        [Parameter(Mandatory = $true)]$SharedConfig
    )

    $Merged = $ProfileConfig | ConvertTo-Json -Depth 10 | ConvertFrom-Json

    if (-not ($Merged.PSObject.Properties.Name -contains "mcpServers")) {
        $Merged | Add-Member -NotePropertyName "mcpServers" -NotePropertyValue ([PSCustomObject]@{}) -Force
    }

    if ($SharedConfig -and ($SharedConfig.PSObject.Properties.Name -contains "mcpServers")) {
        foreach ($serverName in $SharedConfig.mcpServers.PSObject.Properties.Name) {
            $Merged.mcpServers | Add-Member -NotePropertyName $serverName -NotePropertyValue $SharedConfig.mcpServers.$serverName -Force
        }
    }

    foreach ($serverName in $Merged.mcpServers.PSObject.Properties.Name) {
        $server = $Merged.mcpServers.$serverName
        if ($server.PSObject.Properties.Name -contains "args") {
            $server.args = @($server.args)
        }
    }

    if ($Merged.PSObject.Properties.Name -contains "preferences" -and $Merged.preferences) {
        if ($Merged.preferences.PSObject.Properties.Name -contains "launchPreviewPersistedWorkspaces") {
            if ($null -eq $Merged.preferences.launchPreviewPersistedWorkspaces) {
                $Merged.preferences.launchPreviewPersistedWorkspaces = [System.Collections.ArrayList]::new()
            }
            else {
                $Merged.preferences.launchPreviewPersistedWorkspaces = @($Merged.preferences.launchPreviewPersistedWorkspaces)
            }
        }
    }

    return $Merged
}

$ExpandedShared = Expand-TeamMcpPlaceholders -Config $SharedConfig -Root $RepoRoot
$SharedServerNames = @($ExpandedShared.mcpServers.PSObject.Properties.Name)
$SharedCount = $SharedServerNames.Count

function Format-BannerRow([string]$Text, [int]$Width = 66) {
    if ($Text.Length -gt $Width) {
        $Text = $Text.Substring(0, $Width - 3) + "..."
    }
    return "│ " + $Text.PadRight($Width) + " │"
}

Write-Host ("╭" + ("─" * 68) + "╮") -ForegroundColor Cyan
Write-Host ("│" + "  🔄 Force Syncing MCP Servers to Profiles".PadRight(68) + "│") -ForegroundColor Green
Write-Host ("├" + ("─" * 68) + "┤") -ForegroundColor Cyan
Write-Host (Format-BannerRow " ● Shared Servers ($SharedCount) : $($SharedServerNames -join ', ')") -ForegroundColor Yellow
Write-Host (Format-BannerRow " ● Source Config     : team-mcp.json") -ForegroundColor DarkGray
Write-Host ("╰" + ("─" * 68) + "╯") -ForegroundColor Cyan

# Locate profile directories
$ProfilesRoot = Join-Path $env:USERPROFILE ".claude-profiles"
$TargetDirs = @()

if (Test-Path $ProfilesRoot) {
    $AllProfiles = Get-ChildItem -Path $ProfilesRoot -Directory | Where-Object { $_.Name -match '^user\d+$' }
    
    if ($Users -and $Users.Count -gt 0) {
        $FilteredUsers = @($Users | ForEach-Object { $_ -split '[, ]+' } | Where-Object { $_ })
        $TargetDirs += $AllProfiles | Where-Object { $FilteredUsers -contains $_.Name }
    }
    else {
        $TargetDirs += $AllProfiles
    }
}

# Also sync active native AppData config if it exists
$NativeAppDataDir = "$env:LOCALAPPDATA\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude"
if (-not (Test-Path (Split-Path $NativeAppDataDir -Parent))) {
    $NativeAppDataDir = "$env:APPDATA\Claude"
}
$NativeTarget = $null
if (Test-Path $NativeAppDataDir) {
    $NativeTarget = $NativeAppDataDir
}

$SuccessCount = 0
$ErrorCount = 0

function Sync-ConfigToDir([string]$DirName, [string]$DirPath) {
    $ConfigFile = Join-Path $DirPath "claude_desktop_config.json"
    $ExistingConfig = [PSCustomObject]@{}

    if (Test-Path $ConfigFile) {
        try {
            $ExistingConfig = Get-Content $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
        }
        catch {
            Write-Warning "Existing config in '$DirName' is invalid JSON. Overwriting MCP section."
            $ExistingConfig = [PSCustomObject]@{}
        }
    }

    try {
        $Merged = Merge-McpServers -ProfileConfig $ExistingConfig -SharedConfig $ExpandedShared
        
        if ($WhatIf) {
            Write-Host "  [WhatIf] Would sync '$DirName' -> $ConfigFile" -ForegroundColor DarkCyan
        }
        else {
            if (-not (Test-Path $DirPath)) {
                New-Item -ItemType Directory -Force -Path $DirPath | Out-Null
            }
            $Merged | ConvertTo-Json -Depth 10 | Set-Content $ConfigFile -Encoding UTF8
            Write-Host "  [✓] Synced '$DirName'" -ForegroundColor Green
        }
        $script:SuccessCount++
    }
    catch {
        Write-Host "  [✗] Failed to sync '$DirName': $_" -ForegroundColor Red
        $script:ErrorCount++
    }
}

Write-Host "`nSyncing Profiles:" -ForegroundColor Cyan
foreach ($pDir in $TargetDirs) {
    Sync-ConfigToDir -DirName $pDir.Name -DirPath $pDir.FullName
}

if ($NativeTarget -and (-not $Users)) {
    Write-Host "`nSyncing Active Native AppData:" -ForegroundColor Cyan
    Sync-ConfigToDir -DirName "Active Native AppData" -DirPath $NativeTarget
}

Write-Host "`n──────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
if ($WhatIf) {
    Write-Host "Dry run completed: $SuccessCount target(s) would be updated." -ForegroundColor DarkCyan
}
else {
    Write-Host "Sync completed: $SuccessCount succeeded, $ErrorCount failed." -ForegroundColor Green
}
