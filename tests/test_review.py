"""The file the user reads before the batch goes to the phone: every recipe in
plain text, to read and to change in any editor."""

import json
import tempfile
import unittest
from pathlib import Path

from batch import preview, render_review
from machine import open_command
from tests.helpers import batch, recipe


class Render(unittest.TestCase):
    def test_a_recipe_reads_as_text(self):
        text = render_review(
            {
                "recipes": [
                    {
                        "name": "Tortilla de patatas",
                        "author": "Cocina con Carmen",
                        "url": "https://youtu.be/x",
                        "preparationTime": "45 min",
                        "photo": "tortilla.jpg",
                        "ingredients": [
                            {"name": "Patatas", "quantity": "750 g"},
                            {"name": "Sal", "quantity": ""},
                        ],
                        "preparationSteps": ["Pela las patatas.", "Fríelas."],
                    }
                ]
            },
            "es",
        )
        self.assertEqual(
            text,
            "\n".join(
                [
                    "# Tortilla de patatas",
                    "",
                    "Cocina con Carmen · 45 min",
                    "https://youtu.be/x",
                    "",
                    "![Tortilla de patatas](photos/tortilla.jpg)",
                    "",
                    "## Ingredientes",
                    "",
                    "- Patatas: 750 g",
                    "- Sal",
                    "",
                    "## Pasos",
                    "",
                    "1. Pela las patatas.",
                    "2. Fríelas.",
                    "",
                ]
            ),
        )

    def test_the_types_go_on_their_own_line_joined_like_nevera_does(self):
        text = render_review(
            {
                "recipes": [
                    {
                        "name": "Bizcocho",
                        "category": "Postres",
                        "categories": ["postres", "Desayunos", "Arroces, pastas"],
                        "ingredients": [{"name": "Harina", "quantity": "200 g"}],
                    }
                ]
            }
        )
        self.assertIn("\nPostres · Desayunos · Arroces, pastas\n", text)

    def test_any_other_language_gets_the_english_headings(self):
        text = render_review(batch(recipe("Omelette")), "fr")
        self.assertIn("## Ingredients", text)
        self.assertIn("## Steps", text)

    def test_what_a_recipe_does_not_have_leaves_no_empty_lines_behind(self):
        text = render_review(
            {"recipes": [{"name": "Sopa", "ingredients": [], "preparationSteps": []}]},
            "en",
        )
        self.assertEqual(text, "# Sopa\n")

    def test_a_photo_named_with_its_folder_points_at_the_same_file(self):
        text = render_review(batch(recipe("Uno", photo="photos/uno.jpg")), "en")
        self.assertIn("![Uno](photos/uno.jpg)", text)

    def test_two_recipes_are_separated_by_a_rule(self):
        text = render_review(batch(recipe("Uno"), recipe("Dos")), "en")
        self.assertEqual(text.count("\n---\n"), 1)
        self.assertLess(text.index("# Uno"), text.index("# Dos"))


class Preview(unittest.TestCase):
    def test_it_writes_review_md_next_to_the_recipes(self):
        work = Path(tempfile.mkdtemp())
        (work / "recipes.json").write_text(
            json.dumps(batch(recipe("Gazpacho"))), encoding="utf-8"
        )
        path = preview(work, "es")
        self.assertEqual(path, work / "review.md")
        self.assertIn("# Gazpacho", path.read_text(encoding="utf-8"))


class OpenCommand(unittest.TestCase):
    def test_it_uses_each_systems_way_of_opening_a_text_file(self):
        self.assertEqual(open_command("macos", "/x/r.md"), ["open", "-t", "/x/r.md"])
        self.assertEqual(open_command("linux", "/x/r.md"), ["xdg-open", "/x/r.md"])
        self.assertEqual(
            open_command("windows", "C:/x/r.md"),
            ["cmd", "/c", "start", "", "C:/x/r.md"],
        )


if __name__ == "__main__":
    unittest.main()
