# Handoff Dossier: Copilot CLI & AGY Fleet Orchestration

- **Date / Timestamp:** 2026-10-05T19:40:00+05:45
- **Prior Session ID:** `87838ce1-b8f0-4511-8168-dcb4b27cba7c`
- **Target Repositories:** `F:\Aaradhya-Dev-Tamrakar\Claude-Desktop` & `F:\Aaradhya-Dev-Tamrakar\brainstorm`
- **Active Focus Selected:** **Track B (Multi-Account 200-Credit Copilot CLI Fleet & Production Run)**
- **Verified Commit Provenance:**
  - `Claude-Desktop`: Commit [`6ecd3e1`](https://github.com/Aaradhya-Dev-Tamrakar/Claude-Desktop/commit/6ecd3e1)
  - `brainstorm`: Commit [`c7af7c3`](https://github.com/Aaradhya-Dev-Tamrakar/brainstorm/commit/c7af7c3)

---

## 1. Verified Completed State (Phase 2: M5 & M6)

During the prior session, the following components were built, tested, and pushed to `main`:

1. **Native Copilot CLI Subprocess Adapter (`CopilotCLIAdapter`)**:
   - Location: [`client/adapters/copilot_cli_adapter.py`](file:///F:/Aaradhya-Dev-Tamrakar/Claude-Desktop/client/adapters/copilot_cli_adapter.py)
   - Discovers installed `copilot.exe` (GitHub Copilot CLI v1.0.91.0).
   - Executes non-interactive prompts in `--autopilot` mode (`-p "<prompt>" --allow-all --no-ask-user --no-color --no-custom-instructions`).
   - Supports `--worktree` directory sandboxing and `--usage-output-file` parsing for token telemetry.
   - Tested: [`tests/test_copilot_cli_adapter.py`](file:///F:/Aaradhya-Dev-Tamrakar/Claude-Desktop/tests/test_copilot_cli_adapter.py) (6/6 passing).

2. **Autonomous Tool Calling Loop for Headless Adapter (M6)**:
   - Location: [`client/adapters/copilot_headless.py`](file:///F:/Aaradhya-Dev-Tamrakar/Claude-Desktop/client/adapters/copilot_headless.py)
   - Added OpenAI-compatible tool specifications (`read_file`, `write_file`, `run_command`).
   - Implemented sandboxed workspace resolution and multi-turn agent dispatch loop.
   - Tested: [`tests/test_copilot_headless.py`](file:///F:/Aaradhya-Dev-Tamrakar/Claude-Desktop/tests/test_copilot_headless.py) (7/7 passing).

3. **Scheduler & Fleet Supervisor Integration**:
   - Registered `copilot_cli` provider in [`client/fleet_supervisor.py`](file:///F:/Aaradhya-Dev-Tamrakar/Claude-Desktop/client/fleet_supervisor.py).
   - Allocated `0.85` tier weight with `+0.20` affinity for `code`/`draft`/`refactor` stages in [`server/core/scheduler.py`](file:///F:/Aaradhya-Dev-Tamrakar/Claude-Desktop/server/core/scheduler.py).

4. **Hybrid Concurrent Benchmark (M5)**:
   - Location: [`scripts/test_hybrid_copilot_fleet.py`](file:///F:/Aaradhya-Dev-Tamrakar/Claude-Desktop/scripts/test_hybrid_copilot_fleet.py)
   - Deliverable: [`outputs/HYBRID_COPILOT_FLEET_BENCHMARK_REPORT.md`](file:///F:/Aaradhya-Dev-Tamrakar/Claude-Desktop/outputs/HYBRID_COPILOT_FLEET_BENCHMARK_REPORT.md)
   - Certified: Full test suite **110 / 110 passed (100%)** in 35.90s.

---

## 2. Track B Scope & Architectural Blueprint

The goal of Track B is to launch a **production-ready, multi-account Copilot CLI-only fleet** designed around the **200 AI credits monthly limit** per GitHub account:

### Key Design Elements:
1. **Multi-Account Credit Pooling ($N \times 200$)**:
   - Instead of 1 account exhausting its 200 credits, pool $N$ accounts (e.g. 3–5 accounts = 600–1,000 monthly credits).
   - Scheduler arbitrates based on remaining credit headroom.
2. **Per-Task Credit Capping (`--max-ai-credits`)**:
   - Add `--max-ai-credits <count>` (e.g. 30 per task) to `CopilotCLIAdapter` so no single task can drain an account's monthly budget.
3. **Environment & Identity Isolation**:
   - Pass individual GitHub tokens (`COPILOT_TOKEN_1`, `COPILOT_TOKEN_2`, ...) or separate `GH_CONFIG_DIR` into each `copilot.exe` subprocess.
4. **Zero-Friction Launcher & Control CLI**:
   - `Claude-Desktop/orchestrator-state/live-status/active_fleet_copilot_cli.json`: Fleet topology.
   - `Claude-Desktop/launch_copilot_fleet.bat`: Starts coordinator + supervisor daemons in 1 click.
   - `Claude-Desktop/copilot-fleet.bat` or `tools/copilot_fleet.py`: Interactive CLI to submit tasks, view live ASCII status, and tail worker progress.
5. **Real-World Task Execution**:
   - Dispatch an actual repository issue / coding task across the multi-account Copilot fleet to verify real-world code editing and test verification on disk.

---

## 3. Seed Prompt for the New Chat

Copy and paste the block below into the new chat window:

```markdown
Continue from @Claude-Desktop/dev-logs/HANDOFF_COPILOT_AND_AGY_FLEET.md and @brainstorm/research/experiments/FLEET-002.md.
We have selected **Track B: Multi-Account 200-Credit Copilot CLI Fleet & Production Run**.

Current verified state:
- CopilotCLIAdapter (copilot.exe autopilot) and M6 tool loop are complete and committed (commit 6ecd3e1 in Claude-Desktop, c7af7c3 in brainstorm).
- 110/110 tests are passing.

Immediate tasks for this session:
1. Update `CopilotCLIAdapter` to support `--max-ai-credits` per-task budgeting.
2. Create `active_fleet_copilot_cli.json` defining a multi-account fleet pool (with 200 monthly credit limits and assigned roles).
3. Build the one-click launcher `launch_copilot_fleet.bat` and control CLI `tools/copilot_fleet.py` (`status`, `submit`, `tail`).
4. Dispatch and verify a real production engineering task through the fleet.
```
