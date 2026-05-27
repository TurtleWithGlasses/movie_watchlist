import os
import shutil
import subprocess
import sys
import tempfile

import requests

GITHUB_REPO = "TurtleWithGlasses/movie_watchlist"
_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def get_latest_release():
    """Return (tag_name, exe_download_url) or (None, None) on any failure."""
    try:
        resp = requests.get(_API_URL, timeout=5)
        if resp.status_code != 200:
            return None, None
        data = resp.json()
        tag = data.get("tag_name", "")
        for asset in data.get("assets", []):
            if asset["name"].lower().endswith(".exe"):
                return tag, asset["browser_download_url"]
        return tag, None
    except Exception:
        return None, None


def _parse_version(v):
    parts = v.lstrip("v").split(".")
    return tuple(int(x) for x in parts if x.isdigit())


def is_newer(current, latest_tag):
    try:
        return _parse_version(latest_tag) > _parse_version(current)
    except Exception:
        return False


def download_update(url, progress_callback=None):
    """Download the new exe to a temp file. Returns the temp file path."""
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    tmp_fd, tmp_path = tempfile.mkstemp(suffix="_update.exe")
    downloaded = 0
    with os.fdopen(tmp_fd, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total:
                    progress_callback(int(downloaded * 100 / total))
    return tmp_path


def apply_update(tmp_exe_path):
    """
    Stage the downloaded exe next to the current one, then launch a detached
    cmd.exe bat that waits a fixed time for this process to exit, swaps the
    file, and restarts.  Fixed wait avoids all process-detection unreliability.
    Only works when running as a packaged exe (sys.frozen).
    """
    if not getattr(sys, "frozen", False):
        return

    current_exe = os.path.abspath(sys.executable)
    current_dir = os.path.dirname(current_exe)

    staged = os.path.join(current_dir, "_update_staged.exe")
    shutil.move(tmp_exe_path, staged)

    bat_path = os.path.join(current_dir, "_updater.bat")
    log_path = os.path.join(current_dir, "_updater_log.txt")
    # Use ping instead of timeout: timeout needs a console, ping works anywhere.
    # ping -n 26 = 25 one-second intervals = ~25 s wait.
    bat = (
        "@echo off\n"
        f'echo [1] bat started >{log_path}\n'
        "ping 127.0.0.1 -n 26 >nul\n"
        f'echo [2] wait done >>{log_path}\n'
        ":move\n"
        f'move /y "{staged}" "{current_exe}"\n'
        "if errorlevel 1 (\n"
        f'    echo [3] move failed >>{log_path}\n'
        "    ping 127.0.0.1 -n 3 >nul\n"
        "    goto move\n"
        ")\n"
        f'echo [4] move ok >>{log_path}\n'
        f'start "" "{current_exe}"\n'
        f'echo [5] start called >>{log_path}\n'
        "ping 127.0.0.1 -n 3 >nul\n"
        f'del "{log_path}"\n'
        'del "%~f0"\n'
    )
    with open(bat_path, "w") as f:
        f.write(bat)

    subprocess.Popen(
        ["cmd.exe", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
    )
