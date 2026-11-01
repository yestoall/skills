#!/usr/bin/env python3
"""A batch that stopped halfway: what it left behind, and how to throw it away.

    python3 work.py status    # JSON: leftover, recipes done, links still to do
    python3 work.py clean     # delete the work folder; the record stays

The work folder only goes away when a batch ends. If one is cut short, what it
left would end up in the next batch unless someone decides what to do with it:
`status` says what is there, and the user chooses.

Standard library only: it runs with any Python 3.9+.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Optional

from links import Record, link_identity, pending
from machine import nevera_home

WORK = "work"
# what the system leaves in a folder doesn't count as work
NOT_WORK = {".DS_Store", "Thumbs.db", "desktop.ini"}


def _has_work(folder: Path) -> bool:
    return any(
        path.is_file() and path.name not in NOT_WORK for path in folder.rglob("*")
    )


def _recipes(folder: Path) -> list:
    """The recipes written so far. A file cut in half has none: its links are
    simply done again."""
    try:
        data = json.loads((folder / "batch" / "recipes.json").read_text(encoding="utf-8"))
        return [r for r in data["recipes"] if isinstance(r, dict)]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def status(home: Optional[Path] = None) -> dict:
    home = Path(home) if home else nevera_home()
    folder = home / WORK
    if not folder.is_dir() or not _has_work(folder):
        return {"leftover": False}
    recipes = _recipes(folder)
    done = {link_identity(r.get("url")) for r in recipes}
    try:
        text = (folder / "links.txt").read_text(encoding="utf-8")
    except OSError:
        text = ""
    return {
        "leftover": True,
        "recipes": [r.get("name", "") for r in recipes],
        "pending": [
            link
            for link in pending(text, Record(home))["pending"]
            if link["identity"] not in done
        ],
    }


def clean(home: Optional[Path] = None) -> None:
    home = Path(home) if home else nevera_home()
    shutil.rmtree(home / WORK, ignore_errors=True)


def main(argv: list) -> int:
    if argv == ["status"]:
        print(json.dumps(status(), indent=2, ensure_ascii=False))
        return 0
    if argv == ["clean"]:
        clean()
        return 0
    print(__doc__, file=sys.stderr if argv else sys.stdout)
    return 0 if not argv or argv[0] in ("-h", "--help") else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
