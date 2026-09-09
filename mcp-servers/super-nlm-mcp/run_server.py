"""
Launcher shim for the Super-NLM MCP server.

Delegates to the actual super-nlm repo's MCP server module, running inside
its own virtual environment. This keeps the Claude-Desktop repo free of
super-nlm's Python dependencies while following the same mcp-servers/
launcher pattern used by notebooklm-mcp, orchestrator-mcp, and md2pdf-mcp.

Usage (from team-mcp.json or direct):
    python mcp-servers/super-nlm-mcp/run_server.py
"""
import subprocess
import sys
import os

SUPER_NLM_ROOT = r"F:\Aaradhya-Dev-Tamrakar\super-nlm"
PYTHON_EXE = os.path.join(SUPER_NLM_ROOT, ".venv", "Scripts", "python.exe")


def main():
    if not os.path.isfile(PYTHON_EXE):
        print(
            f"ERROR: Super-NLM venv not found at {PYTHON_EXE}\n"
            f"Setup: cd {SUPER_NLM_ROOT} && uv sync",
            file=sys.stderr,
        )
        sys.exit(1)

    sys.exit(
        subprocess.call(
            [PYTHON_EXE, "-m", "mcp_server"],
            cwd=SUPER_NLM_ROOT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    )


if __name__ == "__main__":
    main()
