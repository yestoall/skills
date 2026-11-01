#!/usr/bin/env python3
"""Instagram posts and reels: their metadata, with or without a session.

    python3 instagram.py meta URL OUT.json [--browser NAME] [--yt-dlp PATH] [yt-dlp args...]
    python3 instagram.py ask [--system macos|windows|linux] URL...

`meta` runs `yt-dlp -J` on one post and prints JSON. When it works:
`ok`, `url` (the post's address without the share tracking), `has_video`
(a photo post has only its text) and `session_args`, the flags every later
yt-dlp call for that post needs (the cookies flag, when it took a session).
When it fails: `reason`, `message` (a sentence for the report) and
`session_helps` (true when the browser's session could get it). Exit 0 when
it worked, 3 when a session could help, 1 otherwise.

Without --browser it tries only what Instagram shows to anyone. --browser
reads the session from that browser with yt-dlp's --cookies-from-browser,
which keeps the cookies in memory for that one call: they are never written
to a file, and this script refuses --cookies (the flag that would). Pass
--browser only after the Chef said yes to the question `ask` prints.

`ask` prints that question: what the cookies are for, that nothing is kept,
and the browsers yt-dlp can read on this system.

Standard library only: it runs with any Python 3.9+.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from links import source_video
from machine import this_system

#- why a post failed -
# yt-dlp's Instagram errors (2026.10). The checks go from the most to the
# least specific: a rate limit also mentions the login page.

_REASONS = [
    (
        "cookies",
        r"cookies?\b.*(could not|not permitted|decrypt|keyring|database|unable)"
        r"|(could not|not permitted|unable).*cookies?\b",
        False,
        "the browser's cookies could not be read: on a Mac, Safari needs Full Disk"
        " Access for the terminal (System Settings, Privacy & Security), and Chrome"
        " asks for its Keychain entry; or the browser has no Instagram session.",
    ),
    (
        "rate-limited",
        r"rate-limit|HTTP Error 429|Too Many Requests",
        True,
        "Instagram stopped answering for now (too many posts without a session):"
        " try again later, or with a session.",
    ),
    (
        "private",
        r"registered users who follow|private",
        True,
        "the account is private: only its followers see it.",
    ),
    (
        "restricted",
        r"isn't available to everyone|certain audiences|Restricted Video|\bage\b",
        True,
        "Instagram shows this post only to signed-in accounts (age or region limits).",
    ),
    (
        "empty",
        r"empty media response|log(?:ged)?[ -]?in|login",
        True,
        "Instagram gave nothing: the post was deleted, or it is shown only with"
        " a session.",
    ),
    (
        "gone",
        r"HTTP Error 404|Not Found|has been removed|no longer available",
        False,
        "the post no longer exists.",
    ),
    (
        "network",
        r"Unable to download|urlopen error|timed out|Errno 8|getaddrinfo|Connection (?:refused|reset)",
        False,
        "Instagram did not answer (no network, or it is down): try again later.",
    ),
    (
        "outdated",
        r"Unable to extract|marked as broken|Unsupported URL",
        False,
        "this yt-dlp no longer understands Instagram: update it (brew upgrade"
        " yt-dlp, winget upgrade yt-dlp.yt-dlp, or pip install -U yt-dlp in the"
        " venv) and try again.",
    ),
]


def _error_line(stderr: str) -> str:
    """The last ERROR line (or the last line), without "[Instagram] <code>:"."""
    lines = [line for line in (stderr or "").splitlines() if line.strip()]
    errors = [line for line in lines if line.startswith("ERROR:")]
    line = (errors or lines or [""])[-1]
    return re.sub(r"^ERROR:\s*(\[[A-Za-z:]+\]\s*[A-Za-z0-9_-]+:\s*)?", "", line).strip()


def why_it_failed(stderr: str, with_session: bool = False) -> dict:
    """The reason a post failed, from what yt-dlp wrote to stderr: one
    `reason`, a `message` for the report and `session_helps`, never true
    once the session was already used."""
    line = _error_line(stderr)
    for reason, pattern, session_helps, message in _REASONS:
        if reason == "cookies" and not with_session:
            continue  # no cookies were read: Instagram's own hints name them
        if re.search(pattern, line, re.IGNORECASE):
            sentence = message[0].upper() + message[1:]
            return {
                "reason": reason,
                "message": sentence,
                "session_helps": session_helps and not with_session,
                "error": line,
            }
    sentence = (line or "yt-dlp failed without saying why").rstrip(".") + "."
    return {"reason": "other", "message": sentence, "session_helps": False, "error": line}


#- the yt-dlp call -

# the browsers yt-dlp's --cookies-from-browser reads (2026.10)
BROWSERS = ("brave", "chrome", "chromium", "edge", "firefox", "opera", "safari", "vivaldi", "whale")


def session_args(browser: Optional[str]) -> list:
    """The flags that read the session from `browser`, for this call only."""
    if not browser:
        return []
    name = browser.strip().lower()
    if name not in BROWSERS:
        raise ValueError(f"yt-dlp cannot read cookies from {browser!r}: one of {', '.join(BROWSERS)}")
    return ["--cookies-from-browser", name]


def meta_command(
    url: str, browser: Optional[str] = None, yt_dlp: str = "yt-dlp", extra: Optional[list] = None
) -> list:
    """`yt-dlp -J` for one post. A photo post has no formats; with
    --ignore-no-formats-error it still gives its text."""
    extra = list(extra or [])
    if any(part == "--cookies" or part.startswith("--cookies=") for part in extra):
        raise ValueError("--cookies writes the browser's cookies to a file: use --browser")
    return [yt_dlp, *session_args(browser), "--skip-download", "--ignore-no-formats-error", "-J", *extra, url]


#- the question before reading any cookies -

_NAMES = {
    "brave": "Brave", "chrome": "Chrome", "chromium": "Chromium", "edge": "Edge",
    "firefox": "Firefox", "opera": "Opera", "safari": "Safari", "vivaldi": "Vivaldi",
    "whale": "Whale",
}


def browsers_for(system: str) -> list:
    """The browsers yt-dlp reads on `system`: Safari exists only on a Mac."""
    return [b for b in BROWSERS if b != "safari" or system == "macos"]


def permission_question(urls: list, system: str) -> str:
    """What to ask the Chef, once for the batch, before any --browser."""
    count = len(urls)
    posts = f"{count} post{'s' if count != 1 else ''}"
    them = "them" if count != 1 else "it"
    names = ", ".join(_NAMES[b] for b in browsers_for(system))
    lines = [
        f"Instagram shows {posts} only to signed-in accounts:",
        *[f"  - {url}" for url in urls],
        "",
        f"To get {them}, yt-dlp can use the Instagram session of a browser on this"
        " computer, where you are already signed in. It reads that browser's"
        " cookies for these downloads only: they stay in memory, are never saved"
        " to a file and never leave this computer. Your password is not needed.",
        "",
        f"Which browser are you signed in to Instagram with? ({names})",
        f"If you say no, {'these posts go' if count != 1 else 'it goes'} to the"
        f" report, and the next batch tries {them} again.",
    ]
    if system == "macos":
        lines += [
            "",
            "On a Mac, Safari's cookies need Full Disk Access for this terminal"
            " (System Settings, Privacy & Security); Chrome, Brave and Edge ask"
            " once for their Keychain entry: allow it, or pick another browser.",
        ]
    return "\n".join(lines)


#- one post's metadata -

_REEL = re.compile(r"instagram\.com/(?:[^/?#]+/)?reels?/", re.IGNORECASE)


def post_url(url: str) -> Optional[str]:
    """The post's address without the share tracking (?igsh=, ?utm_…) or the
    account in the path: the `url` of its recipe. Same identity as Nevera."""
    video = source_video(url)
    if not video or video[0] != "instagram":
        return None
    kind = "reel" if _REEL.search(url) else "p"
    return f"https://www.instagram.com/{kind}/{video[1]}/"


def _has_video(meta: dict) -> bool:
    # a carousel comes as a playlist: a video may be any of its items
    items = [meta] + [e for e in meta.get("entries") or [] if isinstance(e, dict)]
    return any(item.get("formats") for item in items)


def fetch_meta(
    url: str,
    out: Path,
    browser: Optional[str] = None,
    yt_dlp: str = "yt-dlp",
    extra: Optional[list] = None,
    run: Callable = subprocess.run,
) -> dict:
    """`yt-dlp -J` for one post into `out`, or the reason it failed. Nothing
    is written when it fails."""
    command = meta_command(url, browser=browser, yt_dlp=yt_dlp, extra=extra)
    try:
        done = run(command, capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        return {
            "ok": False,
            "reason": "no-yt-dlp",
            "message": f"yt-dlp is not at {yt_dlp}: run doctor.py again.",
            "session_helps": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "reason": "network",
            "message": "Instagram did not answer in three minutes: try again later.",
            "session_helps": False,
        }
    meta = None
    if done.returncode == 0:
        try:
            meta = json.loads(done.stdout or "null")
        except ValueError:
            meta = None
    if not isinstance(meta, dict):
        failure = why_it_failed(done.stderr or "", with_session=bool(browser))
        return {"ok": False, **failure}
    Path(out).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return {
        "ok": True,
        "url": post_url(url) or url,
        "has_video": _has_video(meta),
        "session_args": session_args(browser),
    }


#- command line -


def _option(args: list, name: str) -> tuple:
    """(value of --name, the args without it)."""
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1], args[:i] + args[i + 2 :]
    return None, args


def main(argv: list, run: Callable = subprocess.run) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    command, args = argv[0], list(argv[1:])
    if command == "meta" and len(args) >= 2:
        url, out, rest = args[0], args[1], args[2:]
        browser, rest = _option(rest, "--browser")
        yt_dlp, rest = _option(rest, "--yt-dlp")
        try:
            result = fetch_meta(url, Path(out), browser=browser, yt_dlp=yt_dlp or "yt-dlp", extra=rest, run=run)
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result["ok"]:
            return 0
        return 3 if result["session_helps"] else 1
    if command == "ask" and args:
        system, urls = _option(args, "--system")
        if urls:
            print(permission_question(urls, system or this_system()))
            return 0
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
