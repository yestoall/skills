#!/usr/bin/env python3
"""Where the skill keeps its things, and which system it runs on.

The scripts import it as a sibling: they run as `python3 <scripts>/x.py`, so
their own folder is on the import path.

Standard library only: it runs with any Python 3.9+.
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Callable, List, Optional


def this_system(name: Optional[str] = None) -> str:
    """macos, windows or linux: the three the skill knows how to install on.
    `name` is a `platform.system()` value; without it, this machine's."""
    name = name if name is not None else platform.system()
    return {"Darwin": "macos", "Windows": "windows"}.get(name, "linux")


def open_command(system: str, path: str) -> List[str]:
    """How this system opens a text file with the user's default editor."""
    if system == "macos":
        return ["open", "-t", path]
    if system == "windows":
        return ["cmd", "/c", "start", "", path]
    return ["xdg-open", path]


def _xdg_download() -> Optional[str]:
    try:
        return subprocess.run(
            ["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def downloads_folder(
    system: Optional[str] = None, xdg: Callable[[], Optional[str]] = _xdg_download
) -> Path:
    """~/Downloads. A Linux in another language has its own (~/Descargas), and
    only xdg-user-dir knows it. With nothing set, it answers with the home
    folder itself."""
    home = Path.home()
    if (system or this_system()) == "linux":
        found = xdg()
        if found and Path(found) != home:
            return Path(found)
    return home / "Downloads"


def nevera_home() -> Path:
    """Downloads/nevera, or NEVERA_HOME: work, converted.tsv and the venv."""
    override = os.environ.get("NEVERA_HOME")
    return Path(override) if override else downloads_folder() / "nevera"


def batches_folder() -> Path:
    """Where the finished batches go: Downloads, or NEVERA_HOME."""
    override = os.environ.get("NEVERA_HOME")
    return Path(override) if override else downloads_folder()
