param()

$RepoRoot = $PSScriptRoot
$Pythonw = Join-Path $RepoRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $Pythonw)) {
    $Pythonw = "pythonw.exe"
}
$GuiScript = Join-Path $RepoRoot "tools\fleet_gui.py"

$typeDef = @"
using System;
using System.Runtime.InteropServices;

public class FleetGuiLauncher {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct STARTUPINFO {
        public int cb;
        public string lpReserved;
        public string lpDesktop;
        public string lpTitle;
        public int dwX;
        public int dwY;
        public int dwXSize;
        public int dwYSize;
        public int dwXCountChars;
        public int dwYCountChars;
        public int dwFillAttribute;
        public int dwFlags;
        public short wShowWindow;
        public short cbReserved2;
        public IntPtr lpReserved2;
        public IntPtr hStdInput;
        public IntPtr hStdOutput;
        public IntPtr hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct PROCESS_INFORMATION {
        public IntPtr hProcess;
        public IntPtr hThread;
        public int dwProcessId;
        public int dwThreadId;
    }

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern bool CreateProcess(
        string lpApplicationName,
        string lpCommandLine,
        IntPtr lpProcessAttributes,
        IntPtr lpThreadAttributes,
        bool bInheritHandles,
        uint dwCreationFlags,
        IntPtr lpEnvironment,
        string lpCurrentDirectory,
        ref STARTUPINFO lpStartupInfo,
        out PROCESS_INFORMATION lpProcessInformation
    );

    public static int SpawnInteractive(string exe, string script, string cwd) {
        STARTUPINFO si = new STARTUPINFO();
        si.cb = Marshal.SizeOf(si);
        si.lpDesktop = @"WinSta0\Default";
        PROCESS_INFORMATION pi = new PROCESS_INFORMATION();
        string cmd = "\"" + exe + "\" \"" + script + "\"";
        bool ok = CreateProcess(null, cmd, IntPtr.Zero, IntPtr.Zero, false, 0, IntPtr.Zero, cwd, ref si, out pi);
        return ok ? pi.dwProcessId : 0;
    }
}
"@

try {
    Add-Type -TypeDefinition $typeDef -Language CSharp
    $guiPid = [FleetGuiLauncher]::SpawnInteractive($Pythonw, $GuiScript, $RepoRoot)
    if ($guiPid -gt 0) {
        Write-Host "[+] Claude Desktop Fleet Control Center GUI launched on interactive desktop (PID: $guiPid)." -ForegroundColor Green
    } else {
        Start-Process -FilePath $Pythonw -ArgumentList "`"$GuiScript`"" -WorkingDirectory $RepoRoot
        Write-Host "[+] Claude Desktop Fleet Control Center GUI launched via fallback." -ForegroundColor Yellow
    }
}
catch {
    Start-Process -FilePath $Pythonw -ArgumentList "`"$GuiScript`"" -WorkingDirectory $RepoRoot
    Write-Host "[+] Claude Desktop Fleet Control Center GUI launched." -ForegroundColor Green
}
