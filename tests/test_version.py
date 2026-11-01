"""The version is written in four places: the plugin's plugin.json (the one
Claude Code reads), its entry in the marketplace, the top of CHANGELOG.md
and the README. A release that bumps one and forgets another fails here."""

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


class Version(unittest.TestCase):
    def test_every_place_says_the_same_version(self):
        version = plugin_version()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertEqual(
            {
                "marketplace.json": marketplace_version(),
                "CHANGELOG.md": changelog_version(),
                "README.md": readme_version(),
            },
            dict.fromkeys(("marketplace.json", "CHANGELOG.md", "README.md"), version),
        )


if __name__ == "__main__":
    unittest.main()
