<#
.SYNOPSIS
    Pester specs for launch_user_n.ps1's pure and mockable logic.

.DESCRIPTION
    Scope: functions defined and reachable via `launch_user_n.ps1 -TestHook`,
    which dot-sources the script and returns immediately after function
    definitions (before the interactive account-selection block and before
    any filesystem/process/registry side effects). See -TestHook in
    launch_user_n.ps1's param block.

    Covered:
      - Test-ProfilePathWithinBase (pure path-traversal predicate;
                                     Get-ValidatedProfilePath wraps this with
                                     Read-Host + exit on rejection, which is
                                     intentionally NOT unit-tested here — exit
                                     terminates the Pester process rather than
                                     failing a single assertion)
      - Show-ProfileTable          (pure formatting; asserted via captured
                                     Write-Host output, since New-Border/
                                     New-Row are nested and not directly
                                     callable)
      - Merge-McpServers           (pure union-with-precedence merge; takes
                                     two already-parsed PSCustomObjects, no
                                     file I/O, matches its own doc comment)
      - Expand-TeamMcpPlaceholders (pure {{REPO_ROOT}} token substitution
                                     across command/args/env string values;
                                     deep-clones input, no file I/O)

    NOT covered (would require mocking Read-Host, Test-Path, Get-Content,
    Set-Content, and ConvertTo-Json against a real profiles.json — out of
    scope for this pass):
      - Add-NewProfile                       (interactive; mutates profiles.json)
      - Sync-TeamMcpConfig                   (I/O wrapper around Merge-McpServers —
                                               reads team-mcp.json and
                                               claude_desktop_config.json, writes the
                                               merged result back)
      - Everything past the -TestHook return: executable resolution,
        robocopy session swap, registry claude:// handling, the
        mutex-guarded last_login/first_login_time writes, sync.ps1
        invocation.

    Run: Invoke-Pester -Path .\tests\launch_user_n.Tests.ps1 -Output Detailed
#>

BeforeAll {
    $ScriptPath = Join-Path $PSScriptRoot ".." "launch_user_n.ps1"
    . $ScriptPath -TestHook
}

Describe "Test-ProfilePathWithinBase" {

    Context "path within the approved base directory" {
        It "marks a direct child of the base directory as valid" {
            $raw = "%USERPROFILE%\.claude-profiles\user1"
            $result = Test-ProfilePathWithinBase -RawPath $raw
            $result.IsValid | Should -BeTrue
        }

        It "resolves to the same expanded full path Get-ValidatedProfilePath would return" {
            $raw = "%USERPROFILE%\.claude-profiles\user1"
            $result = Test-ProfilePathWithinBase -RawPath $raw
            $expected = [System.IO.Path]::GetFullPath([System.Environment]::ExpandEnvironmentVariables($raw))
            $result.ExpandedFull | Should -Be $expected
        }

        It "marks a nested subdirectory under the base as valid" {
            $raw = "%USERPROFILE%\.claude-profiles\user1\nested"
            (Test-ProfilePathWithinBase -RawPath $raw).IsValid | Should -BeTrue
        }
    }

    Context "path escaping the approved base directory" {
        It "marks a parent-traversal path as invalid" {
            $raw = "%USERPROFILE%\.claude-profiles\..\Desktop"
            (Test-ProfilePathWithinBase -RawPath $raw).IsValid | Should -BeFalse
        }

        It "marks a completely unrelated absolute path as invalid" {
            $raw = "C:\Windows\System32"
            (Test-ProfilePathWithinBase -RawPath $raw).IsValid | Should -BeFalse
        }

        It "marks a sibling directory sharing the base dir's name as a prefix (e.g. '.claude-profiles-evil') as invalid" {
            # Guards against a naive StartsWith("$Base") check (no trailing
            # separator) matching a same-prefixed sibling folder. BaseFull is
            # built with a trailing '\', so this should correctly reject.
            $raw = "%USERPROFILE%\.claude-profiles-evil\user1"
            (Test-ProfilePathWithinBase -RawPath $raw).IsValid | Should -BeFalse
        }
    }
}

Describe "Get-ValidatedProfilePath (accept path only — reject path exits and is not unit-tested)" {
    It "returns the expanded full path when the raw path is within the base" {
        $raw = "%USERPROFILE%\.claude-profiles\user1"
        $result = Get-ValidatedProfilePath -RawPath $raw -ProfileName "user1"
        $expected = [System.IO.Path]::GetFullPath([System.Environment]::ExpandEnvironmentVariables($raw))
        $result | Should -Be $expected
    }
}

Describe "Merge-McpServers" {

    Context "merging into a profile with no existing mcpServers" {
        It "adds all shared servers when the profile config has none" {
            $profileConfig = '{}' | ConvertFrom-Json
            $sharedConfig = '{"mcpServers":{"github":{"command":"npx","args":["-y","@modelcontextprotocol/server-github"]}}}' | ConvertFrom-Json

            $result = Merge-McpServers -ProfileConfig $profileConfig -SharedConfig $sharedConfig

            $result.mcpServers.github.command | Should -Be "npx"
        }
    }

    Context "precedence on key collision" {
        It "overwrites a profile's existing server with the shared version of the same name" {
            $profileConfig = '{"mcpServers":{"github":{"command":"old-command"}}}' | ConvertFrom-Json
            $sharedConfig = '{"mcpServers":{"github":{"command":"new-command"}}}' | ConvertFrom-Json

            $result = Merge-McpServers -ProfileConfig $profileConfig -SharedConfig $sharedConfig

            $result.mcpServers.github.command | Should -Be "new-command"
        }
    }

    Context "profile-only servers" {
        It "preserves a server that exists only in the profile, not in shared" {
            $profileConfig = '{"mcpServers":{"private-tool":{"command":"local-only"}}}' | ConvertFrom-Json
            $sharedConfig = '{"mcpServers":{"github":{"command":"npx"}}}' | ConvertFrom-Json

            $result = Merge-McpServers -ProfileConfig $profileConfig -SharedConfig $sharedConfig

            $result.mcpServers."private-tool".command | Should -Be "local-only"
            $result.mcpServers.github.command | Should -Be "npx"
        }
    }

    Context "non-mcpServers keys" {
        It "passes through unrelated top-level profile keys untouched" {
            $profileConfig = '{"someOtherSetting":"keepme","mcpServers":{}}' | ConvertFrom-Json
            $sharedConfig = '{"mcpServers":{"github":{"command":"npx"}}}' | ConvertFrom-Json

            $result = Merge-McpServers -ProfileConfig $profileConfig -SharedConfig $sharedConfig

            $result.someOtherSetting | Should -Be "keepme"
        }
    }

    Context "immutability of the caller's input" {
        It "does not mutate the original ProfileConfig object" {
            $profileConfig = '{"mcpServers":{}}' | ConvertFrom-Json
            $sharedConfig = '{"mcpServers":{"github":{"command":"npx"}}}' | ConvertFrom-Json

            Merge-McpServers -ProfileConfig $profileConfig -SharedConfig $sharedConfig | Out-Null

            $profileConfig.mcpServers.PSObject.Properties.Name | Should -Not -Contain "github"
        }
    }

    Context "shared config with no mcpServers property" {
        It "returns the profile's own servers unchanged when SharedConfig has no mcpServers key" {
            $profileConfig = '{"mcpServers":{"private-tool":{"command":"local-only"}}}' | ConvertFrom-Json
            $sharedConfig = '{}' | ConvertFrom-Json

            $result = Merge-McpServers -ProfileConfig $profileConfig -SharedConfig $sharedConfig

            $result.mcpServers."private-tool".command | Should -Be "local-only"
        }
    }
}

Describe "Expand-TeamMcpPlaceholders" {

    Context "command field" {
        It "replaces {{REPO_ROOT}} in a server's command string" {
            $sharedConfig = '{"mcpServers":{"tool":{"command":"{{REPO_ROOT}}\\bin\\tool.exe"}}}' | ConvertFrom-Json

            $result = Expand-TeamMcpPlaceholders -SharedConfig $sharedConfig -RepoRoot "D:\repo"

            $result.mcpServers.tool.command | Should -Be "D:\repo\bin\tool.exe"
        }
    }

    Context "args field" {
        It "replaces {{REPO_ROOT}} in every matching args element, leaving others untouched" {
            $sharedConfig = '{"mcpServers":{"tool":{"command":"python3","args":["{{REPO_ROOT}}\\run_server.py","--flag"]}}}' | ConvertFrom-Json

            $result = Expand-TeamMcpPlaceholders -SharedConfig $sharedConfig -RepoRoot "D:\repo"

            $result.mcpServers.tool.args[0] | Should -Be "D:\repo\run_server.py"
            $result.mcpServers.tool.args[1] | Should -Be "--flag"
        }
    }

    Context "env field" {
        It "replaces {{REPO_ROOT}} in env values" {
            $sharedConfig = '{"mcpServers":{"tool":{"command":"x","env":{"DATA_DIR":"{{REPO_ROOT}}\\data"}}}}' | ConvertFrom-Json

            $result = Expand-TeamMcpPlaceholders -SharedConfig $sharedConfig -RepoRoot "D:\repo"

            $result.mcpServers.tool.env.DATA_DIR | Should -Be "D:\repo\data"
        }
    }

    Context "no mcpServers property" {
        It "returns the config unchanged when SharedConfig has no mcpServers key" {
            $sharedConfig = '{}' | ConvertFrom-Json

            $result = Expand-TeamMcpPlaceholders -SharedConfig $sharedConfig -RepoRoot "D:\repo"

            $result.PSObject.Properties.Name | Should -Not -Contain "mcpServers"
        }
    }

    Context "no placeholder present" {
        It "leaves a command with no {{REPO_ROOT}} token untouched" {
            $sharedConfig = '{"mcpServers":{"tool":{"command":"npx"}}}' | ConvertFrom-Json

            $result = Expand-TeamMcpPlaceholders -SharedConfig $sharedConfig -RepoRoot "D:\repo"

            $result.mcpServers.tool.command | Should -Be "npx"
        }
    }

    Context "immutability of the caller's input" {
        It "does not mutate the original SharedConfig object" {
            $sharedConfig = '{"mcpServers":{"tool":{"command":"{{REPO_ROOT}}\\tool.exe"}}}' | ConvertFrom-Json

            Expand-TeamMcpPlaceholders -SharedConfig $sharedConfig -RepoRoot "D:\repo" | Out-Null

            $sharedConfig.mcpServers.tool.command | Should -Be "{{REPO_ROOT}}\tool.exe"
        }
    }
}

Describe "Show-ProfileTable" {

    Context "empty profile set" {
        It "prints the empty-state message and returns without drawing a table" {
            $output = Show-ProfileTable -Profiles ([PSCustomObject]@{}) -AccountKeys @() *>&1 | Out-String
            $output | Should -Match "No profiles yet"
            $output | Should -Not -Match "User#"
        }
    }

    Context "header and column labels" {
        BeforeAll {
            $today = (Get-Date).ToString("yyyy-MM-dd")
            $profiles = [PSCustomObject]@{
                user1 = @{ nickname = "alice"; last_login_date = $today; last_login_time = "10:00:00" }
            }
            $script:Output = Show-ProfileTable -Profiles $profiles -AccountKeys @("user1") *>&1 | Out-String
        }

        It "labels the index column 'User#', not the pre-merge '#'/'Profile' pair" {
            $script:Output | Should -Match "User#"
            $script:Output | Should -Not -Match "\| # \|"
        }

        It "includes all five expected column headers" {
            foreach ($col in @("User#", "Nickname", "Last Time", "Last Date", "Today Rank")) {
                $script:Output | Should -Match $col
            }
        }
    }

    Context "display index vs. internal key" {
        BeforeAll {
            $profiles = [PSCustomObject]@{
                user7  = @{ nickname = "bravo"; last_login_date = $null; last_login_time = $null }
                user12 = @{ nickname = "charlie"; last_login_date = $null; last_login_time = $null }
            }
            # AccountKeys order drives display order/index; deliberately not
            # sorted by userN, mirroring real profiles.json property order.
            $script:Output = Show-ProfileTable -Profiles $profiles -AccountKeys @("user7", "user12") *>&1 | Out-String
        }

        It "shows a bare 1-based row index, not the raw userN key, in the User# column" {
            $script:Output | Should -Match "\|\s+1\s+\|\s+bravo"
            $script:Output | Should -Match "\|\s+2\s+\|\s+charlie"
        }

        It "does not leak the internal 'user7'/'user12' key into the display row" {
            $script:Output | Should -Not -Match "\|\s+user7\s+\|"
            $script:Output | Should -Not -Match "\|\s+user12\s+\|"
        }
    }

    Context "never-logged-in profile" {
        It "renders 'Never' / '-' placeholders instead of null" {
            $profiles = [PSCustomObject]@{
                user1 = @{ nickname = "dana"; last_login_date = $null; last_login_time = $null }
            }
            $output = Show-ProfileTable -Profiles $profiles -AccountKeys @("user1") *>&1 | Out-String
            $output | Should -Match "Never"
        }
    }

    Context "Today Rank ordering" {
        BeforeAll {
            $today = (Get-Date).ToString("yyyy-MM-dd")
            $yesterday = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
            $profiles = [PSCustomObject]@{
                early = @{ nickname = "early-bird"; last_login_date = $today; last_login_time = "08:00:00" }
                late  = @{ nickname = "night-owl"; last_login_date = $today; last_login_time = "23:00:00" }
                old   = @{ nickname = "yesterday-user"; last_login_date = $yesterday; last_login_time = "12:00:00" }
            }
            $script:Output = Show-ProfileTable -Profiles $profiles -AccountKeys @("early", "late", "old") *>&1 | Out-String
        }

        It "ranks the most recent today-login as 1 regardless of row/display order" {
            $script:Output | Should -Match "night-owl\s+\|\s+23:00:00\s+\|\s+$([regex]::Escape((Get-Date).ToString('yyyy-MM-dd')))\s+\|\s+1\s+\|"
        }

        It "ranks an earlier today-login as 2" {
            $script:Output | Should -Match "early-bird\s+\|\s+08:00:00\s+\|\s+$([regex]::Escape((Get-Date).ToString('yyyy-MM-dd')))\s+\|\s+2\s+\|"
        }

        It "gives a non-today login a '-' rank rather than being folded into today's sequence" {
            $script:Output | Should -Match "yesterday-user\s+\|\s+12:00:00\s+\|\s+$([regex]::Escape((Get-Date).AddDays(-1).ToString('yyyy-MM-dd')))\s+\|\s+-\s+\|"
        }
    }

    Context "table structural integrity" {
        It "opens and closes every row with a border of matching width" {
            $profiles = [PSCustomObject]@{
                user1 = @{ nickname = "a-very-long-nickname-for-width-testing"; last_login_date = $null; last_login_time = $null }
            }
            $lines = (Show-ProfileTable -Profiles $profiles -AccountKeys @("user1") *>&1 | Out-String) -split "`r?`n" | Where-Object { $_ -match '\S' }
            $borders = $lines | Where-Object { $_ -match '^\+-+\+' }
            $borders.Count | Should -BeGreaterOrEqual 3  # top, header sep, bottom (+ footer border)
            ($borders | Select-Object -Unique -ExpandProperty Length | Sort-Object -Unique).Count | Should -Be 1
        }

        It "includes the 'Add New Profile' footer row" {
            $profiles = [PSCustomObject]@{ user1 = @{ nickname = "a"; last_login_date = $null; last_login_time = $null } }
            $output = Show-ProfileTable -Profiles $profiles -AccountKeys @("user1") *>&1 | Out-String
            $output | Should -Match "\[N\] Add New Profile"
        }
    }
}

Describe "TestHook contract" {
    It "does not execute past function definitions (no interactive prompt hangs the run)" {
        # If this test file completed BeforeAll without hanging on Read-Host,
        # the contract holds. This assertion just makes that explicit and
        # gives a named failure point if -TestHook regresses.
        Get-Command Test-ProfilePathWithinBase -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Get-ValidatedProfilePath -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Merge-McpServers -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Sync-TeamMcpConfig -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Show-ProfileTable -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Add-NewProfile -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Ensure-LocalOrchestratorServer -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
    }
}