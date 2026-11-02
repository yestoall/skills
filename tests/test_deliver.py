"""Getting the batch to the phone from a Mac: the AirDrop window, with the Finder
when that doesn't send it, or a copy to iCloud Drive."""

import io
import re
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from deliver import (
    AIRDROP_SCRIPT,
    AIRDROP_TIMEOUT,
    DeliverError,
    main,
    send_to_icloud,
)


class ICloud(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.batch = self.home / "nevera-lote-2026-11-01.zip"
        self.batch.write_bytes(b"PK")
        self.drive = self.home / "Library/Mobile Documents/com~apple~CloudDocs"

    def test_it_copies_the_batch_to_a_nevera_folder_in_icloud_drive(self):
        self.drive.mkdir(parents=True)
        copy = send_to_icloud(self.batch, self.home)
        self.assertEqual(copy, self.drive / "Nevera" / self.batch.name)
        self.assertEqual(copy.read_bytes(), b"PK")

    def test_the_batch_stays_where_it_was(self):
        self.drive.mkdir(parents=True)
        send_to_icloud(self.batch, self.home)
        self.assertTrue(self.batch.exists())

    def test_a_second_batch_goes_into_the_same_folder(self):
        (self.drive / "Nevera").mkdir(parents=True)
        self.assertEqual(
            send_to_icloud(self.batch, self.home).parent, self.drive / "Nevera"
        )

    def test_without_icloud_drive_on_this_mac_it_says_so(self):
        with self.assertRaisesRegex(DeliverError, "iCloud Drive"):
            send_to_icloud(self.batch, self.home)

    def test_a_batch_that_is_not_there_is_an_error(self):
        self.drive.mkdir(parents=True)
        with self.assertRaisesRegex(DeliverError, "nope.zip"):
            send_to_icloud(self.home / "nope.zip", self.home)


class AirDrop(unittest.TestCase):
    """Runs `deliver.py airdrop` with the machine faked: what matters is which
    commands it starts, and where the batch ends up when AirDrop doesn't send."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.batch = Path(self.tmp.name) / "nevera-lote.zip"
        self.batch.write_bytes(b"PK")

        self.commands = []
        self.swift = 0
        self.xcode_select = 0
        self.which = "/usr/bin/swift"

        def run(command, **kwargs):
            self.commands.append(command[0])
            if command[0] == "swift":
                if isinstance(self.swift, Exception):
                    raise self.swift
                return subprocess.CompletedProcess(command, self.swift, "why", "")
            if command[0] == "xcode-select":
                return subprocess.CompletedProcess(command, self.xcode_select)
            return subprocess.CompletedProcess(command, 0)

        for patcher in (
            mock.patch("deliver.this_system", return_value="macos"),
            mock.patch("deliver.subprocess.run", side_effect=run),
            mock.patch("deliver.shutil.which", side_effect=lambda _: self.which),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def deliver(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["airdrop", str(self.batch)])
        return code, out.getvalue().strip(), err.getvalue().strip()

    def test_a_send_the_mac_reports_as_done_stays_out_of_the_finder(self):
        self.assertEqual(self.deliver()[:2], (0, "sent"))
        self.assertNotIn("open", self.commands)

    def test_a_failed_send_shows_the_file_in_the_finder_and_says_why(self):
        self.swift = 1
        self.assertEqual(self.deliver(), (0, "finder", "why"))
        self.assertIn("open", self.commands)

    def test_a_send_that_never_ends_shows_the_file_in_the_finder(self):
        self.swift = subprocess.TimeoutExpired("swift", AIRDROP_TIMEOUT)
        self.assertEqual(self.deliver()[:2], (0, "finder"))

    def test_without_swift_it_goes_straight_to_the_finder(self):
        self.which = None
        self.assertEqual(self.deliver()[:2], (0, "finder"))
        self.assertEqual(self.commands, ["open"])

    def test_the_swift_stub_without_the_tools_never_runs(self):
        # Running /usr/bin/swift there can make macOS offer to install them
        self.xcode_select = 2
        self.assertEqual(self.deliver()[:2], (0, "finder"))
        self.assertNotIn("swift", self.commands)

    def test_a_batch_that_is_not_there_is_an_error(self):
        self.batch.unlink()
        code, out, err = self.deliver()
        self.assertEqual((code, out), (1, ""))
        self.assertIn("nevera-lote.zip", err)
        self.assertEqual(self.commands, [])

    def test_the_swift_script_travels_with_this_one(self):
        self.assertTrue(AIRDROP_SCRIPT.is_file())
        self.assertLess(self.script_wait(), AIRDROP_TIMEOUT)

    def script_wait(self):
        text = AIRDROP_SCRIPT.read_text(encoding="utf-8")
        return float(re.search(r"waitSeconds = ([\d.]+)", text).group(1))


if __name__ == "__main__":
    unittest.main()
