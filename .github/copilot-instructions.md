# ShScriptHub - AI Coding Instructions

## Project Overview
PySide6 desktop application (Windows-focused) that scans directories for `.sh` scripts and runs them in Git Bash terminals with automatic environment detection and real-time process metrics.

## Architecture

### Core Modules
- **main.py**: Qt application entry point; loads theme, sets icon, initializes window
- **gui.py** (1149 lines): Main `ShScriptHubApp` window with sidebar tree, detail panel, custom widgets
- **script_manager.py**: Simple recursive `.sh` file scanner (`os.walk`)
- **config.py**: JSON persistence for project/terminal/venv paths, favorites, per-script categories, theme
- **utils.py**: Process spawning (Git Bash), PID tree tracking (Windows-specific), graceful termination, resource path resolution
- **metrics.py**: psutil-based live metrics (CPU%, RAM, threads, peak memory) aggregated over process trees
- **theme.py**: `DARK_PALETTE` and `LIGHT_PALETTE` dicts; generates QSS stylesheet with f-strings

### Data Flow
1. User selects project folder → `ScriptManager` scans for `.sh` files
2. UI organizes scripts into sidebar tree (folders + favorites section)
3. User clicks Run → `run_script_in_gitbash()` spawns process with auto-detected venv
4. 400ms later, capture PID tree via `get_process_tree_after_spawn()` for proper kill
5. 1s timer polls processes and updates metrics in detail panel

## Critical Patterns

### Config File Locations
Config path differs between dev and PyInstaller builds:
```python
# Dev: d:\Code Projetos\ShScriptHub\config.json (repo root)
# Packaged: C:\path\to\ShScriptHub-V3.1.0.exe → same dir as exe
if getattr(sys, "frozen", False):
    app_dir = os.path.dirname(sys.executable)  # PyInstaller
else:
    app_dir = os.path.dirname(os.path.dirname(__file__))  # src/ parent
```
Always use `get_config_path()` from config.py.

### Process Management (Windows-specific)
**Running scripts**: Git Bash launched with `--cd=<script_dir>` and `-c "<activate_cmd> && bash script.sh"`
- CWD is always the **script's own folder**, not project root
- Venv activation command prepended if detected or configured
- Path separators converted to forward slashes for Bash compatibility

**Killing scripts**: Captures full process tree after 400ms delay because Git Bash spawns child processes:
```python
# utils.py: TREE_CAPTURE_DELAY_SEC = 0.4
proc = subprocess.Popen([git_bash_exe, ...])
QTimer.singleShot(400, lambda: capture_tree(proc))  # Delayed to catch children
```
Uses PowerShell `Get-CimInstance` or `wmic` to find child PIDs recursively; terminates with `taskkill /F`.

### Environment Detection Logic
1. **Backend category + configured venv path**: Use configured path (highest priority)
2. **Auto-detect in script folder**: `.venv/Scripts/activate`, `venv/Scripts/activate` (Windows)
3. **Fallback to project root**: Same search if script folder has no venv
4. **None found**: Run script without activation

Detect order in `_get_activate_cmd()` respects category-specific overrides.

### Dynamic Theme Switching
Components update without restart via Qt property system:
```python
def _toggle_theme(self):
    save_theme(self._theme)
    QApplication.instance().setStyleSheet(get_stylesheet(self._theme))
    # Force re-render for custom widgets
    self._sh_highlighter.update_palette(self._palette)
    self._line_gutter.update_palette(self._palette)
```
Properties like `[running="true"]` in QSS enable state-based styling (e.g., green/gray dots).

## Custom Widgets

### NoWheelComboBox
Prevents accidental category changes via scroll wheel:
```python
def wheelEvent(self, event): event.ignore()
```

### LineNumberGutter
QWidget overlay on QPlainTextEdit; paints line numbers, auto-sizes based on max digits:
```python
gutter_width = PADDING + font.width("9") * digits + PADDING
editor.setViewportMargins(gutter_width, 0, 0, 0)
```

### ShellHighlighter
QSyntaxHighlighter with ordered regex rules for shebangs, comments, strings, variables, keywords. Rebuild rules on theme change.

## Build & Release

### PyInstaller Command
```bash
# build_release.sh
pyinstaller --onefile --noconsole --name="ShScriptHub-V3.1.0" \
  --icon=../assets/icon.ico --add-data "../assets;assets" \
  --distpath release --workpath build --specpath release src/main.py
```
Version number embedded in executable name (`V3.1.0`). Assets bundled with `--add-data`.

### Resource Path Handling
```python
# utils.py: get_resource_path()
base_path = sys._MEIPASS if frozen else os.path.dirname(__file__) + '/..'
return os.path.join(base_path, relative_path)
```
Use for `assets/icon.ico` and other bundled files.

## Development Workflow

### Running Dev
```bash
python src/main.py  # From repo root
```
Config writes to `./config.json`. Expects `requirements.txt` deps installed.

### Testing Process Metrics
1. Set project path to folder with test `.sh` scripts
2. Run script → metrics update every 1s in detail panel
3. Check that Kill terminates the terminal window (not just parent process)

### Adding UI Components
Follow existing patterns:
- Extract colors from `self._palette` dict
- Use `setObjectName()` for QSS targeting
- Connect signals in `__init__` after widget creation
- Update `get_stylesheet()` in theme.py for new object names

## Common Gotchas

1. **Path separators**: Always use `os.sep` or `os.path.join()`, then convert to `/` before passing to Git Bash
2. **Category persistence**: Saved as `"backend"/"frontend"/"none"` (lowercase) but UI shows `"Backend"/"Frontend"/"None"`
3. **Favorites storage**: Set of absolute paths; compare with `os.path.abspath()` or script's `path` field
4. **Process polling**: Check `proc.poll() is None` for running, not `proc.returncode`
5. **Timer intervals**: 1000ms for process checks, 180ms for search debounce, 400ms for PID capture
6. **Category inference**: Auto-detect from first-level folder name (`backend/`, `frontend/`), user can override
7. **Metrics collection**: First `cpu_percent()` call returns 0 (priming), track via `cpu_primed_pids` set

## Key Files to Reference

- [src/utils.py](src/utils.py) - Process lifecycle, venv detection, Windows PID trees
- [src/gui.py](src/gui.py#L1-L100) - Main window init, widget hierarchy
- [src/config.py](src/config.py) - Persistent settings pattern
- [src/theme.py](src/theme.py#L1-L100) - Color palettes and QSS generation
- [build_release.sh](build_release.sh) - PyInstaller packaging
