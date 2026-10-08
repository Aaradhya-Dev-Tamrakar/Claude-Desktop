import win32gui
import win32process
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FLEET_JSON = REPO_ROOT / "orchestrator-state" / "live-status" / "active_fleet.json"

def inspect_windows():
    import ctypes
    user32 = ctypes.windll.user32
    h_def = user32.OpenDesktopW("Default", 0, False, 0x01FF)
    if h_def:
        user32.SetThreadDesktop(h_def)

    top_windows = []
    def enum_cb(hwnd, _):
        if win32gui.IsWindow(hwnd):
            title = win32gui.GetWindowText(hwnd)
            cls = win32gui.GetClassName(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w > 200 and h > 200:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                top_windows.append({"hwnd": hwnd, "pid": pid, "title": title, "class": cls, "w": w, "h": h, "rect": rect})
        return True

    win32gui.EnumWindows(enum_cb, None)
    
    print("--- Top Level Visible Windows ---")
    claude_wins = []
    for w in top_windows:
        print(f"HWND: {w['hwnd']:<10} | PID: {w['pid']:<8} | Size: {w['w']}x{w['h']} | Title: '{w['title']}' | Class: '{w['class']}'")
        if "claude" in w['title'].lower() or "claude" in w['class'].lower() or "chrome_widgetwin_1" in w['class'].lower():
            claude_wins.append(w)
            
    print(f"\nFound {len(claude_wins)} Claude candidate windows.")
    return claude_wins

if __name__ == "__main__":
    inspect_windows()
