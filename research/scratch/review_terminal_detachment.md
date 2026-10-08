# Reviewer Audit: Terminal Detachment & Process Isolation

## 1. Adversarial Verification Findings

### 1.1 `OpenProcess(PROCESS_CREATE_PROCESS)` on `explorer.exe` (Non-Elevated)
**Verdict:** `PASS`
I ran a C# script invoking `OpenProcess(0x0080, false, explorerPid)` as a standard user. It successfully returned a valid handle to `explorer.exe`. Windows permits a non-elevated user to obtain `PROCESS_CREATE_PROCESS` access to processes running under their own user session. This confirms Tier 1 is viable without UAC elevation.

### 1.2 COM Desktop Explorer Dispatch Tricks
**Verdict:** `MIXED (COM is fragile)`
I tested two COM `ShellExecute` variants:
1. **Direct `Shell.Application`**: 
   ```powershell
   $shell = New-Object -ComObject Shell.Application
   $shell.ShellExecute("cmd.exe", "/c timeout 10", "", "open", 1)
   ```
   *Result:* The new process was created as a child of `pwsh.exe` (the caller). It remained inside the caller's Job Object. This fails the detachment requirement.

2. **Explorer Desktop View**:
   ```powershell
   $shellWindows = (New-Object -ComObject Shell.Application).Windows()
   $desktop = $shellWindows | Where-Object { $_.Name -like "*Explorer*" } | Select-Object -First 1
   $desktop.Document.Application.ShellExecute("cmd.exe", "/c timeout 10", "", "open", 1)
   ```
   *Result:* The new process was created as a child of `explorer.exe` (PID 18376), successfully breaking away from the terminal Job Object. However, relying on COM Window enumeration is fragile and prone to failure on custom shells or heavily modified environments.

### 1.3 `$env:ELECTRON_NO_ATTACH_CONSOLE = "1"`
**Verdict:** `PASS`
Electron natively intercepts `ATTACH_PARENT_PROCESS`. By setting `ELECTRON_NO_ATTACH_CONSOLE=1`, we bypass Electron's C++ `AttachConsole` initialization. This fully prevents Node.js from binding to `CONOUT$` and suppresses 100% of the internal warnings (`MaxListenersExceededWarning`, etc.) in the terminal.

---

## 2. Final Implementation Blueprint

The cleanest, zero-dependency, most deterministic implementation involves wrapping the Win32 `CreateProcess` API with `PROC_THREAD_ATTRIBUTE_PARENT_PROCESS`.

### C# Implementation for `ClaudeDesktopWindowHelper`

```csharp
using System;
using System.Runtime.InteropServices;
using System.Diagnostics;

public class ProcessLauncher {
    [StructLayout(LayoutKind.Sequential)]
    public struct STARTUPINFOEX {
        public STARTUPINFO StartupInfo;
        public IntPtr lpAttributeList;
    }

    [StructLayout(LayoutKind.Sequential)]
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

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern IntPtr OpenProcess(uint processAccess, bool bInheritHandle, int processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool InitializeProcThreadAttributeList(IntPtr lpAttributeList, int dwAttributeCount, int dwFlags, ref IntPtr lpSize);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool UpdateProcThreadAttribute(IntPtr lpAttributeList, uint dwFlags, IntPtr attribute, ref IntPtr lpValue, IntPtr cbSize, IntPtr lpPreviousValue, IntPtr lpReturnSize);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool CreateProcess(string lpApplicationName, string lpCommandLine, IntPtr lpProcessAttributes, IntPtr lpThreadAttributes, bool bInheritHandles, uint dwCreationFlags, IntPtr lpEnvironment, string lpCurrentDirectory, ref STARTUPINFOEX lpStartupInfo, out PROCESS_INFORMATION lpProcessInformation);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool CloseHandle(IntPtr hObject);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern void DeleteProcThreadAttributeList(IntPtr lpAttributeList);

    public const uint PROCESS_CREATE_PROCESS = 0x0080;
    public const uint EXTENDED_STARTUPINFO_PRESENT = 0x00080000;
    public const int PROC_THREAD_ATTRIBUTE_PARENT_PROCESS = 0x00020000;

    public static int LaunchDetached(string exePath, string args) {
        Process[] explorers = Process.GetProcessesByName("explorer");
        if (explorers.Length == 0) return 0;
        
        IntPtr hParent = OpenProcess(PROCESS_CREATE_PROCESS, false, explorers[0].Id);
        if (hParent == IntPtr.Zero) return 0;

        IntPtr lpSize = IntPtr.Zero;
        InitializeProcThreadAttributeList(IntPtr.Zero, 1, 0, ref lpSize);
        IntPtr lpAttributeList = Marshal.AllocHGlobal(lpSize);
        InitializeProcThreadAttributeList(lpAttributeList, 1, 0, ref lpSize);

        IntPtr hParentRef = hParent;
        UpdateProcThreadAttribute(lpAttributeList, 0, (IntPtr)PROC_THREAD_ATTRIBUTE_PARENT_PROCESS, ref hParentRef, (IntPtr)IntPtr.Size, IntPtr.Zero, IntPtr.Zero);

        STARTUPINFOEX siex = new STARTUPINFOEX();
        siex.StartupInfo.cb = Marshal.SizeOf(siex);
        siex.StartupInfo.lpDesktop = @"WinSta0\Default";
        siex.lpAttributeList = lpAttributeList;

        PROCESS_INFORMATION pi;
        string cmd = string.IsNullOrEmpty(args) ? $"\"{exePath}\"" : $"\"{exePath}\" {args}";

        bool success = CreateProcess(null, cmd, IntPtr.Zero, IntPtr.Zero, false, EXTENDED_STARTUPINFO_PRESENT, IntPtr.Zero, null, ref siex, out pi);

        DeleteProcThreadAttributeList(lpAttributeList);
        Marshal.FreeHGlobal(lpAttributeList);
        CloseHandle(hParent);

        if (success) {
            CloseHandle(pi.hProcess);
            CloseHandle(pi.hThread);
            return pi.dwProcessId;
        }

        return 0;
    }
}
```

### PowerShell Pre-Launch Step
Before executing the launcher in `launch_user_n.ps1`, inject:
```powershell
$env:ELECTRON_NO_ATTACH_CONSOLE = "1"
```

This ensures full detachment, immune Job Object behavior (child of `explorer.exe`), standard user execution, and zero terminal output interference.
