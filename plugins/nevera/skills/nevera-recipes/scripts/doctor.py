#!/usr/bin/env python3
"""What this machine has, and what to install so the skill can run.

    python3 doctor.py

Prints JSON: the system, the tools found, `commands` (the yt-dlp, ffmpeg and
venv Python to call), `yt_dlp_args` (flags every yt-dlp call needs here) and
`steps`: the install commands still missing, in order. No steps means ready.
It installs nothing itself: the steps are run one by one, where the Chef can
see them.

  - macOS: Homebrew (yt-dlp brings Deno, the JavaScript runtime YouTube needs).
  - Windows: winget (yt-dlp.yt-dlp, Gyan.FFmpeg, DenoLand.Deno, Python).
  - Linux: apt for ffmpeg, and yt-dlp from pip inside the venv, because the
    apt package falls behind YouTube within weeks.

Whisper is faster-whisper, in a venv of its own at ~/Downloads/nevera/.venv
(NEVERA_HOME overrides ~/Downloads/nevera), never in the system's Python. It
needs a Python between 3.9 and 3.14: 3.15 has no wheels yet for PyAV, one of
its dependencies.

Standard library only: it runs with any Python 3.9+.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from machine import nevera_home, this_system

PYTHON_RANGE = ((3, 9), (3, 14))
TOOLS = ("yt-dlp", "ffmpeg", "ffprobe", "deno", "node")


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
    whisper: bool,
    venv: str,
    has_brew: bool = True,
    has_apt: bool = True,
) -> list:
    """The install commands still missing. `tools` maps a tool to its path
    (missing or None when it is not there); `python` is a usable Python for
    the venv; `whisper` says whether the venv already has faster-whisper."""
    has = lambda tool: bool(tools.get(tool))  # noqa: E731
    js = has("deno") or has("node")
    steps: list = []
    pip_extra = ""

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
        if not python and not whisper:
            steps.append("brew install python@3.12")
            python = "python3.12"
    elif system == "windows":
        if not has("yt-dlp"):
            steps.append("winget install --id yt-dlp.yt-dlp -e")
        if not (has("ffmpeg") and has("ffprobe")):
            steps.append("winget install --id Gyan.FFmpeg -e")
        if not js:
            steps.append("winget install --id DenoLand.Deno -e")
        if not python and not whisper:
            steps.append("winget install --id Python.Python.3.12 -e")
            python = "py -3.12"
    else:
        apt = []
        if not (has("ffmpeg") and has("ffprobe")):
            apt.append("ffmpeg")
        if not whisper:
            # el python3 de Debian no trae el módulo venv sin python3-venv
            if not python:
                apt.append("python3")
                python = "python3"
            apt.append("python3-venv")
        if apt:
            # un Debian recién instalado no tiene listas de paquetes
            steps.append(
                f"sudo apt-get update && sudo apt-get install -y {' '.join(apt)}"
                if has_apt
                else f"Install {', '.join(apt)} with your package manager"
            )
        if not js:
            steps.append("curl -fsSL https://deno.land/install.sh | sh")
        if not has("yt-dlp"):
            pip_extra = ' "yt-dlp[default]"'

    if not whisper or pip_extra:
        if not whisper:
            steps.append(f"{python} -m venv {venv}")
        packages = ("faster-whisper" if not whisper else "") + pip_extra
        steps.append(f"{venv_python(system, venv)} -m pip install {packages.strip()}")
    return steps


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
    steps = plan(
        system,
        tools,
        python,
        whisper,
        venv=str(venv),
        has_brew=bool(shutil.which("brew")),
        has_apt=bool(shutil.which("apt-get")),
    )
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
        "steps": steps,
        "ready": not steps,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    print(json.dumps(check(), indent=2))
