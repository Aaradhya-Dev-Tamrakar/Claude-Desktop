#!/usr/bin/env python3
"""
Markdown to PDF Converter — Desktop App
Requires: pandoc, wkhtmltopdf (both must be installed and on PATH)
  - macOS:   brew install pandoc wkhtmltopdf
  - Windows: choco install pandoc wkhtmltopdf   (or download installers)
  - Linux:   sudo apt install pandoc wkhtmltopdf
"""

import os
import shutil
import subprocess
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

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


class MD2PDFApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Markdown → PDF Converter")
        self.root.geometry("760x640")
        self.md_path = None

        self._check_deps()
        self._build_ui()

    def _check_deps(self):
        missing = [t for t in ("pandoc", "wkhtmltopdf") if shutil.which(t) is None]
        self.missing_deps = missing

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)

        ttk.Button(top, text="Open .md File", command=self.open_file).pack(side="left")
        self.file_label = ttk.Label(top, text="No file loaded — paste or type Markdown below")
        self.file_label.pack(side="left", padx=10)

        if self.missing_deps:
            warn = ttk.Label(
                self.root,
                text=f"⚠ Missing required tools: {', '.join(self.missing_deps)}. "
                     f"Install them and restart this app.",
                foreground="#b00020",
                wraplength=720,
            )
            warn.pack(fill="x", padx=10, pady=(0, 6))

        # Text editor
        editor_frame = ttk.LabelFrame(self.root, text="Markdown content")
        editor_frame.pack(fill="both", expand=True, padx=10, pady=6)
        self.text = scrolledtext.ScrolledText(editor_frame, wrap="word", font=("Consolas", 11))
        self.text.pack(fill="both", expand=True, padx=6, pady=6)

        # Margin controls
        margin_frame = ttk.Frame(self.root)
        margin_frame.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(margin_frame, text="Margins (mm):").pack(side="left")
        self.margin_var = tk.StringVar(value="20")
        ttk.Entry(margin_frame, textvariable=self.margin_var, width=5).pack(side="left", padx=6)

        # Bottom bar
        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", padx=10, pady=10)
        ttk.Button(bottom, text="Convert to PDF…", command=self.convert).pack(side="right")

        self.status = ttk.Label(self.root, text="Ready", foreground="#444")
        self.status.pack(fill="x", padx=10, pady=(0, 8))

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Select Markdown file",
            filetypes=[("Markdown files", "*.md *.markdown *.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.md_path = path
        self.file_label.config(text=os.path.basename(path))

    def convert(self):
        if self.missing_deps:
            messagebox.showerror(
                "Missing dependencies",
                f"Install these first: {', '.join(self.missing_deps)}",
            )
            return

        md_content = self.text.get("1.0", "end").strip()
        if not md_content:
            messagebox.showwarning("Empty content", "There is no Markdown content to convert.")
            return

        try:
            margin = int(self.margin_var.get())
        except ValueError:
            margin = 20

        default_name = "output.pdf"
        if self.md_path:
            default_name = os.path.splitext(os.path.basename(self.md_path))[0] + ".pdf"

        save_path = filedialog.asksaveasfilename(
            title="Save PDF as",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF files", "*.pdf")],
        )
        if not save_path:
            return

        self.status.config(text="Converting…")
        self.root.update_idletasks()

        try:
            self._run_conversion(md_content, save_path, margin)
            self.status.config(text=f"Saved: {save_path}")
            messagebox.showinfo("Done", f"PDF saved to:\n{save_path}")
        except Exception as e:
            self.status.config(text="Failed")
            messagebox.showerror("Conversion failed", str(e))

    def _resolve_output_path(self, save_path):
        candidate = save_path.strip()
        if not candidate:
            raise ValueError("save_path is required.")

        if not os.path.isabs(candidate):
            repo_root = Path(__file__).resolve().parents[1]
            candidate = str((repo_root / candidate).resolve())

        directory = os.path.dirname(candidate) or os.getcwd()
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError:
            fallback = os.path.join(tempfile.gettempdir(), "md2pdf-app", os.path.basename(candidate))
            os.makedirs(os.path.dirname(fallback), exist_ok=True)
            return fallback
        return candidate

    def _run_conversion(self, md_content, save_path, margin):
        resolved_path = self._resolve_output_path(save_path)

        with tempfile.TemporaryDirectory() as tmp:
            md_file = os.path.join(tmp, "doc.md")
            html_file = os.path.join(tmp, "doc.html")

            with open(md_file, "w", encoding="utf-8") as f:
                f.write(md_content)

            # Markdown -> HTML via pandoc
            result = subprocess.run(
                ["pandoc", md_file, "-o", html_file, "--standalone"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"pandoc failed:\n{result.stderr}")

            # Inject CSS
            with open(html_file, "r", encoding="utf-8") as f:
                html = f.read()
            html = html.replace("</head>", DEFAULT_CSS + "</head>")
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html)

            # HTML -> PDF via wkhtmltopdf (UTF-8 explicit to handle en/em dashes etc.)
            result = subprocess.run(
                [
                    "wkhtmltopdf", "--encoding", "utf-8",
                    "--margin-top", f"{margin}mm", "--margin-bottom", f"{margin}mm",
                    "--margin-left", f"{margin}mm", "--margin-right", f"{margin}mm",
                    html_file, resolved_path,
                ],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"wkhtmltopdf failed:\n{result.stderr}")

        if not os.path.exists(resolved_path) or os.path.getsize(resolved_path) == 0:
            raise RuntimeError(f"Conversion claimed success but no PDF was written to: {resolved_path}")


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    app = MD2PDFApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
