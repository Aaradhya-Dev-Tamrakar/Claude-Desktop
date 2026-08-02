<#
.SYNOPSIS
    Schedules a local toast notification and tracks cooldown for Claude Desktop profiles.

.DESCRIPTION
    Called by launch_user_n.ps1 after a successful (non-WhatIf) login.
    
    Core responsibilities:
    1. Track first_login_date (set once, never overwritten after initial profile creation)
    2. Display cooldown time remaining until next login is available
    3. Register Windows toast alarm via BurntToast (local, no external dependencies)
    4. Google Calendar integration paused for now (infrastructure ready, not invoked)

    Failures in notification or tracking paths are logged to Write-Warning and do not
    stop the caller — a broken notification integration must never block launching Claude Desktop.

.PARAMETER LoginTime
    [datetime] The login timestamp the 5-hour cooldown counts from.

.PARAMETER Nickname
    Profile nickname, used in notification/event text.

.PARAMETER ConfigFile
    Path to profiles.json. Used to update first_login_date and track cooldown state.

.PARAMETER DisableToast
    Switch. Suppress the Windows toast notification when the cooldown expires.
    Toast is shown by default; pass -DisableToast to opt out.

.PARAMETER EnableGCal
    Switch. (Currently paused—not invoked by default; infrastructure remains for future use.)
#>
param (
    [Parameter(Mandatory = $true)][datetime]$LoginTime,
    [Parameter(Mandatory = $true)][string]$Nickname,
    [Parameter(Mandatory = $true)][string]$ProfileName,
    [Parameter(Mandatory = $true)][string]$ConfigFile,
    [switch]$DisableToast,
    [switch]$EnableGCal
)

$CooldownHours = 5
$ReadyTime = $LoginTime.AddHours($CooldownHours)
$ScriptDir = $PSScriptRoot

# ---------------------------------------------------------------------------
# 0. Track first_login_date (immutable once set for each profile)
# ---------------------------------------------------------------------------
function Update-FirstLoginDate {
    param([string]$ConfigPath, [string]$ProfileName, [datetime]$LoginTime)
    
    try {
        $Profiles = Get-Content $ConfigPath -Raw | ConvertFrom-Json
        $Profile = $Profiles.$ProfileName
        
        if (-not $Profile.first_login_date) {
            $FirstLoginDate = $LoginTime.ToString("yyyy-MM-dd")
            $Profile | Add-Member -NotePropertyName "first_login_date" -NotePropertyValue $FirstLoginDate -Force
            $Profiles | ConvertTo-Json -Depth 5 | Set-Content $ConfigPath -Encoding UTF8
            Write-Host "[+] Profile first login date recorded: $FirstLoginDate" -ForegroundColor Green
        }
    }
    catch {
        Write-Warning "cooldown-reminder: failed to track first_login_date ($_). Continuing."
    }
}

# ---------------------------------------------------------------------------
# 1. Local toast alarm via a self-deleting Scheduled Task
# ---------------------------------------------------------------------------
function Register-CooldownToast {
    param([datetime]$LoginTime, [datetime]$ReadyTime, [string]$Nickname)

    if (-not (Get-Module -ListAvailable -Name BurntToast)) {
        try {
            Install-Module -Name BurntToast -Scope CurrentUser -Force -ErrorAction Stop
        }
        catch {
            Write-Warning "cooldown-reminder: BurntToast not available and install failed ($_). Skipping toast alarm."
            return
        }
    }

    $TaskName = "ClaudeCooldown_$($Nickname)_$($ReadyTime.ToString('yyyyMMddHHmmss'))"
    $ToastText = "Claude cooldown ready for '$Nickname' — you can log back in now."
    
    # Calculate and display time remaining until cooldown expires
    $Now = Get-Date
    $TimeRemaining = $ReadyTime - $Now
    $HoursRemaining = [Math]::Floor($TimeRemaining.TotalHours)
    $MinutesRemaining = $TimeRemaining.Minutes
    
    Write-Host "[i] Cooldown time remaining: $HoursRemaining h $MinutesRemaining min (expires $($ReadyTime.ToString('yyyy-MM-dd HH:mm:ss')))" -ForegroundColor Cyan

    # Inline PowerShell payload for the scheduled task: fire the toast, then
    # unregister itself so these don't accumulate in Task Scheduler.
    $Payload = "Import-Module BurntToast; New-BurntToastNotification -Text 'Claude Desktop', '$ToastText'; Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
    $EncodedPayload = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($Payload))

    try {
        $Action = New-ScheduledTaskAction -Execute "pwsh.exe" -Argument "-NoProfile -WindowStyle Hidden -EncodedCommand $EncodedPayload"
        $Trigger = New-ScheduledTaskTrigger -Once -At $ReadyTime
        Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Description "One-shot Claude cooldown alarm for '$Nickname'." -Force | Out-Null
        Write-Host "[+] Local toast alarm registered (fires in $HoursRemaining h $MinutesRemaining min)" -ForegroundColor Green
    }
    catch {
        Write-Warning "cooldown-reminder: failed to register scheduled task ($_). Skipping toast alarm."
    }
}

# ---------------------------------------------------------------------------
# 2. Google Calendar event (opt-in, PAUSED FOR NOW — infrastructure preserved)
# ---------------------------------------------------------------------------
# GCal integration is infrastructure-ready (token refresh, OAuth loopback, event
# creation) but intentionally not invoked (EnableGCal switch not passed).
# Uncomment and call New-CooldownCalendarEvent to re-enable.
#
# Previous function code archived in git history; will restore on re-enablement.
function New-CooldownCalendarEvent {
    param([datetime]$ReadyTime, [string]$Nickname, [string]$ScriptDir)
    Write-Host "[i] Google Calendar integration paused (infrastructure ready for future use)." -ForegroundColor DarkGray
}

# Track first login date (immutable per profile)
Update-FirstLoginDate -ConfigPath $ConfigFile -ProfileName $ProfileName -LoginTime $LoginTime

# Register local toast alarm (default on, shows cooldown time remaining)
if (-not $DisableToast) {
    Register-CooldownToast -LoginTime $LoginTime -ReadyTime $ReadyTime -Nickname $Nickname
}

# GCal integration paused (not invoked by default; uncomment if $EnableGCal to re-enable)
# if ($EnableGCal) {
#     New-CooldownCalendarEvent -ReadyTime $ReadyTime -Nickname $Nickname -ScriptDir $ScriptDir
# }