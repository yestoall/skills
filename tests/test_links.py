"""Link identity: the same rule as `linkIdentity` in Nevera
(src/recipes/video.ts). The cases are Nevera's own, so a link the skill has
converted is the same link Nevera crosses out of its inbox."""

import tempfile
import unittest
from pathlib import Path

from links import Record, link_identity, pending


class LinkIdentity(unittest.TestCase):
    def test_an_instagram_post_is_the_same_in_every_url_shape(self):
        urls = [
            "https://www.instagram.com/p/DdjCD3GIX49/",
            "https://www.instagram.com/reel/DdjCD3GIX49/?igsh=abc",
            "https://instagram.com/reels/DdjCD3GIX49",
            "https://www.instagram.com/veggie.rabbit/reel/DdjCD3GIX49/",
            "https://www.instagram.com/tv/DdjCD3GIX49/",
        ]
        self.assertEqual(
            {link_identity(u) for u in urls}, {"instagram:DdjCD3GIX49"}
        )

    def test_a_youtube_video_is_the_same_in_every_url_shape(self):
        urls = [
            "https://www.youtube.com/watch?v=LEqs_Crvark",
            "https://m.youtube.com/watch?list=PL1&v=LEqs_Crvark#t=30",
            "https://youtu.be/LEqs_Crvark?si=xyz",
            "https://www.youtube.com/shorts/LEqs_Crvark",
            "https://www.youtube.com/watch?feature=share&v=LEqs_Crvark&t=264s",
            "https://www.youtube.com/embed/LEqs_Crvark",
            "https://www.youtube.com/live/LEqs_Crvark",
        ]
        self.assertEqual(
            {link_identity(u) for u in urls}, {"youtube:LEqs_Crvark"}
        )

    def test_a_web_page_is_its_url_without_query_or_fragment(self):
        self.assertEqual(
            link_identity(
                "https://www.petitchef.es/recetas/espaguetis?utm_source=ig#comentarios"
            ),
            "https://www.petitchef.es/recetas/espaguetis",
        )
        self.assertEqual(
            link_identity(" https://walterlui.com "), "https://walterlui.com"
        )
        # the trailing slash and http/https are NOT normalised: Nevera keeps
        # them, and the three places must agree more than they must be clever
        self.assertNotEqual(
            link_identity("https://cocina.es/receta/"),
            link_identity("https://cocina.es/receta"),
        )

    def test_profiles_channels_and_non_urls_have_no_identity(self):
        for value in [
            "https://www.instagram.com/chefeggplantt/",
            "https://www.youtube.com/@canal",
            "https://youtube.com/channel/UC123",
            "tortilla de patatas",
            "cocina.es/receta",
            "https://localhost/receta",
            "https://cocina.es/una receta",
            "url://13",
            "",
            None,
        ]:
            with self.subTest(value=value):
                self.assertIsNone(link_identity(value))



class Pending(unittest.TestCase):
    """What the Chef hands over: links pasted in the chat or in a file, one
    per line or inside any text (Nevera's "Copy links" gives one per line;
    a share sheet gives a sentence with the URL inside)."""

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.record = Record(self.folder)

    def test_every_recognised_link_once_in_the_order_it_came(self):
        text = "\n".join(
            [
                "https://youtu.be/LEqs_Crvark?si=xyz",
                "Look at this one (https://www.youtube.com/watch?v=n37W99UJDqc).",
                "https://www.youtube.com/shorts/LEqs_Crvark",
                "  https://www.petitchef.es/recetas/espaguetis?utm_source=ig  ",
                "tortilla de patatas",
            ]
        )
        result = pending(text, self.record)
        self.assertEqual(
            [(link["url"], link["identity"]) for link in result["pending"]],
            [
                ("https://youtu.be/LEqs_Crvark?si=xyz", "youtube:LEqs_Crvark"),
                (
                    "https://www.youtube.com/watch?v=n37W99UJDqc",
                    "youtube:n37W99UJDqc",
                ),
                (
                    "https://www.petitchef.es/recetas/espaguetis?utm_source=ig",
                    "https://www.petitchef.es/recetas/espaguetis",
                ),
            ],
        )
        self.assertEqual(result["done"], [])
        self.assertEqual(result["unrecognized"], [])

    def test_an_instagram_post_or_reel_is_one_link_shared_any_way(self):
        # a reel shared from the app brings ?igsh= (who shared it); the same
        # post opened in a browser is /p/; both are one link to do
        result = pending(
            "https://www.instagram.com/reel/DdHvVqBoycU/?igsh=MWQ1ZGUxMzBkMA==\n"
            "https://www.instagram.com/p/DdHvVqBoycU/\n"
            "https://www.instagram.com/p/Ddlnn97ttK1",
            self.record,
        )
        self.assertEqual(
            [(link["kind"], link["identity"], link["slug"]) for link in result["pending"]],
            [
                ("instagram", "instagram:DdHvVqBoycU", "instagram-DdHvVqBoycU"),
                ("instagram", "instagram:Ddlnn97ttK1", "instagram-Ddlnn97ttK1"),
            ],
        )

    def test_a_url_that_is_not_a_video_or_a_page_is_reported_not_dropped(self):
        result = pending(
            "https://www.instagram.com/chefeggplantt/\nhttps://www.youtube.com/@canal",
            self.record,
        )
        self.assertEqual(result["pending"], [])
        self.assertEqual(
            result["unrecognized"],
            [
                "https://www.instagram.com/chefeggplantt/",
                "https://www.youtube.com/@canal",
            ],
        )

    def test_a_link_already_converted_is_not_done_again_in_any_url_shape(self):
        self.record.add("recipe", ["https://www.youtube.com/watch?v=LEqs_Crvark"])
        self.record.add("no-recipe", ["https://cocina.es/receta?id=3"])
        result = pending(
            "https://youtu.be/LEqs_Crvark?si=abc\n"
            "https://cocina.es/receta#pasos\n"
            "https://youtu.be/n37W99UJDqc",
            self.record,
        )
        self.assertEqual(
            [link["identity"] for link in result["pending"]],
            ["youtube:n37W99UJDqc"],
        )
        self.assertEqual(
            [(link["identity"], link["status"]) for link in result["done"]],
            [
                ("youtube:LEqs_Crvark", "recipe"),
                ("https://cocina.es/receta", "no-recipe"),
            ],
        )

    def test_each_link_brings_a_name_safe_for_its_folder_and_its_photo(self):
        result = pending(
            "https://youtu.be/LEqs_Crvark?si=xyz\n"
            "https://www.petitchef.es/recetas/espaguetis-al-limón?x=1",
            self.record,
        )
        self.assertEqual(
            [link["slug"] for link in result["pending"]],
            ["youtube-LEqs_Crvark", "www-petitchef-es-recetas-espaguetis-al-lim-n"],
        )


class TheRecord(unittest.TestCase):
    def test_it_survives_between_runs_in_a_plain_tsv(self):
        folder = Path(tempfile.mkdtemp()) / "Nevera"
        Record(folder).add(
            "recipe",
            ["https://youtu.be/LEqs_Crvark", "https://www.petitchef.es/a?b=1"],
        )
        entries = Record(folder).load()
        self.assertEqual(
            sorted(entries), ["https://www.petitchef.es/a", "youtube:LEqs_Crvark"]
        )
        line = (folder / "converted.tsv").read_text().splitlines()[0]
        identity, date, status, url = line.split("\t")
        self.assertEqual(
            (identity, status, url),
            ("youtube:LEqs_Crvark", "recipe", "https://youtu.be/LEqs_Crvark"),
        )
        self.assertRegex(date, r"^\d{4}-\d{2}-\d{2}$")

    def test_recording_a_link_again_keeps_one_line_with_the_last_status(self):
        folder = Path(tempfile.mkdtemp())
        Record(folder).add("no-recipe", ["https://youtu.be/LEqs_Crvark"])
        Record(folder).add("recipe", ["https://www.youtube.com/watch?v=LEqs_Crvark"])
        self.assertEqual(
            {k: v["status"] for k, v in Record(folder).load().items()},
            {"youtube:LEqs_Crvark": "recipe"},
        )
        self.assertEqual(
            len((folder / "converted.tsv").read_text().splitlines()), 1
        )

    def test_a_link_without_identity_or_an_unknown_status_is_refused(self):
        record = Record(Path(tempfile.mkdtemp()))
        with self.assertRaises(ValueError):
            record.add("recipe", ["https://www.youtube.com/@canal"])
        with self.assertRaises(ValueError):
            record.add("maybe", ["https://youtu.be/LEqs_Crvark"])


if __name__ == "__main__":
    unittest.main()
