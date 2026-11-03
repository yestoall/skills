"""The contact sheet: which seconds it shows, and where each one lands, because
that is what the crop reads back."""

import unittest
from pathlib import Path
from unittest import mock

from frames import FramesError, cells_for, make_sheet, seconds_between


class Seconds(unittest.TestCase):
    def test_both_ends_are_included(self):
        self.assertEqual(seconds_between(40, 44, 2), [40, 42, 44])

    def test_a_step_that_overshoots_stops_before_the_end(self):
        self.assertEqual(seconds_between(0, 5, 2), [0, 2, 4])

    def test_fractions_do_not_drift(self):
        self.assertEqual(seconds_between(0, 0.3, 0.1), [0, 0.1, 0.2, 0.3])

    def test_too_many_frames_are_refused(self):
        with self.assertRaises(FramesError):
            seconds_between(0, 100, 1)

    def test_a_range_backwards_is_refused(self):
        with self.assertRaises(FramesError):
            seconds_between(10, 5, 1)


class Cells(unittest.TestCase):
    def test_rows_and_columns_count_from_one(self):
        self.assertEqual(
            cells_for([10, 20, 30], 2),
            [
                {"row": 1, "column": 1, "second": 10},
                {"row": 1, "column": 2, "second": 20},
                {"row": 2, "column": 1, "second": 30},
            ],
        )


class Sheet(unittest.TestCase):
    def fake_ffmpeg(self, missing=()):
        calls = []

        def run(command, **_):
            calls.append(command)
            second = float(command[command.index("-ss") + 1]) if "-ss" in command else None
            if second in missing:
                return mock.Mock(returncode=1, stderr="Nothing was written")
            if second is not None:
                Path(command[-1]).write_bytes(b"jpg")
            return mock.Mock(returncode=0, stderr="")

        return calls, run

    def test_each_frame_is_seeked_to_on_its_own(self):
        calls, run = self.fake_ffmpeg()
        with mock.patch("subprocess.run", run):
            make_sheet(Path("v.mp4"), Path("s.jpg"), "ffmpeg", [40, 42], 2, 320)
        seeks = [c[c.index("-ss") + 1] for c in calls if "-ss" in c]
        self.assertEqual(seeks, ["40", "42"])
        self.assertIn("tile=2x1", calls[-1])

    def test_a_second_past_the_end_gets_no_cell(self):
        _, run = self.fake_ffmpeg(missing=(42,))
        with mock.patch("subprocess.run", run):
            cells = make_sheet(Path("v.mp4"), Path("s.jpg"), "ffmpeg", [40, 42, 44], 3, 320)
        self.assertEqual([c["second"] for c in cells], [40, 44])

    def test_a_range_past_the_end_says_what_ffmpeg_said(self):
        _, run = self.fake_ffmpeg(missing=(40,))
        with mock.patch("subprocess.run", run):
            with self.assertRaisesRegex(FramesError, "Nothing was written"):
                make_sheet(Path("v.mp4"), Path("s.jpg"), "ffmpeg", [40], 3, 320)


if __name__ == "__main__":
    unittest.main()
