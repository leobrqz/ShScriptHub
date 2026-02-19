import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from script_manager import ScriptManager
import utils
from utils import run_script_in_gitbash, kill_script_process, get_process_tree_after_spawn
from config import (
    load_project_path,
    save_project_path,
    load_terminal_path,
    save_terminal_path,
    load_venv_activate_path,
    save_venv_activate_path,
    load_script_categories,
    save_script_category,
)

class ShScriptHubApp:
    def __init__(self, master):
        self.master = master
        self._update_title()
        self.master.geometry("900x520")
        self.master.minsize(520, 360)
        self.script_manager = None
        self.scripts = []
        self.terminal_path = load_terminal_path()
        self.venv_activate_path = load_venv_activate_path()
        self.project_path = None

        self._setup_styles()

        self._build_menubar(master)

        self.frame = ttk.Frame(master, padding=16)
        self.frame.pack(fill="both", expand=True)

        top_frame = ttk.Frame(self.frame)
        top_frame.pack(fill="x", pady=(0, 16))
        self.terminal_label = ttk.Label(top_frame, text="Terminal path: —")
        self.terminal_label.pack(anchor="w", fill="x")
        self.venv_label = ttk.Label(top_frame, text="Venv activate: Auto")
        self.venv_label.pack(anchor="w", fill="x")
        self.project_label = ttk.Label(top_frame, text="Project path: —")
        self.project_label.pack(anchor="w", fill="x", expand=True)
        self._update_path_labels()

        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", pady=(0, 12))

        self.scripts_frame = ttk.Frame(self.frame)
        self.scripts_frame.pack(fill="both", expand=True)

        self.script_rows = []
        saved = load_project_path()
        if saved and os.path.isdir(saved):
            self.project_path = saved
            self._update_title()
            self.load_scripts()
        else:
            self.project_path = None
        self._update_path_labels()

        self.master.after(1000, self._tick_process_check)
        self.master.after(100, self._ensure_terminal_path)

    def _build_menubar(self, master):
        bar_bg = "#f0f0f0"
        bar_hover_bg = "#e5e5e5"
        menubar_frame = tk.Frame(master, bg=bar_bg, height=28)
        menubar_frame.pack(side="top", fill="x")
        menubar_frame.pack_propagate(False)
        menu_style = {"tearoff": 0, "bg": bar_bg, "fg": "#333333", "activebackground": bar_hover_bg, "activeforeground": "#333333"}

        project_menu = tk.Menu(menubar_frame, **menu_style)
        project_menu.add_command(label="Set project path", command=self.select_project)
        project_menu.add_command(label="Refresh", command=self._refresh_scripts)
        project_lbl = tk.Label(menubar_frame, text="Project", bg=bar_bg, fg="#333333", font=("Segoe UI", 9), padx=10, pady=4, cursor="hand2")
        project_lbl.pack(side="left")
        project_lbl.bind("<Button-1>", lambda e: self._show_popup_menu(project_lbl, project_menu))
        project_lbl.bind("<Enter>", lambda e: project_lbl.configure(bg=bar_hover_bg))
        project_lbl.bind("<Leave>", lambda e: project_lbl.configure(bg=bar_bg))

        terminal_menu = tk.Menu(menubar_frame, **menu_style)
        terminal_menu.add_command(label="Set terminal path", command=self._choose_terminal_path)
        terminal_lbl = tk.Label(menubar_frame, text="Terminal", bg=bar_bg, fg="#333333", font=("Segoe UI", 9), padx=10, pady=4, cursor="hand2")
        terminal_lbl.pack(side="left")
        terminal_lbl.bind("<Button-1>", lambda e: self._show_popup_menu(terminal_lbl, terminal_menu))
        terminal_lbl.bind("<Enter>", lambda e: terminal_lbl.configure(bg=bar_hover_bg))
        terminal_lbl.bind("<Leave>", lambda e: terminal_lbl.configure(bg=bar_bg))

        venv_menu = tk.Menu(menubar_frame, **menu_style)
        venv_menu.add_command(label="Set venv activate path", command=self._choose_venv_activate_path)
        venv_menu.add_command(label="Clear venv path", command=self._clear_venv_activate_path)
        venv_lbl = tk.Label(menubar_frame, text="Venv", bg=bar_bg, fg="#333333", font=("Segoe UI", 9), padx=10, pady=4, cursor="hand2")
        venv_lbl.pack(side="left")
        venv_lbl.bind("<Button-1>", lambda e: self._show_popup_menu(venv_lbl, venv_menu))
        venv_lbl.bind("<Enter>", lambda e: venv_lbl.configure(bg=bar_hover_bg))
        venv_lbl.bind("<Leave>", lambda e: venv_lbl.configure(bg=bar_bg))

    def _show_popup_menu(self, widget, menu):
        menu.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())

    def _update_path_labels(self):
        self.terminal_label.config(text=f"Terminal path: {self.terminal_path or '—'}")
        self.venv_label.config(text=f"Venv activate: {self.venv_activate_path or 'Auto'}")
        self.project_label.config(text=f"Project path: {self.project_path or '—'}")

    def _choose_terminal_path(self):
        messagebox.showinfo(
            "ShScriptHub",
            "Select the terminal executable (.exe), e.g. Git Bash.",
        )
        title = "Select terminal executable"
        if os.name == "nt":
            path = filedialog.askopenfilename(
                title=title,
                filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
                initialdir=os.environ.get("ProgramFiles", "/"),
            )
        else:
            path = filedialog.askopenfilename(title=title)
        if path and os.path.isfile(path):
            save_terminal_path(path)
            self.terminal_path = path
            self._update_path_labels()
            messagebox.showinfo("ShScriptHub", "Terminal path saved.")

    def _choose_venv_activate_path(self):
        messagebox.showinfo(
            "ShScriptHub",
            "Select the venv activate script (e.g. backend\\.venv\\Scripts\\activate). Used for backend scripts; overrides auto-detect.",
        )
        path = filedialog.askopenfilename(
            title="Select venv activate script",
            filetypes=[("All files", "*.*")],
            initialdir=self.project_path or os.path.expanduser("~"),
        )
        if path and os.path.isfile(path):
            save_venv_activate_path(path)
            self.venv_activate_path = path
            self._update_path_labels()
            messagebox.showinfo("ShScriptHub", "Venv activate path saved.")

    def _refresh_scripts(self):
        if not self.project_path:
            messagebox.showinfo("ShScriptHub", "Select project path first.")
            return
        self.load_scripts()

    def _clear_venv_activate_path(self):
        save_venv_activate_path("")
        self.venv_activate_path = None
        self._update_path_labels()
        if self.project_path:
            self.load_scripts()
        messagebox.showinfo("ShScriptHub", "Venv path cleared. Backend scripts will use auto-detect.")

    def _ensure_terminal_path(self):
        if self.terminal_path and os.path.isfile(self.terminal_path):
            return
        messagebox.showinfo(
            "ShScriptHub",
            "Select your terminal executable (e.g. Git Bash).",
        )
        self._choose_terminal_path()

    def _setup_styles(self):
        style = ttk.Style()
        style.configure("Bold.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("TableHeader.TLabel", font=("Segoe UI", 9, "bold"), padding=(0, 4))
        style.configure("StatusIdle.TLabel", foreground="#6b7280", font=("Segoe UI", 9))
        style.configure("StatusRunning.TLabel", foreground="#15803d", font=("Segoe UI", 9))
        style.configure("StatusStopped.TLabel", foreground="#64748b", font=("Segoe UI", 9))
        style.configure("Script.TLabel", font=("Segoe UI", 9))
        style.configure("Table.TFrame", padding=2)

    def _get_default_category(self, script_path: str) -> str:
        """Auto-detect category from path: backend/frontend folder as first segment, else none."""
        rel = os.path.relpath(script_path, self.project_path)
        parts = os.path.normpath(rel).split(os.sep)
        if parts and parts[0] == "backend":
            return "backend"
        if parts and parts[0] == "frontend":
            return "frontend"
        return "none"

    def _get_env_display(self, script: dict, category: str) -> str:
        cwd = os.path.dirname(script["path"])
        if not os.path.isdir(cwd):
            return "—"
        if category == "backend" and self.venv_activate_path and os.path.isfile(self.venv_activate_path):
            activate_dir = os.path.dirname(self.venv_activate_path)
            venv_dir = os.path.dirname(activate_dir)
            return os.path.basename(venv_dir) if venv_dir else "—"
        search_roots = [cwd]
        if self.project_path and os.path.isdir(self.project_path) and self.project_path != cwd:
            search_roots.append(self.project_path)
        for root in search_roots:
            for path, name in [
                (os.path.join(root, ".venv", "Scripts", "activate"), ".venv"),
                (os.path.join(root, ".venv", "bin", "activate"), ".venv"),
                (os.path.join(root, "venv", "Scripts", "activate"), "venv"),
                (os.path.join(root, "venv", "bin", "activate"), "venv"),
            ]:
                if os.path.isfile(path):
                    return name
        if os.path.isdir(os.path.join(cwd, "node_modules")):
            return "node_modules"
        return "—"

    def _update_title(self):
        if getattr(self, "project_path", None):
            self.master.title(f"ShScriptHub - {os.path.basename(self.project_path)}")
        else:
            self.master.title("ShScriptHub")

    def select_project(self):
        folder = filedialog.askdirectory(title="Select the root of the project")
        if not folder:
            return
        self.project_path = folder
        self._update_path_labels()
        self._update_title()
        save_project_path(self.project_path)
        self.load_scripts()

    def load_scripts(self):
        try:
            for widget in self.scripts_frame.winfo_children():
                widget.destroy()

            self.script_rows = []
            self.script_manager = ScriptManager(self.project_path)
            self.scripts = self.script_manager.get_scripts()
        except Exception as e:
            messagebox.showerror("ShScriptHub - Error", f"Failed to load scripts: {str(e)}")
            return

        if not self.scripts:
            ttk.Label(self.scripts_frame, text="No .sh scripts found").pack()
            return

        self.table_frame = ttk.Frame(self.scripts_frame, style="Table.TFrame")
        self.table_frame.pack(fill="both", expand=True)

        cell_pad = {"padx": 12, "pady": 8}

        script_categories = load_script_categories()
        CATEGORY_OPTIONS = ("None", "backend", "frontend")

        ttk.Label(self.table_frame, text="File name", style="TableHeader.TLabel").grid(row=0, column=0, sticky="w", **cell_pad)
        ttk.Label(self.table_frame, text="Category", style="TableHeader.TLabel").grid(row=0, column=1, sticky="w", **cell_pad)
        ttk.Label(self.table_frame, text="Env", style="TableHeader.TLabel").grid(row=0, column=2, sticky="w", **cell_pad)
        ttk.Label(self.table_frame, text="Status", style="TableHeader.TLabel").grid(row=0, column=3, sticky="w", **cell_pad)
        ttk.Label(self.table_frame, text="PID", style="TableHeader.TLabel").grid(row=0, column=4, sticky="w", **cell_pad)
        ttk.Label(self.table_frame, text="Actions", style="TableHeader.TLabel").grid(row=0, column=5, sticky="w", **cell_pad)
        ttk.Separator(self.table_frame, orient="horizontal").grid(row=1, column=0, columnspan=8, sticky="ew", pady=(0, 4))

        self.table_frame.columnconfigure(0, weight=1)
        self.table_frame.columnconfigure(1, weight=0, minsize=90)
        self.table_frame.columnconfigure(2, weight=0, minsize=56)
        self.table_frame.columnconfigure(3, weight=0, minsize=80)
        self.table_frame.columnconfigure(4, weight=0, minsize=90)
        self.table_frame.columnconfigure(5, weight=0, minsize=56)
        self.table_frame.columnconfigure(6, weight=0, minsize=56)
        self.table_frame.columnconfigure(7, weight=0, minsize=56)

        for row_idx, s in enumerate(self.scripts):
            r_data = 2 + row_idx * 2
            r_sep = r_data + 1
            rel_path = os.path.relpath(s["path"], self.project_path).replace("\\", "/")
            display_name = rel_path
            if s["path"] in script_categories:
                category_to_show = script_categories[s["path"]]
            else:
                category_to_show = self._get_default_category(s["path"])
            category_display = "None" if category_to_show == "none" else category_to_show
            env_display = self._get_env_display(s, category_to_show)
            status_var = tk.StringVar(value="—")
            pid_var = tk.StringVar(value="—")
            category_var = tk.StringVar(value=category_display)
            ttk.Label(self.table_frame, text=display_name, style="Script.TLabel", anchor="w").grid(row=r_data, column=0, sticky="ew", **cell_pad)
            category_combo = ttk.Combobox(
                self.table_frame,
                textvariable=category_var,
                values=CATEGORY_OPTIONS,
                state="readonly",
                width=10,
            )
            category_combo.grid(row=r_data, column=1, sticky="w", **cell_pad)
            category_combo.set(category_display)

            env_label = ttk.Label(self.table_frame, text=env_display, style="Script.TLabel", anchor="w")
            env_label.grid(row=r_data, column=2, sticky="w", **cell_pad)

            def _on_category_change(script_path, var, lbl):
                val = var.get()
                stored = "none" if val == "None" else val
                save_script_category(script_path, stored)
                if lbl.winfo_exists():
                    lbl.config(text=self._get_env_display({"path": script_path}, stored))

            category_combo.bind(
                "<<ComboboxSelected>>",
                lambda event, sp=s["path"], cv=category_var, el=env_label: _on_category_change(sp, cv, el),
            )

            status_label = ttk.Label(self.table_frame, textvariable=status_var, style="StatusIdle.TLabel", anchor="w")
            status_label.grid(row=r_data, column=3, sticky="w", **cell_pad)
            ttk.Label(self.table_frame, textvariable=pid_var, style="Script.TLabel", anchor="w").grid(row=r_data, column=4, sticky="w", **cell_pad)
            run_btn = ttk.Button(self.table_frame, text="Run", width=6)
            run_btn.grid(row=r_data, column=6, **cell_pad)
            kill_btn = ttk.Button(self.table_frame, text="Kill", width=6)
            kill_btn.grid(row=r_data, column=7, **cell_pad)
            kill_btn.grid_remove()

            if row_idx < len(self.scripts) - 1:
                ttk.Separator(self.table_frame, orient="horizontal").grid(row=r_sep, column=0, columnspan=8, sticky="ew", pady=0)

            row_dict = {
                "script": s,
                "category_var": category_var,
                "status_var": status_var,
                "status_label": status_label,
                "pid_var": pid_var,
                "run_btn": run_btn,
                "kill_btn": kill_btn,
                "process": None,
                "kill_pids": None,
            }
            self.script_rows.append(row_dict)
            run_btn.configure(command=lambda r=row_dict: self._run_script_row(r))
            kill_btn.configure(command=lambda r=row_dict: self._kill_script_row(r))

    def _set_status(self, row, text):
        row["status_var"].set(text)
        style_map = {"—": "StatusIdle.TLabel", "Running": "StatusRunning.TLabel", "Stopped": "StatusStopped.TLabel"}
        row.get("status_label", tk.Misc()).configure(style=style_map.get(text, "StatusIdle.TLabel"))

    def _run_script_row(self, row):
        try:
            cat = row["category_var"].get()
            category = "none" if cat == "None" else cat
            p = run_script_in_gitbash(
                row["script"]["path"],
                category,
                self.project_path,
                terminal_path=self.terminal_path,
                venv_activate_path=self.venv_activate_path,
            )
            row["process"] = p
            row["kill_pids"] = None
            self._set_status(row, "Running")
            row["pid_var"].set(str(p.pid))
            row["kill_btn"].grid()
            delay_ms = int(utils.TREE_CAPTURE_DELAY_SEC * 1000)
            self.master.after(delay_ms, lambda: self._capture_kill_pids(row))
            messagebox.showinfo("ShScriptHub", f"Script '{row['script']['name']}' started.")
        except Exception as e:
            messagebox.showerror("ShScriptHub - Error", str(e))

    def _capture_kill_pids(self, row):
        proc = row.get("process")
        if proc is None or proc.poll() is not None:
            return
        row["kill_pids"] = get_process_tree_after_spawn(proc)

    def _kill_script_row(self, row):
        proc = row.get("process")
        if proc is None:
            return
        kill_pids = row.get("kill_pids")
        if not kill_pids and proc.poll() is None:
            kill_pids = [proc.pid]
        kill_script_process(proc, kill_pids=kill_pids)
        self._set_status(row, "Stopped")
        row["pid_var"].set("—")
        row["process"] = None
        row["kill_pids"] = None
        row["kill_btn"].grid_remove()

    def check_processes(self):
        for row in getattr(self, "script_rows", []):
            proc = row.get("process")
            if proc is None:
                continue
            if proc.poll() is not None:
                self._set_status(row, "Stopped")
                row["pid_var"].set("—")
                row["process"] = None
                kill_btn = row.get("kill_btn")
                if kill_btn:
                    kill_btn.grid_remove()

    def _tick_process_check(self):
        self.check_processes()
        self.master.after(1000, self._tick_process_check)
