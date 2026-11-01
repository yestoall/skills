"""A batch that stopped halfway: what it left behind, and what is still to do,
so the next one neither loses that work nor mixes its recipes in by accident."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from links import Record
from tests.helpers import batch, recipe
from work import clean, status

TORTILLA = "https://youtu.be/AAAAAAAAAAA?si=x"
GAZPACHO = "https://www.youtube.com/watch?v=BBBBBBBBBBB"
PAELLA = "https://example.com/paella"


class Base(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.work = self.home / "work"

    def links(self, *urls):
        self.work.mkdir(parents=True, exist_ok=True)
        (self.work / "links.txt").write_text("\n".join(urls), encoding="utf-8")

    def recipes(self, *items):
        (self.work / "batch").mkdir(parents=True, exist_ok=True)
        (self.work / "batch" / "recipes.json").write_text(
            json.dumps(batch(*items)), encoding="utf-8"
        )


class Status(Base):
    def test_nothing_left_when_there_is_no_work_folder(self):
        self.assertEqual(status(self.home), {"leftover": False})

    def test_empty_folders_are_not_work(self):
        (self.work / "batch" / "photos").mkdir(parents=True)
        (self.work / ".DS_Store").write_text("")
        self.assertEqual(status(self.home), {"leftover": False})

    def test_it_names_the_recipes_done_and_the_links_still_to_do(self):
        self.links(TORTILLA, GAZPACHO, PAELLA)
        self.recipes(recipe("Tortilla", url="https://www.youtube.com/watch?v=AAAAAAAAAAA"))
        result = status(self.home)
        self.assertTrue(result["leftover"])
        self.assertEqual(result["recipes"], ["Tortilla"])
        self.assertEqual([link["url"] for link in result["pending"]], [GAZPACHO, PAELLA])
        self.assertEqual(result["pending"][1]["kind"], "web")

    def test_a_link_already_in_the_record_is_not_to_do_again(self):
        self.links(TORTILLA, GAZPACHO)
        Record(self.home).add("recipe", [TORTILLA])
        self.assertEqual(
            [link["url"] for link in status(self.home)["pending"]], [GAZPACHO]
        )

    def test_a_recipes_file_cut_in_half_counts_as_no_recipes(self):
        self.links(TORTILLA)
        (self.work / "batch").mkdir(parents=True)
        (self.work / "batch" / "recipes.json").write_text('{"version": 1, "reci')
        result = status(self.home)
        self.assertEqual(result["recipes"], [])
        self.assertEqual([link["url"] for link in result["pending"]], [TORTILLA])

    def test_work_without_a_list_of_links_is_still_left_over(self):
        (self.work).mkdir()
        (self.work / "receta.json").write_text("{}")
        self.assertEqual(
            status(self.home), {"leftover": True, "recipes": [], "pending": []}
        )


class Clean(Base):
    def test_it_takes_the_work_and_leaves_the_record(self):
        self.links(TORTILLA)
        Record(self.home).add("recipe", [GAZPACHO])
        clean(self.home)
        self.assertFalse(self.work.exists())
        self.assertTrue((self.home / "converted.tsv").exists())

    def test_nothing_to_clean_is_fine(self):
        clean(self.home)


class Home(unittest.TestCase):
    def test_without_a_folder_it_uses_the_skills_home(self):
        home = tempfile.mkdtemp()
        with mock.patch.dict(os.environ, {"NEVERA_HOME": home}):
            self.assertEqual(status(), {"leftover": False})


if __name__ == "__main__":
    unittest.main()
