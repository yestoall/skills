#!/usr/bin/env python3
"""A contact sheet of a video that says which second each cell shows.

    python3 frames.py video.mp4 sheet.jpg --ffmpeg <ffmpeg> --from 40 --to 52 --step 2

It prints JSON: `cells`, one per frame with its `row`, `column` and `second`,
and the `width` of each frame on the sheet. Every frame is seeked to
on its own, so the second it reports is the second to pass to ffmpeg's `-ss`
when cropping. ffmpeg's `fps` filter rounds, and a cell read off a sheet made
with it can be seconds away from the moment it seems to show.

Standard library only: it runs with any Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

MAX_FRAMES = 48


class FramesError(Exception):
    pass


def seconds_between(start: float, end: float, step: float) -> List[float]:
    """The seconds to show, from `start` up to `end`, both included."""
    if step <= 0:
        raise FramesError("--step has to be more than 0")
    if end < start:
        raise FramesError("--to has to come after --from")
    count = int(math.floor((end - start) / step + 1e-9)) + 1
    if count > MAX_FRAMES:
        raise FramesError(
            f"That is {count} frames: use a bigger --step, {MAX_FRAMES} at most"
        )
    return [round(start + step * i, 3) for i in range(count)]


def cells_for(seconds: List[float], columns: int) -> List[Dict[str, float]]:
    """Where each second lands on the sheet, counting rows and columns from 1."""
    return [
        {
            "row": index // columns + 1,
            "column": index % columns + 1,
            "second": second,
        }
        for index, second in enumerate(seconds)
    ]


def _run(command: List[str]) -> str:
    """What ffmpeg complained about, or nothing if it went well."""
    done = subprocess.run(command, capture_output=True, text=True)
    return "" if done.returncode == 0 else done.stderr.strip() or "ffmpeg failed"


def make_sheet(
    video: Path,
    sheet: Path,
    ffmpeg: str,
    seconds: List[float],
    columns: int,
    width: int,
) -> List[Dict[str, float]]:
    """Writes the sheet and returns its cells. A second past the end of the
    video gives no frame, so it gets no cell. ffmpeg may fail on it or not,
    depending on the version: what counts is whether the frame is there."""
    with tempfile.TemporaryDirectory() as folder:
        taken = []
        complaint = ""
        for second in seconds:
            frame = Path(folder) / f"{len(taken):03d}.jpg"
            complaint = _run(
                [
                    ffmpeg,
                    "-v",
                    "error",
                    "-ss",
                    str(second),
                    "-i",
                    str(video),
                    "-frames:v",
                    "1",
                    "-vf",
                    # full range: the JPEG encoder refuses limited range from some videos
                    f"scale={width}:-2,format=yuvj420p",
                    str(frame),
                ]
            )
            if frame.is_file():
                taken.append(second)
        if not taken:
            raise FramesError(complaint or f"{video} has no frames in that range")
        rows = math.ceil(len(taken) / columns)
        complaint = _run(
            [
                ffmpeg,
                "-v",
                "error",
                "-y",
                "-i",
                str(Path(folder) / "%03d.jpg"),
                "-vf",
                f"tile={columns}x{rows}",
                "-frames:v",
                "1",
                str(sheet),
            ]
        )
        if complaint:
            raise FramesError(complaint)
    return cells_for(taken, columns)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("video", type=Path)
    parser.add_argument("sheet", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--from", dest="start", type=float, default=0.0)
    parser.add_argument("--to", dest="end", type=float, required=True)
    parser.add_argument("--step", type=float, default=1.0)
    parser.add_argument("--columns", type=int, default=6)
    parser.add_argument("--width", type=int, default=320)
    args = parser.parse_args(argv)
    try:
        seconds = seconds_between(args.start, args.end, args.step)
        cells = make_sheet(
            args.video, args.sheet, args.ffmpeg, seconds, args.columns, args.width
        )
    except FramesError as error:
        print(error, file=sys.stderr)
        return 1
    print(json.dumps({"sheet": str(args.sheet), "width": args.width, "cells": cells}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
