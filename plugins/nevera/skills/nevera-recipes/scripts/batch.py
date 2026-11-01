#!/usr/bin/env python3
"""Check and pack a Nevera recipe batch (format v1).

    python3 batch.py validate FILE          # a .zip or a .json batch
    python3 batch.py pack WORKDIR [OUT.zip] # WORKDIR/recipes.json + its photos
    python3 batch.py preview WORKDIR [es|en] [--open]  # WORKDIR/review.md, to read

A batch is a .zip with `recipes.json` and a `photos/` folder:

    recipes.json   {"version": 1, "recipes": [ {...}, {...} ]}
    photos/        one image per recipe, named in the recipe's "photo" field

or the same JSON alone, pasted or in a .json file, without photos. Nevera
reads it in src/utils/recipeBatch.ts, and docs/importar.md in the Nevera repo
is the contract. This validator is stricter than the reader on purpose:
Nevera forgives a lot (prose around the JSON, smart quotes, a broken comma)
because a chat writes it; a tool that writes batches should not need that.

Errors are what would make Nevera refuse the batch, drop a recipe or lose a
photo. Warnings are what Nevera fixes on its own (it crops and compresses
every photo) or ignores. `validate` exits 1 if there is any error. `pack`
validates before writing, and writes nothing if there is any error.

Standard library only: it runs with any Python 3.9+.
"""

from __future__ import annotations

import datetime as _dt
import io
import json
import re
import struct
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from machine import batches_folder, open_command, this_system

VERSION = 1
RECIPES_JSON = "recipes.json"
PHOTOS_DIR = "photos"
BACKUP_JSON = "backup.json"
# Nevera saves every photo as a square of at most 1200 px
PHOTO_MAX = 1200

# the fields Nevera's recipe schema knows (src/types/recipeSchema.ts)
STRING_FIELDS = (
    "url",
    "icon",
    "category",
    "author",
    "notes",
    "preparationTime",
    "app",
    "sharedBy",
    "sharedAt",
)
# these three never drop a recipe: a bad value is just ignored
FORGIVEN_FIELDS = ("photo", "photoUrl", "replaces")
OTHER_FIELDS = ("name", "id", "isRecipe", "favorite", "v", "ingredients", "preparationSteps")
KNOWN_FIELDS = set(STRING_FIELDS + FORGIVEN_FIELDS + OTHER_FIELDS)
# the snake_case of Nevera's old prompt, still read
DIALECT = {"steps": "preparationSteps", "preparation_time": "preparationTime"}


@dataclass
class Report:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    recipes: int = 0
    photos: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def text(self) -> str:
        lines = [
            f"{'OK' if self.ok else 'NOT VALID'}: {self.recipes} recipes, {self.photos} photos"
        ]
        lines += [f"error: {e}" for e in self.errors]
        lines += [f"warning: {w}" for w in self.warnings]
        return "\n".join(lines)


#- validate -


def validate(source: Union[bytes, str, Path]) -> Report:
    data = Path(source).read_bytes() if isinstance(source, (str, Path)) else source
    report = Report()
    if data[:2] == b"PK":
        _validate_zip(data, report)
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            report.errors.append("not a batch: neither a .zip nor a UTF-8 JSON file")
            return report
        parsed = _parse(text, "the file", report)
        if parsed is not None:
            _validate_recipes(parsed, report, photos=None)
    return report


def _parse(text: str, where: str, report: Report):
    try:
        return json.loads(text)
    except ValueError as error:
        report.errors.append(f"{where} is not valid JSON ({error})")
        return None


def _validate_zip(data: bytes, report: Report) -> None:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        files = {
            info.filename: archive.read(info)
            for info in archive.infolist()
            if not info.is_dir() and not info.filename.startswith("__MACOSX/")
        }
    except (zipfile.BadZipFile, OSError, ValueError) as error:
        report.errors.append(f"the .zip cannot be opened ({error})")
        return
    # like Nevera: the recipes.json closest to the root, and the photos/
    # folder next to it (a zipped folder keeps everything one level down)
    candidates = sorted(
        (p for p in files if _basename(p) == RECIPES_JSON), key=len
    )
    if not candidates:
        if any(_basename(p) == BACKUP_JSON for p in files):
            report.errors.append(
                "this is a Nevera backup (backup.json), not a recipe batch: it is restored from the Chef screen"
            )
        else:
            report.errors.append(f"the .zip has no {RECIPES_JSON}")
        return
    json_path = candidates[0]
    folder = json_path[: -len(RECIPES_JSON)]
    if folder:
        report.warnings.append(
            f"{RECIPES_JSON} is inside {folder!r}: Nevera reads it, but put it at the root"
        )
    try:
        text = files[json_path].decode("utf-8-sig")
    except UnicodeDecodeError:
        report.errors.append(f"{RECIPES_JSON} is not UTF-8 text")
        return
    parsed = _parse(text, RECIPES_JSON, report)
    if parsed is None:
        return
    prefix = f"{folder}{PHOTOS_DIR}/"
    photos = {p[len(prefix) :]: content for p, content in files.items() if p.startswith(prefix)}
    used = _validate_recipes(parsed, report, photos=photos)
    for name in sorted(set(photos) - used):
        report.warnings.append(f"{PHOTOS_DIR}/{name} is not used by any recipe")


def _validate_recipes(parsed, report: Report, photos: Optional[dict]) -> set:
    """Checks every recipe; returns the photo names they use."""
    if isinstance(parsed, dict) and "recipes" in parsed:
        version = parsed.get("version")
        if version != VERSION or isinstance(version, bool):
            report.errors.append(
                f"version must be {VERSION} (found {json.dumps(version)})"
            )
        items = parsed["recipes"]
        if not isinstance(items, list):
            report.errors.append('"recipes" must be a list')
            return set()
    elif isinstance(parsed, dict) and isinstance(parsed.get("lists"), list):
        report.errors.append(
            "this is a Nevera backup, not a recipe batch: it is restored from the Chef screen"
        )
        return set()
    else:
        report.warnings.append(
            f'write {{"version": {VERSION}, "recipes": [...]}}: Nevera reads a bare list or a single recipe, but the version is how the format can change without breaking'
        )
        items = parsed if isinstance(parsed, list) else [parsed]
    if not items:
        report.errors.append("the batch has no recipes")
        return set()

    used: set = set()
    names: dict = {}
    for position, item in enumerate(items, start=1):
        label = _label(position, item)
        problems = _recipe_problems(item)
        if problems:
            report.errors.append(f"{label}: Nevera would drop it: {'; '.join(problems)}")
            continue
        report.recipes += 1
        recipe = item
        for old, new in DIALECT.items():
            if old in recipe and new not in recipe:
                report.warnings.append(f"{label}: write {new!r}, not {old!r}")
        unknown = sorted(set(recipe) - KNOWN_FIELDS - set(DIALECT))
        if unknown:
            report.warnings.append(f"{label}: Nevera ignores {', '.join(unknown)}")
        if not str(recipe.get("url") or "").strip():
            report.warnings.append(
                f"{label}: no url: the Chef cannot go back to the source"
            )
        key = _name_key(recipe["name"])
        if key in names:
            report.warnings.append(
                f"{label}: same name as recipe {names[key]}"
            )
        names.setdefault(key, position)
        if photos is None:
            if recipe.get("photo"):
                report.warnings.append(
                    f"{label}: a JSON batch carries no photos: \"photo\" is ignored"
                )
            continue
        name = recipe.get("photo")
        if not isinstance(name, str) or not name.strip():
            report.warnings.append(f"{label}: no photo")
            continue
        file = re.sub(rf"^(\./)?({PHOTOS_DIR}/)?", "", name.strip())
        content = photos.get(file)
        if content is None:
            report.errors.append(
                f"{label}: its photo {name!r} is not in {PHOTOS_DIR}/: it would arrive without it"
            )
            continue
        used.add(file)
        size = image_size(content)
        if size is None:
            report.errors.append(
                f"{label}: {PHOTOS_DIR}/{file} is not a JPEG or a PNG Nevera can read: it would arrive without it"
            )
            continue
        report.photos += 1
        width, height = size
        if width != height or max(width, height) > PHOTO_MAX:
            report.warnings.append(
                f"{label}: {PHOTOS_DIR}/{file} is {width}x{height}: Nevera crops it to a centred square of up to {PHOTO_MAX} px; crop it yourself to choose what stays"
            )
    return used


def _recipe_problems(item) -> list:
    if not isinstance(item, dict):
        return ["not an object"]
    recipe = dict(item)
    for old, new in DIALECT.items():
        if new not in recipe and old in recipe:
            recipe[new] = recipe[old]
    problems = []
    name = recipe.get("name")
    if name is not None and not isinstance(name, str):
        problems.append('"name" must be text')
    elif not (name or "").strip():
        problems.append("missing name")
    for key in STRING_FIELDS:
        if key in recipe and not isinstance(recipe[key], str):
            kind = "null" if recipe[key] is None else type(recipe[key]).__name__
            problems.append(f'"{key}" must be text, not {kind} (use "" when unknown)')
    ingredients = recipe.get("ingredients")
    if ingredients is None or ingredients == []:
        problems.append("no ingredients")
    elif not isinstance(ingredients, list):
        problems.append('"ingredients" must be a list')
    else:
        for i, ingredient in enumerate(ingredients, start=1):
            if not (
                isinstance(ingredient, dict)
                and isinstance(ingredient.get("name"), str)
                and isinstance(ingredient.get("quantity"), str)
            ):
                problems.append(
                    f'ingredient {i} must be {{"name": text, "quantity": text}} (quantity "" when there is none)'
                )
    steps = recipe.get("preparationSteps")
    if steps is not None and not (
        isinstance(steps, list) and all(isinstance(s, str) for s in steps)
    ):
        problems.append('"preparationSteps" must be a list of texts')
    for key, kind in (("favorite", bool), ("isRecipe", bool)):
        if key in recipe and not isinstance(recipe[key], kind):
            problems.append(f'"{key}" must be true or false')
    return problems


def _label(position: int, item) -> str:
    name = item.get("name") if isinstance(item, dict) else None
    return f"recipe {position}" + (f" ({name.strip()})" if isinstance(name, str) and name.strip() else "")


def _name_key(name: str) -> str:
    import unicodedata

    plain = unicodedata.normalize("NFD", name.lower())
    plain = "".join(c for c in plain if unicodedata.category(c) != "Mn")
    return " ".join(plain.split())


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


#- image_size -
# Width and height from the header, without decoding: what Nevera does
# (imageSize in src/photos/utils.ts). None if it is not a JPEG or a PNG.

_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def image_size(data: bytes) -> Optional[tuple]:
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return (width, height) if width and height else None
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker in _SOF:
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return (width, height) if width and height else None
        i += 2 + length
    return None


#- pack -


def default_output(folder: Path, today: Optional[_dt.date] = None) -> Path:
    """nevera-lote-YYYY-MM-DD.zip, with -2, -3… if that day already has one."""
    stem = f"nevera-lote-{(today or _dt.date.today()).isoformat()}"
    out = folder / f"{stem}.zip"
    n = 2
    while out.exists():
        out = folder / f"{stem}-{n}.zip"
        n += 1
    return out


def pack(workdir: Union[str, Path], out: Union[str, Path]) -> Report:
    """WORKDIR/recipes.json and the photos it names (in WORKDIR/photos/) into
    OUT. Only the photos a recipe uses go in: the candidates and contact
    sheets left in photos/ stay out. Nothing is written if the batch has
    errors."""
    workdir = Path(workdir)
    recipes_json = workdir / RECIPES_JSON
    if not recipes_json.exists():
        return Report(errors=[f"{recipes_json} does not exist"])
    text = recipes_json.read_text(encoding="utf-8")
    parsed = _parse(text, RECIPES_JSON, Report())
    names = set()
    if isinstance(parsed, dict) and isinstance(parsed.get("recipes"), list):
        for item in parsed["recipes"]:
            photo = item.get("photo") if isinstance(item, dict) else None
            if isinstance(photo, str) and photo.strip():
                names.add(re.sub(rf"^(\./)?({PHOTOS_DIR}/)?", "", photo.strip()))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            zipfile.ZipInfo(RECIPES_JSON, _now()), text.encode("utf-8"), zipfile.ZIP_DEFLATED
        )
        for name in sorted(names):
            path = workdir / PHOTOS_DIR / name
            if path.is_file():
                # photos are already JPEG: stored, not compressed again
                archive.writestr(
                    zipfile.ZipInfo(f"{PHOTOS_DIR}/{name}", _now()),
                    path.read_bytes(),
                    zipfile.ZIP_STORED,
                )
    data = buffer.getvalue()
    report = validate(data)
    if report.ok:
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(out.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(out)
    return report


def _now() -> tuple:
    return _dt.datetime.now().timetuple()[:6]


#- preview -
# The batch in plain text, for the user to read and change in any editor before
# it goes to the phone. Only one way: the agent reads their changes and carries
# them over to recipes.json, so this file has no format to keep to.

HEADINGS = {
    "en": ("Ingredients", "Steps"),
    "es": ("Ingredientes", "Pasos"),
}


def render_review(parsed: dict, lang: str = "en") -> str:
    ingredients_title, steps_title = HEADINGS.get(lang, HEADINGS["en"])
    pages = []
    for recipe in parsed["recipes"]:
        lines = [f"# {recipe['name']}"]
        byline = " · ".join(
            v for v in (recipe.get("author"), recipe.get("preparationTime")) if v
        )
        about = [v for v in (byline, recipe.get("url")) if v]
        if about:
            lines += ["", *about]
        if recipe.get("photo"):
            file = re.sub(rf"^(\./)?({PHOTOS_DIR}/)?", "", recipe["photo"].strip())
            lines += ["", f"![{recipe['name']}]({PHOTOS_DIR}/{file})"]
        if recipe.get("ingredients"):
            lines += ["", f"## {ingredients_title}", ""]
            lines += [
                f"- {i['name']}: {i['quantity']}" if i.get("quantity") else f"- {i['name']}"
                for i in recipe["ingredients"]
            ]
        if recipe.get("preparationSteps"):
            lines += ["", f"## {steps_title}", ""]
            lines += [
                f"{n}. {step}"
                for n, step in enumerate(recipe["preparationSteps"], start=1)
            ]
        pages.append("\n".join(lines) + "\n")
    return "\n---\n\n".join(pages)


def preview(workdir: Union[str, Path], lang: str = "en") -> Path:
    """WORKDIR/review.md, next to the photos it points at."""
    workdir = Path(workdir)
    parsed = json.loads((workdir / RECIPES_JSON).read_text(encoding="utf-8"))
    path = workdir / "review.md"
    path.write_text(render_review(parsed, lang), encoding="utf-8")
    return path


#- command line -


def main(argv: list) -> int:
    if len(argv) >= 2 and argv[0] == "validate":
        report = validate(Path(argv[1]))
        print(report.text())
        return 0 if report.ok else 1
    if len(argv) >= 2 and argv[0] == "pack":
        out = Path(argv[2]) if len(argv) >= 3 else default_output(batches_folder())
        report = pack(argv[1], out)
        print(report.text())
        if report.ok:
            print(f"written: {out}")
        return 0 if report.ok else 1
    if len(argv) >= 2 and argv[0] == "preview":
        options = argv[2:]
        should_open = "--open" in options
        langs = [o for o in options if o != "--open"]
        path = preview(argv[1], langs[0] if langs else "en")
        print(f"written: {path}")
        if should_open:
            subprocess.run(open_command(this_system(), str(path)), check=False)
        return 0
    print(__doc__, file=sys.stderr if argv else sys.stdout)
    return 0 if not argv or argv[0] in ("-h", "--help") else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
