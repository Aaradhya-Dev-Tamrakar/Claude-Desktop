param (
    [Alias("m")]
    [string]$Message,

    [switch]$PullOnly
)

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

    $allChanged = $addedFiles + $modifiedFiles + $deletedFiles
    if ($allChanged.Count -eq 0) { return $null }

    $prefix = "chore"
    if ($addedFiles.Count -gt 0) { $prefix = "feat" }
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
                if ($snippet.Length -gt 50) { $snippet = $snippet.Substring(0, 50) + "..." }
                $hunkContext = $snippet
            }
        }
    }

    if ($hunkContext) {
        return "${prefix}: update ${summary} - ${hunkContext}${churn}"
    }
    return "${prefix}: update ${summary}${churn}"
}

$RepoPath = $PSScriptRoot
if (-not (Test-Path "$RepoPath\.git")) {
    Write-Host "Not a git repo: $RepoPath" -ForegroundColor Red
    exit 1
}
Push-Location $RepoPath

$currentBranch = (git branch --show-current 2>$null)
if ($currentBranch) { $currentBranch = $currentBranch.Trim() }
if (-not $currentBranch) { $currentBranch = "main" }

Write-Host "[Sync] Pulling latest from origin $currentBranch..." -ForegroundColor Cyan
git pull --rebase --autostash origin $currentBranch

if ($PullOnly) {
    Write-Host "[Sync] Pull complete (PullOnly flag set)." -ForegroundColor Green
    Pop-Location
    exit 0
}

Write-Host "[Sync] Staging changes..." -ForegroundColor Cyan
git add -A

if (-not $Message) {
    $Message = Get-AutoCommitMessage
    if ($Message) {
        Write-Host "[Sync] Auto-generated commit message: '$Message'" -ForegroundColor Yellow
    }
}

if ($Message) {
    Write-Host "[Sync] Committing: '$Message'..." -ForegroundColor Cyan
    git commit -m "$Message"

    Write-Host "[Sync] Pushing to origin $currentBranch..." -ForegroundColor Cyan
    git push origin $currentBranch
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[Sync] Push rejected. Re-pulling and retrying push..." -ForegroundColor Yellow
        git pull --rebase --autostash origin $currentBranch
        git push origin $currentBranch
    }
}
else {
    Write-Host "[Sync] No local changes detected to commit." -ForegroundColor Gray
}

Pop-Location
Write-Host "[Sync] Workspace is clean and fully synchronized!" -ForegroundColor Green