"""File Organizer - the window.

All the real work happens in organizer.py. This file only shows things
and reacts to clicks, so the logic can be tested without a window.

Run with:  python app.py
"""

import logging
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from organizer import (
    Plan,
    RunResult,
    apply_moves,
    build_plan,
    clean_empties,
    load_rules,
    protected_reason,
    undo_last_run,
)

# Folders offered as checkboxes (only shown if they exist on this PC)
COMMON_FOLDERS = ["Desktop", "Downloads", "Documents", "Pictures", "Videos", "Music"]


def app_data_dir() -> Path:
    """Where the undo log and error log live: %LOCALAPPDATA%\\FileOrganizer."""
    base = os.environ.get("LOCALAPPDATA")
    folder = Path(base) / "FileOrganizer" if base else Path.home() / ".file-organizer"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def resource_path(name: str) -> Path:
    """Find bundled files both when run as a script and as a PyInstaller .exe."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / name


DATA_DIR = app_data_dir()
UNDO_LOG = DATA_DIR / "last_run.json"

# Full error details go to this file; the user only sees friendly messages.
logging.basicConfig(
    filename=DATA_DIR / "app.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def short(path: Path) -> str:
    """Show paths relative to the user folder: Downloads\\photo.jpg."""
    try:
        return str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


class OrganizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("File Organizer")
        self.geometry("860x600")
        self.minsize(640, 460)

        self.rules = load_rules(resource_path("rules.json"))
        self.plan: Plan | None = None
        self.folder_vars: dict[Path, tk.BooleanVar] = {}
        self.clean_var = tk.BooleanVar(value=True)

        self.build_folder_section()
        self.build_buttons()
        self.build_preview()
        self.refresh_buttons()

    # ---------------------------------------------------------------- layout

    def build_folder_section(self):
        box = ttk.LabelFrame(self, text="1. Choose folders to organize", padding=10)
        box.pack(fill="x", padx=12, pady=(12, 6))

        self.folder_list = ttk.Frame(box)
        self.folder_list.pack(fill="x")
        for name in COMMON_FOLDERS:
            folder = Path.home() / name
            if folder.is_dir():
                self.add_folder_checkbox(folder, checked=False)

        ttk.Button(box, text="Add another folder…", command=self.on_add_folder).pack(anchor="w", pady=(8, 0))
        ttk.Checkbutton(
            box,
            text="Also remove empty files and folders (they go to the Recycle Bin)",
            variable=self.clean_var,
        ).pack(anchor="w", pady=(8, 0))

    def add_folder_checkbox(self, folder: Path, checked: bool):
        var = tk.BooleanVar(value=checked)
        self.folder_vars[folder] = var
        column = (len(self.folder_vars) - 1) % 3
        row = (len(self.folder_vars) - 1) // 3
        ttk.Checkbutton(self.folder_list, text=short(folder), variable=var).grid(
            row=row, column=column, sticky="w", padx=(0, 24), pady=2
        )

    def build_buttons(self):
        row = ttk.Frame(self, padding=(12, 0))
        row.pack(fill="x", pady=6)
        ttk.Label(row, text="2.").pack(side="left")
        ttk.Button(row, text="Preview", command=self.on_preview).pack(side="left", padx=(4, 8))
        ttk.Label(row, text="3.").pack(side="left")
        self.organize_button = ttk.Button(row, text="Organize", command=self.on_organize)
        self.organize_button.pack(side="left", padx=(4, 8))
        self.undo_button = ttk.Button(row, text="Undo last run", command=self.on_undo)
        self.undo_button.pack(side="right")

    def build_preview(self):
        box = ttk.LabelFrame(self, text="Preview — nothing changes until you click Organize", padding=8)
        box.pack(fill="both", expand=True, padx=12, pady=(6, 4))

        columns = ("action", "item", "goes_to")
        self.tree = ttk.Treeview(box, columns=columns, show="headings")
        self.tree.heading("action", text="Action")
        self.tree.heading("item", text="Item")
        self.tree.heading("goes_to", text="Goes to")
        self.tree.column("action", width=160, stretch=False)
        self.tree.column("item", width=330)
        self.tree.column("goes_to", width=330)

        scroll = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.status = ttk.Label(self, text="Tick some folders, then click Preview.", padding=(12, 0, 12, 10))
        self.status.pack(fill="x")

    def refresh_buttons(self):
        has_plan = self.plan is not None and (self.plan.moves or self.plan.empties)
        self.organize_button.state(["!disabled"] if has_plan else ["disabled"])
        self.undo_button.state(["!disabled"] if UNDO_LOG.exists() else ["disabled"])

    # --------------------------------------------------------------- actions

    def selected_folders(self) -> list[Path]:
        return [folder for folder, var in self.folder_vars.items() if var.get()]

    def on_add_folder(self):
        chosen = filedialog.askdirectory(title="Choose a folder to organize")
        if not chosen:
            return
        folder = Path(chosen)
        reason = protected_reason(folder)
        if reason:
            messagebox.showwarning("Can't organize that folder", f"That folder can't be organized because {reason}.")
            return
        if folder in self.folder_vars:
            self.folder_vars[folder].set(True)
            return
        self.add_folder_checkbox(folder, checked=True)

    def on_preview(self):
        folders = self.selected_folders()
        if not folders:
            messagebox.showinfo("No folders chosen", "Tick at least one folder first.")
            return

        with self.busy():
            self.plan = build_plan(folders, self.rules, self.clean_var.get())
        self.show_plan(self.plan)
        self.refresh_buttons()

    def show_plan(self, plan: Plan):
        self.tree.delete(*self.tree.get_children())
        for move in plan.moves:
            target = move.destination.relative_to(move.source.parent)
            self.tree.insert("", "end", values=("Move", short(move.source), str(target)))
        for path in plan.empties:
            kind = "folder" if path.is_dir() else "file"
            self.tree.insert("", "end", values=(f"Remove empty {kind}", short(path), "Recycle Bin"))

        if not plan.moves and not plan.empties:
            self.status.config(text="Already tidy — nothing to do in those folders.")
        else:
            self.status.config(
                text=f"{len(plan.moves)} file(s) to sort, {len(plan.empties)} empty item(s) to remove. "
                "Check the list, then click Organize."
            )

    def on_organize(self):
        plan = self.plan
        if not plan:
            return
        total = len(plan.moves) + len(plan.empties)
        if not messagebox.askyesno("Organize now?", f"Make these {total} change(s)?\n\nYou can undo this afterwards."):
            return

        with self.busy():
            moved = apply_moves(plan.moves, UNDO_LOG)
            cleaned = clean_empties(plan.empties, UNDO_LOG)

        self.plan = None
        self.tree.delete(*self.tree.get_children())
        self.status.config(text=f"Done: {moved.done} file(s) sorted, {cleaned.done} empty item(s) removed.")
        self.refresh_buttons()
        self.show_result("Organized", moved, cleaned)

    def on_undo(self):
        if not messagebox.askyesno("Undo last run?", "Put everything from the last run back where it was?"):
            return
        with self.busy():
            result = undo_last_run(UNDO_LOG)
        self.plan = None
        self.tree.delete(*self.tree.get_children())
        self.status.config(text=f"Undo finished: {result.done} item(s) restored.")
        self.refresh_buttons()
        self.show_result("Undo finished", result)

    # --------------------------------------------------------------- helpers

    def show_result(self, title: str, *results: RunResult):
        done = sum(r.done for r in results)
        failed = [msg for r in results for msg in r.failed]
        message = f"{done} item(s) done."
        if failed:
            shown = "\n".join(f"• {msg}" for msg in failed[:10])
            more = f"\n…and {len(failed) - 10} more" if len(failed) > 10 else ""
            message += f"\n\n{len(failed)} item(s) were skipped:\n{shown}{more}"
            messagebox.showwarning(title, message)
        else:
            messagebox.showinfo(title, message)

    def busy(self):
        """Show a wait cursor while something slow runs: `with self.busy():`"""
        app = self

        class Busy:
            def __enter__(self):
                app.config(cursor="watch")
                app.update_idletasks()

            def __exit__(self, *exc):
                app.config(cursor="")

        return Busy()

    def report_callback_exception(self, exc_type, exc_value, exc_traceback):
        """Any unexpected error: full details to app.log, a friendly box for the user."""
        logging.error("Unexpected error", exc_info=(exc_type, exc_value, exc_traceback))
        self.config(cursor="")
        messagebox.showerror(
            "Something went wrong",
            "Sorry, something unexpected happened. No further changes were made.\n\n"
            f"Details were saved to:\n{DATA_DIR / 'app.log'}",
        )


def enable_sharp_text_on_windows():
    """Stop Windows from blurring the window on scaled (e.g. 125%) displays."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass  # not Windows, or an older Windows: the window still works


if __name__ == "__main__":
    enable_sharp_text_on_windows()
    OrganizerApp().mainloop()