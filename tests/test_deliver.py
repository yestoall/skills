"""Getting the batch to the phone from a Mac: a copy to iCloud Drive, or the
AirDrop window with the file in front of the user."""

import tempfile
import unittest
from pathlib import Path

from deliver import DeliverError, airdrop_commands, send_to_icloud


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
    def test_it_opens_the_airdrop_window_and_shows_the_file_in_the_finder(self):
        # A script can't start AirDrop: macOS offers it no sharing service, so
        # the user drags the file onto their phone
        commands = airdrop_commands(Path("/x/nevera-lote.zip"))
        self.assertEqual(
            commands,
            [
                [
                    "open",
                    "/System/Library/CoreServices/Finder.app/Contents/Applications/AirDrop.app",
                ],
                ["open", "-R", "/x/nevera-lote.zip"],
            ],
        )


if __name__ == "__main__":
    unittest.main()
