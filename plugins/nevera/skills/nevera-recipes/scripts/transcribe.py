#!/usr/bin/env python3
"""What is said in a video, as plain text.

    python3 transcribe.py pick META.json
    python3 transcribe.py subtitles SUBS.vtt OUT.txt
    <venv python> transcribe.py whisper AUDIO OUT.txt [--language es] [--model small]

`pick` reads the metadata yt-dlp gives (`yt-dlp -J`) and prints which
subtitles to download: `subs <lang>` (the creator's own), `auto <lang>`
(YouTube's automatic captions of the original audio) or `whisper <lang>`
when there are none (the language may be `auto`, unknown).

`subtitles` turns the .vtt that yt-dlp downloads into text, once per line
(YouTube's automatic captions repeat every line while the next one rolls
in). It runs with any Python 3.9+.

`whisper` transcribes with faster-whisper, so it has to run with the Python
of the venv (~/Nevera/.venv) that doctor.py sets up. The model is `small` by
default; `medium` is slower and hears better. The first run downloads the
model (about 480 MB for small) into the Hugging Face cache. Without
--language it detects it, and prints what it detected.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

_TIMING = re.compile(r"-->")
_TAG = re.compile(r"<[^>]+>")


def _base(language) -> str:
    return (language or "").split("-")[0].lower()


def pick_subtitles(meta: dict):
    """(track, "subs" | "auto") in the spoken language, or None for Whisper."""
    language = meta.get("language") or ""
    base = _base(language)
    subs = list((meta.get("subtitles") or {}).keys())
    auto = list((meta.get("automatic_captions") or {}).keys())
    if base:
        for track in [language] + sorted(subs):
            if track in subs and _base(track) == base:
                return (track, "subs")
        if f"{base}-orig" in auto:
            return (f"{base}-orig", "auto")
        if base in auto and not any(t.endswith("-orig") for t in auto):
            return (base, "auto")
        return None
    orig = [t for t in auto if t.endswith("-orig")]
    return (orig[0], "auto") if orig else None


def vtt_text(vtt: str) -> str:
    lines: list = []
    for block in re.split(r"\n\s*\n", vtt.replace("\r\n", "\n")):
        rows = block.split("\n")
        if not any(_TIMING.search(row) for row in rows):
            continue  # the header, a NOTE or a STYLE block
        after = rows[[i for i, row in enumerate(rows) if _TIMING.search(row)][0] + 1 :]
        for row in after:
            text = html.unescape(_TAG.sub("", row)).strip()
            text = re.sub(r"\s+", " ", text)
            # a rolling caption repeats the line just written
            if text and (not lines or lines[-1] != text):
                lines.append(text)
    # and the same line can come back two cues later, once complete
    out: list = []
    for line in lines:
        if line not in out[-2:]:
            out.append(line)
    return "\n".join(out)


def _samples(audio: str):
    """The audio as 16 kHz mono samples, decoded by ffmpeg. faster-whisper
    can decode it itself with PyAV, but PyAV 19 broke that (faster-whisper
    1.2.1 passes an argument PyAV no longer takes); ffmpeg is here anyway."""
    import subprocess

    import numpy

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", audio, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True,
        check=True,
    ).stdout
    return numpy.frombuffer(raw, numpy.int16).astype(numpy.float32) / 32768.0


def whisper(audio: str, out: str, language: str | None, model: str) -> None:
    from faster_whisper import WhisperModel  # only in the venv

    engine = WhisperModel(model, device="auto", compute_type="int8")
    if language == "auto":
        language = None
    segments, info = engine.transcribe(_samples(audio), language=language, vad_filter=True)
    text = "\n".join(segment.text.strip() for segment in segments)
    Path(out).write_text(text + "\n", encoding="utf-8")
    print(f"language: {info.language} ({info.language_probability:.2f}), {len(text)} characters")


def main(argv: list) -> int:
    if len(argv) == 2 and argv[0] == "pick":
        import json

        meta = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        picked = pick_subtitles(meta)
        if picked:
            print(f"{picked[1]} {picked[0]}")
        else:
            print(f"whisper {_base(meta.get('language')) or 'auto'}")
        return 0
    if len(argv) == 3 and argv[0] == "subtitles":
        text = vtt_text(Path(argv[1]).read_text(encoding="utf-8", errors="replace"))
        Path(argv[2]).write_text(text + "\n", encoding="utf-8")
        print(f"{len(text)} characters")
        return 0
    if len(argv) >= 3 and argv[0] == "whisper":
        options = dict(zip(argv[3::2], argv[4::2]))
        whisper(argv[1], argv[2], options.get("--language"), options.get("--model", "small"))
        return 0
    print(__doc__, file=sys.stderr if argv else sys.stdout)
    return 0 if not argv or argv[0] in ("-h", "--help") else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
