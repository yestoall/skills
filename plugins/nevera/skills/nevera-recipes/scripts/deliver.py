#!/usr/bin/env python3
"""Gets the batch closer to the phone, from a Mac, when the user asks.

    python3 deliver.py airdrop <batch.zip>   open the AirDrop window with the
                                             file, and wait for the user to
                                             pick a device
    python3 deliver.py icloud <batch.zip>    copy it to iCloud Drive/Nevera

`airdrop` prints `sent` when the Mac reports the send as done, and `finder` when
it doesn't, with the file shown in the Finder too: Control-click, Share, AirDrop.
That report can come after the file arrives, so `finder` doesn't prove it never
did. It's also where it ends up on a Mac without Xcode or the Command Line Tools,
since the window comes from `airdrop.swift`, run with `swift`. Dragging the file
onto the AirDrop window started no send on macOS 27, even with the phone in
sight.

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
AIRDROP_SCRIPT = Path(__file__).resolve().with_name("airdrop.swift")

# airdrop.swift gives up after 240 seconds. This covers compiling it as well,
# and a run that hangs before its own timer starts.
AIRDROP_TIMEOUT = 300


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


def has_swift() -> bool:
    """Asks xcode-select, because /usr/bin/swift exists even without the tools,
    and running it there can make macOS offer to install them."""
    if shutil.which("swift") is None:
        return False
    found = subprocess.run(
        ["xcode-select", "-p"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return found.returncode == 0


def send_with_airdrop(batch: Path) -> bool:
    """True when the Mac reports the send as done. Waits for the user to pick a
    device, and says why on stderr when it wasn't sent."""
    if not has_swift():
        print("Swift isn't available on this Mac", file=sys.stderr)
        return False
    try:
        done = subprocess.run(
            ["swift", str(AIRDROP_SCRIPT), str(batch)],
            capture_output=True,
            text=True,
            timeout=AIRDROP_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        print(error, file=sys.stderr)
        return False
    if done.returncode != 0:
        print(done.stdout.strip() or done.stderr.strip(), file=sys.stderr)
    return done.returncode == 0


def show_in_finder(batch: Path) -> None:
    subprocess.run(["open", "-R", str(batch)], check=True)


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
        if send_with_airdrop(batch):
            print("sent")
            return 0
        show_in_finder(batch)
        print("finder")
        return 0
    except (DeliverError, OSError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
