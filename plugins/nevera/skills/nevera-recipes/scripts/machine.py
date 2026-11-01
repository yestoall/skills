#!/usr/bin/env python3
"""Where the skill keeps its things, and which system it runs on.

The scripts import it as a sibling: they run as `python3 <scripts>/x.py`, so
their own folder is on the import path.

Standard library only: it runs with any Python 3.9+.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Optional


def this_system(name: Optional[str] = None) -> str:
    """macos, windows or linux: the three the skill knows how to install on.
    `name` is a `platform.system()` value; without it, this machine's."""
    name = name if name is not None else platform.system()
    return {"Darwin": "macos", "Windows": "windows"}.get(name, "linux")


def nevera_home() -> Path:
    """~/Nevera, or NEVERA_HOME: the batches, converted.tsv and the venv."""
    return Path(os.environ.get("NEVERA_HOME") or Path.home() / "Nevera")
