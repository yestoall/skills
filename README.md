# yestoall skills

Skills for the AI on your computer, made for the yestoall apps. One plugin
per app; for now, [Nevera](https://www.yestoall.com/nevera).

[Léelo en español](README.es.md)

Version 0.8.0

## nevera-recipes

Give your AI a list of cooking videos and recipe pages, and get back one
`.zip` you open with Nevera on your phone: every recipe with its ingredients,
its steps and a photo of the finished dish.

- **YouTube videos**: the recipe comes from the description and from what is
  said in the video. It uses the video's subtitles when there are any, and
  transcribes the audio with Whisper, on your computer, when there aren't.
- **Instagram reels and posts**: the recipe comes from the post's text and
  from what is said in the reel, transcribed with Whisper.
- **Recipe web pages**: the recipe the page carries for search engines, or
  its text.
- **A photo per recipe**: a frame of the finished dish, cropped square,
  without titles or watermarks. From a page, its own photo.
- **Links you already converted are skipped**: the skill keeps a record in
  `~/Downloads/nevera/`, so you can give it the same list twice.
- **What failed, and why**: a private video, a page that doesn't answer, a
  link without a recipe. One link never stops the rest.
- **A batch cut short isn't lost**: next time, it tells you what it left and
  asks whether to continue it or start over.
- **You review before sending**: it lists the recipes and writes them to a text
  file you can read and change in any editor, or just tell your AI what to fix.

### Instagram and your browser

Instagram shows some posts only to signed-in accounts. The skill first gets
what anyone can see. If a post needs a session, it asks you once for the
whole batch: you choose whether it can use the Instagram session of a
browser on your computer, and which one. `yt-dlp` reads that browser's
cookies in memory, for those downloads only. They're never saved to a file
and never leave your computer, and your password isn't needed. Say no, and
those posts go to the report; the next batch tries them again.

On a Mac, reading Safari's cookies needs Full Disk Access for your terminal,
and Chrome, Brave and Edge ask once for their Keychain entry.

### Install

With any AI that reads skills (Claude Code, Codex, Antigravity CLI), using
Node 22 or later:

```bash
npx skills add yestoall/skills --skill nevera-recipes
```

In Claude Code, you can also add this repository as a plugin marketplace:

```text
/plugin marketplace add yestoall/skills
/plugin install nevera@yestoall
```

### Update

Update the same way you installed it:

```bash
# with npx skills
npx skills update nevera-recipes

# as a Claude Code plugin; then start a new session
claude plugin marketplace update yestoall && claude plugin update nevera@yestoall
```

You don't need to keep track of it. Each time you use it, the skill reads one
public file from GitHub to see if there's a newer version, and sends nothing. If
there is, it tells you first thing, in a highlighted block with the command, and
goes on with the version you have. It tells you the same about an old `yt-dlp`,
which it updates for you.

### Use

Ask your AI in your own words, and paste the links or name a file with them:

> Make me a Nevera batch with these: https://youtu.be/… https://www.…

The first time, the skill installs what it needs and tells you before it
does: `yt-dlp` (downloads) and `ffmpeg` (the photos). Whisper (`faster-whisper`,
about 480 MB with its model) only goes in when a video has no subtitles, in a
folder of its own, `~/Downloads/nevera/.venv`. It uses Homebrew on a Mac, winget
on Windows, and apt on Linux. On a Mac, macOS asks once to let your terminal into
Downloads. If `yt-dlp` falls behind YouTube, the skill updates it, and tells you
first.

Keep `~/Downloads/nevera/` when you clean up your Downloads: without it, the
skill installs Whisper again and no longer knows which links it converted.

When it's done, it gives you the path of the batch,
`~/Downloads/nevera-lote-YYYY-MM-DD.zip`. On a Mac, it asks how you want to send
it to your phone: it opens AirDrop with the file so you only choose your phone,
or it copies it to iCloud Drive for you. AirDrop needs Xcode or the Command Line
Tools. Without them, the skill shows you the file in the Finder, where you
Control-click it and choose **Share** → **AirDrop**. From anywhere else, use
Quick Share, iCloud Drive, Google Drive or a cable.
Then open it:

- **On an iPhone**, in the Files app (AirDrop leaves it in Downloads), touch
  and hold the file and tap **Share** → Nevera.
- **On Android**, open it from Files or Downloads and choose Nevera.
- **On either**, in Nevera, tap **Choose file** on the import screen.

Nevera shows you every recipe before saving any.

### Works on

| System | Status |
| --- | --- |
| macOS | Tested |
| Linux (Debian, Ubuntu) | Tested on Debian 12 in Docker: `docker build -t yestoall-skills-test . && docker run --rm yestoall-skills-test` runs the check |
| Windows | Not tested yet |

On Windows, the skill installs with `winget install --id yt-dlp.yt-dlp -e`,
`winget install --id Gyan.FFmpeg -e`, `winget install --id DenoLand.Deno -e`
and `winget install --id Python.Python.3.12 -e`. If you try it, tell us how
it went in an [issue](https://github.com/yestoall/skills/issues).

### The batch format

The `.zip` holds a `recipes.json` and a `photos/` folder:

```json
{
  "version": 1,
  "recipes": [
    {
      "name": "Spanish omelette",
      "author": "Cook with Carmen",
      "url": "https://www.youtube.com/watch?v=uc8Pwe7alJ8",
      "category": "eggs",
      "preparationTime": "45 min",
      "photo": "omelette.jpg",
      "ingredients": [{ "name": "Potatoes", "quantity": "750 g" }],
      "preparationSteps": ["Peel and slice the potatoes."]
    }
  ]
}
```

Any tool can write a batch. Check yours with the validator, which needs only
Python 3.9 or later:

```bash
python3 plugins/nevera/skills/nevera-recipes/scripts/batch.py validate my-batch.zip
```

### For contributors

```bash
python3 -m unittest
```

The tests use only the standard library. The skill lives in
`plugins/nevera/skills/nevera-recipes/`: `SKILL.md` and its `scripts/`. Each
version is a tag (`v0.4.0`), with its entry in `CHANGELOG.md` and its number
in the plugin's `plugin.json`, in `marketplace.json`, in `doctor.py` and at the top of both
READMEs; `tests/test_version.py` fails if one of them is left behind. The batch
format has its own version (`"version": 1`), which only goes up when Nevera can
read the new one and still reads the old.

## License

[MIT](LICENSE)
