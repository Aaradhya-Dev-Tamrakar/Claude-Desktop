from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = REPO_ROOT / "outputs" / "runs"
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8000/api/v1")

def show_windows_toast(title: str, message: str) -> None:
    """Trigger a Windows desktop toast notification via PowerShell."""
    ps_cmd = f"""
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    $template = @"
    <toast>
        <visual>
            <binding template="ToastGeneric">
                <text>{title}</text>
                <text>{message}</text>
            </binding>
        </visual>
    </toast>
"@
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($template)
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Claude Desktop Fleet")
    $notifier.Show($toast)
    """
    try:
        subprocess.run(["pwsh", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=5)
    except Exception:
        pass

async def harvest_completed_jobs(client: httpx.AsyncClient, seen_jobs: set[str]) -> None:
    """Check for completed jobs and compile deliverables."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        r = await client.get(f"{ORCHESTRATOR_URL}/jobs", params={"status": "completed"})
        if r.status_code != 200:
            return
        jobs = r.json()
        for job in jobs:
            job_id = job["id"]
            if job_id in seen_jobs:
                continue

            # Fetch tasks and checkpoints for this job
            t_resp = await client.get(f"{ORCHESTRATOR_URL}/tasks", params={"job_id": job_id})
            if t_resp.status_code != 200:
                continue
            tasks = t_resp.json()

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            report_file = OUTPUTS_DIR / f"{job_id}_{timestamp}.md"

            content_blocks = [
                f"# Autonomous Fleet Deliverable: {job_id}",
                f"- **Completed At:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                f"- **Pipeline:** {job.get('pipeline')}",
                f"- **Status:** COMPLETED & QA AUDITED",
                "\n---\n"
            ]

            for t in sorted(tasks, key=lambda x: x.get("stage_order", 0)):
                stage = t.get("stage", "stage")
                content_blocks.append(f"## Stage: {stage.upper()} ({t.get('id')})")
                content_blocks.append(f"**Spec:**\n{t.get('spec', '')}\n")
                
                # Fetch checkpoints
                cp_resp = await client.get(f"{ORCHESTRATOR_URL}/tasks/{t['id']}/checkpoints")
                if cp_resp.status_code == 200:
                    cps = cp_resp.json()
                    for cp in cps:
                        content_blocks.append(f"### Output ({cp.get('submitted_by', 'worker')}):\n")
                        content_blocks.append(cp.get("result_text", ""))
                        content_blocks.append("\n")

            report_file.write_text("\n".join(content_blocks), encoding="utf-8")
            seen_jobs.add(job_id)
            print(f"[+] Harvested completed job '{job_id}' -> {report_file}")
            show_windows_toast(
                "Claude Desktop Fleet: Job Completed",
                f"Job {job_id} passed QA and output is saved to outputs/runs/."
            )

    except Exception as e:
        print(f"[!] Error in harvester: {e}")

async def run_harvester_loop():
    seen_jobs: set[str] = set()
    print("[*] Output Harvester active. Watching for completed jobs...")
    async with httpx.AsyncClient(timeout=15.0) as client:
        while True:
            await harvest_completed_jobs(client, seen_jobs)
            await asyncio.sleep(5.0)

if __name__ == "__main__":
    try:
        asyncio.run(run_harvester_loop())
    except KeyboardInterrupt:
        print("[*] Harvester stopped.")
