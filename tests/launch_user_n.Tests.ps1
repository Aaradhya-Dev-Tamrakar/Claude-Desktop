<#
.SYNOPSIS
    Smoke tests for launch_user_n.ps1.

.DESCRIPTION
    Two areas covered:
      1. Get-ValidatedProfilePath - the path-containment boundary. Tested by
         invoking a throwaway harness script in a child pwsh process, since
         the real function calls `exit 1` on rejection (correct for the
         script's own control flow, but means it cannot be dot-sourced and
         asserted against directly without exiting the test host).
      2. -WhatIf - asserts a dry run against a scratch profile leaves the
         real filesystem, registry key, and .claude-profiles state
         untouched. Does not attempt to launch Claude.exe or exercise
         robocopy/reg.exe.

         IMPORTANT: Get-ValidatedProfilePath hardcodes its containment
         check against the real %USERPROFILE%\.claude-profiles by design
         (this is correct - the base dir intentionally isn't
         config-driven, since that would defeat the containment boundary
         it enforces). Because of this, the -WhatIf tests CANNOT use a
         fully isolated TestDrive scratch directory - a path outside the
         real base dir would be rejected by Get-ValidatedProfilePath
         before ever reaching WhatIf-gated code. Instead this suite
         temporarily adds one scratch entry ("pester-whatif-scratch") to
         your REAL profiles.json, backs the original file up first, and
         restores it in AfterAll. It does not touch any of your real
         numbered profiles (user1-user20).

.NOTES
    NOT YET EXECUTED. Written and statically reviewed only - this sandbox
    has no pwsh/Pester and no access to install them (packages.microsoft.com
    is not on the network allowlist). Run locally with:

        cd tests
        Invoke-Pester -Path .\launch_user_n.Tests.ps1 -Output Detailed

    Requires Pester 5+ (Install-Module Pester -MinimumVersion 5.0 -Scope CurrentUser).
#>

BeforeAll {
    $script:RepoRoot = Split-Path $PSScriptRoot -Parent
    $script:LauncherPath = Join-Path $RepoRoot "launch_user_n.ps1"
    $script:RealBaseDir = [System.Environment]::ExpandEnvironmentVariables("%USERPROFILE%\.claude-profiles")

    # Minimal harness that dot-sources just the function definition out of the
    # real script (via AST) and calls it with test args, so the test asserts
    # against the actual shipped implementation rather than a re-typed copy.
    $script:HarnessPath = Join-Path $TestDrive "harness.ps1"
    $launcherContent = Get-Content $LauncherPath -Raw
    $ast = [System.Management.Automation.Language.Parser]::ParseInput($launcherContent, [ref]$null, [ref]$null)
    $funcDef = $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-ValidatedProfilePath' }, $true) | Select-Object -First 1
    if (-not $funcDef) {
        throw "Get-ValidatedProfilePath not found in launch_user_n.ps1 - has it been renamed?"
    }
    $harnessContent = @"
$($funcDef.Extent.Text)

`$result = Get-ValidatedProfilePath -RawPath `$args[0] -ProfileName `$args[1]
Write-Output `$result
"@
    Set-Content -Path $HarnessPath -Value $harnessContent -Encoding UTF8
}

Describe "Get-ValidatedProfilePath (path containment)" {

    Context "Paths that resolve inside %USERPROFILE%\.claude-profiles" {
        It "accepts the standard profile path shape" {
            $rawPath = "%USERPROFILE%\.claude-profiles\user1"
            $proc = Start-Process pwsh -ArgumentList @("-NoProfile", "-File", $HarnessPath, $rawPath, "user1") -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$TestDrive\out.txt" -RedirectStandardError "$TestDrive\err.txt"
            $proc.ExitCode | Should -Be 0
            $output = Get-Content "$TestDrive\out.txt" -Raw
            $output.Trim() | Should -Match $([regex]::Escape("user1"))
        }

        It "accepts a nested subfolder still under the base dir" {
            $rawPath = "%USERPROFILE%\.claude-profiles\user1\subfolder"
            $proc = Start-Process pwsh -ArgumentList @("-NoProfile", "-File", $HarnessPath, $rawPath, "user1") -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$TestDrive\out2.txt" -RedirectStandardError "$TestDrive\err2.txt"
            $proc.ExitCode | Should -Be 0
        }
    }

    Context "Paths that attempt to escape the base dir" {
        It "rejects a parent-directory traversal (..\..\)" {
            $rawPath = "%USERPROFILE%\.claude-profiles\..\..\Desktop\evil"
            $proc = Start-Process pwsh -ArgumentList @("-NoProfile", "-File", $HarnessPath, $rawPath, "malicious") -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$TestDrive\out3.txt" -RedirectStandardError "$TestDrive\err3.txt"
            $proc.ExitCode | Should -Be 1
        }

        It "rejects an absolute path entirely outside the base dir" {
            $rawPath = "C:\Windows\System32\config"
            $proc = Start-Process pwsh -ArgumentList @("-NoProfile", "-File", $HarnessPath, $rawPath, "malicious") -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$TestDrive\out4.txt" -RedirectStandardError "$TestDrive\err4.txt"
            $proc.ExitCode | Should -Be 1
        }

        It "rejects a sibling directory that merely shares a string prefix (.claude-profiles-evil)" {
            # Guards against a naive StartsWith check without the trailing
            # separator, which would wrongly accept this as "inside".
            $rawPath = "%USERPROFILE%\.claude-profiles-evil\payload"
            $proc = Start-Process pwsh -ArgumentList @("-NoProfile", "-File", $HarnessPath, $rawPath, "malicious") -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$TestDrive\out5.txt" -RedirectStandardError "$TestDrive\err5.txt"
            $proc.ExitCode | Should -Be 1
        }
    }
}

Describe "-WhatIf (no-mutation guarantee)" {

    BeforeAll {
        # IMPORTANT: Get-ValidatedProfilePath hardcodes its containment check
        # against the REAL %USERPROFILE%\.claude-profiles (by design - see
        # its implementation; the base dir is intentionally not
        # configurable, since making it config-driven would defeat the
        # purpose of the containment boundary). This means a fully isolated
        # TestDrive scratch dir CANNOT be used here: a scratch path outside
        # the real base dir would correctly be rejected by
        # Get-ValidatedProfilePath before ever reaching WhatIf-gated code,
        # producing a false pass on this test for the same reason described
        # in the Claude.exe guard below.
        #
        # Instead this test uses a real subfolder under the actual base dir,
        # with a profile name unlikely to collide with real ones
        # ("pester-whatif-scratch"). It reads/restores the real profiles.json
        # (backed up first) rather than substituting an isolated one.
        $script:RealConfigFile = Join-Path $RepoRoot "profiles.json"
        $script:RealConfigBackup = Join-Path $TestDrive "profiles.json.bak"
        Copy-Item $RealConfigFile $RealConfigBackup

        $script:ScratchProfileName = "pester-whatif-scratch"
        $script:ScratchDir = Join-Path $RealBaseDir $ScratchProfileName

        if (Test-Path $ScratchDir) {
            throw "Refusing to run: '$ScratchDir' already exists. Remove it manually before running this test suite, in case it holds real data."
        }

        $profiles = Get-Content $RealConfigFile | ConvertFrom-Json
        $profiles | Add-Member -NotePropertyName $ScratchProfileName -NotePropertyValue @{
            nickname   = "pester-scratch"
            path       = "%USERPROFILE%\.claude-profiles\$ScratchProfileName"
            last_login = $null
        } -Force
        $profiles | ConvertTo-Json -Depth 5 | Set-Content $RealConfigFile -Encoding UTF8
    }

    AfterAll {
        # Restore the real profiles.json exactly as it was, and remove the
        # scratch directory if the test (incorrectly) created one.
        Copy-Item $RealConfigBackup $RealConfigFile -Force
        if (Test-Path $ScratchDir) {
            Remove-Item $ScratchDir -Recurse -Force
        }
    }

    It "does not create the profile storage directory" {
        # NOTE: This It block performs the actual -WhatIf run; the two It
        # blocks below read files this one produces (whatif_out.txt) and
        # state this one is expected NOT to have changed (profiles.json's
        # last_login). They depend on running in file order, after this
        # block, in the same process - do not add -Parallel to this Describe
        # without restructuring (e.g. moving the run into BeforeAll).
        Test-Path $ScratchDir | Should -Be $false

        $proc = Start-Process pwsh -ArgumentList @("-NoProfile", "-File", $LauncherPath, "-Account", $ScratchProfileName, "-WhatIf") -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$TestDrive\whatif_out.txt" -RedirectStandardError "$TestDrive\whatif_err.txt"

        $outContent = Get-Content "$TestDrive\whatif_out.txt" -Raw -ErrorAction SilentlyContinue
        $errContent = Get-Content "$TestDrive\whatif_err.txt" -Raw -ErrorAction SilentlyContinue
        $combined = "$outContent $errContent"

        # Guard against the specific known false-negative: if Claude.exe
        # isn't discoverable on this machine, the script exits 1 before any
        # WhatIf-gated code runs, producing the same "no directory created"
        # outcome as a correctly-working WhatIf. Detect that exact case by
        # its known message rather than by absence of [WhatIf] markers,
        # since a clean machine with no prior session/registry state can
        # legitimately produce few or no markers without being a false
        # negative.
        if ($combined -match 'Claude Desktop executable.*not found') {
            Set-ItResult -Inconclusive -Because "No Claude.exe discoverable on this machine - script exited before reaching WhatIf-gated code, so this is not a valid test of the no-mutation guarantee here. Exit code: $($proc.ExitCode)"
            return
        }

        Test-Path $ScratchDir | Should -Be $false
    }

    It "leaves profiles.json's scratch entry with last_login still null" {
        # The state-file/timestamp write is one of the WhatIf-gated steps;
        # confirm it did not fire for the scratch profile.
        $profiles = Get-Content $RealConfigFile | ConvertFrom-Json
        $profiles.$ScratchProfileName.last_login | Should -BeNullOrEmpty
    }

    It "output contains [WhatIf] markers, not [+] action markers, for the gated steps" {
        $outContent = Get-Content "$TestDrive\whatif_out.txt" -Raw -ErrorAction SilentlyContinue
        if ($outContent) {
            $outContent | Should -Not -Match '\[\+\] Restoring session data'
            $outContent | Should -Not -Match '\[\+\] Initializing fresh profile storage'
            $outContent | Should -Not -Match '\[\+\] Saving current session data'
        }
    }
}