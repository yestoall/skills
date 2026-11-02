# Changelog

Each version is a git tag. The plugin's version lives in its `plugin.json`;
the batch format has a version of its own (`"version": 1` in
`recipes.json`).

## 0.9.0 · 2026-11-02

- TikTok videos, in their long URLs and in the short ones the app shares
  (`vm.tiktok.com`, `vt.tiktok.com`, `tiktok.com/t`). `links.py pending` gives them
  the `tiktok` kind; a profile stays unrecognized.
- A short link is a link of its own: it doesn't carry the video's id, and getting
  it would take the network. The recipe keeps the link as the user gave it, so
  Nevera crosses it off. The same video pasted short and long counts as two links.
- Whisper transcribes the video, not TikTok's `audio` format, which can be only
  the song that plays over it.
- A photo post (`/photo/`) goes to the report: yt-dlp doesn't read them.
- The last question, how to send the batch, comes as your AI's menu when it has
  one, instead of as text.

## 0.8.0 · 2026-11-02

- AirDrop comes first on a Mac, and you only choose your phone: `deliver.py
  airdrop` opens the AirDrop window with the batch and waits for you. It prints
  `sent` when the Mac reports the send as done.
- The window comes from `scripts/airdrop.swift`, run with `swift`, so it needs
  Xcode or the Command Line Tools. Without them, or when the send doesn't finish,
  the file appears in the Finder as before, and the command prints `finder`.
- A script can start AirDrop after all: on macOS 27.2, AppKit offers it the
  sharing service that 0.3.0 says it doesn't.

## 0.7.0 · 2026-11-01

- The skill says when something needs updating, first thing and in a highlighted
  block: a newer version of itself, with the command for the way it was installed,
  and an old `yt-dlp`. `doctor.py` prints them in `updates`. To know about the
  skill, it reads one public file from GitHub and sends nothing; without an answer
  it says nothing. The block for the skill comes again at the end of the report.
- The READMEs explain how to update, with `npx skills` and as a plugin.

## 0.6.0 · 2026-11-01

- A batch cut short no longer leaks into the next one. `scripts/work.py status`
  says what an earlier batch left, and the user chooses to continue it or start
  over (`work.py clean`). Each recipe goes into `recipes.json` as soon as it is
  done, so continuing keeps it.
- Whisper installs only when a link needs it. `doctor.py` no longer counts it
  towards `ready`: its commands are apart, in `whisper_steps`, and most links
  never ask for them.
- An old `yt-dlp` gets updated. `doctor.py` prints `yt_dlp_version`, `yt_dlp_old`
  (over two months since its release) and `yt_dlp_update`, the command for the
  way it was installed. The skill runs it when yt-dlp is old, and once per batch
  when two links in a row fail for no reason of their own.

## 0.5.0 · 2026-11-01

- The skill works in Downloads and no longer creates `~/Nevera/`. The batches
  go straight into `~/Downloads`; the work folder, `converted.tsv` and the venv
  go into `~/Downloads/nevera/`. On a Linux in another language, Downloads is
  the folder `xdg-user-dir` names (`~/Descargas`). On a Mac, macOS asks once to
  let the terminal in.
- Nothing moves on its own: a `~/Nevera/` from an earlier version stays where
  it is, unused. To keep the record of converted links, move its
  `converted.tsv` to `~/Downloads/nevera/`. The venv doesn't survive a move:
  the skill installs it again.

## 0.4.0 · 2026-11-01

- The skill stops for a review before sending the batch: it lists the recipes
  and writes them to `review.md` (`batch.py preview`), to read and change in any
  text editor, or the user says what to fix. The batch is packed again over the
  same `.zip`.
- The links are recorded after the review, not when the batch is first packed,
  so a recipe dropped in the review can be asked for again.

## 0.3.1 · 2026-11-01

- AirDrop from a Mac goes through the Finder: `deliver.py airdrop` shows the
  file there, for Control-click → **Share** → **AirDrop**, and no longer opens
  the AirDrop window. On macOS 27, dragging the file onto that window started
  no send, even with the phone in sight, and sharing from the Finder worked
  the first time.
- Two READMEs: `README.md` in English and `README.es.md`, complete, in Spanish.
  A test fails if their sections or their version stop matching.

## 0.3.0 · 2026-11-01

- On a Mac, the skill asks how to send the batch to the phone when it's done.
  `scripts/deliver.py` copies it to a Nevera folder in iCloud Drive, or opens
  the AirDrop window and shows the file in the Finder, ready to drag. A script
  can't start AirDrop by itself: on macOS 27, AppKit offers no sharing service
  for a file from a script, a binary or a small app.

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
