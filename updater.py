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
    PowerShell script that waits for this process to fully exit (including
    PyInstaller temp-dir cleanup), swaps the file, and restarts.
    Only works when running as a packaged exe (sys.frozen).
    """
    if not getattr(sys, "frozen", False):
        return

    current_exe = os.path.abspath(sys.executable)
    current_dir = os.path.dirname(current_exe)

    staged = os.path.join(current_dir, "_update_staged.exe")
    shutil.move(tmp_exe_path, staged)

    pid = os.getpid()
    ps1_path = os.path.join(current_dir, "_updater.ps1")
    # Use single quotes inside the script so PowerShell doesn't expand variables
    # at write-time. All {pid}/{staged}/{current_exe} are Python f-string expansions.
    script = (
        f"$pid = {pid}\n"
        # Wait until the old process is fully gone (reliable — no tasklist quirks)
        "while (Get-Process -Id $pid -ErrorAction SilentlyContinue) {\n"
        "    Start-Sleep -Seconds 1\n"
        "}\n"
        # Extra wait for PyInstaller to finish removing its _MEI temp directory
        "Start-Sleep -Seconds 6\n"
        # Retry the move until antivirus / OS releases any remaining lock
        "$moved = $false\n"
        "for ($i = 0; $i -lt 20 -and -not $moved; $i++) {\n"
        "    try {\n"
        f"        Move-Item -Force -Path '{staged}' -Destination '{current_exe}' -ErrorAction Stop\n"
        "        $moved = $true\n"
        "    } catch {\n"
        "        Start-Sleep -Seconds 2\n"
        "    }\n"
        "}\n"
        "if ($moved) {\n"
        f"    Start-Process -FilePath '{current_exe}'\n"
        "}\n"
        "Remove-Item $PSCommandPath -Force -ErrorAction SilentlyContinue\n"
    )
    with open(ps1_path, "w", encoding="utf-8") as f:
        f.write(script)

    subprocess.Popen(
        [
            "powershell.exe",
            "-ExecutionPolicy", "Bypass",
            "-WindowStyle", "Hidden",
            "-NonInteractive",
            "-File", ps1_path,
        ],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
    )
