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

        It "normalizes a profile server's single args value to an array" {
            $profileConfig = '{"mcpServers":{"private-tool":{"command":"python","args":"run_server.py"}}}' | ConvertFrom-Json
            $sharedConfig = '{"mcpServers":{}}' | ConvertFrom-Json

            $result = Merge-McpServers -ProfileConfig $profileConfig -SharedConfig $sharedConfig

            @($result.mcpServers."private-tool".args).Count | Should -Be 1
            $result.mcpServers."private-tool".args[0] | Should -Be "run_server.py"
        }
    }

    Context "non-mcpServers keys" {
        It "passes through unrelated top-level profile keys untouched" {
            $profileConfig = '{"someOtherSetting":"keepme","mcpServers":{}}' | ConvertFrom-Json
            $sharedConfig = '{"mcpServers":{"github":{"command":"npx"}}}' | ConvertFrom-Json

            $result = Merge-McpServers -ProfileConfig $profileConfig -SharedConfig $sharedConfig

            $result.someOtherSetting | Should -Be "keepme"
        }

        It "normalizes the persisted workspaces preference to an array" {
            $profileConfig = '{"preferences":{"launchPreviewPersistedWorkspaces":null,"launchPreviewSessionScopedSessions":null}}' | ConvertFrom-Json
            $sharedConfig = '{"mcpServers":{}}' | ConvertFrom-Json

            $result = Merge-McpServers -ProfileConfig $profileConfig -SharedConfig $sharedConfig

            $null -ne $result.preferences.launchPreviewPersistedWorkspaces | Should -BeTrue
            @($result.preferences.launchPreviewPersistedWorkspaces).Count | Should -Be 0
            $null -ne $result.preferences.launchPreviewSessionScopedSessions | Should -BeTrue
            @($result.preferences.launchPreviewSessionScopedSessions).Count | Should -Be 0
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

Describe "Write-JsonConfigSafely" {
    It "backs up the existing config and writes a valid replacement" {
        $directory = Join-Path $TestDrive "config"
        New-Item -ItemType Directory -Path $directory | Out-Null
        $path = Join-Path $directory "claude_desktop_config.json"
        Set-Content -Path $path -Value '{"mcpServers":{"old":{"command":"old"}}}' -Encoding UTF8

        Write-JsonConfigSafely -Path $path -Config ([PSCustomObject]@{
            mcpServers = [PSCustomObject]@{
                replacement = [PSCustomObject]@{ command = "new" }
            }
        })

        (Get-Content $path -Raw | ConvertFrom-Json).mcpServers.replacement.command | Should -Be "new"
        (Get-Content "$path.bak" -Raw | ConvertFrom-Json).mcpServers.old.command | Should -Be "old"
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

    Context "sync banner layout" {
        It "uses ASCII-only banner text so the borders stay aligned" {
            $output = & (Join-Path $PSScriptRoot "..\sync-mcp.ps1") -WhatIf 2>&1 | Out-String
            $output | Should -Not -Match "🔄|●|→|║|╔|╚|╭|╰|╯|╮|├|┤|─|│"
        }
    }

    Context "launch card wrapping" {
        It "wraps long executable paths onto a continuation line instead of truncating them" {
            $output = & $ScriptPath -Account user1 -WhatIf *>&1 | Out-String
            $output | Should -Match 'Executable'
            $output | Should -Match 'claude\.exe'
            $output | Should -Match 'app\\'
        }
    }
}

Describe "Get-EnrichedProfileRows" {
    Context "enrichment logic" {
        It "correctly extracts role, nickname, and today ranks" {
            $today = (Get-Date).ToString("yyyy-MM-dd")
            $profiles = [PSCustomObject]@{
                user1 = @{ nickname = "alice"; role = "orchestrator"; last_login_date = $today; last_login_time = "10:00:00" }
                user2 = @{ nickname = "bob"; role = "researcher"; last_login_date = $null; last_login_time = $null }
            }
            $rows = Get-EnrichedProfileRows -Profiles $profiles -AccountKeys @("user1", "user2")
            
            $rows.Count | Should -Be 2
            $rows[0].Role | Should -Be "orchestrator"
            $rows[0].TodayRank | Should -Be "1"
            $rows[0].IsToday | Should -BeTrue
            $rows[1].Role | Should -Be "researcher"
            $rows[1].LastDate | Should -Be "Never"
            $rows[1].TodayRank | Should -Be "-"
        }
    }
}

Describe "Get-WindowGridLayout" {
    Context "edge cases" {
        It "returns empty array when Count is 0 or negative" {
            $bounds = [PSCustomObject]@{ X = 0; Y = 0; Width = 1920; Height = 1080 }
            (Get-WindowGridLayout -Bounds $bounds -Count 0).Count | Should -Be 0
            (Get-WindowGridLayout -Bounds $bounds -Count -1).Count | Should -Be 0
        }
    }

    Context "1 window (normal space)" {
        It "returns full work area for single window" {
            $bounds = [PSCustomObject]@{ X = 0; Y = 0; Width = 1920; Height = 1040 }
            $slots = Get-WindowGridLayout -Bounds $bounds -Count 1
            $slots.Count | Should -Be 1
            $slots[0].Slot | Should -Be 1
            $slots[0].X | Should -Be 0
            $slots[0].Y | Should -Be 0
            $slots[0].Width | Should -Be 1920
            $slots[0].Height | Should -Be 1040
        }
    }

    Context "2 windows (side-by-side 50% split)" {
        It "splits screen into left and right halves" {
            $bounds = [PSCustomObject]@{ X = 0; Y = 0; Width = 1920; Height = 1040 }
            $slots = Get-WindowGridLayout -Bounds $bounds -Count 2
            $slots.Count | Should -Be 2
            # Left half
            $slots[0].Slot | Should -Be 1
            $slots[0].X | Should -Be 0
            $slots[0].Y | Should -Be 0
            $slots[0].Width | Should -Be 960
            $slots[0].Height | Should -Be 1040
            # Right half
            $slots[1].Slot | Should -Be 2
            $slots[1].X | Should -Be 960
            $slots[1].Y | Should -Be 0
            $slots[1].Width | Should -Be 960
            $slots[1].Height | Should -Be 1040
        }
    }

    Context "3 windows (2x2 quad grid with 3 active slots)" {
        It "places windows in top-left, top-right, bottom-left" {
            $bounds = [PSCustomObject]@{ X = 0; Y = 0; Width = 1920; Height = 1040 }
            $slots = Get-WindowGridLayout -Bounds $bounds -Count 3
            $slots.Count | Should -Be 3
            # Top-Left (Slot 1)
            $slots[0].Slot | Should -Be 1
            $slots[0].X | Should -Be 0
            $slots[0].Y | Should -Be 0
            $slots[0].Width | Should -Be 960
            $slots[0].Height | Should -Be 520
            # Top-Right (Slot 2)
            $slots[1].Slot | Should -Be 2
            $slots[1].X | Should -Be 960
            $slots[1].Y | Should -Be 0
            $slots[1].Width | Should -Be 960
            $slots[1].Height | Should -Be 520
            # Bottom-Left (Slot 3)
            $slots[2].Slot | Should -Be 3
            $slots[2].X | Should -Be 0
            $slots[2].Y | Should -Be 520
            $slots[2].Width | Should -Be 960
            $slots[2].Height | Should -Be 520
        }
    }

    Context "4 windows (2x2 quad grid)" {
        It "places 4 windows into 4 quadrants" {
            $bounds = [PSCustomObject]@{ X = 0; Y = 0; Width = 1920; Height = 1040 }
            $slots = Get-WindowGridLayout -Bounds $bounds -Count 4
            $slots.Count | Should -Be 4
            # Top-Left
            $slots[0].Slot | Should -Be 1
            $slots[0].X | Should -Be 0
            $slots[0].Y | Should -Be 0
            $slots[0].Width | Should -Be 960
            $slots[0].Height | Should -Be 520
            # Top-Right
            $slots[1].Slot | Should -Be 2
            $slots[1].X | Should -Be 960
            $slots[1].Y | Should -Be 0
            $slots[1].Width | Should -Be 960
            $slots[1].Height | Should -Be 520
            # Bottom-Left
            $slots[2].Slot | Should -Be 3
            $slots[2].X | Should -Be 0
            $slots[2].Y | Should -Be 520
            $slots[2].Width | Should -Be 960
            $slots[2].Height | Should -Be 520
            # Bottom-Right
            $slots[3].Slot | Should -Be 4
            $slots[3].X | Should -Be 960
            $slots[3].Y | Should -Be 520
            $slots[3].Width | Should -Be 960
            $slots[3].Height | Should -Be 520
        }
    }

    Context "6 windows (2x3 grid as in screenshot)" {
        It "arranges 6 slots across 2 columns and 3 rows" {
            $bounds = [PSCustomObject]@{ X = 0; Y = 0; Width = 1920; Height = 1080 }
            $slots = Get-WindowGridLayout -Bounds $bounds -Count 6
            $slots.Count | Should -Be 6
            # Row 1 (top): Slot 1, Slot 2
            $slots[0].Slot | Should -Be 1
            $slots[0].X | Should -Be 0
            $slots[0].Y | Should -Be 0
            $slots[1].Slot | Should -Be 2
            $slots[1].X | Should -Be 960
            $slots[1].Y | Should -Be 0
            # Row 2 (mid): Slot 3, Slot 4
            $slots[2].Slot | Should -Be 3
            $slots[2].X | Should -Be 0
            $slots[2].Y | Should -Be 360
            $slots[3].Slot | Should -Be 4
            $slots[3].X | Should -Be 960
            $slots[3].Y | Should -Be 360
            # Row 3 (bot): Slot 5, Slot 6
            $slots[4].Slot | Should -Be 5
            $slots[4].X | Should -Be 0
            $slots[4].Y | Should -Be 720
            $slots[5].Slot | Should -Be 6
            $slots[5].X | Should -Be 960
            $slots[5].Y | Should -Be 720
        }
    }

    Context "screen bounds with offset (e.g. secondary monitor)" {
        It "respects non-zero X/Y origin coordinates" {
            $bounds = [PSCustomObject]@{ X = 1920; Y = 100; Width = 1920; Height = 1000 }
            $slots = Get-WindowGridLayout -Bounds $bounds -Count 2
            $slots[0].X | Should -Be 1920
            $slots[0].Y | Should -Be 100
            $slots[1].X | Should -Be 2880
            $slots[1].Y | Should -Be 100
        }
    }
}

Describe "Get-DesktopBatchAllocation" {
    Context "edge cases" {
        It "returns empty array when TotalCount or MaxPerDesktop is <= 0" {
            (Get-DesktopBatchAllocation -TotalCount 0).Count | Should -Be 0
            (Get-DesktopBatchAllocation -TotalCount -1).Count | Should -Be 0
            (Get-DesktopBatchAllocation -TotalCount 5 -MaxPerDesktop 0).Count | Should -Be 0
        }
    }

    Context "single desktop allocations (1..4 users)" {
        It "allocates 1 user to Desktop 1 (index 0)" {
            $allocs = Get-DesktopBatchAllocation -TotalCount 1 -MaxPerDesktop 4
            $allocs.Count | Should -Be 1
            $allocs[0].AccountIndex | Should -Be 0
            $allocs[0].DesktopIndex | Should -Be 0
            $allocs[0].DesktopSlot | Should -Be 1
            $allocs[0].DesktopTotal | Should -Be 1
        }

        It "allocates 4 users to Desktop 1 with slots 1..4" {
            $allocs = Get-DesktopBatchAllocation -TotalCount 4 -MaxPerDesktop 4
            $allocs.Count | Should -Be 4
            for ($i = 0; $i -lt 4; $i++) {
                $allocs[$i].AccountIndex | Should -Be $i
                $allocs[$i].DesktopIndex | Should -Be 0
                $allocs[$i].DesktopSlot | Should -Be ($i + 1)
                $allocs[$i].DesktopTotal | Should -Be 4
            }
        }
    }

    Context "multi-desktop distribution (5+ users with max 4 per desktop)" {
        It "distributes 6 users as 4 on Desktop 1 and 2 on Desktop 2" {
            $allocs = Get-DesktopBatchAllocation -TotalCount 6 -MaxPerDesktop 4
            $allocs.Count | Should -Be 6

            # First 4 on Desktop 1 (index 0)
            for ($i = 0; $i -lt 4; $i++) {
                $allocs[$i].AccountIndex | Should -Be $i
                $allocs[$i].DesktopIndex | Should -Be 0
                $allocs[$i].DesktopSlot | Should -Be ($i + 1)
                $allocs[$i].DesktopTotal | Should -Be 4
            }

            # Remaining 2 on Desktop 2 (index 1)
            $allocs[4].AccountIndex | Should -Be 4
            $allocs[4].DesktopIndex | Should -Be 1
            $allocs[4].DesktopSlot | Should -Be 1
            $allocs[4].DesktopTotal | Should -Be 2

            $allocs[5].AccountIndex | Should -Be 5
            $allocs[5].DesktopIndex | Should -Be 1
            $allocs[5].DesktopSlot | Should -Be 2
            $allocs[5].DesktopTotal | Should -Be 2
        }

        It "distributes 9 users across 3 desktops (4, 4, 1)" {
            $allocs = Get-DesktopBatchAllocation -TotalCount 9 -MaxPerDesktop 4
            $allocs.Count | Should -Be 9

            ($allocs | Where-Object { $_.DesktopIndex -eq 0 }).Count | Should -Be 4
            ($allocs | Where-Object { $_.DesktopIndex -eq 1 }).Count | Should -Be 4
            ($allocs | Where-Object { $_.DesktopIndex -eq 2 }).Count | Should -Be 1
            $allocs[8].DesktopSlot | Should -Be 1
            $allocs[8].DesktopTotal | Should -Be 1
        }
    }
}

Describe "TestHook contract" {
    It "does not execute past function definitions (no interactive prompt hangs the run)" {
        Get-Command Test-ProfilePathWithinBase -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Get-ValidatedProfilePath -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Merge-McpServers -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Sync-TeamMcpConfig -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Show-ProfileTable -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Get-EnrichedProfileRows -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Select-ProfileInteractive -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Add-NewProfile -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Start-LocalOrchestratorServer -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Get-DesktopBatchAllocation -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Initialize-VirtualDesktopTool -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Get-WindowGridLayout -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Initialize-WindowHelperType -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
        Get-Command Set-ClaudeWindowsLayout -ErrorAction SilentlyContinue | Should -Not -BeNullOrEmpty
    }
}