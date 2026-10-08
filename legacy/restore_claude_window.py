import win32gui
import win32con
import win32process
import ctypes
import subprocess
import json

def restore_all_claude_windows():
    claude_pids = set()
    try:
        cmd = ["powershell", "-NoProfile", "-Command", "Get-Process claude -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if line.strip().isdigit():
                claude_pids.add(int(line.strip()))
    except Exception:
        pass

    print(f"Found {len(claude_pids)} Claude processes: {claude_pids}")

    found_windows = []
    def enum_cb(hwnd, _):
        if win32gui.IsWindow(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid in claude_pids:
                title = win32gui.GetWindowText(hwnd)
                cls = win32gui.GetClassName(hwnd)
                rect = win32gui.GetWindowRect(hwnd)
                w = rect[2] - rect[0]
                h = rect[3] - rect[1]
                found_windows.append((hwnd, pid, title, cls, w, h))
                print(f"Restoring HWND {hwnd} (PID {pid}, Title: '{title}', Class: '{cls}', Size: {w}x{h})")
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                try:
                    win32gui.SetForegroundWindow(hwnd)
                except Exception:
                    pass
        return True

    win32gui.EnumWindows(enum_cb, None)
    print(f"Restored {len(found_windows)} windows.")

if __name__ == "__main__":
    restore_all_claude_windows()
