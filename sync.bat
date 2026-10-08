@echo off
setlocal
REM ============================================================================
REM sync.bat - Zero-Friction Execution Wrapper for sync.ps1
REM Automatically bypasses PowerShell ExecutionPolicy across fresh clones/devices.
REM
REM USAGE:
REM   .\sync.bat                              - Routine sync with auto commit message
REM   .\sync.bat -m "feat(scope): message"    - Sync with custom commit message
REM   .\sync.bat -SkipCI                      - Explicitly bypass GitHub Actions matrix
REM   .\sync.bat -PullOnly                    - Safely rebase-pull without committing
REM   .\sync.bat -WhatIf                      - Dry-run preview without altering git state
REM
REM NOTES:
REM   - [skip ci] is automatically appended when only operational state, memory dumps,
REM     or markdown files are staged (orchestrator-state/**, team-memory.md, dev-logs/**).
REM   - Aliases for -SkipCI: -NoCI, -SkipActions
REM   - Alias for -WhatIf: -DryRun
REM ============================================================================

where pwsh >nul 2>nul
if %ERRORLEVEL% equ 0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync.ps1" %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync.ps1" %*
)
exit /b %ERRORLEVEL%