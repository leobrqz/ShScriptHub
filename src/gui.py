import os
import time
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QFrame,
    QMenuBar,
    QMenu,
    QSizePolicy,
    QApplication,
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QFontMetrics, QResizeEvent, QWheelEvent
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
    load_favorites,
    toggle_favorite,
)
from metrics import collect_metrics, format_elapsed, format_cpu_time, PLACEHOLDER
from theme import PALETTE

CELL_PAD = 12
CATEGORY_OPTIONS = ("None", "backend", "frontend")
CARD_MIN_WIDTH = 320


class NoWheelComboBox(QComboBox):
    """QComboBox that ignores mouse wheel to avoid accidental option change."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


class ShScriptHubApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.script_manager = None
        self.scripts = []
        self.terminal_path = load_terminal_path()
        self.venv_activate_path = load_venv_activate_path()
        self.project_path = None
        self.script_rows = []
        self._grid_columns = 2

        self._update_title()
        self._build_menubar()
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        top_frame = QWidget()
        top_layout = QVBoxLayout(top_frame)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(4)
        self.terminal_label = QLabel("Terminal path: —")
        self.venv_label = QLabel("Venv activate: Auto")
        self.project_label = QLabel("Project path: —")
        top_layout.addWidget(self.terminal_label)
        top_layout.addWidget(self.venv_label)
        top_layout.addWidget(self.project_label)
        layout.addWidget(top_frame)
        layout.addSpacing(16)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)
        layout.addSpacing(12)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        vp = self.scroll_area.viewport()
        vp.setObjectName("scrollViewport")
        vp.setAutoFillBackground(True)
        self.scripts_container = QWidget()
        self.scripts_container.setObjectName("scriptsContainer")
        self.scripts_layout = QVBoxLayout(self.scripts_container)
        self.scripts_layout.setContentsMargins(0, 0, 0, 0)
        self.scripts_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.scripts_container)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("searchEdit")
        self.search_edit.setPlaceholderText("Search by folder or file name...")
        self.search_edit.setClearButtonEnabled(True)
        self.folder_combo = NoWheelComboBox()
        self.folder_combo.setObjectName("folderCombo")
        self.folder_combo.setMinimumWidth(140)
        self.folder_combo.addItem("All")
        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(QLabel("Folder:"))
        search_row.addWidget(self.folder_combo, 0)
        layout.addLayout(search_row)
        layout.addSpacing(8)
        layout.addWidget(self.scroll_area, 1)

        self.search_edit.textChanged.connect(self._on_search_changed)
        self.folder_combo.currentTextChanged.connect(self._on_folder_changed)

        self._update_path_labels()
        saved = load_project_path()
        if saved and os.path.isdir(saved):
            self.project_path = saved
            self._update_title()
            self.load_scripts()
        else:
            self.project_path = None
        self._update_path_labels()

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick_process_check)
        self._tick_timer.start(1000)
        QTimer.singleShot(100, self._ensure_terminal_path)

    def _menu_width_from_actions(self, menu: QMenu) -> None:
        fm = QFontMetrics(menu.font())
        w = max(fm.horizontalAdvance(act.text()) for act in menu.actions()) if menu.actions() else 0
        menu.setMinimumWidth(w + 28)

    def _build_menubar(self):
        menubar = self.menuBar()
        project_menu = menubar.addMenu("Project")
        act = QAction("Set project path", self)
        act.triggered.connect(self.select_project)
        project_menu.addAction(act)
        act = QAction("Refresh", self)
        act.triggered.connect(self._refresh_scripts)
        project_menu.addAction(act)
        self._menu_width_from_actions(project_menu)

        terminal_menu = menubar.addMenu("Terminal")
        act = QAction("Set terminal path", self)
        act.triggered.connect(self._choose_terminal_path)
        terminal_menu.addAction(act)
        self._menu_width_from_actions(terminal_menu)

        venv_menu = menubar.addMenu("Venv")
        act = QAction("Set venv activate path", self)
        act.triggered.connect(self._choose_venv_activate_path)
        venv_menu.addAction(act)
        act = QAction("Clear venv path", self)
        act.triggered.connect(self._clear_venv_activate_path)
        venv_menu.addAction(act)
        self._menu_width_from_actions(venv_menu)

    def _update_path_labels(self):
        self.terminal_label.setText(f"Terminal path: {self.terminal_path or '—'}")
        self.venv_label.setText(f"Venv activate: {self.venv_activate_path or 'Auto'}")
        self.project_label.setText(f"Project path: {self.project_path or '—'}")

    def _get_grid_columns(self) -> int:
        width = self.scroll_area.viewport().width() if self.scroll_area else 0
        if width <= 0:
            return 2
        return max(1, min(3, width // CARD_MIN_WIDTH))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if not self.script_rows:
            return
        new_cols = self._get_grid_columns()
        if new_cols != self._grid_columns:
            self._grid_columns = new_cols
            self._rebuild_cards_layout()

    def _choose_terminal_path(self):
        QMessageBox.information(
            self,
            "ShScriptHub",
            "Select the terminal executable (.exe), e.g. Git Bash.",
        )
        title = "Select terminal executable"
        if os.name == "nt":
            path, _ = QFileDialog.getOpenFileName(
                self,
                title,
                os.environ.get("ProgramFiles", "/"),
                "Executable (*.exe);;All files (*.*)",
            )
        else:
            path, _ = QFileDialog.getOpenFileName(self, title)
        if path and os.path.isfile(path):
            save_terminal_path(path)
            self.terminal_path = path
            self._update_path_labels()
            QMessageBox.information(self, "ShScriptHub", "Terminal path saved.")

    def _choose_venv_activate_path(self):
        QMessageBox.information(
            self,
            "ShScriptHub",
            "Select the venv activate script (e.g. backend\\.venv\\Scripts\\activate). Used for backend scripts; overrides auto-detect.",
        )
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select venv activate script",
            self.project_path or os.path.expanduser("~"),
            "All files (*.*)",
        )
        if path and os.path.isfile(path):
            save_venv_activate_path(path)
            self.venv_activate_path = path
            self._update_path_labels()
            QMessageBox.information(self, "ShScriptHub", "Venv activate path saved.")

    def _refresh_scripts(self):
        if not self.project_path:
            QMessageBox.information(self, "ShScriptHub", "Select project path first.")
            return
        self.load_scripts()

    def _clear_venv_activate_path(self):
        save_venv_activate_path("")
        self.venv_activate_path = None
        self._update_path_labels()
        if self.project_path:
            self.load_scripts()
        QMessageBox.information(
            self, "ShScriptHub", "Venv path cleared. Backend scripts will use auto-detect."
        )

    def _ensure_terminal_path(self):
        if self.terminal_path and os.path.isfile(self.terminal_path):
            return
        QMessageBox.information(
            self,
            "ShScriptHub",
            "Select your terminal executable (e.g. Git Bash).",
        )
        self._choose_terminal_path()

    def _get_default_category(self, script_path: str) -> str:
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
            self.setWindowTitle(f"ShScriptHub - {os.path.basename(self.project_path)}")
        else:
            self.setWindowTitle("ShScriptHub")

    def select_project(self):
        folder = QFileDialog.getExistingDirectory(self, "Select the root of the project")
        if not folder:
            return
        self.project_path = folder
        self._update_path_labels()
        self._update_title()
        save_project_path(self.project_path)
        self.load_scripts()

    def _matches_search(self, script: dict, search_text: str) -> bool:
        if not search_text or not search_text.strip():
            return True
        q = search_text.strip().lower()
        rel = os.path.relpath(script["path"], self.project_path).replace("\\", "/").lower()
        name = script["name"].lower()
        folder = os.path.basename(os.path.dirname(script["path"])).lower()
        return q in rel or q in name or q in folder

    def _on_search_changed(self, text: str) -> None:
        self._rebuild_cards_layout()

    def _on_folder_changed(self, text: str) -> None:
        self._rebuild_cards_layout()

    def _script_folder(self, script: dict) -> str:
        """Return 'root' if script is at project root, else the first folder name."""
        rel = os.path.relpath(script["path"], self.project_path)
        parts = os.path.normpath(rel).split(os.sep)
        if len(parts) <= 1:
            return "root"
        return parts[0]

    def _get_folders_with_scripts(self) -> list[str]:
        """Folders that have at least one script: 'root' plus first path folders."""
        folders = set()
        for s in self.scripts:
            folders.add(self._script_folder(s))
        return ["root"] + sorted(f for f in folders if f != "root")

    def _refresh_folder_filter(self) -> None:
        """Populate the folder dropdown with only folders that have scripts."""
        self.folder_combo.blockSignals(True)
        self.folder_combo.clear()
        self.folder_combo.addItem("All")
        for folder in self._get_folders_with_scripts():
            self.folder_combo.addItem(folder)
        self.folder_combo.setCurrentIndex(0)
        self.folder_combo.blockSignals(False)

    def _on_favorite_clicked(self, row: dict) -> None:
        path = row["script"]["path"]
        now_fav = toggle_favorite(path)
        row["fav_btn"].setText("★" if now_fav else "☆")
        row["fav_btn"].setToolTip("Unfavorite" if now_fav else "Favorite")
        self._rebuild_cards_layout()

    def _rebuild_cards_layout(self) -> None:
        """Build rows of cards: each row is full-width; cards in a row share width equally. No empty columns."""
        if not self.script_rows:
            return
        search_text = self.search_edit.text() if getattr(self, "search_edit", None) else ""
        folder_filter = self.folder_combo.currentText() if getattr(self, "folder_combo", None) else "All"
        favorites = load_favorites()
        matching = [
            r for r in self.script_rows
            if self._matches_search(r["script"], search_text)
            and (folder_filter == "All" or self._script_folder(r["script"]) == folder_filter)
        ]
        matching.sort(key=lambda r: (r["script"]["path"] not in favorites, r["script"]["path"].lower()))

        while self.scripts_layout.count():
            item = self.scripts_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cols = self._grid_columns
        for i in range(0, len(matching), cols):
            row_cards = [matching[j]["card"] for j in range(i, min(i + cols, len(matching)))]
            row_widget = QWidget()
            row_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(16)
            for card in row_cards:
                row_layout.addWidget(card, 1)
            self.scripts_layout.addWidget(row_widget)
        self.scripts_layout.addStretch()

    def _clear_scripts_ui(self):
        while self.scripts_layout.count():
            item = self.scripts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def load_scripts(self):
        try:
            self._clear_scripts_ui()
            self.script_rows = []
            self.script_manager = ScriptManager(self.project_path)
            self.scripts = self.script_manager.get_scripts()
        except Exception as e:
            QMessageBox.critical(self, "ShScriptHub - Error", f"Failed to load scripts: {str(e)}")
            return

        if not self.scripts:
            no_scripts = QLabel("No .sh scripts found")
            self.scripts_layout.addWidget(no_scripts)
            return

        favorites = load_favorites()
        self.scripts.sort(key=lambda s: (s["path"] not in favorites, s["path"].lower()))

        script_categories = load_script_categories()
        self._grid_columns = self._get_grid_columns()

        for row_idx, s in enumerate(self.scripts):
            rel_path = os.path.relpath(s["path"], self.project_path).replace("\\", "/")
            display_name = rel_path
            if s["path"] in script_categories:
                category_to_show = script_categories[s["path"]]
            else:
                category_to_show = self._get_default_category(s["path"])
            category_display = "None" if category_to_show == "none" else category_to_show
            env_display = self._get_env_display(s, category_to_show)

            card = QFrame()
            card.setObjectName("scriptCard")
            card.setMinimumWidth(0)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            card_layout.setSpacing(10)

            title_row = QHBoxLayout()
            name_lbl = QLabel(display_name)
            name_lbl.setObjectName("cardTitleLabel")
            name_lbl.setWordWrap(True)
            title_row.addWidget(name_lbl, 1)
            is_fav = s["path"] in favorites
            fav_btn = QPushButton("★" if is_fav else "☆")
            fav_btn.setObjectName("favBtn")
            fav_btn.setToolTip("Unfavorite" if is_fav else "Favorite")
            fav_btn.setFixedSize(32, 32)
            title_row.addWidget(fav_btn, 0)
            card_layout.addLayout(title_row)

            meta_row = QHBoxLayout()
            meta_row.setSpacing(12)
            category_combo = NoWheelComboBox()
            category_combo.addItems(CATEGORY_OPTIONS)
            category_combo.setCurrentText(category_display)
            category_combo.setMinimumWidth(100)
            env_label = QLabel(env_display)
            meta_row.addWidget(category_combo)
            meta_row.addWidget(env_label, 1)
            card_layout.addLayout(meta_row)

            status_label = QLabel(PLACEHOLDER)
            pid_label = QLabel(PLACEHOLDER)
            status_row = QHBoxLayout()
            status_row.addWidget(QLabel("Status:"))
            status_row.addWidget(status_label)
            status_row.addSpacing(12)
            status_row.addWidget(QLabel("PID:"))
            status_row.addWidget(pid_label)
            status_row.addStretch()
            card_layout.addLayout(status_row)

            metrics_grid = QGridLayout()
            metric_specs = [
                ("CPU %", "cpu_pct_label"),
                ("RAM (RSS)", "ram_rss_label"),
                ("RAM %", "ram_pct_label"),
                ("Elapsed", "elapsed_label"),
                ("Peak memory", "peak_mem_label"),
                ("CPU time", "cpu_time_label"),
                ("Threads", "threads_label"),
            ]
            metric_widgets = {}
            for i, (title, key) in enumerate(metric_specs):
                r, c = i // 2, (i % 2) * 2
                metrics_grid.addWidget(QLabel(title + ":"), r, c)
                w = QLabel(PLACEHOLDER)
                w.setObjectName("metricValueLabel")
                metrics_grid.addWidget(w, r, c + 1)
                metric_widgets[key] = w
            cpu_pct_label = metric_widgets["cpu_pct_label"]
            ram_rss_label = metric_widgets["ram_rss_label"]
            ram_pct_label = metric_widgets["ram_pct_label"]
            elapsed_label = metric_widgets["elapsed_label"]
            peak_mem_label = metric_widgets["peak_mem_label"]
            cpu_time_label = metric_widgets["cpu_time_label"]
            threads_label = metric_widgets["threads_label"]
            card_layout.addLayout(metrics_grid)

            btn_layout = QHBoxLayout()
            run_btn = QPushButton("Run")
            run_btn.setObjectName("runBtn")
            kill_btn = QPushButton("Kill")
            kill_btn.setObjectName("killBtn")
            kill_btn.setVisible(False)
            btn_layout.addWidget(run_btn)
            btn_layout.addWidget(kill_btn)
            btn_layout.addStretch()
            card_layout.addLayout(btn_layout)

            def _on_category_change(script_path, combo, env_lbl):
                val = combo.currentText()
                stored = "none" if val == "None" else val
                save_script_category(script_path, stored)
                env_lbl.setText(self._get_env_display({"path": script_path}, stored))

            category_combo.currentTextChanged.connect(
                lambda text, sp=s["path"], cb=category_combo, el=env_label: _on_category_change(sp, cb, el)
            )

            row_dict = {
                "script": s,
                "card": card,
                "fav_btn": fav_btn,
                "category_combo": category_combo,
                "status_label": status_label,
                "pid_label": pid_label,
                "cpu_pct_label": cpu_pct_label,
                "ram_rss_label": ram_rss_label,
                "ram_pct_label": ram_pct_label,
                "elapsed_label": elapsed_label,
                "peak_mem_label": peak_mem_label,
                "cpu_time_label": cpu_time_label,
                "threads_label": threads_label,
                "run_btn": run_btn,
                "kill_btn": kill_btn,
                "process": None,
                "kill_pids": None,
                "start_time": None,
                "peak_rss": 0.0,
                "cpu_primed_pids": None,
            }
            self.script_rows.append(row_dict)
            run_btn.clicked.connect(lambda checked=False, r=row_dict: self._run_script_row(r))
            kill_btn.clicked.connect(lambda checked=False, r=row_dict: self._kill_script_row(r))
            fav_btn.clicked.connect(lambda checked=False, r=row_dict: self._on_favorite_clicked(r))

        self._refresh_folder_filter()
        self._rebuild_cards_layout()

    def _set_status(self, row: dict, text: str) -> None:
        row["status_label"].setText(text)
        color = {
            "—": PALETTE["status_placeholder"],
            "Running": PALETTE["status_running"],
            "Stopped": PALETTE["status_stopped"],
        }.get(text, PALETTE["status_placeholder"])
        row["status_label"].setStyleSheet(f"color: {color};")

    def _run_script_row(self, row: dict) -> None:
        try:
            cat = row["category_combo"].currentText()
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
            row["start_time"] = time.monotonic()
            row["peak_rss"] = 0.0
            row["cpu_primed_pids"] = set()
            self._set_status(row, "Running")
            row["pid_label"].setText(str(p.pid))
            for key in ("cpu_pct_label", "ram_rss_label", "ram_pct_label", "elapsed_label", "peak_mem_label", "cpu_time_label", "threads_label"):
                row[key].setText(PLACEHOLDER)
            row["kill_btn"].setVisible(True)
            delay_ms = int(utils.TREE_CAPTURE_DELAY_SEC * 1000)
            QTimer.singleShot(delay_ms, lambda: self._capture_kill_pids(row))
            QMessageBox.information(self, "ShScriptHub", f"Script '{row['script']['name']}' started.")
        except Exception as e:
            QMessageBox.critical(self, "ShScriptHub - Error", str(e))

    def _capture_kill_pids(self, row: dict) -> None:
        proc = row.get("process")
        if proc is None or proc.poll() is not None:
            return
        row["kill_pids"] = get_process_tree_after_spawn(proc)

    def _kill_script_row(self, row: dict) -> None:
        proc = row.get("process")
        if proc is None:
            return
        kill_pids = row.get("kill_pids")
        if not kill_pids and proc.poll() is None:
            kill_pids = [proc.pid]
        kill_script_process(proc, kill_pids=kill_pids)
        self._set_status(row, "Stopped")
        row["pid_label"].setText(PLACEHOLDER)
        row["process"] = None
        row["kill_pids"] = None
        row["start_time"] = None
        row["peak_rss"] = 0.0
        row["cpu_primed_pids"] = None
        for key in ("cpu_pct_label", "ram_rss_label", "ram_pct_label", "elapsed_label", "peak_mem_label", "cpu_time_label", "threads_label"):
            row[key].setText(PLACEHOLDER)
        row["kill_btn"].setVisible(False)

    def check_processes(self) -> None:
        for row in getattr(self, "script_rows", []):
            proc = row.get("process")
            if proc is None:
                continue
            if proc.poll() is not None:
                self._set_status(row, "Stopped")
                row["pid_label"].setText(PLACEHOLDER)
                row["process"] = None
                row["start_time"] = None
                row["peak_rss"] = 0.0
                row["cpu_primed_pids"] = None
                for key in ("cpu_pct_label", "ram_rss_label", "ram_pct_label", "elapsed_label", "peak_mem_label", "cpu_time_label", "threads_label"):
                    row[key].setText(PLACEHOLDER)
                kill_btn = row.get("kill_btn")
                if kill_btn:
                    kill_btn.setVisible(False)

    def _update_row_metrics(self, row: dict) -> None:
        proc = row.get("process")
        if proc is None or proc.poll() is not None:
            return
        pids = row.get("kill_pids")
        if not pids:
            pids = [proc.pid]
        start_time = row.get("start_time") or 0
        peak_rss = row.get("peak_rss") or 0.0
        cpu_primed_pids = row.get("cpu_primed_pids")
        if cpu_primed_pids is None:
            cpu_primed_pids = set()
            row["cpu_primed_pids"] = cpu_primed_pids
        try:
            m = collect_metrics(pids, start_time, peak_rss, cpu_primed_pids)
        except Exception:
            return
        row["peak_rss"] = m["peak_rss_bytes"]
        row["cpu_pct_label"].setText(f"{m['cpu_percent']:.1f}%")
        row["ram_rss_label"].setText(f"{m['rss_mb']:.2f} MB")
        row["ram_pct_label"].setText(f"{m['ram_percent']:.1f}%")
        row["elapsed_label"].setText(format_elapsed(m["elapsed_sec"]))
        row["peak_mem_label"].setText(f"{m['peak_rss_mb']:.2f} MB")
        row["cpu_time_label"].setText(format_cpu_time(m["cpu_time_sec"]))
        row["threads_label"].setText(str(m["num_threads"]))

    def _tick_process_check(self) -> None:
        self.check_processes()
        for row in getattr(self, "script_rows", []):
            if row.get("process") is not None and row["process"].poll() is None:
                self._update_row_metrics(row)
