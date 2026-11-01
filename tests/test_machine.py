"""Where the skill keeps its things and which system it runs on: one answer
for every script, so doctor, links and instagram never disagree."""

import os
import unittest
from pathlib import Path
from unittest import mock

from machine import nevera_home, this_system


class System(unittest.TestCase):
    def test_it_names_the_three_systems_the_skill_installs_on(self):
        for platform_name, system in (
            ("Darwin", "macos"),
            ("Windows", "windows"),
            ("Linux", "linux"),
        ):
            with self.subTest(platform_name):
                self.assertEqual(this_system(platform_name), system)

    def test_any_other_unix_counts_as_linux(self):
        self.assertEqual(this_system("FreeBSD"), "linux")


class Home(unittest.TestCase):
    def test_it_is_nevera_in_the_home_folder(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NEVERA_HOME", None)
            self.assertEqual(nevera_home(), Path.home() / "Nevera")

    def test_nevera_home_overrides_it(self):
        with mock.patch.dict(os.environ, {"NEVERA_HOME": "/tmp/elsewhere"}):
            self.assertEqual(nevera_home(), Path("/tmp/elsewhere"))


if __name__ == "__main__":
    unittest.main()
