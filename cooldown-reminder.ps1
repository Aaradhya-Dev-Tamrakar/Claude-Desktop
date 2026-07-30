<#
.SYNOPSIS
    Schedules a local toast notification and (optionally) a Google Calendar
    event for when a profile's 5-hour cooldown expires.

.DESCRIPTION
    Called by launch_user_n.ps1 after a successful (non-WhatIf) login.
    Two independent notification paths, each best-effort / non-blocking:

    1. Toast alarm (default on): a Windows Scheduled Task is registered to
       fire a BurntToast notification at $LoginTime.AddHours(5), then
       delete itself. No auth, no external calls.

    2. Google Calendar event (opt-in): creates an event on the user's
       primary calendar titled "Claude cooldown ready — <Nickname>" at the
       same timestamp. Requires gcal-credentials.json (OAuth installed-app
       client secret) in this directory — gitignored, never committed.
       First run opens a browser consent screen; the resulting token is
       cached to gcal-token.json (also gitignored) and reused silently
       after that.

    Failures in either path are logged to Write-Warning and do not stop
    the caller — a broken notification integration must never block
    launching Claude Desktop.

.PARAMETER LoginTime
    [datetime] The login timestamp the 5-hour cooldown counts from.

.PARAMETER Nickname
    Profile nickname, used in notification/event text.

.PARAMETER DisableToast
    Switch. Suppress the Windows toast notification when the cooldown expires.
    Toast is shown by default; pass -DisableToast to opt out.

.PARAMETER EnableGCal
    Switch. Attempt to create the Google Calendar event. Off by default —
    requires gcal-credentials.json to be present; silently skipped (with a
    one-line notice) if the file is missing, so this is safe to always pass.
#>
param (
    [Parameter(Mandatory = $true)][datetime]$LoginTime,
    [Parameter(Mandatory = $true)][string]$Nickname,
    [switch]$DisableToast,
    [switch]$EnableGCal
)

$CooldownHours = 5
$ReadyTime = $LoginTime.AddHours($CooldownHours)
$ScriptDir = $PSScriptRoot

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

    # Inline PowerShell payload for the scheduled task: fire the toast, then
    # unregister itself so these don't accumulate in Task Scheduler.
    $Payload = "Import-Module BurntToast; New-BurntToastNotification -Text 'Claude Desktop', '$ToastText'; Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
    $EncodedPayload = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($Payload))

    try {
        $Action = New-ScheduledTaskAction -Execute "pwsh.exe" -Argument "-NoProfile -WindowStyle Hidden -EncodedCommand $EncodedPayload"
        $Trigger = New-ScheduledTaskTrigger -Once -At $ReadyTime
        Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Description "One-shot Claude cooldown alarm for '$Nickname'." -Force | Out-Null
        Write-Host "[+] Cooldown alarm scheduled for $($ReadyTime.ToString('yyyy-MM-dd HH:mm:ss')) (task: $TaskName)." -ForegroundColor Green
    }
    catch {
        Write-Warning "cooldown-reminder: failed to register scheduled task ($_). Skipping toast alarm."
    }
}

# ---------------------------------------------------------------------------
# 2. Google Calendar event (opt-in, requires local OAuth credentials)
# ---------------------------------------------------------------------------
function New-CooldownCalendarEvent {
    param([datetime]$ReadyTime, [string]$Nickname, [string]$ScriptDir)

    $CredPath = Join-Path $ScriptDir "gcal-credentials.json"
    $TokenPath = Join-Path $ScriptDir "gcal-token.json"

    if (-not (Test-Path $CredPath)) {
        Write-Host "[i] gcal-credentials.json not found — skipping Google Calendar event. See README for setup." -ForegroundColor DarkGray
        return
    }

    try {
        $Cred = Get-Content $CredPath -Raw | ConvertFrom-Json
        $ClientId = $Cred.installed.client_id
        $ClientSecret = $Cred.installed.client_secret

        $AccessToken = $null

        if (Test-Path $TokenPath) {
            $Token = Get-Content $TokenPath -Raw | ConvertFrom-Json
            if ($Token.expiry -and ([datetime]$Token.expiry -gt (Get-Date))) {
                $AccessToken = $Token.access_token
            }
            elseif ($Token.refresh_token) {
                $RefreshBody = @{
                    client_id     = $ClientId
                    client_secret = $ClientSecret
                    refresh_token = $Token.refresh_token
                    grant_type    = "refresh_token"
                }
                $RefreshResp = Invoke-RestMethod -Uri "https://oauth2.googleapis.com/token" -Method Post -Body $RefreshBody
                $AccessToken = $RefreshResp.access_token
                $NewToken = @{
                    access_token  = $RefreshResp.access_token
                    refresh_token = $Token.refresh_token
                    expiry        = (Get-Date).AddSeconds($RefreshResp.expires_in).ToString("o")
                }
                $NewToken | ConvertTo-Json | Set-Content $TokenPath -Encoding UTF8
            }
        }

        if (-not $AccessToken) {
            # First-run consent flow. Google deprecated the OOB
            # (urn:ietf:wg:oauth:2.0:oob) copy-paste flow in Jan 2023 — desktop
            # clients must use the loopback IP redirect instead. We spin up a
            # short-lived local HTTP listener, open the consent screen pointed
            # at it, and capture the ?code= Google redirects back with.
            $Listener = New-Object System.Net.HttpListener
            $LoopbackPort = Get-Random -Minimum 49152 -Maximum 65535
            $RedirectUri = "http://127.0.0.1:$LoopbackPort/"
            $Listener.Prefixes.Add($RedirectUri)
            $Listener.Start()

            $AuthUrl = "https://accounts.google.com/o/oauth2/v2/auth?client_id=$ClientId&redirect_uri=$([uri]::EscapeDataString($RedirectUri))&response_type=code&scope=https://www.googleapis.com/auth/calendar.events&access_type=offline&prompt=consent"
            Write-Host "[i] First-time Google Calendar auth — opening browser for consent..." -ForegroundColor Cyan
            Start-Process $AuthUrl

            $Context = $Listener.GetContext()  # blocks until Google redirects back
            $Code = $Context.Request.QueryString["code"]
            $ResponseHtml = "<html><body>Authentication complete — you can close this tab and return to PowerShell.</body></html>"
            $Buffer = [System.Text.Encoding]::UTF8.GetBytes($ResponseHtml)
            $Context.Response.ContentLength64 = $Buffer.Length
            $Context.Response.OutputStream.Write($Buffer, 0, $Buffer.Length)
            $Context.Response.OutputStream.Close()
            $Listener.Stop()

            if (-not $Code) {
                throw "No authorization code received from loopback redirect."
            }

            $TokenBody = @{
                client_id     = $ClientId
                client_secret = $ClientSecret
                code          = $Code
                grant_type    = "authorization_code"
                redirect_uri  = $RedirectUri
            }
            $TokenResp = Invoke-RestMethod -Uri "https://oauth2.googleapis.com/token" -Method Post -Body $TokenBody
            $AccessToken = $TokenResp.access_token
            $NewToken = @{
                access_token  = $TokenResp.access_token
                refresh_token = $TokenResp.refresh_token
                expiry        = (Get-Date).AddSeconds($TokenResp.expires_in).ToString("o")
            }
            $NewToken | ConvertTo-Json | Set-Content $TokenPath -Encoding UTF8
        }

        $EventStart = $ReadyTime.ToString("yyyy-MM-ddTHH:mm:ss")
        $EventEnd = $ReadyTime.AddMinutes(15).ToString("yyyy-MM-ddTHH:mm:ss")
        $TimeZone = [System.TimeZoneInfo]::Local.Id

        $EventBody = @{
            summary     = "Claude cooldown ready — $Nickname"
            description = "5-hour cooldown for profile '$Nickname' has elapsed. You can log back in."
            start       = @{ dateTime = $EventStart; timeZone = $TimeZone }
            end         = @{ dateTime = $EventEnd; timeZone = $TimeZone }
            reminders   = @{ useDefault = $false; overrides = @(@{ method = "popup"; minutes = 0 }) }
        } | ConvertTo-Json -Depth 5

        $Headers = @{ Authorization = "Bearer $AccessToken"; "Content-Type" = "application/json" }
        Invoke-RestMethod -Uri "https://www.googleapis.com/calendar/v3/calendars/primary/events" -Method Post -Headers $Headers -Body $EventBody | Out-Null

        Write-Host "[+] Google Calendar event created for $($ReadyTime.ToString('yyyy-MM-dd HH:mm:ss'))." -ForegroundColor Green
    }
    catch {
        Write-Warning "cooldown-reminder: Google Calendar event creation failed ($_). Continuing without it."
    }
}

if (-not $DisableToast) {
    Register-CooldownToast -ReadyTime $ReadyTime -Nickname $Nickname
}

if ($EnableGCal) {
    New-CooldownCalendarEvent -ReadyTime $ReadyTime -Nickname $Nickname -ScriptDir $ScriptDir
}