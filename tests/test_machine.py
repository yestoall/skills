"""Where the skill keeps its things and which system it runs on: one answer
for every script, so doctor, links and instagram never disagree."""

import os
import unittest
from pathlib import Path
from unittest import mock

from machine import (
    batches_folder,
    downloads_folder,
    nevera_home,
    open_image_command,
    this_system,
)


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


class Downloads(unittest.TestCase):
    def test_it_is_the_downloads_folder_on_a_mac_and_on_windows(self):
        for system in ("macos", "windows"):
            with self.subTest(system):
                self.assertEqual(downloads_folder(system), Path.home() / "Downloads")

    def test_a_linux_in_another_language_names_its_own(self):
        found = lambda: "/home/ana/Descargas"
        self.assertEqual(downloads_folder("linux", found), Path("/home/ana/Descargas"))

    def test_a_linux_that_names_none_gets_the_usual_one(self):
        # with nothing set, xdg-user-dir answers with the home folder itself
        for found in (lambda: None, lambda: str(Path.home())):
            self.assertEqual(downloads_folder("linux", found), Path.home() / "Downloads")


class Home(unittest.TestCase):
    def without_override(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("NEVERA_HOME", None)

    def test_the_skills_own_things_are_in_a_folder_inside_downloads(self):
        self.without_override()
        self.assertEqual(nevera_home(), downloads_folder() / "nevera")

    def test_the_batches_are_in_downloads_itself(self):
        self.without_override()
        self.assertEqual(batches_folder(), downloads_folder())

    def test_nevera_home_overrides_both(self):
        with mock.patch.dict(os.environ, {"NEVERA_HOME": "/tmp/elsewhere"}):
            self.assertEqual(nevera_home(), Path("/tmp/elsewhere"))
            self.assertEqual(batches_folder(), Path("/tmp/elsewhere"))


class OpenImageCommand(unittest.TestCase):
    def test_macos_and_linux_open_it_with_their_default_viewer(self):
        self.assertEqual(open_image_command("macos", "q.png"), ["open", "q.png"])
        self.assertEqual(open_image_command("linux", "q.png"), ["xdg-open", "q.png"])


if __name__ == "__main__":
    unittest.main()
