#!/usr/bin/env python3
"""The links the Chef hands over, and the record of the ones already done.

    python3 links.py pending [FILE]     # FILE, or stdin if missing or "-"
    python3 links.py record STATUS URL... # STATUS: recipe | no-recipe

Every link is known by its identity, the same rule Nevera uses
(`linkIdentity` in src/recipes/video.ts): `instagram:<code>`,
`youtube:<id>`, or a web page's URL without `?` or `#`. One video reaches us
in many URL shapes (`?si=`, `youtu.be`, `/shorts/`, `?igsh=`, `/reel/` or
`/p/`); its identity is one.

The record lives in ~/Nevera/converted.tsv (NEVERA_HOME overrides the
folder): one line per link, `identity<TAB>date<TAB>status<TAB>url`. It sits
next to the batches and not in the skill's folder, which every update of the
package overwrites.

Standard library only: it runs with any Python 3.9+.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Iterable, Optional

from machine import nevera_home

#- identity -
# Ported from Nevera (src/recipes/video.ts). Keep them identical: the inbox in
# the app crosses links out with this same identity.

_CODE = r"[A-Za-z0-9_-]+"
_INSTAGRAM = re.compile(
    r"^https?://(?:www\.)?instagram\.com/(?:[^/?#]+/)?(?:p|reels?|tv)/(" + _CODE + ")",
    re.IGNORECASE,
)
_YOUTUBE_WATCH = re.compile(
    r"^https?://(?:www\.|m\.)?youtube\.com/watch\?(?:[^#]*&)?v=(" + _CODE + ")",
    re.IGNORECASE,
)
_YOUTUBE_PATH = re.compile(
    r"^https?://(?:(?:www\.|m\.)?youtube\.com/(?:shorts|embed|live)/|youtu\.be/)("
    + _CODE
    + ")",
    re.IGNORECASE,
)
_WEB = re.compile(r"^https?://[^\s/?#]+\.[^\s/?#]+(?:[/?#]\S*)?$", re.IGNORECASE)
_VIDEO_HOSTS = re.compile(
    r"^https?://(?:[^/?#]+\.)?(?:instagram\.com|youtube\.com|youtu\.be)(?:[/?#:]|$)",
    re.IGNORECASE,
)


def source_video(url: Optional[str]) -> Optional[tuple[str, str]]:
    """(platform, code) for an Instagram post or a YouTube video, else None."""
    text = (url or "").strip()
    instagram = _INSTAGRAM.match(text)
    if instagram:
        return ("instagram", instagram.group(1))
    youtube = _YOUTUBE_WATCH.match(text) or _YOUTUBE_PATH.match(text)
    if youtube:
        return ("youtube", youtube.group(1))
    return None


def source_page(url: Optional[str]) -> Optional[str]:
    """A web page that is not Instagram or YouTube, as it came, else None."""
    text = (url or "").strip()
    if not _WEB.match(text) or _VIDEO_HOSTS.match(text):
        return None
    return text


def link_identity(url: Optional[str]) -> Optional[str]:
    video = source_video(url)
    if video:
        return f"{video[0]}:{video[1]}"
    page = source_page(url)
    return re.sub(r"[?#].*$", "", page) if page else None


#- the links in a text -
# Pasted in the chat, saved in a file, copied from Nevera ("Copy links", one
# per line) or shared from an app (a sentence with the URL inside).

_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"'«»]+", re.IGNORECASE)
_TRAILING_PUNCTUATION = re.compile(r"[.,;:!?)\]}]+$")


def urls_in(text: str) -> list[str]:
    return [
        _TRAILING_PUNCTUATION.sub("", match.group(0))
        for match in _URL_IN_TEXT.finditer(text or "")
    ]


#- the record of converted links -

STATUSES = ("recipe", "no-recipe")


class Record:
    """~/Nevera/converted.tsv: identity, date, status and URL of each link
    already converted. `recipe` went into a delivered batch; `no-recipe` had
    no recipe to take. A link that failed to download is never recorded, so
    the next run tries it again."""

    def __init__(self, folder: Optional[Path] = None):
        self.folder = Path(folder) if folder else nevera_home()
        self.path = self.folder / "converted.tsv"

    def load(self) -> dict[str, dict[str, str]]:
        entries: dict[str, dict[str, str]] = {}
        if not self.path.exists():
            return entries
        for line in self.path.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) < 4 or not parts[0]:
                continue
            identity, date, status, url = parts[:4]
            entries[identity] = {"date": date, "status": status, "url": url}
        return entries

    def add(self, status: str, urls: Iterable[str]) -> list[str]:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {', '.join(STATUSES)}")
        new = []
        for url in urls:
            identity = link_identity(url)
            if not identity:
                raise ValueError(f"not a video or a recipe page: {url}")
            new.append((identity, url.strip()))
        entries = self.load()
        today = _dt.date.today().isoformat()
        for identity, url in new:
            entries.pop(identity, None)
            entries[identity] = {"date": today, "status": status, "url": url}
        self.folder.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tsv.tmp")
        tmp.write_text(
            "".join(
                f"{identity}\t{e['date']}\t{e['status']}\t{e['url']}\n"
                for identity, e in entries.items()
            ),
            encoding="utf-8",
        )
        tmp.replace(self.path)
        return [identity for identity, _ in new]


#- pending -


def slug(identity: str) -> str:
    """A name for the link's work folder and its photo: letters, digits, _ and -."""
    plain = re.sub(r"^https?://", "", identity)
    return re.sub(r"[^A-Za-z0-9_]+", "-", plain).strip("-")[:80]


def pending(text: str, record: Record) -> dict[str, list]:
    """Every link in the text, once, in the order it came: `pending` (to do),
    `done` (already in the record, with its status and date) and
    `unrecognized` (a URL that is not a video or a recipe page: a profile, a
    channel)."""
    done_before = record.load()
    seen: set[str] = set()
    result: dict[str, list] = {"pending": [], "done": [], "unrecognized": []}
    for url in urls_in(text):
        identity = link_identity(url)
        if not identity:
            if url not in result["unrecognized"]:
                result["unrecognized"].append(url)
            continue
        if identity in seen:
            continue
        seen.add(identity)
        platform = identity.split(":", 1)[0] if source_video(url) else "web"
        link = {"url": url, "identity": identity, "kind": platform, "slug": slug(identity)}
        if identity in done_before:
            link.update(done_before[identity])
            link["url"] = url
            result["done"].append(link)
        else:
            result["pending"].append(link)
    return result


#- command line -

USAGE = __doc__.split("\n\n")[0]


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    command, args = argv[0], argv[1:]
    if command == "pending":
        source = args[0] if args else "-"
        text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
        print(json.dumps(pending(text, Record()), indent=2, ensure_ascii=False))
        return 0
    if command == "record" and len(args) >= 2:
        try:
            identities = Record().add(args[0], args[1:])
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        print(f"recorded as {args[0]}: {', '.join(identities)}")
        return 0
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
