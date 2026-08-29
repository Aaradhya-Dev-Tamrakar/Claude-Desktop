from __future__ import annotations

import asyncio
import json
import os
import re
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
        timeout: float = 180.0
    ):
        super().__init__(worker_id, nickname, ["writing", "research", "code", "qa", "seo", "formatting"])
        self.cdp_port = cdp_port
        self.cdp_host = cdp_host
        self.timeout = timeout
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

    async def _send_cdp_command(self, ws: websockets.WebSocketClientProtocol, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a JSON-RPC command over WebSocket and await result."""
        self._msg_id += 1
        cmd_id = self._msg_id
        payload = {"id": cmd_id, "method": method, "params": params or {}}
        await ws.send(json.dumps(payload))
        
        while True:
            raw = await ws.recv()
            resp = json.loads(raw)
            if resp.get("id") == cmd_id:
                return resp

    async def _eval_js(self, ws: websockets.WebSocketClientProtocol, js_expression: str) -> Any:
        """Evaluate a JavaScript expression in the page and return the unwrapped value."""
        res = await self._send_cdp_command(
            ws,
            "Runtime.evaluate",
            {"expression": js_expression, "returnByValue": True, "awaitPromise": True}
        )
        result_obj = res.get("result", {}).get("result", {})
        return result_obj.get("value")

    async def execute_task(self, task_id: str, spec: str, stage: str, context: dict[str, Any]) -> dict[str, Any]:
        """
        Automate Claude Desktop via CDP:
        1. Connect to page
        2. Check for rate limit / 5h cooldown
        3. Reset / start clean conversation
        4. Inject stage prompt & spec
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
                await asyncio.sleep(1.0)

                # 4. Construct prompt
                prompt = (
                    f"You are executing stage '{stage}' for task {task_id}.\n\n"
                    f"TASK SPECIFICATION:\n{spec}\n\n"
                    f"Please generate the complete, high-quality production deliverable directly."
                )

                # 5. Inject prompt into editor and click send
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

    async def _inject_prompt_and_send(self, ws: websockets.WebSocketClientProtocol, prompt: str) -> bool:
        """Inject prompt into ProseMirror / contenteditable and click send."""
        # Use JSON dump to safely escape quotes and multiline strings in JS
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
                // Contenteditable / ProseMirror
                editor.innerHTML = `<p>${{text.replace(/\\n/g, '<br>')}}</p>`;
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
        prev_text = ""
        stable_count = 0

        while (asyncio.get_event_loop().time() - start_time) < self.timeout:
            # 1. Check for mid-generation 429
            if await self._check_cooldown_banner(ws):
                return {"success": False, "error": "RATE_LIMIT_429"}

            # 2. Check if Stop Generating button is still active
            is_streaming_js = """
            (() => {
                const stopBtn = document.querySelector('button[aria-label*="Stop generating"], button[aria-label*="Stop"]');
                return !!stopBtn;
            })()
            """
            is_streaming = await self._eval_js(ws, is_streaming_js)

            # 3. Extract current assistant text
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

            await asyncio.sleep(1.0)

        return {"success": False, "error": f"CDP Generation timed out after {self.timeout}s"}
