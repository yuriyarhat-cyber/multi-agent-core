# Repository Skills

This folder mirrors the local Codex skills you want to keep in GitHub and move to another computer.

What is included:
- your repo-level skills
- custom marketing, website, bot, and sales skills
- other non-system skills currently present in `~/.codex/skills`

What is not included:
- `.system` skills managed by Codex itself

## Install on another computer

Clone this repository, then run:

```bash
python scripts/install_codex_skills.py
```

By default this copies the repository skills into:

```text
~/.codex/skills
```

If you want to overwrite existing skills in the target:

```bash
python scripts/install_codex_skills.py --force
```

## Notes

- The script copies skill folders as-is.
- Existing target folders are skipped unless you pass `--force`.
- After copying, restart Codex if it is already open.
