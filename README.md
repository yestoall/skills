# yestoall skills

Skills for the AI on your computer, made for the yestoall apps. One plugin
per app; for now, [Nevera](https://www.yestoall.com/nevera).

[Léelo en español](README.es.md)

Version 0.4.0

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
  `~/Nevera/`, so you can give it the same list twice.
- **What failed, and why**: a private video, a page that doesn't answer, a
  link without a recipe. One link never stops the rest.
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

### Use

Ask your AI in your own words, and paste the links or name a file with them:

> Make me a Nevera batch with these: https://youtu.be/… https://www.…

The first time, the skill installs what it needs and tells you before it
does: `yt-dlp` (downloads), `ffmpeg` (the photos), and Whisper
(`faster-whisper`, about 480 MB with its model) in a folder of its own,
`~/Nevera/.venv`. It uses Homebrew on a Mac, winget on Windows, and apt on
Linux.

When it's done, it gives you the path of the batch,
`~/Nevera/nevera-lote-YYYY-MM-DD.zip`. On a Mac, it asks how you want to send
it to your phone: it copies it to iCloud Drive for you, or shows you the file
in the Finder, where you Control-click it and choose **Share** → **AirDrop**.
From anywhere else, use Quick Share, iCloud Drive, Google Drive or a cable.
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
in the plugin's `plugin.json`, in `marketplace.json` and at the top of both
READMEs; `tests/test_version.py` fails if one of them is left behind. The batch
format has its own version (`"version": 1`), which only goes up when Nevera can
read the new one and still reads the old.

## License

[MIT](LICENSE)
