# Guaranteed Windows Terminal Detachment and Console Output Suppression

- **Date:** 2026-10-08
- **Author:** Aaradhya Dev Tamrakar
- **Issue Reference:** [[Issue #16]] (https://github.com/Aaradhya-Dev-Tamrakar/Claude-Desktop/issues/16)
- **Scout Report:** [[scout_terminal_detachment]]
- **Reviewer Audit:** [[review_terminal_detachment]]

---

## 1. Problem Statement

Two operational defects were observed when launching Claude Desktop via `launch_user_n.ps1` (`launch.bat`) on Windows 11:

1. **Abrupt Child Process Termination:** When the launcher terminal window (e.g. Windows Terminal tab or console window) was closed by the user, all active `claude.exe` instances launched in that session were immediately killed by the operating system.
2. **Terminal Console Warning Spew:** Internal Node.js/Electron diagnostics (such as `MaxListenersExceededWarning`, `ExperimentalWarning`, and `$eipc_message$` buffers) polluted the terminal console, leaving a dead input buffer where prompt inputs appeared unresponsive.

---

## 2. Root Cause Analysis

### 2.1 The Windows Terminal Job Object Trap
Windows Terminal encapsulates each terminal tab inside a dedicated Win32 Job Object. By default, this Job Object is created with:

$$\text{LimitFlags} = \text{JOB\_OBJECT\_LIMIT\_KILL\_ON\_JOB\_CLOSE}\;(0\text{x}00002000)$$

Crucially, Windows Terminal omits the flag `JOB_OBJECT_LIMIT_BREAKAWAY_OK (0x00000800)` from the parent job definition. Consequently:
- Calling Win32 `CreateProcess` with `CREATE_BREAKAWAY_FROM_JOB (0x01000000)` from within the terminal process tree immediately fails with `ERROR_ACCESS_DENIED` (Win32 Error 5).
- Standard console decoupling flags (`CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS`) only isolate console control events (`CTRL+C`, `CTRL_BREAK_EVENT`); they do not alter Job Object membership.
- When the tab or terminal window closes, the kernel closes the Job Object handle, terminating every process assigned to that job tree.

### 2.2 Electron Console Attachment
Electron's native Windows bootstrap initializes console attachment by calling `AttachConsole(ATTACH_PARENT_PROCESS)`. When launched from PowerShell, Electron automatically binds standard descriptors to the host console's `CONOUT$`, streaming internal runtime diagnostics directly to the terminal buffer.

---

## 3. Architecture & Resolution

### 3.1 Win32 Parent Process Reparenting (`PROC_THREAD_ATTRIBUTE_PARENT_PROCESS`)
Because a process running inside a non-breakaway Job Object cannot break away on its own, the process must be created by an external entity that already resides outside the terminal's Job Object.

On interactive Windows desktop sessions, `explorer.exe` (the Windows shell) runs outside Windows Terminal's Job Object. Under standard Windows 11 security policies, a standard non-elevated user token possesses sufficient access rights to obtain `PROCESS_CREATE_PROCESS (0x0080)` on their own user-session `explorer.exe` process.

By utilizing extended process creation attributes:
1. Obtain an open handle to `explorer.exe` with `PROCESS_CREATE_PROCESS`.
2. Initialize a `PROC_THREAD_ATTRIBUTE_LIST` with count 1.
3. Update the attribute list with `PROC_THREAD_ATTRIBUTE_PARENT_PROCESS (0x00020000)` targeting the `explorer.exe` handle.
4. Pass `EXTENDED_STARTUPINFO_PRESENT (0x00080000)` along with `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS` to `CreateProcess`.

The resulting `claude.exe` process is parented directly under `explorer.exe`, placing it outside the terminal's Job Object and rendering it 100% immune to terminal window closures.

### 3.2 Console Suppression via `ELECTRON_NO_ATTACH_CONSOLE`
Electron natively inspects the `ELECTRON_NO_ATTACH_CONSOLE` environment variable during C++ initialization. Injecting:

```powershell
$env:ELECTRON_NO_ATTACH_CONSOLE = "1"
```

prior to process instantiation instructs Electron to bypass `AttachConsole(ATTACH_PARENT_PROCESS)`, cleanly silencing all internal Node.js diagnostic output without swallowing application-level file logging.

---

## 4. Verification Proof

- **Win32 Job Breakaway Test:** Verified `ERROR_ACCESS_DENIED` (5) when using `CREATE_BREAKAWAY_FROM_JOB` directly, validating the non-breakaway Job Object constraint.
- **Parent Process Reparenting:** Verified that `LaunchDetached` with `claude.exe` returned `ExitCode: 0` and resolved parent PID to `explorer.exe`.
- **Pester Specs:** 51/51 tests passing in `tests/launch_user_n.Tests.ps1`.
- **FastMCP Specs:** 37/37 specs passing in `tests/orchestrator_mcp_test.py`.
- **CI Self-Healing Audit:** 100% clean pass across 334 scanned state files.
