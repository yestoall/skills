"""A recipe web page: the schema.org Recipe in its JSON-LD when it has one,
the readable text when it does not (the same order /receta follows)."""

import unittest

from web import read_page

RECIPE = {
    "@type": "Recipe",
    "name": "Espaguetis al limón",
    "recipeIngredient": ["200 g de espaguetis", "1 limón"],
    "recipeInstructions": [{"@type": "HowToStep", "text": "Cuece la pasta."}],
    "image": ["https://cdn.example.com/small.jpg", "https://cdn.example.com/big.jpg"],
}


def page(*scripts, body="<p>Hola</p>", head=""):
    tags = "".join(
        f'<script type="application/ld+json">{s}</script>' for s in scripts
    )
    return f"<html><head>{head}{tags}</head><body>{body}</body></html>"


class ReadPage(unittest.TestCase):
    def test_the_recipe_in_the_json_ld(self):
        import json

        found = read_page(page(json.dumps(RECIPE)))
        self.assertEqual([r["name"] for r in found["recipes"]], ["Espaguetis al limón"])
        self.assertNotIn("text", found)

    def test_inside_a_graph_with_its_type_in_a_list_or_in_a_list_of_blocks(self):
        import json

        graph = {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "WebPage", "name": "Página"},
                dict(RECIPE, **{"@type": ["Recipe", "NewsArticle"]}),
            ],
        }
        self.assertEqual(len(read_page(page(json.dumps(graph)))["recipes"]), 1)
        listed = [{"@type": "Organization"}, RECIPE]
        self.assertEqual(len(read_page(page(json.dumps(listed)))["recipes"]), 1)

    def test_a_broken_block_does_not_hide_a_good_one(self):
        import json

        found = read_page(page("{ not json", json.dumps(RECIPE)))
        self.assertEqual(len(found["recipes"]), 1)

    def test_without_a_recipe_the_readable_text_and_never_the_scripts(self):
        found = read_page(
            page(
                body=(
                    "<nav>Menú Inicio</nav><script>var ad = 1</script>"
                    "<style>p{}</style><h1>Lentejas</h1><ul><li>300 g de lentejas</li></ul>"
                    "<footer>© Cocina</footer>"
                ),
                head="<title>Lentejas de la abuela</title>",
            )
        )
        self.assertEqual(found["recipes"], [])
        self.assertIn("Lentejas", found["text"])
        self.assertIn("300 g de lentejas", found["text"])
        for left_out in ("var ad", "p{}", "Menú Inicio", "© Cocina"):
            self.assertNotIn(left_out, found["text"])
        self.assertEqual(found["title"], "Lentejas de la abuela")

    def test_the_candidate_photos_the_recipe_images_then_og_image(self):
        import json

        found = read_page(
            page(
                json.dumps(RECIPE),
                head='<meta property="og:image" content="https://cdn.example.com/og.jpg">',
            )
        )
        self.assertEqual(
            found["images"],
            [
                "https://cdn.example.com/small.jpg",
                "https://cdn.example.com/big.jpg",
                "https://cdn.example.com/og.jpg",
            ],
        )


if __name__ == "__main__":
    unittest.main()
