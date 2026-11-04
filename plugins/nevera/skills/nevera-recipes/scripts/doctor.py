#!/usr/bin/env python3
"""What this machine has, and what to install so the skill can run.

    python3 doctor.py

Prints JSON: the system, the tools found, `commands` (the yt-dlp, ffmpeg and
venv Python to call), `yt_dlp_args` (flags every yt-dlp call needs here) and
`steps`: the install commands still missing, in order. No steps means ready.
It installs nothing itself: the steps are run one by one, where the Chef can
see them.

  - macOS: Homebrew (yt-dlp brings Deno, the JavaScript runtime YouTube needs).
  - Windows: winget (yt-dlp.yt-dlp, Gyan.FFmpeg, DenoLand.Deno).
  - Linux: apt for ffmpeg, and yt-dlp from pip inside the venv, because the
    apt package falls behind YouTube within weeks.

Whisper is apart, in `whisper_steps`, because most links never need it and it
weighs about 480 MB with its model: they are run when a link first asks for
it, and `commands.python` stays null until then. It is faster-whisper, in a
venv of its own at ~/Downloads/nevera/.venv (NEVERA_HOME overrides
~/Downloads/nevera), never in the system's Python. It needs a Python between
3.9 and 3.14: 3.15 has no wheels yet for PyAV, one of its dependencies.

`yt_dlp_version`, `yt_dlp_old` and `yt_dlp_update` are there because YouTube
breaks an old yt-dlp: old is more than two months since its release, and the
update is the command for the way this one was installed.

`updates` is what the user should hear about: a newer version of this skill,
and an old yt-dlp. To know about the skill, it reads one public file from
GitHub, sends nothing, and says nothing if the answer doesn't come.

Standard library only: it runs with any Python 3.9+.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from machine import nevera_home, this_system

PYTHON_RANGE = ((3, 9), (3, 14))
TOOLS = ("yt-dlp", "ffmpeg", "ffprobe", "deno", "node")
OLD_AFTER_DAYS = 60
SKILL_VERSION = "0.11.0"
PUBLISHED_PLUGIN = (
    "https://raw.githubusercontent.com/yestoall/skills/main"
    "/plugins/nevera/.claude-plugin/plugin.json"
)


def pick_python(found: dict) -> Optional[str]:
    """The newest Python inside PYTHON_RANGE, from {(major, minor): path}."""
    low, high = PYTHON_RANGE
    usable = [v for v in found if low <= v <= high]
    return found[max(usable)] if usable else None


def venv_python(system: str, venv: str) -> str:
    return f"{venv}/Scripts/python" if system == "windows" else f"{venv}/bin/python"


def plan(
    system: str,
    tools: dict,
    python: Optional[str],
    venv: str,
    venv_exists: bool = False,
    has_brew: bool = True,
    has_apt: bool = True,
) -> list:
    """The install commands still missing to download and to cut a photo.
    `tools` maps a tool to its path (missing or None when it is not there);
    `python` is a usable Python for the venv, the only way yt-dlp goes in on
    Linux."""
    has = lambda tool: bool(tools.get(tool))  # noqa: E731
    js = has("deno") or has("node")
    steps: list = []

    if system == "macos":
        if not has_brew:
            return [
                "Install Homebrew first (https://brew.sh), then run this check again"
            ]
        if not has("yt-dlp"):
            steps.append("brew install yt-dlp")
        elif not js:
            steps.append("brew install deno")
        if not (has("ffmpeg") and has("ffprobe")):
            steps.append("brew install ffmpeg")
    elif system == "windows":
        if not has("yt-dlp"):
            steps.append("winget install --id yt-dlp.yt-dlp -e")
        if not (has("ffmpeg") and has("ffprobe")):
            steps.append("winget install --id Gyan.FFmpeg -e")
        if not js:
            steps.append("winget install --id DenoLand.Deno -e")
    else:
        new_venv = not has("yt-dlp") and not venv_exists
        apt = []
        if not (has("ffmpeg") and has("ffprobe")):
            apt.append("ffmpeg")
        if new_venv:
            python, packages = _venv_packages(python)
            apt += packages
        if apt:
            steps.append(_apt_step(apt, has_apt))
        if not js:
            steps.append("curl -fsSL https://deno.land/install.sh | sh")
        if new_venv:
            steps.append(f"{python} -m venv {venv}")
        if not has("yt-dlp"):
            steps.append(f'{venv_python(system, venv)} -m pip install "yt-dlp[default]"')
    return steps


def whisper_plan(
    system: str,
    python: Optional[str],
    venv: str,
    venv_exists: bool = False,
    has_apt: bool = True,
) -> list:
    """The install commands for Whisper, for when a link asks for it."""
    steps: list = []
    if not venv_exists:
        if system == "macos" and not python:
            steps.append("brew install python@3.12")
            python = "python3.12"
        elif system == "windows" and not python:
            steps.append("winget install --id Python.Python.3.12 -e")
            python = "py -3.12"
        elif system == "linux":
            python, packages = _venv_packages(python)
            steps.append(_apt_step(packages, has_apt))
        steps.append(f"{python} -m venv {venv}")
    steps.append(f"{venv_python(system, venv)} -m pip install faster-whisper")
    return steps


def _venv_packages(python: Optional[str]) -> tuple:
    # el python3 de Debian no trae el módulo venv sin python3-venv
    if python:
        return python, ["python3-venv"]
    return "python3", ["python3", "python3-venv"]


def _apt_step(packages: list, has_apt: bool) -> str:
    # un Debian recién instalado no tiene listas de paquetes
    if has_apt:
        return f"sudo apt-get update && sudo apt-get install -y {' '.join(packages)}"
    return f"Install {', '.join(packages)} with your package manager"


#- an old yt-dlp -


def version_age(version: Optional[str], today: _dt.date) -> Optional[int]:
    """Days since a yt-dlp release, whose version is its date (2026.10.22)."""
    match = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", version or "")
    if not match:
        return None
    try:
        return (today - _dt.date(*map(int, match.groups()))).days
    except ValueError:
        return None


def is_old(age: Optional[int]) -> bool:
    return age is not None and age > OLD_AFTER_DAYS


def update_command(system: str, path: Optional[str], venv: str) -> Optional[str]:
    """How to update this yt-dlp: each way of installing it has its own, and
    `yt-dlp -U` only works on the standalone binary."""
    if not path:
        return None
    if path.startswith(venv):
        return f'{venv_python(system, venv)} -m pip install -U "yt-dlp[default]"'
    if system == "windows":
        return "winget upgrade --id yt-dlp.yt-dlp -e"
    if system == "macos" and ("/Cellar/" in path or "/homebrew/" in path):
        return "brew upgrade yt-dlp"
    return f"{path} -U"


def _yt_dlp_version(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    try:
        return subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=20
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


#- a new version of the skill -


def _fetch_published() -> bytes:
    with urllib.request.urlopen(PUBLISHED_PLUGIN, timeout=3) as response:
        return response.read()


def latest_version(fetch: Callable[[], bytes] = _fetch_published) -> Optional[str]:
    """The published version, or None: no network never stops the skill."""
    try:
        return json.loads(fetch())["version"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _version_numbers(version: Optional[str]) -> Optional[tuple]:
    if not version or not re.fullmatch(r"\d+(\.\d+)*", version):
        return None
    return tuple(int(part) for part in version.split("."))


def is_newer(latest: Optional[str], current: str) -> bool:
    latest_numbers = _version_numbers(latest)
    current_numbers = _version_numbers(current)
    return bool(latest_numbers and current_numbers and latest_numbers > current_numbers)


def skill_update_command(scripts: str) -> str:
    """How to update the skill: as a plugin, or with the skills CLI."""
    if "/.claude/plugins/" in Path(scripts).as_posix():
        return "claude plugin marketplace update yestoall && claude plugin update nevera@yestoall"
    return "npx skills update nevera-recipes"


def updates(skill: dict, yt_dlp: dict) -> list:
    """What the user should hear about, the skill first."""
    found = []
    if is_newer(skill["latest"], skill["current"]):
        found.append(
            {
                "name": "nevera-recipes",
                "current": skill["current"],
                "latest": skill["latest"],
                "command": skill["command"],
            }
        )
    if yt_dlp["old"]:
        found.append(
            {"name": "yt-dlp", "current": yt_dlp["current"], "command": yt_dlp["command"]}
        )
    return found


#- what is on this machine -


def _pythons() -> dict:
    found = {}
    names = [f"python3.{minor}" for minor in range(9, 16)] + ["python3", "python"]
    for name in names:
        path = shutil.which(name)
        if not path:
            continue
        try:
            out = subprocess.run(
                [path, "-c", "import sys; print(sys.version_info[0], sys.version_info[1])"],
                capture_output=True,
                text=True,
                timeout=20,
            ).stdout.split()
            found.setdefault((int(out[0]), int(out[1])), path)
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            continue
    return found


def check() -> dict:
    system = this_system()
    home = nevera_home()
    venv = home / ".venv"
    venv_py = Path(venv_python(system, str(venv)))
    tools = {tool: shutil.which(tool) for tool in TOOLS}
    venv_bin = venv_py.parent
    for tool in ("yt-dlp",):
        local = venv_bin / (tool + (".exe" if system == "windows" else ""))
        if not tools[tool] and local.exists():
            tools[tool] = str(local)
    whisper = False
    if venv_py.exists():
        whisper = (
            subprocess.run(
                [str(venv_py), "-c", "import faster_whisper"], capture_output=True, timeout=60
            ).returncode
            == 0
        )
    python = pick_python(_pythons())
    has_apt = bool(shutil.which("apt-get"))
    steps = plan(
        system,
        tools,
        python,
        venv=str(venv),
        venv_exists=venv_py.exists(),
        has_brew=bool(shutil.which("brew")),
        has_apt=has_apt,
    )
    whisper_steps = (
        []
        if whisper
        else whisper_plan(
            system, python, str(venv), venv_exists=venv_py.exists(), has_apt=has_apt
        )
    )
    yt_dlp_version = _yt_dlp_version(tools["yt-dlp"])
    # brew's bin/ is a symlink: its real path says who installed it
    yt_dlp_path = str(Path(tools["yt-dlp"]).resolve()) if tools["yt-dlp"] else None
    yt_dlp_old = is_old(version_age(yt_dlp_version, _dt.date.today()))
    yt_dlp_update = update_command(system, yt_dlp_path, str(venv.resolve()))
    # yt-dlp only turns Deno on by itself; Node has to be asked for
    yt_dlp_args = ["--js-runtimes", "node"] if not tools["deno"] and tools["node"] else []
    return {
        "system": system,
        "home": str(home),
        "tools": tools,
        "commands": {
            "yt-dlp": tools["yt-dlp"],
            "ffmpeg": tools["ffmpeg"],
            "ffprobe": tools["ffprobe"],
            "python": str(venv_py) if whisper else None,
        },
        "yt_dlp_args": yt_dlp_args,
        "yt_dlp_version": yt_dlp_version,
        "yt_dlp_old": yt_dlp_old,
        "yt_dlp_update": yt_dlp_update,
        "version": SKILL_VERSION,
        "updates": updates(
            {
                "current": SKILL_VERSION,
                "latest": latest_version(),
                "command": skill_update_command(str(Path(__file__).resolve().parent)),
            },
            {"current": yt_dlp_version, "old": yt_dlp_old, "command": yt_dlp_update},
        ),
        "steps": steps,
        "whisper_steps": whisper_steps,
        "ready": not steps,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    print(json.dumps(check(), indent=2))
