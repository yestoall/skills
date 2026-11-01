#!/usr/bin/env bash
# What the skill does on Linux, without the agent: install what doctor.py
# asks for, read a real YouTube video (subtitles, Whisper and a frame), pack a
# batch and validate it. The recipe text is a stand-in: writing it is the
# agent's part. Runs inside the Dockerfile's image.
set -euo pipefail

SKILL=/skills/plugins/nevera/skills/nevera-recipes
S="$SKILL/scripts"
URL="https://youtu.be/uc8Pwe7alJ8?si=docker"
json() { python3 -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

echo "== unit tests"
python3 -m unittest

echo "== npx skills finds the skill"
npx --yes skills add /skills --list 2>&1 | tee /tmp/list.txt
grep -q nevera-recipes /tmp/list.txt

echo "== doctor: install steps"
python3 "$S/doctor.py" > /tmp/doctor.json
python3 -c "import json; [print(s) for s in json.load(open('/tmp/doctor.json'))['steps']]" > /tmp/steps.txt
cat /tmp/steps.txt
while IFS= read -r step; do
  # the deno installer asks before touching the shell profile
  bash -c "$step" < /dev/null
done < /tmp/steps.txt
export PATH="$HOME/.deno/bin:$PATH"
python3 "$S/doctor.py" > /tmp/doctor.json
cat /tmp/doctor.json
test "$(json "d['ready']" < /tmp/doctor.json)" = "True"
YTDLP=$(json "d['commands']['yt-dlp']" < /tmp/doctor.json)
VPY=$(json "d['commands']['python']" < /tmp/doctor.json)
ARGS=$(json "' '.join(d['yt_dlp_args'])" < /tmp/doctor.json)

W=$(mktemp -d)
cd "$W"
echo "$URL" > links.txt
python3 "$S/links.py" pending links.txt | tee pending.json
SLUG=$(json "d['pending'][0]['slug']" < pending.json)
mkdir -p "$SLUG" batch/photos

echo "== subtitles"
$YTDLP $ARGS --skip-download -J "$URL" > "$SLUG/meta.json"
python3 "$S/transcribe.py" pick "$SLUG/meta.json" | tee pick.txt
read -r KIND LANG < pick.txt
$YTDLP $ARGS --skip-download --write-subs --write-auto-subs --sub-langs "$LANG" --sub-format vtt -o "$SLUG/subs.%(ext)s" "$URL"
python3 "$S/transcribe.py" subtitles "$SLUG/subs.$LANG.vtt" "$SLUG/transcript.txt"
head -5 "$SLUG/transcript.txt"

echo "== whisper (first 30 s)"
$YTDLP $ARGS --no-progress -f "ba[ext=m4a]/ba" -o "$SLUG/audio.%(ext)s" "$URL"
ffmpeg -v error -t 30 -i "$SLUG"/audio.* -c copy "$SLUG/clip.m4a"
"$VPY" "$S/transcribe.py" whisper "$SLUG/clip.m4a" "$SLUG/whisper.txt" --language es
head -5 "$SLUG/whisper.txt"

echo "== frame"
$YTDLP $ARGS --no-progress -f "bv*[height<=1080][ext=mp4]/bv*[height<=1080]/b" -o "$SLUG/video.%(ext)s" "$URL"
ffmpeg -v error -ss 137 -i "$SLUG/video.mp4" -frames:v 1 -vf "crop=1080:1080:390:0" -q:v 3 "batch/photos/$SLUG.jpg"

echo "== batch"
TITLE=$(json "d['title']" < "$SLUG/meta.json")
python3 - "$TITLE" "$SLUG" <<'PY'
import json, sys
title, slug = sys.argv[1], sys.argv[2]
recipe = {
    "name": title,
    "author": "",
    "url": "https://www.youtube.com/watch?v=uc8Pwe7alJ8",
    "category": "",
    "preparationTime": "",
    "photo": f"{slug}.jpg",
    "ingredients": [{"name": "stand-in", "quantity": ""}],
    "preparationSteps": ["stand-in"],
}
json.dump({"version": 1, "recipes": [recipe]}, open("batch/recipes.json", "w"), ensure_ascii=False)
PY
NEVERA_HOME="$W/Nevera" python3 "$S/batch.py" pack batch
python3 "$S/batch.py" validate "$W"/Nevera/nevera-lote-*.zip
NEVERA_HOME="$W/Nevera" python3 "$S/links.py" record recipe "$URL"
NEVERA_HOME="$W/Nevera" python3 "$S/links.py" pending links.txt

echo "== OK: the skill's tools work on this Linux"
