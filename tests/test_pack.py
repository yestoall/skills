"""Packing the batch the skill wrote in its work folder: only what Nevera
needs goes in, and nothing is written if the batch would not pass."""

import datetime
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from lote import default_output, pack, validate
from tests.helpers import batch, jpeg, recipe


class Pack(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        (self.work / "photos").mkdir()
        self.out = Path(tempfile.mkdtemp()) / "Nevera" / "lote.zip"

    def write(self, data):
        (self.work / "recipes.json").write_text(json.dumps(data), encoding="utf-8")

    def test_the_recipes_and_only_the_photos_they_use(self):
        self.write(batch(recipe(photo="tortilla.jpg"), recipe("Gazpacho")))
        (self.work / "photos" / "tortilla.jpg").write_bytes(jpeg(1080, 1080))
        (self.work / "photos" / "sheet.jpg").write_bytes(jpeg(1200, 900))
        report = pack(self.work, self.out)
        self.assertTrue(report.ok, report.text())
        with zipfile.ZipFile(self.out) as archive:
            self.assertEqual(
                sorted(archive.namelist()), ["photos/tortilla.jpg", "recipes.json"]
            )
        self.assertTrue(validate(self.out).ok)

    def test_nothing_is_written_when_the_batch_would_not_pass(self):
        self.write(batch(recipe(photo="tortilla.jpg")))
        report = pack(self.work, self.out)
        self.assertFalse(report.ok)
        self.assertFalse(self.out.exists())

    def test_the_default_name_is_the_day_and_never_overwrites(self):
        folder = Path(tempfile.mkdtemp())
        day = datetime.date(2026, 11, 1)
        first = default_output(folder, day)
        self.assertEqual(first.name, "nevera-lote-2026-11-01.zip")
        first.write_bytes(b"")
        self.assertEqual(default_output(folder, day).name, "nevera-lote-2026-11-01-2.zip")


if __name__ == "__main__":
    unittest.main()
