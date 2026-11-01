"""The batch validator: what Nevera reads (src/utils/recipeBatch.ts), checked
before the batch reaches the Chef. Errors are what would make Nevera refuse
the batch, drop a recipe or lose a photo; warnings are what Nevera fixes on
its own or ignores."""

import unittest

from tests.helpers import batch, jpeg, make_zip, png, recipe
from batch import validate


class AGoodBatch(unittest.TestCase):
    def test_a_zip_with_recipes_and_their_photos_passes(self):
        report = validate(
            make_zip(
                {
                    "recipes.json": batch(
                        recipe(photo="tortilla.jpg"),
                        recipe("Gazpacho", photo="photos/gazpacho.png"),
                    ),
                    "photos/tortilla.jpg": jpeg(1080, 1080),
                    "photos/gazpacho.png": png(1080, 1080),
                }
            )
        )
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])
        self.assertEqual((report.recipes, report.photos), (2, 2))

    def test_a_recipe_without_a_photo_is_fine_but_said(self):
        report = validate(make_zip({"recipes.json": batch(recipe())}))
        self.assertEqual(report.errors, [])
        self.assertEqual(report.photos, 0)
        self.assertEqual(len(report.warnings), 1)
        self.assertIn("no photo", report.warnings[0])


class NotABatch(unittest.TestCase):
    def test_bytes_that_are_neither_a_zip_nor_json(self):
        self.assertEqual(len(validate(b"\x00\x01garbage").errors), 1)

    def test_a_zip_without_recipes_json(self):
        report = validate(make_zip({"notes.txt": "hola"}))
        self.assertIn("recipes.json", report.errors[0])

    def test_the_chef_backup_is_not_a_batch(self):
        report = validate(make_zip({"backup.json": "{}"}))
        self.assertIn("backup", report.errors[0])

    def test_recipes_json_must_be_strict_json(self):
        # Nevera would repair it; a tool that writes batches should not rely on that
        report = validate(make_zip({"recipes.json": "{'version': 1, recipes: []"}))
        self.assertIn("not valid JSON", report.errors[0])

    def test_the_v1_shape_with_at_least_one_recipe(self):
        self.assertIn(
            "version", validate(make_zip({"recipes.json": batch(recipe(), version=2)})).errors[0]
        )
        self.assertIn(
            "no recipes", validate(make_zip({"recipes.json": batch()})).errors[0]
        )


class EachRecipe(unittest.TestCase):
    def errors_for(self, *recipes):
        return validate(make_zip({"recipes.json": batch(*recipes)})).errors

    def test_what_makes_nevera_drop_a_recipe_is_an_error_naming_it(self):
        cases = {
            "missing name": recipe(name="  "),
            "no ingredients": recipe(ingredients=[]),
            "null": recipe(url=None),
            "ingredient": recipe(ingredients=[{"name": "Sal"}]),
            "preparationSteps": recipe(preparationSteps="Fríe todo."),
            "not an object": "Tortilla",
        }
        for expected, bad in cases.items():
            with self.subTest(expected):
                errors = self.errors_for(recipe("Buena"), bad)
                self.assertEqual(len(errors), 1)
                self.assertIn("recipe 2", errors[0])
                self.assertIn(expected, errors[0])

    def test_the_old_snake_case_dialect_is_read_but_warned(self):
        old = recipe()
        old["steps"] = old.pop("preparationSteps")
        old["preparation_time"] = old.pop("preparationTime")
        report = validate(make_zip({"recipes.json": batch(old)}))
        self.assertEqual(report.errors, [])
        self.assertTrue(any("preparationSteps" in w for w in report.warnings))

    def test_an_unknown_field_is_a_warning(self):
        report = validate(make_zip({"recipes.json": batch(recipe(calories="300"))}))
        self.assertEqual(report.errors, [])
        self.assertTrue(any("calories" in w for w in report.warnings))


class Photos(unittest.TestCase):
    def test_a_named_photo_that_is_missing_or_not_an_image_is_an_error(self):
        report = validate(
            make_zip(
                {
                    "recipes.json": batch(
                        recipe(photo="tortilla.jpg"),
                        recipe("Gazpacho", photo="gazpacho.jpg"),
                    ),
                    "photos/gazpacho.jpg": "not a jpeg",
                }
            )
        )
        self.assertEqual(len(report.errors), 2)
        self.assertIn("tortilla.jpg", report.errors[0])
        self.assertIn("gazpacho.jpg", report.errors[1])

    def test_a_spare_photo_or_one_nevera_has_to_crop_is_a_warning(self):
        report = validate(
            make_zip(
                {
                    "recipes.json": batch(recipe(photo="tortilla.jpg")),
                    "photos/tortilla.jpg": jpeg(1920, 1080),
                    "photos/spare.jpg": jpeg(100, 100),
                }
            )
        )
        self.assertEqual(report.errors, [])
        self.assertTrue(any("spare.jpg" in w for w in report.warnings))
        self.assertTrue(any("1920x1080" in w for w in report.warnings))

    def test_a_zipped_folder_from_finder_is_read_like_nevera_does(self):
        report = validate(
            make_zip(
                {
                    "__MACOSX/lote/._recipes.json": "Finder junk",
                    "lote/recipes.json": batch(recipe(photo="tortilla.jpg")),
                    "lote/photos/tortilla.jpg": jpeg(1080, 1080),
                }
            )
        )
        self.assertEqual(report.errors, [])
        self.assertEqual(report.photos, 1)


class AJsonBatch(unittest.TestCase):
    def test_a_json_file_is_a_batch_without_photos(self):
        import json

        report = validate(json.dumps(batch(recipe(), recipe("Gazpacho"))).encode())
        self.assertEqual(report.errors, [])
        self.assertEqual(report.recipes, 2)

    def test_a_bare_list_or_a_single_recipe_is_read_but_warned(self):
        import json

        for shape in ([recipe()], recipe()):
            with self.subTest(type(shape).__name__):
                report = validate(json.dumps(shape).encode())
                self.assertEqual(report.errors, [])
                self.assertTrue(any("version" in w for w in report.warnings))


if __name__ == "__main__":
    unittest.main()
