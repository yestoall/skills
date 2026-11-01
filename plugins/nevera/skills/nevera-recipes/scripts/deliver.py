#!/usr/bin/env python3
"""Gets the batch closer to the phone, from a Mac, when the user asks.

    python3 deliver.py icloud <batch.zip>    copy it to iCloud Drive/Nevera
    python3 deliver.py airdrop <batch.zip>   show the file in the Finder, ready
                                             to share with AirDrop

A script can't start AirDrop by itself: on macOS 27, AppKit offers no sharing
service for a file from a script, a binary or a small app. Dragging the file
onto the AirDrop window starts no send there either, even with the phone in
sight, so the user shares it from the Finder: Control-click, Share, AirDrop.

Standard library only: it runs with any Python 3.9+.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

from machine import this_system

ICLOUD_DRIVE = "Library/Mobile Documents/com~apple~CloudDocs"


class DeliverError(Exception):
    """What went wrong, in words the user can read."""


def send_to_icloud(batch: Path, home: Path) -> Path:
    """Copies the batch to a Nevera folder in iCloud Drive and returns the copy.
    The batch stays where it was."""
    if not batch.is_file():
        raise DeliverError(f"There is no batch at {batch}")
    drive = home / ICLOUD_DRIVE
    if not drive.is_dir():
        raise DeliverError("iCloud Drive is not turned on for this Mac")
    folder = drive / "Nevera"
    folder.mkdir(exist_ok=True)
    return Path(shutil.copy2(batch, folder / batch.name))


def airdrop_commands(batch: Path) -> List[List[str]]:
    return [["open", "-R", str(batch)]]


def main(argv: List[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("icloud", "airdrop"):
        print(__doc__, file=sys.stderr)
        return 2
    action, batch = argv[0], Path(argv[1]).expanduser()
    try:
        if this_system() != "macos":
            raise DeliverError("This only works on a Mac")
        if action == "icloud":
            print(send_to_icloud(batch, Path.home()))
            return 0
        if not batch.is_file():
            raise DeliverError(f"There is no batch at {batch}")
        for command in airdrop_commands(batch):
            subprocess.run(command, check=True)
        return 0
    except (DeliverError, OSError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
