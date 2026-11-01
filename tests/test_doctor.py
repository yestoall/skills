"""What the skill installs the first time, per system: the steps come from
what is already there, so a ready machine gets no steps at all."""

import unittest

import datetime

from doctor import (
    is_old,
    pick_python,
    plan,
    update_command,
    version_age,
    whisper_plan,
)

ALL = {"yt-dlp": "/x/yt-dlp", "ffmpeg": "/x/ffmpeg", "ffprobe": "/x/ffprobe", "deno": "/x/deno"}
VENV = "~/Downloads/nevera/.venv"


def steps(system, tools=ALL, python="/x/python3.12", **kw):
    return plan(system, dict(tools), python, venv=VENV, **kw)


class Plan(unittest.TestCase):
    def test_a_ready_machine_has_nothing_to_do(self):
        for system in ("macos", "windows", "linux"):
            with self.subTest(system):
                self.assertEqual(steps(system), [])

    def test_whisper_is_not_part_of_being_ready(self):
        # most links never need it, and it weighs 480 MB
        for system in ("macos", "windows", "linux"):
            with self.subTest(system):
                joined = " ".join(steps(system, tools={}, python=None))
                self.assertNotIn("faster-whisper", joined)

    def test_macos_installs_with_brew(self):
        self.assertEqual(
            steps("macos", tools={"deno": None}, python=None),
            ["brew install yt-dlp", "brew install ffmpeg"],
        )

    def test_macos_without_brew_asks_the_chef_to_install_it_first(self):
        self.assertIn("https://brew.sh", steps("macos", tools={}, has_brew=False)[0])

    def test_windows_installs_with_winget(self):
        self.assertEqual(
            steps("windows", tools={}, python=None),
            [
                "winget install --id yt-dlp.yt-dlp -e",
                "winget install --id Gyan.FFmpeg -e",
                "winget install --id DenoLand.Deno -e",
            ],
        )

    def test_linux_takes_ffmpeg_from_apt_and_a_fresh_yt_dlp_into_the_venv(self):
        # apt's yt-dlp falls behind YouTube within weeks
        self.assertEqual(
            steps("linux", tools={"node": "/usr/bin/node"}, python="/usr/bin/python3"),
            [
                # a fresh Debian has no package lists, and its python3 lacks
                # the venv module until python3-venv is in (seen in Docker)
                "sudo apt-get update && sudo apt-get install -y ffmpeg python3-venv",
                "/usr/bin/python3 -m venv ~/Downloads/nevera/.venv",
                '~/Downloads/nevera/.venv/bin/python -m pip install "yt-dlp[default]"',
            ],
        )

    def test_node_is_enough_as_the_javascript_runtime_youtube_needs(self):
        tools = {"yt-dlp": "/x", "ffmpeg": "/x", "ffprobe": "/x", "node": "/x/node"}
        self.assertEqual(steps("macos", tools=tools), [])


class WhisperPlan(unittest.TestCase):
    def test_macos_brings_a_python_when_it_has_none_it_can_use(self):
        self.assertEqual(
            whisper_plan("macos", None, VENV),
            [
                "brew install python@3.12",
                "python3.12 -m venv ~/Downloads/nevera/.venv",
                "~/Downloads/nevera/.venv/bin/python -m pip install faster-whisper",
            ],
        )

    def test_windows_brings_a_python_too(self):
        self.assertEqual(
            whisper_plan("windows", None, VENV),
            [
                "winget install --id Python.Python.3.12 -e",
                "py -3.12 -m venv ~/Downloads/nevera/.venv",
                "~/Downloads/nevera/.venv/Scripts/python -m pip install faster-whisper",
            ],
        )

    def test_linux_needs_the_venv_module_first(self):
        self.assertEqual(
            whisper_plan("linux", "/usr/bin/python3", VENV),
            [
                "sudo apt-get update && sudo apt-get install -y python3-venv",
                "/usr/bin/python3 -m venv ~/Downloads/nevera/.venv",
                "~/Downloads/nevera/.venv/bin/python -m pip install faster-whisper",
            ],
        )

    def test_a_venv_that_is_already_there_only_needs_the_package(self):
        # on Linux, yt-dlp may have created it
        for system in ("macos", "linux"):
            with self.subTest(system):
                self.assertEqual(
                    whisper_plan(system, None, VENV, venv_exists=True),
                    ["~/Downloads/nevera/.venv/bin/python -m pip install faster-whisper"],
                )


class OldYtDlp(unittest.TestCase):
    TODAY = datetime.date(2026, 11, 1)

    def test_its_version_is_the_day_it_came_out(self):
        self.assertEqual(version_age("2026.10.22", self.TODAY), 10)
        self.assertEqual(version_age("2026.10.22.233100", self.TODAY), 10)

    def test_a_version_it_cannot_read_has_no_age(self):
        for version in ("", None, "unknown", "2026.13.45"):
            with self.subTest(version):
                self.assertIsNone(version_age(version, self.TODAY))

    def test_old_means_over_two_months(self):
        self.assertFalse(is_old(60))
        self.assertTrue(is_old(61))
        self.assertFalse(is_old(None))

    def test_it_updates_the_way_it_was_installed(self):
        for system, path, command in (
            (
                "macos",
                "/opt/homebrew/Cellar/yt-dlp/2026.10.22/bin/yt-dlp",
                "brew upgrade yt-dlp",
            ),
            ("windows", "C:/winget/yt-dlp.exe", "winget upgrade --id yt-dlp.yt-dlp -e"),
            (
                "linux",
                "~/Downloads/nevera/.venv/bin/yt-dlp",
                '~/Downloads/nevera/.venv/bin/python -m pip install -U "yt-dlp[default]"',
            ),
            ("macos", "/usr/local/bin/yt-dlp", "/usr/local/bin/yt-dlp -U"),
            ("linux", "/home/ana/bin/yt-dlp", "/home/ana/bin/yt-dlp -U"),
        ):
            with self.subTest(path):
                self.assertEqual(update_command(system, path, VENV), command)

    def test_nothing_to_update_when_it_is_not_installed(self):
        self.assertIsNone(update_command("macos", None, VENV))


class PickPython(unittest.TestCase):
    def test_the_newest_python_faster_whisper_has_wheels_for(self):
        found = {(3, 15): "/b/python3.15", (3, 14): "/b/python3.14", (3, 8): "/b/python3.8"}
        self.assertEqual(pick_python(found), "/b/python3.14")
        self.assertIsNone(pick_python({(3, 15): "/b/python3.15"}))


if __name__ == "__main__":
    unittest.main()
