"""What the skill installs the first time, per system: the steps come from
what is already there, so a ready machine gets no steps at all."""

import unittest

from doctor import pick_python, plan

ALL = {"yt-dlp": "/x/yt-dlp", "ffmpeg": "/x/ffmpeg", "ffprobe": "/x/ffprobe", "deno": "/x/deno"}
VENV = "~/Downloads/nevera/.venv"


def steps(system, tools=ALL, python="/x/python3.12", whisper=True, **kw):
    return plan(system, dict(tools), python, whisper, venv=VENV, **kw)


class Plan(unittest.TestCase):
    def test_a_ready_machine_has_nothing_to_do(self):
        for system in ("macos", "windows", "linux"):
            with self.subTest(system):
                self.assertEqual(steps(system, tools=dict(ALL, **{"yt-dlp": "/v/yt-dlp"})), [])

    def test_macos_installs_with_brew(self):
        self.assertEqual(
            steps("macos", tools={"deno": None}, python=None, whisper=False),
            [
                "brew install yt-dlp",
                "brew install ffmpeg",
                "brew install python@3.12",
                "python3.12 -m venv ~/Downloads/nevera/.venv",
                "~/Downloads/nevera/.venv/bin/python -m pip install faster-whisper",
            ],
        )

    def test_macos_without_brew_asks_the_chef_to_install_it_first(self):
        self.assertIn("https://brew.sh", steps("macos", tools={}, has_brew=False)[0])

    def test_windows_installs_with_winget(self):
        self.assertEqual(
            steps("windows", tools={}, python=None, whisper=False),
            [
                "winget install --id yt-dlp.yt-dlp -e",
                "winget install --id Gyan.FFmpeg -e",
                "winget install --id DenoLand.Deno -e",
                "winget install --id Python.Python.3.12 -e",
                "py -3.12 -m venv ~/Downloads/nevera/.venv",
                "~/Downloads/nevera/.venv/Scripts/python -m pip install faster-whisper",
            ],
        )

    def test_linux_takes_ffmpeg_from_apt_and_a_fresh_yt_dlp_into_the_venv(self):
        # apt's yt-dlp falls behind YouTube within weeks
        self.assertEqual(
            steps("linux", tools={"node": "/usr/bin/node"}, python="/usr/bin/python3", whisper=False),
            [
                # a fresh Debian has no package lists, and its python3 lacks
                # the venv module until python3-venv is in (seen in Docker)
                "sudo apt-get update && sudo apt-get install -y ffmpeg python3-venv",
                "/usr/bin/python3 -m venv ~/Downloads/nevera/.venv",
                '~/Downloads/nevera/.venv/bin/python -m pip install faster-whisper "yt-dlp[default]"',
            ],
        )

    def test_node_is_enough_as_the_javascript_runtime_youtube_needs(self):
        tools = {"yt-dlp": "/x", "ffmpeg": "/x", "ffprobe": "/x", "node": "/x/node"}
        self.assertEqual(steps("macos", tools=tools), [])


class PickPython(unittest.TestCase):
    def test_the_newest_python_faster_whisper_has_wheels_for(self):
        found = {(3, 15): "/b/python3.15", (3, 14): "/b/python3.14", (3, 8): "/b/python3.8"}
        self.assertEqual(pick_python(found), "/b/python3.14")
        self.assertIsNone(pick_python({(3, 15): "/b/python3.15"}))


if __name__ == "__main__":
    unittest.main()
