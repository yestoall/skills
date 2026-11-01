# yestoall skills

Skills for the AI on your computer, made for the yestoall apps. One plugin
per app; for now, [Nevera](https://www.yestoall.com/nevera).

[En español, más abajo](#en-español)

Version 0.1.0

## nevera-recipes

Give your AI a list of cooking videos and recipe pages, and get back one
`.zip` you open with Nevera on your phone: every recipe with its ingredients,
its steps and a photo of the finished dish.

- **YouTube videos**: the recipe comes from the description and from what is
  said in the video. It uses the video's subtitles when there are any, and
  transcribes the audio with Whisper, on your computer, when there aren't.
- **Recipe web pages**: the recipe the page carries for search engines, or
  its text.
- **A photo per recipe**: a frame of the finished dish, cropped square,
  without titles or watermarks. From a page, its own photo.
- **Links you already converted are skipped**: the skill keeps a record in
  `~/Nevera/`, so you can give it the same list twice.
- **What failed, and why**: a private video, a page that doesn't answer, a
  link without a recipe. One link never stops the rest.

Instagram reels are coming in a later version.

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
`~/Nevera/nevera-lote-YYYY-MM-DD.zip`. Send it to your phone (AirDrop,
Quick Share, iCloud Drive, Google Drive or a cable) and open it with Nevera.
Nevera shows you every recipe before saving any.

### Works on

| System | Status |
| --- | --- |
| macOS | Tested |
| Linux (Debian, Ubuntu) | Not tested yet: `docker build -t yestoall-skills-test . && docker run --rm yestoall-skills-test` runs the check |
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
python3 plugins/nevera/skills/nevera-recipes/scripts/lote.py validate my-batch.zip
```

### For contributors

```bash
python3 -m unittest
```

The tests use only the standard library. The skill lives in
`plugins/nevera/skills/nevera-recipes/`: `SKILL.md` and its `scripts/`. Each
version is a tag (`v0.1.0`), with its entry in `CHANGELOG.md` and its number
in the plugin's `plugin.json`. The batch format has its own version
(`"version": 1`), which only goes up when Nevera can read the new one and
still reads the old.

## En español

Skills para la IA de tu ordenador, hechas para las apps de yestoall. Hoy,
una: `nevera-recipes`, para [Nevera](https://www.yestoall.com/nevera).

Dale a tu IA una lista de vídeos de cocina de YouTube y de webs de recetas, y
te devuelve un `.zip` que abres con Nevera en el teléfono: cada receta con
sus ingredientes, sus pasos y una foto del plato terminado. Los subtítulos
del vídeo, si los tiene; si no, transcribe el audio con Whisper, en tu
ordenador. Recuerda los enlaces que ya hizo, para que puedas pasarle la misma
lista dos veces, y te dice qué no pudo sacar y por qué. Los reels de
Instagram llegan en una versión posterior.

Instálala con Node 22 o más:

```bash
npx skills add yestoall/skills --skill nevera-recipes
```

O, en Claude Code:

```text
/plugin marketplace add yestoall/skills
/plugin install nevera@yestoall
```

Luego pídeselo a tu IA con tus palabras y pégale los enlaces. La primera vez
instala lo que le falta (`yt-dlp`, `ffmpeg` y Whisper) y te avisa antes.
El Lote queda en `~/Nevera/nevera-lote-AAAA-MM-DD.zip`: pásalo al teléfono
(AirDrop, Quick Share, iCloud Drive, Google Drive o un cable) y ábrelo con
Nevera, que te enseña todas las recetas antes de guardar ninguna.

Probada en macOS. Linux y Windows, todavía sin probar.

## License

[MIT](LICENSE)
