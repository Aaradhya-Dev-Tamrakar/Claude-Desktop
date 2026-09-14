param()

$RepoRoot = $PSScriptRoot
$Pythonw = Join-Path $RepoRoot ".venv\Scripts\pythonw.exe"
$GuiScript = Join-Path $RepoRoot "tools\fleet_gui.py"

if (Test-Path $Pythonw) {
    Start-Process -FilePath $Pythonw -ArgumentList "`"$GuiScript`"" -WorkingDirectory $RepoRoot
}
else {
    Start-Process -FilePath "pythonw.exe" -ArgumentList "`"$GuiScript`"" -WorkingDirectory $RepoRoot
}
Write-Host "[+] Claude Desktop Fleet Control Center GUI launched." -ForegroundColor Green
