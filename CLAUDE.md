# CLAUDE.md - yestoall skills

This repo is **public** (github.com/yestoall/skills): anyone installs the
skills from it with `npx skills add` or as a Claude Code marketplace.

- **Everything here is in English, code comments included.** This is the
  exception to the yestoall workspace rule of comments in Spanish: the
  readers are strangers. The README has a complete Spanish twin, `README.es.md`: a change to one goes
  to the other.
- One plugin per app (`plugins/<app>/`), each skill in
  `plugins/<app>/skills/<skill>/`: its `SKILL.md` and its `scripts/`.
- The scripts run with a bare `python3` (3.9+) and the standard library
  only. They import each other as siblings (`from machine import …`), never
  as a package.
- Tests: `python3 -m unittest`. The Linux check runs in Docker (see the
  README).
- A release bumps the version in `plugins/<app>/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, the top of `CHANGELOG.md` and both
  READMEs, and tags it (`vX.Y.Z`). `tests/test_version.py` checks they all
  agree.
- Nothing here commits or pushes on its own: Nacho publishes.
