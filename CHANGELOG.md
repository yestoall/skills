# Changelog

Each version is a git tag. The plugin's version lives in its `plugin.json`;
the batch format has a version of its own (`"version": 1` in
`recipes.json`).

## 0.2.2 · 2026-11-01

- Linux: `doctor.py` runs `apt-get update` before installing, and always
  asks for `python3-venv` when it has to create `~/Nevera/.venv`. On a fresh
  Debian there are no package lists yet, and its `python3` has no `venv`
  module without that package. Found by the Docker check, which now passes
  on Debian 12.

## 0.2.1 · 2026-11-01

- The report says how to open the batch on an iPhone as it works today: in
  the Files app, **Share** → Nevera. AirDrop does not ask which app opens a
  file (since iOS 17 it goes to Downloads), and on recent iOS versions
  Nevera is not in **Open With**.
- Every command in `SKILL.md` names the script by its full path and calls
  yt-dlp, ffmpeg and ffprobe by the paths `doctor.py` gives, with
  `yt_dlp_args`.
- `scripts/lote.py` is now `scripts/batch.py`. The `.zip` keeps its name,
  `nevera-lote-YYYY-MM-DD.zip`.
- `scripts/machine.py` holds what `doctor.py`, `links.py` and
  `instagram.py` each had a copy of: the system and `~/Nevera`.
- A test checks that `plugin.json`, `marketplace.json`, this changelog and
  the README say the same version.

## 0.2.0 · 2026-11-01

- Instagram reels and posts (`/p/`, `/reel/`, with or without `?igsh=`):
  the post's text, the reel transcribed with Whisper, and a frame of the
  dish. A post with only photos gives its text and its own image.
- It first gets what anyone can see. Posts that need a session wait for one
  question per batch: whether to use the Instagram session of a browser on
  the computer, and which. `yt-dlp` reads its cookies in memory with
  `--cookies-from-browser`; they are never written to a file, and
  `scripts/instagram.py` refuses `--cookies`. A no sends those posts to the
  report, and the next batch tries them again.
- Every Instagram failure has its reason in the report (a deleted or hidden
  post, a private account, an age or region limit, a rate limit, a yt-dlp
  too old for Instagram) and never stops the batch.
- The recipe's `url` is the post without its share tracking; its identity
  is the same as in Nevera.
- The batch format does not change: still `"version": 1`.
- Tested on macOS with public posts only, without cookies. The session path
  is covered by tests, not yet run against a real browser.

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
