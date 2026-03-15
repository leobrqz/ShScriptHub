import subprocess
import os
import platform
import signal
import sys

KILL_GRACEFUL_WAIT = 2.0
KILL_FORCE_WAIT = 1.0


TREE_CAPTURE_DELAY_SEC = 0.4


def _get_activate_cmd(
    cwd: str,
    category: str,
    venv_activate_path: str | None,
    is_windows: bool,
    project_path: str | None = None,
) -> str | None:
    """Returns shell command to activate venv, or None if no venv to activate."""
    if category == "backend" and venv_activate_path and os.path.isfile(venv_activate_path):
        return f'source "{venv_activate_path.replace(os.sep, "/")}"'
    search_roots = [cwd]
    if project_path and os.path.isdir(project_path) and project_path != cwd:
        search_roots.append(project_path)
    if is_windows:
        for root in search_roots:
            for subpath in [
                os.path.join(root, ".venv", "Scripts", "activate"),
                os.path.join(root, "venv", "Scripts", "activate"),
            ]:
                if os.path.isfile(subpath):
                    return f'source "{subpath.replace(os.sep, "/")}"'
    else:
        for root in search_roots:
            for subpath in [
                os.path.join(root, ".venv", "bin", "activate"),
                os.path.join(root, "venv", "bin", "activate"),
            ]:
                if os.path.isfile(subpath):
                    return f'source "{subpath.replace(os.sep, "/")}"'
    return None


def run_script_in_gitbash(
    script_path: str,
    category: str,
    project_path: str,
    terminal_path: str | None = None,
    venv_activate_path: str | None = None,
) -> subprocess.Popen:
    """
    Runs a .sh script in the configured terminal. CWD is always the script's directory.
    Venv is auto-detected in that directory; for category "backend", config venv path is preferred.
    """
    system = platform.system()
    is_windows = system == "Windows"
    cwd = os.path.dirname(script_path)
    script_name = os.path.basename(script_path)

    activate_cmd = _get_activate_cmd(cwd, category, venv_activate_path, is_windows, project_path)
    if activate_cmd:
        command = f"{activate_cmd} && bash {script_name}"
    else:
        command = f"bash {script_name}"

    if is_windows:
        exe = (terminal_path or "").strip()
        if not exe or not os.path.exists(exe):
            raise FileNotFoundError("Terminal executable not found. Set it in Terminal → Set terminal path.")
        command = f"({command}); exec bash"
        return subprocess.Popen(
            [exe, f"--cd={cwd}", "-c", command],
            shell=False,
        )

    return subprocess.Popen(
        command,
        shell=True,
        executable="/bin/bash",
        cwd=cwd,
    )


def run_script_in_gitbash_captured(
    script_path: str,
    category: str,
    project_path: str,
    terminal_path: str | None = None,
    venv_activate_path: str | None = None,
    log_file_path: str | None = None,
) -> subprocess.Popen:
    """
    Runs a .sh script with output captured for logging. No terminal window.
    When log_file_path is set, script stdout/stderr are redirected to that file
    (avoids Git Bash on Windows not writing to PIPE). Caller must poll the file
    and persist to history_logs. When log_file_path is None, uses PIPE (may not
    work on Windows with Git Bash).
    """
    system = platform.system()
    is_windows = system == "Windows"
    cwd = os.path.dirname(script_path)
    script_name = os.path.basename(script_path)

    activate_cmd = _get_activate_cmd(cwd, category, venv_activate_path, is_windows, project_path)
    if activate_cmd:
        inner_cmd = f"{activate_cmd} && bash {script_name}"
    else:
        inner_cmd = f"bash {script_name}"

    creationflags = 0
    if is_windows and hasattr(subprocess, "CREATE_NO_WINDOW") and not log_file_path:
        creationflags = subprocess.CREATE_NO_WINDOW

    if log_file_path:
        log_path_bash = os.path.abspath(log_file_path).replace("\\", "/")
        command = f"( trap '' INT; ({inner_cmd}) 2>&1 | tee '{log_path_bash}' ); exec bash"
        stdout_target = None
        stderr_target = None
    else:
        command = f"({inner_cmd}); exec bash" if is_windows else inner_cmd
        stdout_target = subprocess.PIPE
        stderr_target = subprocess.STDOUT

    popen_kw = dict(
        stdout=stdout_target,
        stderr=stderr_target,
        text=True if not log_file_path else None,
        encoding="utf-8" if not log_file_path else None,
        errors="replace" if not log_file_path else None,
    )

    if is_windows:
        exe = (terminal_path or "").strip()
        if not exe or not os.path.exists(exe):
            raise FileNotFoundError("Terminal executable not found. Set it in Terminal → Set terminal path.")
        if not log_file_path:
            command = f"({inner_cmd}); exec bash"
        return subprocess.Popen(
            [exe, f"--cd={cwd}", "-c", command],
            shell=False,
            creationflags=creationflags,
            **popen_kw,
        )

    return subprocess.Popen(
        command,
        shell=True,
        executable="/bin/bash",
        cwd=cwd,
        **popen_kw,
    )


def _get_children_windows(pid: int) -> list[int]:
    """Returns PIDs of child processes of pid on Windows (PowerShell or wmic)."""
    creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    try:
        ps_cmd = (
            f"Get-CimInstance Win32_Process -Filter \"ParentProcessId={pid}\" | Select-Object -ExpandProperty ProcessId"
        )
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=creationflags,
        )
        if out.returncode == 0 and out.stdout:
            children = []
            for line in out.stdout.strip().splitlines():
                line = line.strip()
                if line.isdigit():
                    children.append(int(line))
            return children
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    try:
        out = subprocess.run(
            ["wmic", "process", "where", f"(ParentProcessId={pid})", "get", "ProcessId"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=creationflags,
        )
        if out.returncode == 0 and out.stdout:
            children = []
            for line in out.stdout.strip().splitlines():
                line = line.strip()
                if line and line != "ProcessId" and line.isdigit():
                    children.append(int(line))
            return children
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return []


def _get_process_tree_windows(root_pid: int) -> list[int]:
    """Returns [root_pid] + all descendant PIDs on Windows."""
    result = [root_pid]
    for child_pid in _get_children_windows(root_pid):
        result.append(child_pid)
        result.extend(_get_process_tree_windows(child_pid))
    return result


def get_process_tree_after_spawn(process: subprocess.Popen) -> list[int]:
    """
    Call after a short delay (e.g. 0.4s) after Popen; returns list of PIDs
    (process + children) so we can close the window even if the launcher already exited.
    """
    if process is None:
        return []
    if platform.system() != "Windows":
        return [process.pid]
    return _get_process_tree_windows(process.pid)


def kill_script_process(process: subprocess.Popen, kill_pids: list[int] | None = None) -> None:
    """
    Terminates the terminal process and on Windows the full tree (window may
    be a child of the process Popen returned). kill_pids: list of PIDs
    captured with get_process_tree_after_spawn to kill the correct processes.
    """
    if process is None:
        return
    try:
        if platform.system() == "Windows":
            pids_to_kill = list(kill_pids) if kill_pids else [process.pid]
            for pid in pids_to_kill:
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/F"],
                        capture_output=True,
                        timeout=5,
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                    )
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
            try:
                process.wait(timeout=KILL_FORCE_WAIT)
            except subprocess.TimeoutExpired:
                pass
        else:
            if process.poll() is not None:
                return
            try:
                os.kill(process.pid, signal.SIGINT)
            except (ProcessLookupError, OSError):
                pass
            try:
                process.wait(timeout=KILL_GRACEFUL_WAIT)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=KILL_FORCE_WAIT)
                except subprocess.TimeoutExpired:
                    process.kill()
    except (ProcessLookupError, OSError):
        pass


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return os.path.join(base_path, relative_path)
