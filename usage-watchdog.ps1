<#
.SYNOPSIS
    Polls the Claude Desktop tray flyout for "Usage: NN%" via Windows UI
    Automation and auto-checkpoints the running account to orchestrator-mcp
    once usage crosses -Threshold (default 80).

.DESCRIPTION
    There is no local file, API, or CLI exposing live per-account usage —
    the only place it's rendered is the tray icon's right-click flyout menu
    (see the "Free plan / Usage: NN%" row). This script automates reading
    that flyout via System.Windows.Automation (UIA), the same accessibility
    tree screen readers use, rather than OCR or pixel-scraping — UIA survives
    minor UI reflows; it breaks only if Anthropic renames/restructures the
    menu's automation tree, not on a cosmetic style change. That fragility
    is real and accepted (see README caveat this script is documented under).

    On threshold breach, calls push_live_status + push_memory_entry directly
    against orchestrator-mcp's run_server.py (imported as a module, not
    invoked as an MCP tool over stdio — this runs headless with no live chat
    session to make the tool call from). This is a local file write exactly
    like a chat-invoked call would produce; sync.ps1 carries it to every
    other profile on the next pull, same as any other push_memory_entry.

    Fires once per cooldown cycle (tracked in profiles.json alongside
    first_login_time) so it doesn't spam a checkpoint every poll interval
    once past threshold.

.PARAMETER Account
    Profile account name (profiles.json key) to attribute the checkpoint to.
    Required — orchestrator-mcp entries are meaningless without an owner.

.PARAMETER Threshold
    Usage percent to trigger at. Default 80.

.PARAMETER IntervalSeconds
    Poll interval. Default 120 (2 min) — frequent enough to catch the
    threshold without hammering UI Automation.

.PARAMETER Once
    Poll a single time and exit, instead of looping. Useful for testing
    or for driving this from Task Scheduler instead of a long-lived loop.

.PARAMETER WhatIf
    Detect and report threshold breach without calling push_live_status /
    push_memory_entry or writing to profiles.json.

.EXAMPLE
    pwsh -File .\usage-watchdog.ps1 -Account aaradhya

.EXAMPLE
    pwsh -File .\usage-watchdog.ps1 -Account aaradhya -Once -WhatIf
#>

param(
    [Parameter(Mandatory = $true)][string]$Account,
    [int]$Threshold = 80,
    [int]$IntervalSeconds = 120,
    [switch]$Once,
    [switch]$WhatIf
)

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$RepoRoot = $PSScriptRoot
$ProfilesPath = Join-Path $RepoRoot "profiles.json"

function Get-ClaudeTrayUsagePercent {
    # Opens the Claude Desktop tray flyout and reads the "Usage: NN%" text
    # via UI Automation. Returns $null (not 0) on any failure — callers
    # must not treat "couldn't read it" as "usage is zero".
    #
    # NOTE ON FRAGILITY: this walks the tray flyout's automation tree
    # looking for a text node matching 'Usage:\s*(\d{1,3})%'. If Claude
    # Desktop's tray UI is restructured (different control type, renamed
    # automation id, usage moved out of the flyout entirely), this returns
    # $null every time until updated — it does not throw, so the caller's
    # WhatIf/logging path stays informative rather than crashing the loop.
    try {
        $ClaudeProcess = Get-Process -Name "claude" -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $ClaudeProcess) {
            Write-Verbose "usage-watchdog: no running 'claude' process found."
            return $null
        }

        # Locate the tray icon via the taskbar notification area's automation
        # tree rather than simulating a physical click coordinate (which
        # breaks the moment screen resolution/DPI/icon order changes).
        $Root = [System.Windows.Automation.AutomationElement]::RootElement
        $TrayCondition = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ClassNameProperty, "NotifyIconOverflowWindow"
        )
        $TrayWindow = $Root.FindFirst([System.Windows.Automation.TreeScope]::Children, $TrayCondition)
        if (-not $TrayWindow) {
            # Icon may be visible (not overflowed) — fall back to scanning
            # the main taskbar tray host instead of the overflow flyout.
            $TrayHostCondition = New-Object System.Windows.Automation.PropertyCondition(
                [System.Windows.Automation.AutomationElement]::ClassNameProperty, "TrayNotifyWnd"
            )
            $TrayWindow = $Root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $TrayHostCondition)
        }
        if (-not $TrayWindow) {
            Write-Verbose "usage-watchdog: could not locate tray notification area in the automation tree."
            return $null
        }

        $NameCondition = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::NameProperty, "Claude"
        )
        $ClaudeIcon = $TrayWindow.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $NameCondition)
        if (-not $ClaudeIcon) {
            Write-Verbose "usage-watchdog: Claude tray icon not found by name 'Claude'."
            return $null
        }

        # Invoke a right-click via the Invoke/ExpandCollapse pattern rather
        # than SendKeys/mouse-coordinate simulation, so this doesn't depend
        # on the window having OS input focus or being on the primary monitor.
        $InvokePattern = $ClaudeIcon.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
        if (-not $InvokePattern) {
            Write-Verbose "usage-watchdog: tray icon does not support InvokePattern; cannot open flyout headlessly."
            return $null
        }
        $InvokePattern.Invoke()
        Start-Sleep -Milliseconds 400  # let the flyout render before walking it

        $MenuCondition = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Menu
        )
        $Menu = $Root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $MenuCondition)
        if (-not $Menu) {
            Write-Verbose "usage-watchdog: tray flyout menu did not appear within timeout."
            return $null
        }

        $TextCondition = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Text
        )
        $TextNodes = $Menu.FindAll([System.Windows.Automation.TreeScope]::Descendants, $TextCondition)

        $UsagePercent = $null
        foreach ($node in $TextNodes) {
            $name = $node.Current.Name
            if ($name -match 'Usage:\s*(\d{1,3})%') {
                $UsagePercent = [int]$Matches[1]
                break
            }
        }

        # Close the flyout so it doesn't sit open stealing focus.
        [System.Windows.Forms.SendKeys]::SendWait("{ESC}")

        return $UsagePercent
    }
    catch {
        Write-Warning "usage-watchdog: UI Automation read failed ($_). Treating as unreadable this poll."
        return $null
    }
}

function Test-CheckpointAlreadyFiredThisCycle {
    # Reuses first_login_time as the cycle anchor (same anchor cooldown-reminder.ps1
    # uses) so "fired this cycle" resets naturally on the same 5h boundary the
    # cooldown itself resets on, without a second independent timer to drift
    # out of sync with the real cooldown window.
    param([string]$Account, [string]$ProfilesPath)

    if (-not (Test-Path $ProfilesPath)) { return $false }
    try {
        $Profiles = Get-Content $ProfilesPath -Raw | ConvertFrom-Json
    }
    catch {
        Write-Warning "usage-watchdog: failed to read profiles.json ($_). Assuming not yet fired."
        return $false
    }
    $TargetProfile = $Profiles.$Account
    if (-not $TargetProfile) { return $false }
    if (-not $TargetProfile.first_login_time) { return $false }
    return ($TargetProfile.last_watchdog_cycle -eq $TargetProfile.first_login_time)
}

function Set-CheckpointFiredThisCycle {
    param([string]$Account, [string]$ProfilesPath)

    try {
        $Profiles = Get-Content $ProfilesPath -Raw | ConvertFrom-Json
        $TargetProfile = $Profiles.$Account
        if (-not $TargetProfile) { return }
        $Anchor = $TargetProfile.first_login_time
        $TargetProfile | Add-Member -NotePropertyName "last_watchdog_cycle" -NotePropertyValue $Anchor -Force
        $Profiles | ConvertTo-Json -Depth 10 | Set-Content -Path $ProfilesPath -Encoding utf8
    }
    catch {
        Write-Warning "usage-watchdog: failed to persist last_watchdog_cycle ($_). May re-fire next poll."
    }
}

function Invoke-AutoCheckpoint {
    # Calls push_live_status + push_memory_entry directly against
    # run_server.py's Python functions (imported, not invoked over MCP
    # stdio — there is no live chat turn here to make a tool call from).
    # Writes land as ordinary orchestrator-state files; sync.ps1's
    # Sync-OrchestratorMemoryToTeamMemory mirrors the memory entry into
    # team-memory.md on the next sync, same as any chat-invoked push.
    param([string]$Account, [int]$UsagePercent, [string]$RepoRoot, [switch]$WhatIf)

    $Note = "usage-watchdog: auto-checkpoint at ${UsagePercent}% usage (threshold reached)."
    if ($WhatIf) {
        Write-Host "[WhatIf] Would push_live_status + push_memory_entry for '$Account': `"$Note`"" -ForegroundColor DarkCyan
        return
    }

    $ServerScript = Join-Path $RepoRoot "mcp-servers\orchestrator-mcp\run_server.py"
    if (-not (Test-Path $ServerScript)) {
        Write-Warning "usage-watchdog: run_server.py not found at '$ServerScript'. Skipping checkpoint."
        return
    }

    $PyCode = @"
import sys
sys.path.insert(0, r'$(Split-Path $ServerScript -Parent)')
from run_server import push_live_status, push_memory_entry

account = r'''$Account'''
note = r'''$Note'''
push_live_status(account=account, current_task_id=None, note=note)
push_memory_entry(account=account, text=note)
print('usage-watchdog: checkpoint pushed OK.')
"@

    try {
        $Result = $PyCode | python3 - 2>&1
        Write-Host "[+] $Result" -ForegroundColor Green
    }
    catch {
        Write-Warning "usage-watchdog: checkpoint push failed ($_). Task 2's whole point is this NOT silently failing near a limit — check manually."
    }
}

function Invoke-WatchdogPoll {
    param([string]$Account, [int]$Threshold, [string]$RepoRoot, [string]$ProfilesPath, [switch]$WhatIf)

    $Usage = Get-ClaudeTrayUsagePercent
    if ($null -eq $Usage) {
        Write-Host "[i] usage-watchdog: could not read usage this poll (see -Verbose for detail)." -ForegroundColor Gray
        return
    }
    Write-Host "[i] usage-watchdog: '$Account' at ${Usage}% (threshold ${Threshold}%)" -ForegroundColor Gray

    if ($Usage -lt $Threshold) { return }

    if (Test-CheckpointAlreadyFiredThisCycle -Account $Account -ProfilesPath $ProfilesPath) {
        Write-Verbose "usage-watchdog: threshold already handled this cooldown cycle for '$Account'. Skipping re-fire."
        return
    }

    Invoke-AutoCheckpoint -Account $Account -UsagePercent $Usage -RepoRoot $RepoRoot -WhatIf:$WhatIf
    if (-not $WhatIf) {
        Set-CheckpointFiredThisCycle -Account $Account -ProfilesPath $ProfilesPath
    }
}

if ($Once) {
    Invoke-WatchdogPoll -Account $Account -Threshold $Threshold -RepoRoot $RepoRoot -ProfilesPath $ProfilesPath -WhatIf:$WhatIf
}
else {
    Write-Host "[usage-watchdog] Polling every ${IntervalSeconds}s for '$Account', threshold ${Threshold}%. Ctrl+C to stop." -ForegroundColor Cyan
    while ($true) {
        Invoke-WatchdogPoll -Account $Account -Threshold $Threshold -RepoRoot $RepoRoot -ProfilesPath $ProfilesPath -WhatIf:$WhatIf
        Start-Sleep -Seconds $IntervalSeconds
    }
}
