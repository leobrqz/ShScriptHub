# ShScriptHub

![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat&logo=windows&logoColor=white)

A **Windows** desktop launcher to run `.sh` scripts from any project with one click — opens Git Bash in a new window. Each script runs in **its own folder** (CWD = script directory). Env (Python venv, Node) is auto-detected there; optional config venv path applies only when you mark a script as **backend**.

---

## ✨ Features

- **Select project folder** — Choose any project root; the path is saved for next runs
- **Refresh** — Project → Refresh to rescan scripts without restarting
- **Config** — Set Git Bash path (prompted on first run); optional **venv activate path** (for scripts you mark as backend; shows "Auto" when not set); **Clear venv path** to revert to auto-detect
- **Script table** — File name (path relative to project), **Category** (dropdown: None / backend / frontend), **Env** (auto-detected or from config), Status, PID, Run / Kill
- **Category** — Auto-detected when the script lives under a folder named `backend/` or `frontend/`; you can change it per script. Your choice is saved and overrides auto-detect next time
- **Run** — Opens a new Git Bash window; CWD is always the script’s directory (never project root unless the script is at root)
- **Kill** — Stops the terminal for that script (only the one launched from the app)
- **Status** — Idle, Running, Stopped
- **Env** — Auto-detected in the script’s folder: `.venv`, `venv` (Python), or `node_modules` (Node). If category is **backend** and you set a venv path in Config, that path is used instead


## 📁 How scripts are discovered

The app scans the **selected folder** recursively and lists every `.sh` file. For each script:

- **File name** — Shown as path relative to the project (e.g. `backend/run.sh`, `frontend/dev.sh`, `scripts/docker-up.sh`)
- **Category** — Dropdown: **None**, **backend**, **frontend**. If you haven’t set a category, it’s auto-detected: scripts under a folder named `backend/` or `frontend/` get that category; others get None. Your selection is saved and takes priority next time
- **Working directory** — When you Run, the terminal’s CWD is **always the folder where the script lives** (so paths in the script are relative to that folder). If the script is at project root, CWD is project root
- **Env** — Detected in that folder: `.venv` or `venv` (Python) or `node_modules` (Node). For category **backend** only, you can set **Config → Set venv activate path** to force a specific venv; otherwise auto-detect is used. If no env is found, the script just runs

Example layout (any structure works):

```
your-project/
├── backend/          # .sh scripts; category auto = backend; .venv/venv auto-detected
├── frontend/         # .sh scripts; category auto = frontend; node_modules shown if present
├── api/              # your own name; category defaults to None
└── scripts/          # category None; CWD = scripts/ when you run
```

You can point ShScriptHub at any folder; it finds all `.sh` files and runs each one from its own directory with env auto-detected (or your venv path for backend).


## ⚙️ Setup & Run

### 1. Clone or open the project

```bash
git clone https://github.com/leobrqz/ShScriptHub.git
cd ShScriptHub
```

### 2. Run the app

```bash
python src/main.py
```

On first launch you may be asked to set the **terminal path** (Git Bash). Use **Project → Set project path** to choose the root of the project you want to run scripts from. Paths and category choices are saved in `config.json`. You can change them via **Config** (terminal path, venv path, clear venv path) and **Project** (set path, refresh).

## Author

**Leonardo B.**

- GitHub: [@leobrqz](https://github.com/leobrqz)
- LinkedIn: [leonardobri](https://linkedin.com/in/leonardobri)

Check out my other projects <3
