#!/usr/bin/env python3
"""md2pdf-mcp: Markdown -> PDF conversion via pandoc + wkhtmltopdf.

Same convention as mcp-servers/orchestrator-mcp/run_server.py — a
hand-written MCP server using mcp.server.mcpserver.MCPServer (mcp==2.0.0),
not the 1.x FastMCP API. Requires `mcp` installed locally (`pip install mcp`
or `pip install mcp --break-system-packages` on Windows/Debian-style Python
installs).

Wraps the same conversion logic as tools/md2pdf_app.py's _run_conversion,
exposed as a single MCP tool so Claude Desktop can trigger conversions
directly instead of the Tkinter GUI. Requires pandoc and wkhtmltopdf on
PATH (already installed via choco on this machine).

Invoked via team-claude-config.json:
    "command": "python", "args": ["{{REPO_ROOT}}\\mcp-servers\\md2pdf-mcp\\run_server.py"]
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from mcp.server.mcpserver import MCPServer

DEFAULT_CSS = """
<style>
body { font-family: Georgia, 'Times New Roman', serif; font-size: 12pt; line-height: 1.55;
       color: #1a1a1a; max-width: 720px; margin: 0 auto; padding: 10px 20px; }
h1 { font-size: 18pt; text-align: center; margin-bottom: 4px; }
h2 { font-size: 13pt; border-bottom: 1px solid #999; padding-bottom: 4px; margin-top: 22px; }
h3 { font-size: 12pt; margin-top: 16px; }
p { margin: 6px 0; }
ul, ol { margin: 6px 0 12px 0; padding-left: 22px; }
li { margin-bottom: 4px; }
hr { border: none; border-top: 1px solid #ccc; margin: 14px 0; }
strong { color: #111; }
code { background: #f2f2f2; padding: 1px 4px; border-radius: 3px; font-size: 10.5pt; }
pre { background: #f2f2f2; padding: 10px; border-radius: 4px; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; }
th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; }
th { background: #f2f2f2; }
</style>
"""


def _check_deps() -> list[str]:
    return [t for t in ("pandoc", "wkhtmltopdf") if shutil.which(t) is None]


def _run_conversion(md_content: str, save_path: str, margin_mm: int) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        md_file = os.path.join(tmp, "doc.md")
        html_file = os.path.join(tmp, "doc.html")

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        result = subprocess.run(
            ["pandoc", md_file, "-o", html_file, "--standalone"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pandoc failed:\n{result.stderr}")

        with open(html_file, "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace("</head>", DEFAULT_CSS + "</head>")
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html)

        result = subprocess.run(
            [
                "wkhtmltopdf", "--encoding", "utf-8",
                "--margin-top", f"{margin_mm}mm", "--margin-bottom", f"{margin_mm}mm",
                "--margin-left", f"{margin_mm}mm", "--margin-right", f"{margin_mm}mm",
                html_file, save_path,
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"wkhtmltopdf failed:\n{result.stderr}")


srv = MCPServer(
    name="md2pdf-mcp",
    description=(
        "Markdown to PDF conversion via pandoc + wkhtmltopdf. Local-only, "
        "shells out to both binaries which must be on PATH."
    ),
)


@srv.tool(
    name="convert_markdown_to_pdf",
    description=(
        "Convert Markdown to a PDF file using pandoc + wkhtmltopdf. Provide "
        "either markdown_content (raw text) or source_path (path to an "
        "existing .md file) — not both. Writes the PDF to output_path. "
        "Returns {status, output_path} on success, or raises with a clear "
        "message on missing deps, missing/empty input, or a pandoc/"
        "wkhtmltopdf failure."
    ),
)
def convert_markdown_to_pdf(
    output_path: str,
    markdown_content: str | None = None,
    source_path: str | None = None,
    margin_mm: int = 20,
) -> dict[str, Any]:
    missing = _check_deps()
    if missing:
        raise RuntimeError(
            f"Missing required tools on PATH: {', '.join(missing)}. "
            "Install via choco/brew/apt and retry."
        )

    if not markdown_content and not source_path:
        raise ValueError("Provide either markdown_content or source_path.")
    if markdown_content and source_path:
        raise ValueError("Provide only one of markdown_content or source_path, not both.")

    if source_path:
        if not os.path.isfile(source_path):
            raise ValueError(f"source_path not found: {source_path}")
        with open(source_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = markdown_content or ""

    if not content.strip():
        raise ValueError("No Markdown content to convert (empty input).")

    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.isdir(out_dir):
        raise ValueError(f"Output directory does not exist: {out_dir}")

    if not (0 <= margin_mm <= 100):
        raise ValueError(f"margin_mm must be between 0 and 100, got {margin_mm}")

    _run_conversion(content, output_path, margin_mm)
    return {"status": "saved", "output_path": output_path}


def main() -> None:
    try:
        srv.run(transport="stdio")
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
