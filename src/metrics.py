"""
Aggregate process metrics for a list of PIDs (process tree) using psutil.
Used to display CPU %, RAM RSS/%, active time, peak memory, CPU time, thread count.
"""
import time
import psutil

BYTES_PER_MB = 1024 * 1024
PLACEHOLDER = "—"


def _safe_process(pid: int):
    try:
        return psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def format_elapsed(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    if seconds < 0:
        seconds = 0
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{int(s):02d}"


def format_cpu_time(seconds: float) -> str:
    """Format CPU time (user+system) as 0:00:12.5."""
    if seconds < 0:
        seconds = 0
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = seconds % 60
    return f"{h}:{m:02d}:{s:.1f}"


def collect_metrics(
    pids: list[int],
    start_time: float,
    peak_rss_bytes: float,
    cpu_primed_pids: set[int],
) -> dict:
    """
    Aggregate metrics over the given PIDs (process tree).
    start_time: time.monotonic() when run started.
    peak_rss_bytes: previous peak RSS in bytes; returned updated.
    cpu_primed_pids: set of PIDs that have had at least one cpu_percent() call (first returns 0).
    Returns dict: cpu_percent, rss_mb, ram_percent, elapsed_sec, peak_rss_mb, cpu_time_sec, num_threads.
    """
    total_rss = 0.0
    total_cpu_percent = 0.0
    total_cpu_time = 0.0
    total_threads = 0
    new_peak_rss = peak_rss_bytes

    try:
        mem_total = psutil.virtual_memory().total
    except Exception:
        mem_total = 1

    for pid in pids:
        proc = _safe_process(pid)
        if proc is None:
            continue
        try:
            mi = proc.memory_info()
            rss = mi.rss
            total_rss += rss
            if rss > new_peak_rss:
                new_peak_rss = rss

            cpu_pct = proc.cpu_percent(interval=None)
            if pid in cpu_primed_pids:
                total_cpu_percent += cpu_pct
            else:
                cpu_primed_pids.add(pid)

            try:
                ct = proc.cpu_times()
                total_cpu_time += (ct.user or 0) + (ct.system or 0)
            except (AttributeError, OSError):
                pass
            try:
                total_threads += proc.num_threads()
            except (AttributeError, OSError):
                pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    elapsed = time.monotonic() - start_time if start_time else 0
    ram_percent = (total_rss / mem_total * 100) if mem_total else 0

    return {
        "cpu_percent": total_cpu_percent,
        "rss_mb": total_rss / BYTES_PER_MB,
        "ram_percent": ram_percent,
        "elapsed_sec": elapsed,
        "peak_rss_mb": new_peak_rss / BYTES_PER_MB,
        "peak_rss_bytes": new_peak_rss,
        "cpu_time_sec": total_cpu_time,
        "num_threads": total_threads,
    }
