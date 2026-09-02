#!/usr/bin/env python3
"""
Markdown to PDF Converter — Desktop App
Requires: pandoc, wkhtmltopdf (both must be installed and on PATH)
  - macOS:   brew install pandoc wkhtmltopdf
  - Windows: choco install pandoc wkhtmltopdf   (or download installers)
  - Linux:   sudo apt install pandoc wkhtmltopdf

Optional (enables live rendered preview instead of "open in browser"):
  pip install tkinterweb
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

try:
    from tkinterweb import HtmlFrame  # type: ignore

    HAVE_TKINTERWEB = True
except ImportError:
    HAVE_TKINTERWEB = False


# --------------------------------------------------------------------------
# Themes
# --------------------------------------------------------------------------

THEMES: dict[str, str] = {
    "Classic Serif": """
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
""",
    "Modern Sans": """
<style>
body { font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 11pt;
       line-height: 1.6; color: #24292f; max-width: 760px; margin: 0 auto; padding: 10px 24px; }
h1 { font-size: 22pt; font-weight: 700; margin-bottom: 6px; letter-spacing: -0.02em; }
h2 { font-size: 15pt; font-weight: 600; border-bottom: 2px solid #d0d7de; padding-bottom: 6px;
     margin-top: 26px; }
h3 { font-size: 12.5pt; font-weight: 600; margin-top: 18px; }
p { margin: 8px 0; }
ul, ol { margin: 8px 0 14px 0; padding-left: 24px; }
li { margin-bottom: 5px; }
hr { border: none; border-top: 1px solid #d0d7de; margin: 18px 0; }
strong { color: #000; }
a { color: #0969da; }
code { background: #f6f8fa; padding: 2px 5px; border-radius: 4px; font-size: 10pt;
       font-family: 'SF Mono', Consolas, monospace; }
pre { background: #f6f8fa; padding: 12px; border-radius: 6px; overflow-x: auto; border: 1px solid #d0d7de; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { border: 1px solid #d0d7de; padding: 8px 12px; text-align: left; }
th { background: #f6f8fa; font-weight: 600; }
blockquote { border-left: 3px solid #d0d7de; margin: 10px 0; padding: 4px 16px; color: #57606a; }
</style>
""",
    "Compact Technical": """
<style>
body { font-family: 'Consolas', 'SF Mono', Menlo, monospace; font-size: 9.5pt; line-height: 1.45;
       color: #1a1a1a; max-width: 100%; margin: 0 auto; padding: 6px 16px; }
h1 { font-size: 15pt; margin-bottom: 4px; }
h2 { font-size: 12pt; border-bottom: 1px solid #666; padding-bottom: 3px; margin-top: 16px; }
h3 { font-size: 10.5pt; margin-top: 12px; }
p { margin: 4px 0; }
ul, ol { margin: 4px 0 8px 0; padding-left: 18px; }
li { margin-bottom: 2px; }
hr { border: none; border-top: 1px solid #ccc; margin: 10px 0; }
code { background: #eee; padding: 1px 3px; font-size: 9pt; }
pre { background: #f0f0f0; padding: 8px; overflow-x: auto; font-size: 8.5pt; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 9pt; }
th, td { border: 1px solid #999; padding: 4px 7px; text-align: left; }
th { background: #e8e8e8; }
</style>
""",
    "High Contrast Print": """
<style>
body { font-family: 'Times New Roman', serif; font-size: 12pt; line-height: 1.5;
       color: #000; max-width: 700px; margin: 0 auto; padding: 10px 20px; }
h1 { font-size: 20pt; text-align: center; border-bottom: 3px solid #000; padding-bottom: 8px; }
h2 { font-size: 14pt; margin-top: 24px; text-decoration: underline; }
h3 { font-size: 12pt; font-weight: bold; margin-top: 16px; }
p { margin: 6px 0; }
ul, ol { margin: 6px 0 12px 0; padding-left: 24px; }
hr { border: none; border-top: 2px solid #000; margin: 16px 0; }
strong { font-weight: 900; }
code { background: #ddd; padding: 1px 4px; border: 1px solid #000; }
pre { background: #eee; padding: 10px; border: 1px solid #000; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; }
th, td { border: 2px solid #000; padding: 6px 10px; text-align: left; }
th { background: #ccc; }
</style>
""",
}

DEFAULT_THEME = "Classic Serif"

CONFIG_PATH = Path.home() / ".md2pdf_app_config.json"


# --------------------------------------------------------------------------
# Conversion core (no tkinter dependency — usable headless / from batch)
# --------------------------------------------------------------------------


def check_deps() -> list[str]:
    return [t for t in ("pandoc", "wkhtmltopdf") if shutil.which(t) is None]


def resolve_output_path(save_path: str) -> str:
    candidate = save_path.strip()
    if not candidate:
        raise ValueError("save_path is required.")

    if not os.path.isabs(candidate):
        candidate = str(Path(candidate).resolve())

    directory = os.path.dirname(candidate) or os.getcwd()
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"Cannot create output directory '{directory}': {exc}. "
            "Choose a location this process can write to."
        ) from exc
    return candidate


def markdown_to_html(md_content: str, theme_css: str) -> str:
    """Run pandoc only, return standalone HTML with theme injected. Used by both
    the PDF path and the live preview so both stay in sync."""
    missing = check_deps()
    if "pandoc" in missing:
        raise RuntimeError("pandoc not found on PATH.")

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

    return html.replace("</head>", theme_css + "</head>")


def run_conversion(md_content: str, save_path: str, margin_mm: int, theme_css: str) -> str:
    """Full markdown -> PDF pipeline. Returns the resolved output path.
    Raises RuntimeError/ValueError on any failure — never fails silently."""
    resolved_path = resolve_output_path(save_path)
    missing = check_deps()
    if missing:
        raise RuntimeError(f"Missing required tools on PATH: {', '.join(missing)}")

    html = markdown_to_html(md_content, theme_css)

    with tempfile.TemporaryDirectory() as tmp:
        html_file = os.path.join(tmp, "doc.html")
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html)

        result = subprocess.run(
            [
                "wkhtmltopdf", "--encoding", "utf-8",
                "--margin-top", f"{margin_mm}mm", "--margin-bottom", f"{margin_mm}mm",
                "--margin-left", f"{margin_mm}mm", "--margin-right", f"{margin_mm}mm",
                html_file, resolved_path,
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"wkhtmltopdf failed:\n{result.stderr}")

    if not os.path.exists(resolved_path) or os.path.getsize(resolved_path) == 0:
        raise RuntimeError(f"Conversion claimed success but no PDF was written to: {resolved_path}")

    return resolved_path


# --------------------------------------------------------------------------
# Batch job model
# --------------------------------------------------------------------------


@dataclass
class BatchItem:
    md_path: str
    output_path: str = ""
    status: str = "Pending"  # Pending | Converting | Done | Failed | Skipped | Cancelled
    error: str = ""

    def display_name(self) -> str:
        return os.path.basename(self.md_path)


@dataclass
class Config:
    theme: str = DEFAULT_THEME
    margin_mm: int = 20
    output_dir: str = ""
    overwrite: bool = False
    open_after: bool = False

    def save(self) -> None:
        try:
            CONFIG_PATH.write_text(json.dumps(self.__dict__, indent=2), encoding="utf-8")
        except OSError:
            pass  # non-fatal — settings just won't persist

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except (json.JSONDecodeError, OSError, TypeError):
                pass
        return cls()


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------


class MD2PDFApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Markdown → PDF Converter")
        self.root.geometry("1080x720")
        self.root.minsize(880, 560)

        self.config_ = Config.load()
        self.missing_deps = check_deps()
        self.batch: list[BatchItem] = []
        self._progress_queue: "queue.Queue[tuple]" = queue.Queue()
        self._converting = False
        self._cancel_requested = False
        self.md_path: str | None = None
        self.preview_widget = None
        self._preview_mode = "html" if HAVE_TKINTERWEB else "browser"

        self._build_ui()
        self._apply_deps_warning()
        self.root.after(150, self._poll_progress)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- layout ------------------------------------------------------------

    def _build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        self.deps_banner = ttk.Label(
            self.root, text="", foreground="#b00020", wraplength=1040, padding=(10, 6)
        )
        self.deps_banner.pack(fill="x")

        paned = ttk.Panedwindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=6)

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=2)

        self._build_batch_panel(left)
        self._build_editor_panel(right)
        self._build_settings_bar()
        self._build_status_bar()

    def _build_batch_panel(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill="x", padx=4, pady=(4, 2))
        ttk.Label(header, text="Batch queue", font=("", 10, "bold")).pack(side="left")

        btns = ttk.Frame(parent)
        btns.pack(fill="x", padx=4, pady=2)
        ttk.Button(btns, text="Add File(s)", command=self.add_files).pack(side="left", padx=(0, 4))
        ttk.Button(btns, text="Add Folder", command=self.add_folder).pack(side="left", padx=(0, 4))
        ttk.Button(btns, text="Remove", command=self.remove_selected).pack(side="left", padx=(0, 4))
        ttk.Button(btns, text="Clear", command=self.clear_batch).pack(side="left")

        columns = ("status",)
        self.tree = ttk.Treeview(
            parent, columns=columns, show="tree headings", selectmode="extended", height=16
        )
        self.tree.heading("#0", text="File")
        self.tree.heading("status", text="Status")
        self.tree.column("#0", width=220, anchor="w")
        self.tree.column("status", width=90, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        self.batch_progress = ttk.Progressbar(parent, mode="determinate")
        self.batch_progress.pack(fill="x", padx=4, pady=(0, 4))

        action_row = ttk.Frame(parent)
        action_row.pack(fill="x", padx=4, pady=(0, 6))
        self.convert_batch_btn = ttk.Button(
            action_row, text="Convert All", command=self.convert_batch
        )
        self.convert_batch_btn.pack(side="left")
        self.cancel_btn = ttk.Button(
            action_row, text="Cancel", command=self.cancel_batch, state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=(6, 0))

    def _build_editor_panel(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=4, pady=(4, 2))
        ttk.Button(top, text="Open .md File", command=self.open_single_file).pack(side="left")
        self.file_label = ttk.Label(top, text="No file loaded — paste or type Markdown below")
        self.file_label.pack(side="left", padx=10)

        editor_notebook = ttk.Notebook(parent)
        editor_notebook.pack(fill="both", expand=True, padx=4, pady=4)

        edit_tab = ttk.Frame(editor_notebook)
        editor_notebook.add(edit_tab, text="Markdown")
        self.text = scrolledtext.ScrolledText(edit_tab, wrap="word", font=("Consolas", 11))
        self.text.pack(fill="both", expand=True, padx=4, pady=4)

        preview_tab = ttk.Frame(editor_notebook)
        editor_notebook.add(preview_tab, text="Preview")
        self._build_preview(preview_tab)

    def _build_preview(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", padx=4, pady=4)
        ttk.Button(toolbar, text="Refresh Preview", command=self.refresh_preview).pack(side="left")

        if HAVE_TKINTERWEB:
            self.preview_widget = HtmlFrame(parent, messages_enabled=False)
            self.preview_widget.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        else:
            ttk.Label(
                toolbar,
                text="(tkinterweb not installed — preview opens in your browser instead. "
                     "pip install tkinterweb for inline preview.)",
                foreground="#666",
            ).pack(side="left", padx=8)

    # -- settings / status bars --------------------------------------------

    def _build_settings_bar(self) -> None:
        bar = ttk.LabelFrame(self.root, text="Conversion settings")
        bar.pack(fill="x", padx=8, pady=(0, 4))

        row = ttk.Frame(bar)
        row.pack(fill="x", padx=8, pady=6)

        ttk.Label(row, text="Theme:").pack(side="left")
        self.theme_var = tk.StringVar(value=self.config_.theme)
        theme_combo = ttk.Combobox(
            row, textvariable=self.theme_var, values=list(THEMES.keys()),
            state="readonly", width=18,
        )
        theme_combo.pack(side="left", padx=(4, 16))
        theme_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_preview())

        ttk.Label(row, text="Margins (mm):").pack(side="left")
        self.margin_var = tk.StringVar(value=str(self.config_.margin_mm))
        ttk.Entry(row, textvariable=self.margin_var, width=5).pack(side="left", padx=(4, 16))

        self.overwrite_var = tk.BooleanVar(value=self.config_.overwrite)
        ttk.Checkbutton(
            row, text="Overwrite existing files", variable=self.overwrite_var
        ).pack(side="left", padx=(0, 16))

        self.open_after_var = tk.BooleanVar(value=self.config_.open_after)
        ttk.Checkbutton(
            row, text="Open PDF after conversion", variable=self.open_after_var
        ).pack(side="left", padx=(0, 16))

        row2 = ttk.Frame(bar)
        row2.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(row2, text="Output folder (batch):").pack(side="left")
        self.output_dir_var = tk.StringVar(value=self.config_.output_dir)
        ttk.Entry(row2, textvariable=self.output_dir_var, width=48).pack(
            side="left", padx=(4, 6), fill="x", expand=True
        )
        ttk.Button(row2, text="Browse…", command=self.pick_output_dir).pack(side="left")
        ttk.Label(
            row2, text="(blank = same folder as each source file)", foreground="#666"
        ).pack(side="left", padx=(8, 0))

        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(bottom, text="Convert Current to PDF…", command=self.convert_single).pack(
            side="right"
        )

    def _build_status_bar(self) -> None:
        self.status = ttk.Label(self.root, text="Ready", foreground="#444", padding=(8, 4))
        self.status.pack(fill="x", side="bottom")

    def _apply_deps_warning(self) -> None:
        if self.missing_deps:
            self.deps_banner.config(
                text=f"⚠ Missing required tools: {', '.join(self.missing_deps)}. "
                     f"Install them and restart this app."
            )
        else:
            self.deps_banner.config(text="")

    # -- single-file actions -------------------------------------------------

    def open_single_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Markdown file",
            filetypes=[("Markdown files", "*.md *.markdown *.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        self._load_file_into_editor(path)

    def _load_file_into_editor(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.md_path = path
        self.file_label.config(text=os.path.basename(path))

    def _current_theme_css(self) -> str:
        return THEMES.get(self.theme_var.get(), THEMES[DEFAULT_THEME])

    def _current_margin(self) -> int:
        try:
            return int(self.margin_var.get())
        except ValueError:
            return 20

    def refresh_preview(self) -> None:
        md_content = self.text.get("1.0", "end").strip()
        if not md_content:
            self.status.config(text="Nothing to preview — editor is empty.")
            return
        if self.missing_deps and "pandoc" in self.missing_deps:
            messagebox.showerror("Missing dependency", "pandoc is required for preview.")
            return

        self.status.config(text="Rendering preview…")

        def work():
            try:
                html = markdown_to_html(md_content, self._current_theme_css())
                self._progress_queue.put(("preview_ready", html))
            except Exception as e:
                self._progress_queue.put(("preview_failed", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def convert_single(self) -> None:
        if self.missing_deps:
            messagebox.showerror(
                "Missing dependencies", f"Install these first: {', '.join(self.missing_deps)}"
            )
            return

        md_content = self.text.get("1.0", "end").strip()
        if not md_content:
            messagebox.showwarning("Empty content", "There is no Markdown content to convert.")
            return

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
            resolved = run_conversion(
                md_content, save_path, self._current_margin(), self._current_theme_css()
            )
            self.status.config(text=f"Saved: {resolved}")
            self._save_settings()
            if self.open_after_var.get():
                self._open_file(resolved)
            messagebox.showinfo("Done", f"PDF saved to:\n{resolved}")
        except Exception as e:
            self.status.config(text="Failed")
            messagebox.showerror("Conversion failed", str(e))

    # -- batch actions ---------------------------------------------------

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select Markdown file(s)",
            filetypes=[("Markdown files", "*.md *.markdown *.txt"), ("All files", "*.*")],
        )
        for p in paths:
            self._add_batch_item(p)

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select folder of Markdown files")
        if not folder:
            return
        found = sorted(set(Path(folder).rglob("*.md")) | set(Path(folder).rglob("*.markdown")))
        if not found:
            messagebox.showinfo("No files found", "No .md/.markdown files found in that folder.")
            return
        for p in found:
            self._add_batch_item(str(p))

    def _add_batch_item(self, path: str) -> None:
        if any(item.md_path == path for item in self.batch):
            return  # no duplicates
        item = BatchItem(md_path=path)
        self.batch.append(item)
        self.tree.insert("", "end", iid=path, text=item.display_name(), values=(item.status,))

    def remove_selected(self) -> None:
        for iid in self.tree.selection():
            self.batch = [b for b in self.batch if b.md_path != iid]
            self.tree.delete(iid)

    def clear_batch(self) -> None:
        if self._converting:
            return
        self.batch.clear()
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.batch_progress["value"] = 0

    def _on_tree_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if len(sel) == 1:
            self._load_file_into_editor(sel[0])

    def pick_output_dir(self) -> None:
        folder = filedialog.askdirectory(title="Select output folder for batch conversion")
        if folder:
            self.output_dir_var.set(folder)

    def convert_batch(self) -> None:
        if self._converting:
            return
        if self.missing_deps:
            messagebox.showerror(
                "Missing dependencies", f"Install these first: {', '.join(self.missing_deps)}"
            )
            return
        if not self.batch:
            messagebox.showinfo("Empty queue", "Add files or a folder first.")
            return

        self._converting = True
        self.convert_batch_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self._cancel_requested = False
        self.batch_progress["value"] = 0
        self.batch_progress["maximum"] = len(self.batch)

        for item in self.batch:
            item.status = "Pending"
            item.error = ""
            self.tree.item(item.md_path, values=("Pending",))

        margin = self._current_margin()
        theme_css = self._current_theme_css()
        out_dir = self.output_dir_var.get().strip()
        overwrite = self.overwrite_var.get()
        self._save_settings()

        def work():
            done = 0
            for item in list(self.batch):
                if self._cancel_requested:
                    self._progress_queue.put(("item_status", item.md_path, "Cancelled", ""))
                    continue

                self._progress_queue.put(("item_status", item.md_path, "Converting", ""))
                try:
                    src = Path(item.md_path)
                    target_dir = Path(out_dir) if out_dir else src.parent
                    target = target_dir / (src.stem + ".pdf")

                    if target.exists() and not overwrite:
                        self._progress_queue.put(
                            ("item_status", item.md_path, "Skipped", "Already exists")
                        )
                    else:
                        md_content = src.read_text(encoding="utf-8")
                        resolved = run_conversion(md_content, str(target), margin, theme_css)
                        item.output_path = resolved
                        self._progress_queue.put(("item_status", item.md_path, "Done", ""))
                except Exception as e:
                    self._progress_queue.put(("item_status", item.md_path, "Failed", str(e)))

                done += 1
                self._progress_queue.put(("progress", done))

            self._progress_queue.put(("batch_complete", done))

        threading.Thread(target=work, daemon=True).start()

    def cancel_batch(self) -> None:
        self._cancel_requested = True
        self.cancel_btn.config(state="disabled")
        self.status.config(text="Cancelling after current file…")

    # -- background progress pump ----------------------------------------

    def _poll_progress(self) -> None:
        try:
            while True:
                event = self._progress_queue.get_nowait()
                kind = event[0]

                if kind == "item_status":
                    _, path, status, error = event
                    for item in self.batch:
                        if item.md_path == path:
                            item.status = status
                            item.error = error
                    if self.tree.exists(path):
                        self.tree.item(path, values=(status,))
                    self.status.config(text=f"{os.path.basename(path)}: {status}")

                elif kind == "progress":
                    self.batch_progress["value"] = event[1]

                elif kind == "batch_complete":
                    self._converting = False
                    self.convert_batch_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    failed = [b for b in self.batch if b.status == "Failed"]
                    done = [b for b in self.batch if b.status == "Done"]
                    self.status.config(
                        text=f"Batch complete: {len(done)} done, {len(failed)} failed."
                    )
                    if failed:
                        detail = "\n".join(f"{b.display_name()}: {b.error}" for b in failed[:8])
                        messagebox.showwarning("Some conversions failed", detail)
                    elif self.open_after_var.get() and done:
                        for b in done:
                            self._open_file(b.output_path)

                elif kind == "preview_ready":
                    self._render_preview_html(event[1])
                    self.status.config(text="Preview updated.")

                elif kind == "preview_failed":
                    self.status.config(text="Preview failed.")
                    messagebox.showerror("Preview failed", event[1])

        except queue.Empty:
            pass
        self.root.after(150, self._poll_progress)

    def _render_preview_html(self, html: str) -> None:
        if self._preview_mode == "html" and self.preview_widget is not None:
            self.preview_widget.load_html(html)
        else:
            with tempfile.NamedTemporaryFile(
                "w", suffix=".html", delete=False, encoding="utf-8"
            ) as f:
                f.write(html)
                tmp_path = f.name
            webbrowser.open(f"file://{tmp_path}")

    # -- misc -------------------------------------------------------------

    def _open_file(self, path: str) -> None:
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif shutil.which("open"):
                subprocess.run(["open", path], check=False)
            elif shutil.which("xdg-open"):
                subprocess.run(["xdg-open", path], check=False)
        except OSError:
            pass  # non-fatal — file was still saved successfully

    def _save_settings(self) -> None:
        self.config_.theme = self.theme_var.get()
        self.config_.margin_mm = self._current_margin()
        self.config_.output_dir = self.output_dir_var.get().strip()
        self.config_.overwrite = self.overwrite_var.get()
        self.config_.open_after = self.open_after_var.get()
        self.config_.save()

    def _on_close(self) -> None:
        self._save_settings()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = MD2PDFApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()