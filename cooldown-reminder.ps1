<#
.SYNOPSIS
    Schedules a local toast notification and tracks cooldown for Claude Desktop profiles.

.DESCRIPTION
    Called by launch_user_n.ps1 after a successful (non-WhatIf) login.
    
    Core responsibilities:
    1. Track first_login_time (set once, never overwritten after initial profile creation)
    2. Anchor the 5-hour cooldown to first_login_time, NOT to this call's LoginTime —
       the window must reflect the actual first login of the cycle even across
       repeated relogins within the same 5-hour period.
    3. Display cooldown time remaining until next login is available
    4. Register Windows toast alarm via BurntToast (local, no external dependencies)
    5. Google Calendar integration paused for now (infrastructure ready, not invoked)

    Failures in notification or tracking paths are logged to Write-Warning and do not
    stop the caller — a broken notification integration must never block launching Claude Desktop.

.PARAMETER LoginTime
    [datetime] This login's timestamp. Used to seed first_login_time on a profile's
    very first login, and as the display/WhatIf value. The 5-hour cooldown itself
    counts from first_login_time (recorded once per cycle), not from this value —
    see Update-FirstLoginDate and CooldownAnchorTime below.

.PARAMETER Nickname
    Profile nickname, used in notification/event text.

.PARAMETER ConfigFile
    Path to profiles.json. Used to update first_login_time and track cooldown state.

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
$ScriptDir = $PSScriptRoot

# ---------------------------------------------------------------------------
# 0. Track first_login_time (immutable once set for each profile) and return
#    the anchor the 5-hour cooldown counts from.
#
#    Stored as a full timestamp ("yyyy-MM-dd HH:mm:ss"), not date-only —
#    date-only precision can't anchor an hour-level window. Legacy rows that
#    still carry the old date-only "first_login_date" property are migrated
#    in place on next login (see migration block below) rather than requiring
#    a separate one-off script, since every login already goes through this
#    mutex-locked read/write path.
# ---------------------------------------------------------------------------
function Update-FirstLoginDate {
    param([string]$ConfigPath, [string]$ProfileName, [datetime]$LoginTime)

    # Named Mutex serializes read-modify-write across separate processes.
    # Required because -Concurrent launches run as independent PowerShell
    # processes that can call this function at the same instant — without a
    # lock, two processes can each read a stale copy of profiles.json, and
    # whichever writes last silently discards the other's update (its own
    # first_login_time, or launch_user_n.ps1's last_login_date/time write
    # that landed just before this call). "Global\" scopes the mutex across
    # all user sessions on the machine, matching the shared-file scope.
    $MutexName = "Global\ClaudeDesktopProfilesJsonLock"
    $Mutex = $null
    $AcquiredLock = $false

    try {
        $Mutex = New-Object System.Threading.Mutex($false, $MutexName)
        try {
            $AcquiredLock = $Mutex.WaitOne([TimeSpan]::FromSeconds(10))
        }
        catch [System.Threading.AbandonedMutexException] {
            # A previous holder crashed while holding the lock without releasing
            # it. .NET still grants ownership to this thread despite raising the
            # exception, so we DO hold the lock — proceed normally rather than
            # treating this as a failure. (Realistic here: profile-switch logic
            # elsewhere in this codebase force-kills Claude processes, and a
            # PowerShell process could be killed mid-write the same way.)
            $AcquiredLock = $true
        }
        if (-not $AcquiredLock) {
            Write-Warning "cooldown-reminder: timed out waiting for profiles.json lock (10s). Skipping first_login_time tracking this run. Falling back to this login's time as the cooldown anchor."
            return $LoginTime
        }

        $AllProfiles = Get-Content $ConfigPath -Raw | ConvertFrom-Json
        $TargetProfile = $AllProfiles.$ProfileName

        if (-not $TargetProfile) {
            Write-Warning "cooldown-reminder: profile '$ProfileName' not found in '$ConfigPath'. Skipping first_login_time tracking. Falling back to this login's time as the cooldown anchor."
            return $LoginTime
        }

        $NeedsWrite = $false
        $AnchorTime = $null

        if ($TargetProfile.first_login_time) {
            # Anchor already recorded for this cycle — parse and reuse it.
            # Round-trip format matches what we write below.
            $AnchorTime = [datetime]::ParseExact($TargetProfile.first_login_time, "yyyy-MM-dd HH:mm:ss", $null)
        }
        elseif ($TargetProfile.first_login_date) {
            # Legacy date-only property from before first_login_time existed.
            # Migrate in place: date-only precision can't anchor an hour-level
            # cooldown, so treat this login as the new anchor and drop the
            # stale property (first_login_time supersedes it).
            $AnchorTime = $LoginTime
            $TargetProfile.PSObject.Properties.Remove("first_login_date")
            $NeedsWrite = $true
        }
        else {
            # True first login for this profile/cycle.
            $AnchorTime = $LoginTime
            $NeedsWrite = $true
        }

        if ($NeedsWrite) {
            $FirstLoginTimeStr = $AnchorTime.ToString("yyyy-MM-dd HH:mm:ss")
            $TargetProfile | Add-Member -NotePropertyName "first_login_time" -NotePropertyValue $FirstLoginTimeStr -Force

            # Atomic write: serialize to a temp file, then move into place, so a
            # crash mid-write cannot corrupt profiles.json for all profiles.
            $TempPath = "$ConfigPath.tmp"
            $AllProfiles | ConvertTo-Json -Depth 5 | Set-Content $TempPath -Encoding UTF8
            Move-Item -Path $TempPath -Destination $ConfigPath -Force

            Write-Host "[+] Profile first login time recorded: $FirstLoginTimeStr" -ForegroundColor Green
        }

        return $AnchorTime
    }
    catch {
        Write-Warning "cooldown-reminder: failed to track first_login_time ($_). Falling back to this login's time as the cooldown anchor."
        return $LoginTime
    }
    finally {
        if ($AcquiredLock) {
            $Mutex.ReleaseMutex()
        }
        if ($Mutex) {
            $Mutex.Dispose()
        }
    }
}

# ---------------------------------------------------------------------------
# 1. Local toast alarm via a self-deleting Scheduled Task
# ---------------------------------------------------------------------------
function Register-CooldownToast {
    param([datetime]$ReadyTime, [string]$Nickname)

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

    # Calculate and display time remaining until cooldown expires.
    # Guard against a past/zero ReadyTime (e.g. script re-run after cooldown
    # already elapsed) so output reads "0h 0m / already available" instead of
    # a confusing negative duration.
    $Now = Get-Date
    $TimeRemaining = $ReadyTime - $Now
    if ($TimeRemaining.TotalSeconds -le 0) {
        Write-Host "[i] Cooldown already elapsed — profile is available now." -ForegroundColor Cyan
        Write-Host "[i] Skipping toast alarm registration (nothing to wait for)." -ForegroundColor DarkGray
        return
    }
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

# Track first login time (immutable per profile) and get the cooldown anchor.
# ReadyTime is computed from the anchor (this profile's first login of the
# current 5-hour cycle), NOT from this call's $LoginTime — so relogging in
# partway through the window doesn't push the ready time back out.
$CooldownAnchorTime = Update-FirstLoginDate -ConfigPath $ConfigFile -ProfileName $ProfileName -LoginTime $LoginTime
$ReadyTime = $CooldownAnchorTime.AddHours($CooldownHours)

# Once the window has fully elapsed, this login starts a new cycle — reset
# the anchor to now so the next 5-hour window is measured from here, not
# from whenever the previous cycle originally began.
if ($LoginTime -ge $ReadyTime) {
    $CooldownAnchorTime = $LoginTime
    $ReadyTime = $CooldownAnchorTime.AddHours($CooldownHours)
    try {
        $ResetTimeStr = $CooldownAnchorTime.ToString("yyyy-MM-dd HH:mm:ss")
        $MutexName = "Global\ClaudeDesktopProfilesJsonLock"
        $Mutex = New-Object System.Threading.Mutex($false, $MutexName)
        $AcquiredLock = $false
        try {
            $AcquiredLock = $Mutex.WaitOne([TimeSpan]::FromSeconds(10))
        }
        catch [System.Threading.AbandonedMutexException] {
            $AcquiredLock = $true
        }
        if ($AcquiredLock) {
            $AllProfiles = Get-Content $ConfigFile -Raw | ConvertFrom-Json
            $TargetProfile = $AllProfiles.$ProfileName
            if ($TargetProfile) {
                $TargetProfile | Add-Member -NotePropertyName "first_login_time" -NotePropertyValue $ResetTimeStr -Force
                $TempPath = "$ConfigFile.tmp"
                $AllProfiles | ConvertTo-Json -Depth 5 | Set-Content $TempPath -Encoding UTF8
                Move-Item -Path $TempPath -Destination $ConfigFile -Force
                Write-Host "[i] Previous cooldown cycle elapsed — new cycle anchored at $ResetTimeStr" -ForegroundColor Cyan
            }
            $Mutex.ReleaseMutex()
        }
        else {
            Write-Warning "cooldown-reminder: timed out waiting for profiles.json lock (10s) while resetting elapsed cooldown cycle. Anchor will re-reset on next login."
        }
    }
    catch {
        Write-Warning "cooldown-reminder: failed to persist new cooldown cycle anchor ($_). Anchor will re-reset on next login."
    }
    finally {
        if ($Mutex) { $Mutex.Dispose() }
    }
}

# Register local toast alarm (default on, shows cooldown time remaining)
if (-not $DisableToast) {
    Register-CooldownToast -ReadyTime $ReadyTime -Nickname $Nickname
}

# GCal integration paused (not invoked by default; uncomment if $EnableGCal to re-enable)
# if ($EnableGCal) {
#     New-CooldownCalendarEvent -ReadyTime $ReadyTime -Nickname $Nickname -ScriptDir $ScriptDir
# }