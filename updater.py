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
    Move the downloaded exe to _update_staged.exe next to the current exe.
    The actual swap is performed by do_staged_update(), called from closeEvent
    after all data has been saved.
    Only has effect when running as a packaged exe (sys.frozen).
    """
    if not getattr(sys, "frozen", False):
        return
    current_dir = os.path.dirname(os.path.abspath(sys.executable))
    staged = os.path.join(current_dir, "_update_staged.exe")
    shutil.move(tmp_exe_path, staged)


def do_staged_update():
    """
    If _update_staged.exe exists, perform an atomic rename-based swap and
    relaunch.  Windows allows renaming a running exe, so this is safe to call
    from closeEvent after data is saved — no external bat/ps1 script needed.

    Steps:
      1. Rename the running exe to _old_version.exe  (still runs fine)
      2. Rename _update_staged.exe to the original exe name
      3. Launch the new exe
      4. The current process finishes closing normally

    Returns True if the new exe was launched, False if nothing to do or error.
    """
    if not getattr(sys, "frozen", False):
        return False
    current_exe = os.path.abspath(sys.executable)
    current_dir = os.path.dirname(current_exe)
    staged = os.path.join(current_dir, "_update_staged.exe")
    if not os.path.exists(staged):
        return False

    old_exe = os.path.join(current_dir, "_old_version.exe")
    try:
        # Clean up any leftover from a previous failed update
        if os.path.exists(old_exe):
            os.remove(old_exe)
        # Step 1 — rename ourselves out of the way
        os.rename(current_exe, old_exe)
    except Exception:
        return False

    try:
        # Step 2 — put the new exe in our place
        os.rename(staged, current_exe)
    except Exception:
        # Restore our original name before giving up
        try:
            os.rename(old_exe, current_exe)
        except Exception:
            pass
        return False

    # Step 3 — launch the new exe and let the current process finish closing
    try:
        subprocess.Popen([current_exe])
    except Exception:
        pass
    return True


def cleanup_old_version():
    """
    Delete _old_version.exe if it exists (left over from a previous update).
    Called at startup so the file is removed once the old process has exited.
    """
    if not getattr(sys, "frozen", False):
        return
    current_dir = os.path.dirname(os.path.abspath(sys.executable))
    old_exe = os.path.join(current_dir, "_old_version.exe")
    try:
        if os.path.exists(old_exe):
            os.remove(old_exe)
    except Exception:
        pass  # Old process may not have fully exited yet; retry next startup
