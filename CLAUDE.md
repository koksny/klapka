# KLAPKA

Read **[AGENTS.md](AGENTS.md)**: it is the runbook for adding or fixing a phone, and it applies to
Claude sessions too. The standard itself is [docs/PIPELINE.md](docs/PIPELINE.md) (v1, approved by
Koks 2026-11-08); changing it needs Koks's yes.

Maintainer notes (Koks's machine):
- The image server is KLIF System CGI on `qwen-image-21`; `klapka.local.json` (not committed) points
  `tools/backend.py` at `klif-cli`.
- `refs/` holds input photos and `phones/**/work/` the working files; neither is committed.
- Prototype phase: no test suites; Koks approves visually (`klapka.py mark <id> --approved`).
- Commits and pushes only when Koks asks for them.
