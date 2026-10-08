# Scout Report: Investigation of Terminal Detachment & Process Isolation in Claude Desktop (Windows)

**Target Repository:** `F:\Aaradhya-Dev-Tamrakar\Claude-Desktop`  
**Issue Reference:** #16 (`fix(launcher): guarantee true terminal detachment, suppress console output, and prevent child termination on exit`)  
**Investigator:** Scout Agent (research / flash)  
**Date:** 2026-10-08  

---

## 1. Concrete Inspection of `launch_user_n.ps1`

### 1.1 `ClaudeDesktopWindowHelper.LaunchOnDefaultDesktop` (Lines 1572–1605)

```csharp
// Lines 1572-1577
public const uint STARTF_USESHOWWINDOW = 0x00000001;
public const short SW_SHOWNORMAL = 1;
public const uint CREATE_NEW_PROCESS_GROUP = 0x00000200;
public const uint CREATE_BREAKAWAY_FROM_JOB = 0x01000000;
public const uint DETACHED_PROCESS = 0x00000008;

// Lines 1587-1605
public static int LaunchOnDefaultDesktop(string exePath, string args) {
    AttachToDefaultDesktop();
    STARTUPINFO si = new STARTUPINFO();
    si.cb = Marshal.SizeOf(si);
    si.lpDesktop = @"WinSta0\Default";
    si.dwFlags = (int)STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_SHOWNORMAL;
    PROCESS_INFORMATION pi = new PROCESS_INFORMATION();
    string cmd = string.IsNullOrEmpty(args) ? ("\"" + exePath + "\"") : ("\"" + exePath + "\" " + args);
    uint creationFlags = CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS;
    bool success = CreateProcess(null, cmd, IntPtr.Zero, IntPtr.Zero, false, creationFlags, IntPtr.Zero, null, ref si, out pi);
    if (success) {
        int pid = pi.dwProcessId;
        if (pi.hProcess != IntPtr.Zero) CloseHandle(pi.hProcess);
        if (pi.hThread != IntPtr.Zero) CloseHandle(pi.hThread);
        return pid;
    }
    return 0;
}
```

**Key Code Observations:**
- `CREATE_BREAKAWAY_FROM_JOB = 0x01000000` is defined as a constant at line 1575, but `creationFlags` at line 1596 only uses `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS`.
- `si.dwFlags` contains only `STARTF_USESHOWWINDOW` (`0x00000001`). `STARTF_USESTDHANDLES` (`0x00000100`) is omitted. `si.hStdOutput`, `si.hStdError`, and `si.hStdInput` are left unassigned (`IntPtr.Zero`).
- `bInheritHandles` is `false`.

### 1.2 `Invoke-ProfileLaunch` (Lines 2460–2494)

- `$OutLog` and `$ErrLog` are defined and their directories ensured, but they are **never passed** to `[ClaudeDesktopWindowHelper]::LaunchOnDefaultDesktop($ClaudeExe, $argsStr)`. The method signature takes only `(string exePath, string args)`. The log paths are completely orphaned.
- The fallback `Start-Process` calls .NET `Process.Start` without breakaway or redirection.

---

## 2. Root Cause Analysis: Why Closing the Terminal Kills `claude.exe`

### 2.1 The Windows Terminal Job Object Trap
- On Windows 11, Windows Terminal (`WindowsTerminal.exe` / `OpenConsole.exe`) hosts each tab inside a dedicated NT Job Object.
- It sets `LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x00002000)`.
- It intentionally does **not** enable `JOB_OBJECT_LIMIT_BREAKAWAY_OK (0x00000800)` or `JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK (0x00001000)`.
- **Live Empirical Verification:**
  `QueryInformationJobObject` on the active `pwsh.exe` session returned:
  - `LimitFlagsHex : 0x00002000`
  - `KILL_ON_JOB_CLOSE : True`
  - `BREAKAWAY_OK : False`

### 2.2 Why `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS` Did Not Prevent Termination
- `CREATE_NEW_PROCESS_GROUP` and `DETACHED_PROCESS` are Console Subsystem creation flags only.
- In Windows NT kernel (`ntoskrnl.exe`), when a process in a Job Object calls `CreateProcess`, all child processes are automatically and involuntarily assigned to the parent's Job Object.
- When the user closes Windows Terminal, the terminal host closes its handle to the Job Object. The NT kernel immediately executes `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, terminating all member processes (`pwsh.exe` and `claude.exe` alike).

### 2.3 Why `CREATE_BREAKAWAY_FROM_JOB` Cannot Be Used Directly
- MSDN: `CREATE_BREAKAWAY_FROM_JOB` is valid **only** if the parent's Job Object has `JOB_OBJECT_LIMIT_BREAKAWAY_OK`.
- If the parent Job Object lacks this flag, `CreateProcess` fails with **Error 5 (`ERROR_ACCESS_DENIED`)**.

---

## 3. Root Cause Analysis: Node.js / Electron Warnings in Terminal

### 3.1 Electron Native `AttachConsole`
- Electron contains native C++ startup logic calling `AttachConsole(ATTACH_PARENT_PROCESS)`.
- Because `pwsh.exe` is the direct parent, Electron attaches to `pwsh.exe`'s console and reopens `CONOUT$`.
- As a result, Node.js internal warnings (`MaxListenersExceededWarning`, `ExperimentalWarning`, `$eipc_message$`) are printed directly into the launcher's terminal window.
- Setting `$env:ELECTRON_NO_ATTACH_CONSOLE = "1"` tells Electron not to attach to the parent console.

---

## 4. Evaluation of Process Launching & Isolation Techniques

| Launch Method | Job Object Immunity | Console Suppression | CLI Argument Support | Interactive Desktop (`WinSta0\Default`) | Empirical Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. `CreateProcess` + `CREATE_BREAKAWAY_FROM_JOB`** | ❌ Fails | ⚠️ Partial | ✅ Full | ✅ Full | Fails with Error 5 in Windows Terminal |
| **2. `explorer.exe <exe> <args>`** | N/A | N/A | ❌ Fails | N/A | Fails (Explorer treats args as folders) |
| **3. `WScript.Shell.Run`** | ❌ Fails | ❌ Inherited | ✅ Full | ✅ Full | Fails (Child remains in Job Object) |
| **4. COM `Shell.Application.ShellExecute`** | ❌ Fails | ⚠️ Partial | ✅ Full | ✅ Full | Fails (Child retains `pwsh.exe` parent & Job Object) |
| **5. WMI `Win32_Process.Create`** | ✅ Escapes Job | ✅ Detached | ✅ Full | ❌ Non-interactive | Unsuitable for GUI apps |
| **6. Extended `CreateProcess` (`PROC_THREAD_ATTRIBUTE_PARENT_PROCESS` -> `explorer.exe`)** | ✅ **100% Immune** | ✅ **100% Detached** | ✅ Full | ✅ **Full interactive access** | **Recommended Primary Engine** |
| **7. Transient User Scheduled Task (`schtasks.exe /it`)** | ✅ **100% Immune** | ✅ **100% Detached** | ✅ Full | ✅ **Full interactive access** | **Recommended Universal Fallback** |

---

## 5. Architectural Recommendations

1. **Console Warning Suppression**:
   - Set `$env:ELECTRON_NO_ATTACH_CONSOLE = "1"` in `launch_user_n.ps1` before spawning.
   - Redirect standard handles in `STARTUPINFO` (`hStdOutput`/`hStdError` to `NUL` or `$OutLog`/`$ErrLog`).
2. **Two-Tier Resilient Process Breakaway**:
   - **Tier 1 (Primary)**: Win32 Extended `CreateProcess` with `PROC_THREAD_ATTRIBUTE_PARENT_PROCESS` targeting `explorer.exe`. This causes the kernel to adopt `explorer.exe` as the parent, creating `claude.exe` outside Windows Terminal's Job Object on the interactive desktop.
   - **Tier 2 (Fallback)**: Transient `schtasks.exe /create ... /it` and `schtasks /run` to launch out-of-band under Task Scheduler service if parent spoofing is restricted by OS policy.
