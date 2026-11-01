"""The version is written in five places: the plugin's plugin.json (the one
Claude Code reads), its entry in the marketplace, the top of CHANGELOG.md
and the two READMEs. A release that bumps one and forgets another fails here,
and so does a README that loses a section the other one has."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def plugin_version() -> str:
    path = ROOT / "plugins" / "nevera" / ".claude-plugin" / "plugin.json"
    return json.loads(path.read_text(encoding="utf-8"))["version"]


def marketplace_version() -> str:
    path = ROOT / ".claude-plugin" / "marketplace.json"
    plugins = json.loads(path.read_text(encoding="utf-8"))["plugins"]
    return next(p for p in plugins if p["name"] == "nevera")["version"]


def changelog_version() -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return re.search(r"^## (\d+\.\d+\.\d+)\b", text, re.M).group(1)


def readme_version() -> str:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    return re.search(r"^Version (\d+\.\d+\.\d+)$", text, re.M).group(1)


def spanish_readme_version() -> str:
    text = (ROOT / "README.es.md").read_text(encoding="utf-8")
    return re.search(r"^Versión (\d+\.\d+\.\d+)$", text, re.M).group(1)


def heading_levels(name: str) -> list:
    text = (ROOT / name).read_text(encoding="utf-8")
    text = re.sub(r"^```.*?^```$", "", text, flags=re.M | re.S)
    return re.findall(r"^(#+) ", text, re.M)


class Version(unittest.TestCase):
    def test_every_place_says_the_same_version(self):
        version = plugin_version()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertEqual(
            {
                "marketplace.json": marketplace_version(),
                "CHANGELOG.md": changelog_version(),
                "README.md": readme_version(),
                "README.es.md": spanish_readme_version(),
            },
            dict.fromkeys(
                ("marketplace.json", "CHANGELOG.md", "README.md", "README.es.md"),
                version,
            ),
        )


class Readmes(unittest.TestCase):
    def test_both_have_the_same_sections(self):
        self.assertEqual(heading_levels("README.es.md"), heading_levels("README.md"))


if __name__ == "__main__":
    unittest.main()
