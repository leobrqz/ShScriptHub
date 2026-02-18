import subprocess
import os
import platform
import signal

KILL_GRACEFUL_WAIT = 2.0
KILL_FORCE_WAIT = 1.0

# Delay to capture process tree (git-bash may be a launcher that exits quickly)
TREE_CAPTURE_DELAY_SEC = 0.4


def _get_activate_cmd(cwd: str, category: str, venv_activate_path: str | None, is_windows: bool) -> str | None:
    """Returns shell command to activate venv, or None if no venv to activate."""
    if category == "backend" and venv_activate_path and os.path.isfile(venv_activate_path):
        return f'source "{venv_activate_path.replace(os.sep, "/")}"'
    if is_windows:
        for subpath, name in [
            (os.path.join(cwd, ".venv", "Scripts", "activate"), ".venv"),
            (os.path.join(cwd, "venv", "Scripts", "activate"), "venv"),
        ]:
            if os.path.isfile(subpath):
                return f"source {name}/Scripts/activate"
    else:
        for subpath, name in [
            (os.path.join(cwd, ".venv", "bin", "activate"), ".venv"),
            (os.path.join(cwd, "venv", "bin", "activate"), "venv"),
        ]:
            if os.path.isfile(subpath):
                return f"source {name}/bin/activate"
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

    activate_cmd = _get_activate_cmd(cwd, category, venv_activate_path, is_windows)
    if activate_cmd:
        command = f"{activate_cmd} && bash {script_name}"
    else:
        command = f"bash {script_name}"

    if is_windows:
        exe = (terminal_path or "").strip()
        if not exe or not os.path.exists(exe):
            raise FileNotFoundError("Terminal executable not found. Set it in Config → Terminal path.")
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
