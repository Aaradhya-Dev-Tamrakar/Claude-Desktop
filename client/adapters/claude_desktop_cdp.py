from __future__ import annotations

import asyncio
import json
import os
from typing import Any
import httpx
import websockets

from client.adapters.base_adapter import BaseWorkerAdapter

class ClaudeDesktopCDPAdapter(BaseWorkerAdapter):
    """
    Adapter automating a locally running Claude Desktop Electron app
    via Chrome DevTools Protocol (CDP) without requiring paid API keys.
    """
    def __init__(
        self,
        worker_id: str,
        nickname: str,
        cdp_port: int = 9222,
        cdp_host: str = "127.0.0.1",
        preferred_model: str = "claude-3-5-sonnet",
        thinking_budget: int = 0,
        timeout: float = 180.0,
        poll_interval: float | None = None,
    ):
        super().__init__(worker_id, nickname, ["writing", "research", "code", "qa", "seo", "formatting"])
        self.cdp_port = cdp_port
        self.cdp_host = cdp_host
        self.preferred_model = preferred_model
        self.thinking_budget = thinking_budget
        self.timeout = timeout
        self.poll_interval = poll_interval if poll_interval is not None else max(
            0.5, float(os.getenv("CLAUDE_CDP_POLL_INTERVAL_SECONDS", "2"))
        )
        self._msg_id = 0

    @property
    def http_url(self) -> str:
        return f"http://{self.cdp_host}:{self.cdp_port}"

    async def check_health(self) -> bool:
        """Check if Claude Desktop Electron process is exposing CDP port and has an active page."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{self.http_url}/json/version")
                if r.status_code == 200:
                    return True
        except Exception:
            return False
        return False

    async def get_page_ws_url(self) -> str | None:
        """Find the WebSocket debugger URL for the active Claude Desktop UI page."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.http_url}/json/list")
                if r.status_code != 200:
                    return None
                targets = r.json()
                # Find page target
                for t in targets:
                    if t.get("type") in ("page", "webview", "app"):
                        ws_url = t.get("webSocketDebuggerUrl")
                        if ws_url:
                            return ws_url
                if targets and "webSocketDebuggerUrl" in targets[0]:
                    return targets[0]["webSocketDebuggerUrl"]
        except Exception:
            return None
        return None

    async def wait_until_ready(self, timeout: float = 30.0) -> bool:
        """Poll until Claude Desktop CDP is reachable and ProseMirror editor element is mounted."""
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) < timeout:
            ws_url = await self.get_page_ws_url()
            if ws_url:
                try:
                    async with websockets.connect(ws_url, max_size=5_000_000, open_timeout=3.0) as ws:
                        await self._send_cdp_command(ws, "Runtime.enable")
                        await self._dismiss_overlays(ws)
                        check_js = """
                        (() => {
                            const editor = document.querySelector('.ProseMirror, div[contenteditable="true"], textarea');
                            return !!editor;
                        })()
                        """
                        is_ready = await self._eval_js(ws, check_js)
                        if is_ready:
                            return True
                except Exception:
                    pass
            await asyncio.sleep(1.0)
        return False

    async def _send_cdp_command(
        self,
        ws: websockets.WebSocketClientProtocol,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30.0
    ) -> dict[str, Any]:
        """Send a JSON-RPC command over WebSocket and await result with timeout."""
        self._msg_id += 1
        cmd_id = self._msg_id
        payload = {"id": cmd_id, "method": method, "params": params or {}}
        await ws.send(json.dumps(payload))
        
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) < timeout:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                resp = json.loads(raw)
                if resp.get("id") == cmd_id:
                    return resp
            except asyncio.TimeoutError:
                break
        raise TimeoutError(f"CDP command {method} (id={cmd_id}) timed out after {timeout}s")

    async def _eval_js(self, ws: websockets.WebSocketClientProtocol, js_expression: str) -> Any:
        """Evaluate a JavaScript expression in the page and return the unwrapped value."""
        res = await self._send_cdp_command(
            ws,
            "Runtime.evaluate",
            {"expression": js_expression, "returnByValue": True, "awaitPromise": True}
        )
        if "exceptionDetails" in res.get("result", {}):
            desc = res["result"]["exceptionDetails"].get("text", "JS Exception")
            raise RuntimeError(f"CDP JavaScript evaluation failed: {desc}")
        result_obj = res.get("result", {}).get("result", {})
        return result_obj.get("value")

    async def execute_task(self, task_id: str, spec: str, stage: str, context: dict[str, Any]) -> dict[str, Any]:
        """
        Automate Claude Desktop via CDP:
        1. Connect to page
        2. Check for rate limit / 5h cooldown
        3. Reset / start clean conversation
        4. Inject stage prompt & spec safely without DOM XSS
        5. Submit and wait for stream completion
        6. Extract response
        """
        ws_url = await self.get_page_ws_url()
        if not ws_url:
            return {
                "success": False,
                "error": f"Claude Desktop CDP not reachable at {self.http_url}. Make sure launch_user_n.ps1 was run with -RemoteDebuggingPort {self.cdp_port}.",
                "summary": "",
                "result_text": ""
            }

        try:
            async with websockets.connect(ws_url, max_size=10_000_000, open_timeout=10.0) as ws:
                # 1. Enable Runtime & DOM
                await self._send_cdp_command(ws, "Runtime.enable")

                # 2. Check if a cooldown / rate-limit banner is already displayed
                is_limited = await self._check_cooldown_banner(ws)
                if is_limited:
                    return {
                        "success": False,
                        "error": "RATE_LIMIT_429",
                        "summary": "Detected Claude 5-hour limit / cooldown in UI",
                        "result_text": ""
                    }

                # 3. Start a new chat to keep context window clean
                await self._start_new_chat(ws)
                await asyncio.sleep(0.5)

                # 3b. Dismiss any overlays & ensure target model / thinking mode
                await self._dismiss_overlays(ws)
                await self._ensure_model_and_thinking(ws, self.preferred_model, self.thinking_budget)
                await asyncio.sleep(0.5)

                # 4. Construct prompt
                prompt = (
                    f"You are executing stage '{stage}' for task {task_id}.\n\n"
                    f"TASK SPECIFICATION:\n{spec}\n\n"
                    f"Please generate the complete, high-quality production deliverable directly."
                )

                # 5. Inject prompt into editor and click send (XSS-safe textContent injection)
                injected = await self._inject_prompt_and_send(ws, prompt)
                if not injected:
                    return {
                        "success": False,
                        "error": "Failed to inject prompt into Claude Desktop editor element",
                        "summary": "",
                        "result_text": ""
                    }

                # 6. Wait for response generation to complete
                generation_res = await self._wait_for_generation_complete(ws)
                if not generation_res.get("success"):
                    return generation_res

                result_text = generation_res.get("result_text", "").strip()
                if not result_text:
                    return {
                        "success": False,
                        "error": "Empty response received from Claude Desktop",
                        "summary": "",
                        "result_text": ""
                    }

                return {
                    "success": True,
                    "summary": f"Completed {stage} via Claude Desktop (CDP : {self.nickname})",
                    "result_text": result_text,
                    "error": None
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"CDP Execution Exception: {e}",
                "summary": "",
                "result_text": ""
            }

    async def _check_cooldown_banner(self, ws: websockets.WebSocketClientProtocol) -> bool:
        """Scan DOM for 5-hour usage limit and cooldown warnings."""
        js = """
        (() => {
            const bodyText = document.body ? document.body.innerText : "";
            const patterns = [
                /You've reached your (usage|message) limit/i,
                /Free plan limit reached/i,
                /You can send more messages at/i,
                /Try again in/i,
                /usage limit reached/i
            ];
            return patterns.some(p => p.test(bodyText));
        })()
        """
        res = await self._eval_js(ws, js)
        return bool(res)

    async def _start_new_chat(self, ws: websockets.WebSocketClientProtocol) -> None:
        """Click new chat or reset conversation."""
        js = """
        (() => {
            // Find New Chat button or link
            const newChatBtn = document.querySelector('button[aria-label*="New chat"], a[href="/new"], button[data-testid="new-chat-button"]');
            if (newChatBtn) {
                newChatBtn.click();
                return true;
            }
            return false;
        })()
        """
        await self._eval_js(ws, js)

    async def _dismiss_overlays(self, ws: websockets.WebSocketClientProtocol) -> None:
        """Dismiss non-essential popups (update notes, cookie/terms banners)."""
        js = """
        (() => {
            const btns = document.querySelectorAll('button[aria-label="Close"], button[data-testid="close-button"], div[role="dialog"] button');
            for (const b of btns) {
                const txt = (b.innerText || b.textContent || "").toLowerCase();
                if (txt.includes("close") || txt.includes("got it") || txt.includes("dismiss") || txt.includes("continue")) {
                    b.click();
                }
            }
            return true;
        })()
        """
        try:
            await self._eval_js(ws, js)
        except Exception:
            pass

    async def _ensure_model_and_thinking(self, ws: websockets.WebSocketClientProtocol, target_model: str, thinking_budget: int = 0) -> None:
        """Ensure correct model and thinking mode are selected in the UI before prompt dispatch."""
        if not target_model:
            return

        model_clean = target_model.lower()
        if "haiku" in model_clean:
            model_keyword = "haiku"
        elif "opus" in model_clean:
            model_keyword = "opus"
        else:
            model_keyword = "sonnet"

        js = f"""
        (async () => {{
            const targetKeyword = {json.dumps(model_keyword)};
            const targetBudget = {thinking_budget};

            // 1. Check current model selector button
            const modelBtn = document.querySelector('button[aria-label*="model" i], [data-testid="model-selector-dropdown"], button[aria-haspopup="menu"]');
            if (modelBtn) {{
                const currentText = (modelBtn.innerText || modelBtn.textContent || "").toLowerCase();
                if (!currentText.includes(targetKeyword)) {{
                    modelBtn.click();
                    await new Promise(r => setTimeout(r, 250));
                    const options = Array.from(document.querySelectorAll('[role="menuitem"], [role="option"], button'));
                    const match = options.find(opt => (opt.innerText || opt.textContent || "").toLowerCase().includes(targetKeyword));
                    if (match) {{
                        match.click();
                        await new Promise(r => setTimeout(r, 200));
                    }}
                }}
            }}

            // 2. Extended Thinking configuration if requested
            if (targetBudget > 0) {{
                const thinkingToggle = document.querySelector('button[aria-label*="Thinking" i], [data-testid*="thinking" i], button[aria-label*="Extended thinking" i]');
                if (thinkingToggle) {{
                    const isPressed = thinkingToggle.getAttribute('aria-pressed') === 'true' || thinkingToggle.classList.contains('active');
                    if (!isPressed) {{
                        thinkingToggle.click();
                    }}
                }}
            }}
            return true;
        }})()
        """
        try:
            await self._eval_js(ws, js)
        except Exception:
            pass

    async def _inject_prompt_and_send(self, ws: websockets.WebSocketClientProtocol, prompt: str) -> bool:
        """Inject prompt into ProseMirror / contenteditable and click send safely without innerHTML."""
        prompt_json = json.dumps(prompt)
        js = f"""
        (() => {{
            const text = {prompt_json};
            // Look for ProseMirror editor
            const editor = document.querySelector('.ProseMirror, div[contenteditable="true"], textarea');
            if (!editor) return false;
            
            editor.focus();
            if (editor.tagName.toLowerCase() === 'textarea') {{
                editor.value = text;
                editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
                editor.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }} else {{
                // Contenteditable / ProseMirror - DOM text node creation (XSS immune)
                editor.textContent = '';
                const lines = text.split('\\n');
                lines.forEach((line) => {{
                    const p = document.createElement('p');
                    p.textContent = line || '\\u200B';
                    editor.appendChild(p);
                }});
                editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
            
            // Allow React state to sync
            setTimeout(() => {{
                // Click Send Button
                const sendBtn = document.querySelector('button[aria-label*="Send Message"], button[aria-label*="Send"], button[data-testid="send-button"], button.bg-accent-main-100');
                if (sendBtn && !sendBtn.disabled) {{
                    sendBtn.click();
                }} else {{
                    // Fallback to Enter keydown
                    editor.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
                }}
            }}, 300);
            return true;
        }})()
        """
        return bool(await self._eval_js(ws, js))

    async def _wait_for_generation_complete(self, ws: websockets.WebSocketClientProtocol) -> dict[str, Any]:
        """Poll until generation stop button disappears and text settles."""
        start_time = asyncio.get_event_loop().time()
        # Give 1.5s initial grace period for streaming transition
        await asyncio.sleep(1.5)
        
        prev_text = ""
        stable_count = 0

        while (asyncio.get_event_loop().time() - start_time) < self.timeout:
            # 1. Check for mid-generation 429
            if await self._check_cooldown_banner(ws):
                return {"success": False, "error": "RATE_LIMIT_429"}

            # 2. Check for explicit error banners
            error_js = """
            (() => {
                const err = document.querySelector('[data-testid="error-message"], .text-danger');
                return err ? (err.innerText || err.textContent) : null;
            })()
            """
            err_msg = await self._eval_js(ws, error_js)
            if err_msg:
                return {"success": False, "error": f"Claude UI Error: {err_msg}"}

            # 3. Check if Stop Generating button is still active
            is_streaming_js = """
            (() => {
                const stopBtn = document.querySelector('button[aria-label*="Stop generating"], button[aria-label*="Stop"]');
                return !!stopBtn;
            })()
            """
            is_streaming = await self._eval_js(ws, is_streaming_js)

            # 4. Extract current assistant text
            get_text_js = """
            (() => {
                const msgs = document.querySelectorAll('.font-claude-message, [data-is-streaming], div[class*="claude-response"], .grid-cols-1');
                if (msgs.length > 0) {
                    const last = msgs[msgs.length - 1];
                    return last.innerText || last.textContent;
                }
                return "";
            })()
            """
            current_text = await self._eval_js(ws, get_text_js) or ""

            if not is_streaming and current_text:
                if current_text == prev_text:
                    stable_count += 1
                    if stable_count >= 2:  # Stable across 2 polling cycles
                        return {"success": True, "result_text": current_text}
                else:
                    stable_count = 0
                    prev_text = current_text

            await asyncio.sleep(self.poll_interval)

        return {"success": False, "error": f"CDP Generation timed out after {self.timeout}s"}


class ClaudeDesktopUIAAdapter(BaseWorkerAdapter):
    """
    Automates prompt delivery to Claude Desktop on Windows via UI Automation / SendInput.
    Brings the target profile window (HWND) to the foreground on Desktop 2, pastes the
    prompt into the input field via Windows clipboard, and presses Enter to submit.
    """

    def __init__(
        self,
        worker_id: str,
        nickname: str,
        hwnd: int | None = None,
        role: str = "worker",
        preferred_model: str = "claude-3-5-sonnet",
        thinking_budget: int = 0,
    ):
        super().__init__(worker_id, nickname, ["writing", "research", "code", "qa", "seo", "formatting"])
        self.hwnd = hwnd
        self.role = role
        self.preferred_model = preferred_model
        self.thinking_budget = thinking_budget

    @staticmethod
    def _attach_default_desktop():
        try:
            import ctypes
            user32 = ctypes.windll.user32
            h_def = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_def:
                user32.SetThreadDesktop(h_def)
        except Exception:
            pass

    async def check_health(self) -> bool:
        """Verify the window handle is alive and visible."""
        if not self.hwnd:
            return False
        self._attach_default_desktop()
        import win32gui
        return bool(win32gui.IsWindow(self.hwnd) and win32gui.IsWindowVisible(self.hwnd))

    def _focus_window(self) -> bool:
        """Bring window to foreground safely handling Windows focus locks and virtual desktops."""
        if not self.hwnd:
            return False
        self._attach_default_desktop()
        import win32gui, win32con, win32process, ctypes, subprocess, re, time
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        dwmapi = ctypes.windll.dwmapi
        try:
            # If window is cloaked on an inactive virtual desktop, switch to its desktop first
            DWMWA_CLOAKED = 14
            cloaked = ctypes.c_uint()
            dwmapi.DwmGetWindowAttribute(self.hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
            if cloaked.value != 0:
                vd_exe = Path(__file__).resolve().parent.parent.parent / "tools" / "VirtualDesktop.exe"
                if vd_exe.exists():
                    res = subprocess.run([str(vd_exe), f"/GetDesktopFromWindowHandle:{self.hwnd}"], capture_output=True, text=True)
                    for line in res.stdout.splitlines():
                        if "desktop number" in line.lower():
                            m = re.search(r"desktop number (\d+)", line, re.IGNORECASE)
                            if m:
                                subprocess.run([str(vd_exe), f"/Switch:{m.group(1)}"], capture_output=True)
                                time.sleep(0.3)
                                break

            if win32gui.IsIconic(self.hwnd):
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)

            # Bypass Windows foreground lock restriction
            user32.AllowSetForegroundWindow(-1)
            VK_MENU = 0x12
            KEYEVENTF_KEYUP = 0x0002
            user32.keybd_event(VK_MENU, 0, 0, 0)
            time.sleep(0.02)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

            current_thread = kernel32.GetCurrentThreadId()
            target_thread, _ = win32process.GetWindowThreadProcessId(self.hwnd)
            user32.AttachThreadInput(current_thread, target_thread, True)

            user32.ShowWindow(self.hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(self.hwnd)
            try:
                user32.SwitchToThisWindow(self.hwnd, True)
            except Exception:
                pass
            user32.BringWindowToTop(self.hwnd)

            user32.AttachThreadInput(current_thread, target_thread, False)
            time.sleep(0.2)

            # Click in prompt textarea area to ensure caret focus
            rect = win32gui.GetWindowRect(self.hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w > 150 and h > 150:
                cx = rect[0] + w // 2
                cy = rect[1] + int(h * 0.88)
                user32.SetCursorPos(cx, cy)
                MOUSEEVENTF_LEFTDOWN = 0x0002
                MOUSEEVENTF_LEFTUP = 0x0004
                user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.05)
                user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                time.sleep(0.15)

            return True
        except Exception as e:
            print(f"DEBUG: _focus_window error for HWND {self.hwnd}: {e}")
            return False

    def _paste_and_enter(self, text: str) -> bool:
        """Paste text into current focus and send Enter keypress."""
        self._attach_default_desktop()
        import win32clipboard, ctypes, time
        user32 = ctypes.windll.user32

        for _ in range(5):
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                break
            except Exception:
                time.sleep(0.1)
        else:
            return False

        time.sleep(0.2)

        VK_CONTROL = 0x11
        VK_V = 0x56
        VK_RETURN = 0x0D
        KEYEVENTF_KEYUP = 0x0002

        # Press Ctrl+V
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_V, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

        time.sleep(0.35)

        # Press Enter
        user32.keybd_event(VK_RETURN, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.2)

        return True

    async def execute_task(self, task_id: str, spec: str, stage: str, context: dict[str, Any]) -> dict[str, Any]:
        """Activate the window and dispatch prompt."""
        loop = asyncio.get_running_loop()

        def _do_dispatch():
            if not self._focus_window():
                return {"success": False, "error": f"Failed to focus window for {self.worker_id} (HWND={self.hwnd})"}

            prompt = (
                f"You are executing stage '{stage}' for task {task_id}.\n\n"
                f"TASK SPECIFICATION:\n{spec}\n\n"
                f"Please generate the complete, high-quality production deliverable directly."
            )
            ok = self._paste_and_enter(prompt)
            if not ok:
                return {"success": False, "error": "Clipboard paste or Enter submission failed."}

            return {
                "success": True,
                "summary": f"Prompt dispatched to {self.worker_id} window on desktop.",
                "result_text": "Dispatched to window. Model is generating response in UI."
            }

        return await loop.run_in_executor(None, _do_dispatch)

    async def send_text(self, text: str) -> dict[str, Any]:
        """Direct prompt injection without task headers."""
        loop = asyncio.get_running_loop()

        def _do_send():
            if not self._focus_window():
                return {"success": False, "error": f"Failed to focus window for {self.worker_id} (HWND={self.hwnd})"}
            ok = self._paste_and_enter(text)
            if not ok:
                return {"success": False, "error": "Clipboard paste or Enter submission failed."}
            return {
                "success": True,
                "summary": f"Prompt sent to {self.worker_id}.",
                "result_text": "Dispatched to window."
            }

        return await loop.run_in_executor(None, _do_send)
