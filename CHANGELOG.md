# Changelog

Each version is a git tag. The plugin's version lives in its `plugin.json`;
the batch format has a version of its own (`"version": 1` in
`recipes.json`).

## 0.1.0 · 2026-11-01

First version, with one plugin, `nevera`, and its skill, `nevera-recipes`.

- Turns YouTube videos and recipe web pages into a Nevera batch: a `.zip`
  with `recipes.json` (format version 1) and one photo per recipe.
- Subtitles when the video has them; Whisper (`faster-whisper`, model
  `small`) when it doesn't. Pages: their schema.org Recipe, or their text.
- The photo is a frame of the finished dish, cropped square, or the page's
  own photo.
- Installs `yt-dlp`, `ffmpeg` and Whisper the first time, with Homebrew,
  winget or apt; Whisper in its own venv at `~/Nevera/.venv`.
- Keeps a record of converted links in `~/Nevera/converted.tsv`, with the
  same link identity as Nevera, and skips them next time.
- `scripts/lote.py validate` checks any batch against the format.
- Tested on macOS. Linux and Windows not tested yet.
