<#
.SYNOPSIS
Safely sync a Git repo, check staged changes for secrets, and commit when appropriate.

.DESCRIPTION
Pulls the latest changes from the configured origin remote, appends new orchestrator memory
entries to team-memory.md, prevents accidental credential commits, and exits cleanly when there
is nothing to commit.
#>

[CmdletBinding()]
param (
    [Alias("m")]
    [string]$Message,

    [switch]$PullOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Status {
    param(
        [string]$Message,
        [System.ConsoleColor]$Color = [System.ConsoleColor]::Cyan
    )
    Write-Host "[$((Get-Date).ToString('HH:mm:ss'))] $Message" -ForegroundColor $Color
}

function Write-Notice {
    param([string]$Message)
    Write-Status -Message $Message -Color ([System.ConsoleColor]::Yellow)
}

function Write-Success {
    param([string]$Message)
    Write-Status -Message $Message -Color ([System.ConsoleColor]::Green)
}

function Find-StagedSecrets {
    $stagedDiff = git diff --cached -U0 2>$null
    if (-not $stagedDiff) { return @() }

    $addedLines = $stagedDiff | Where-Object { $_ -match '^\+[^+]' } | ForEach-Object { $_.Substring(1) }
    if (-not $addedLines) { return @() }

    $secretPatterns = @(
        'AKIA[0-9A-Z]{16}'
        'sk-[a-zA-Z0-9]{20,}'
        'sk-ant-[a-zA-Z0-9\-]{20,}'
        'ghp_[a-zA-Z0-9]{36}'
        'github_pat_[a-zA-Z0-9_]{20,}'
        'AIza[0-9A-Za-z\-_]{35}'
        'xox[baprs]-[0-9a-zA-Z\-]{10,}'
        '-----BEGIN (RSA|EC|OPENSSH|PGP|DSA)? ?PRIVATE KEY-----'
        '(?i)(api[_-]?key|secret|password|token|passwd)\s*[:=]\s*[''"][^''"\s]{8,}[''"]'
    )

    $hits = @()
    foreach ($line in $addedLines) {
        foreach ($pattern in $secretPatterns) {
            if ($line -match $pattern) {
                $snippet = $line.Trim()
                $hits += [PSCustomObject]@{
                    Pattern = $pattern
                    Snippet = $snippet.Substring(0, [Math]::Min(60, $snippet.Length))
                }
                break
            }
        }
    }

    return @($hits)
}

function Get-AutoCommitMessage {
    $statusLines = git status --porcelain
    if (-not $statusLines) { return $null }

    $modifiedFiles = @()
    $addedFiles = @()
    $deletedFiles = @()

    foreach ($line in $statusLines) {
        $status = $line.Substring(0, 2).Trim()
        $file = $line.Substring(3).Trim()
        $fileName = Split-Path $file -Leaf

        if ($status -match 'A|\?\?') { $addedFiles += $fileName }
        elseif ($status -match 'D') { $deletedFiles += $fileName }
        else { $modifiedFiles += $fileName }
    }

    $allChanged = @($addedFiles + $modifiedFiles + $deletedFiles)
    if (@($allChanged).Count -eq 0) { return $null }

    $prefix = "chore"
    if (@($addedFiles).Count -gt 0) { $prefix = "feat" }
    elseif ($modifiedFiles | Where-Object { $_ -match '\.(ps1|json)$' }) { $prefix = "refactor" }

    $summary = ""
    if ($allChanged.Count -le 3) {
        $summary = $allChanged -join ", "
    }
    else {
        $firstTwo = ($allChanged[0..1]) -join ", "
        $extraCount = $allChanged.Count - 2
        $summary = "$firstTwo +$extraCount more"
    }

    $rawDiff = git diff --cached -U0 2>$null
    $diffStat = git diff --cached --shortstat 2>$null
    $churn = ""
    if ($diffStat -match '(\d+) insertion') { $ins = $Matches[1] } else { $ins = 0 }
    if ($diffStat -match '(\d+) deletion') { $del = $Matches[1] } else { $del = 0 }
    if (($ins + 0) -gt 0 -or ($del + 0) -gt 0) { $churn = " (+$ins/-$del)" }

    $isNewlineOnly = $false
    if ($rawDiff -match '\\ No newline at end of file') {
        $addedLines = $rawDiff | Where-Object { $_ -match '^\+[^+]' } | ForEach-Object { $_.Substring(1) }
        $removedLines = $rawDiff | Where-Object { $_ -match '^-[^-]' } | ForEach-Object { $_.Substring(1) }
        if ($addedLines.Count -eq 1 -and $removedLines.Count -eq 1 -and $addedLines[0] -eq $removedLines[0]) {
            $isNewlineOnly = $true
        }
    }

    $hunkContext = $null
    if ($isNewlineOnly) {
        $hunkContext = "add trailing newline"
    }
    else {
        $hunkContext = $rawDiff |
            Select-String '^@@.*@@\s*(\S.*)$' |
            ForEach-Object { $_.Matches[0].Groups[1].Value } |
            Select-Object -First 1

        if (-not $hunkContext) {
            $addedLine = $rawDiff |
                Select-String '^\+[^+]' |
                ForEach-Object { $_.Line.Substring(1).Trim() } |
                Where-Object { $_.Length -gt 0 } |
                Select-Object -First 1
            if ($addedLine) {
                $snippet = $addedLine
                if ($snippet -match '(?i)(api[_-]?key|secret|password|token|passwd)\s*[:=]') {
                    $snippet = "[redacted: credential-like line]"
                }
                elseif ($snippet.Length -gt 50) { $snippet = $snippet.Substring(0, 50) + "..." }
                $hunkContext = $snippet
            }
        }
    }

    if ($hunkContext) {
        return "${prefix}: update ${summary} - ${hunkContext}${churn}"
    }

    return "${prefix}: update ${summary}${churn}"
}

function Sync-MemoryToTeamMemory {
    param([string]$RepoPath)

    $memoryDir = Join-Path $RepoPath "orchestrator-state\memory"
    $trackerPath = Join-Path $RepoPath "orchestrator-state\.memory-appended"
    $teamMemoryPath = Join-Path $RepoPath "team-memory.md"

    if (-not (Test-Path $memoryDir)) { return }
    if (-not (Test-Path $teamMemoryPath)) { return }

    $appended = @{}
    if (Test-Path $trackerPath) {
        Get-Content $trackerPath | Where-Object { $_.Trim() } | ForEach-Object { $appended[$_.Trim()] = $true }
    }

    $entryFiles = Get-ChildItem -Path $memoryDir -Filter "*.json" -File -ErrorAction SilentlyContinue |
        Sort-Object Name
    if (-not $entryFiles) { return }

    $newLines = @()
    $newIds = @()

    foreach ($f in $entryFiles) {
        $entryId = $f.BaseName
        if ($appended.ContainsKey($entryId)) { continue }

        try {
            $json = Get-Content $f.FullName -Raw | ConvertFrom-Json
        }
        catch {
            Write-Status -Message "Skipping unparseable memory entry: $($f.Name)" -Color ([System.ConsoleColor]::Yellow)
            continue
        }

        $account = $json.account
        $text = $json.text
        $pushedAtRaw = $json.pushed_at
        if (-not $account -or -not $text -or -not $pushedAtRaw) {
            Write-Status -Message "Skipping malformed memory entry (missing field): $($f.Name)" -Color ([System.ConsoleColor]::Yellow)
            continue
        }

        $pushedAt = if ($pushedAtRaw -is [DateTime]) { $pushedAtRaw.ToString("yyyy-MM-ddTHH:mm:ssZ") } else { [string]$pushedAtRaw }
        $day = $pushedAt.Substring(0, 10)
        $line = "- [$account, $pushedAt] $text"
        $newLines += [PSCustomObject]@{ Day = $day; Line = $line }
        $newIds += $entryId
    }

    if ($newLines.Count -eq 0) { return }

    $content = Get-Content $teamMemoryPath -Raw
    $marker = "<!-- Nothing logged yet. -->"

    $groupedByDay = $newLines | Group-Object Day
    $block = ""
    foreach ($group in $groupedByDay) {
        $block += "`n## $($group.Name)`n"
        foreach ($item in $group.Group) { $block += "$($item.Line)`n" }
    }

    if ($content -match [regex]::Escape($marker)) {
        $content = $content -replace [regex]::Escape($marker), "$block"
    }
    else {
        $content = $content.TrimEnd("`n") + "`n$block"
    }

    Set-Content -Path $teamMemoryPath -Value $content -NoNewline
    Add-Content -Path $trackerPath -Value $newIds

    Write-Status -Message "Auto-appended $($newIds.Count) orchestrator memory entr$(if ($newIds.Count -eq 1) { 'y' } else { 'ies' }) to team-memory.md." -Color ([System.ConsoleColor]::Cyan)
}

$RepoPath = $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoPath '.git'))) {
    Write-Error "Not a git repo: $RepoPath"
    exit 1
}

Push-Location $RepoPath
try {
    $currentBranch = (git branch --show-current 2>$null)
    if ($currentBranch) { $currentBranch = $currentBranch.Trim() }
    if (-not $currentBranch) { $currentBranch = "main" }

    $hasOrigin = $false
    try {
        git remote get-url origin *> $null
        $hasOrigin = $true
    }
    catch {
        $hasOrigin = $false
    }

    Write-Status -Message "Repository: $RepoPath"
    Write-Status -Message "Current branch: $currentBranch"

    if ($hasOrigin) {
        Write-Status -Message "Pulling latest from origin/$currentBranch..."
        git pull --rebase --autostash origin $currentBranch
    }
    else {
        Write-Notice -Message "No 'origin' remote configured; skipping pull and push to avoid a broken sync step."
    }

    Sync-MemoryToTeamMemory -RepoPath $RepoPath

    if ($PullOnly) {
        Write-Success -Message "Pull complete; no commit was created because -PullOnly was set."
        exit 0
    }

    Write-Status -Message "Staging all tracked and new files..."
    git add -A

    git diff --cached --quiet 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Success -Message "No local changes detected. Nothing to commit."
        exit 0
    }

    $secretHits = Find-StagedSecrets
    if (@($secretHits).Count -gt 0) {
        Write-Error "Possible secret(s) detected in staged changes. The repo was left unstaged for safety."
        foreach ($hit in @($secretHits)) {
            Write-Host "    Pattern: $($hit.Pattern)" -ForegroundColor Yellow
            Write-Host "    Line   : $($hit.Snippet)..." -ForegroundColor Gray
        }
        Write-Notice -Message "Unstage or remove the offending content, then re-run the script."
        git reset
        exit 1
    }

    if (-not $Message) {
        $Message = Get-AutoCommitMessage
        if ($Message) {
            Write-Notice -Message "Auto-generated commit message: '$Message'"
        }
    }

    if ($Message) {
        Write-Status -Message "Committing: '$Message'..."
        git commit -m "$Message"

        if ($hasOrigin) {
            Write-Status -Message "Pushing to origin/$currentBranch..."
            git push origin $currentBranch
            if ($LASTEXITCODE -ne 0) {
                Write-Notice -Message "Push rejected. Re-pulling and retrying push..."
                git pull --rebase --autostash origin $currentBranch
                git push origin $currentBranch
            }
        }
        else {
            Write-Notice -Message "Commit created locally, but no 'origin' remote was available to push it."
        }

        Write-Success -Message "Workspace synced successfully."
    }
    else {
        Write-Success -Message "No local changes detected to commit."
    }
}
finally {
    Pop-Location
}