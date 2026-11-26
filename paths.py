import os
import sys


def app_dir():
    """Folder holding the exe (frozen) or this source file (dev)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DB_PATH = os.path.join(app_dir(), "watchlist.db")
