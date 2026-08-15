# pgrn-lead-optimization

Hackathon project for **re:AGENT**, 15–16 Aug 2026 (Stanford / Arc Institute).

Project direction is **not settled yet** — ask before assuming a target, modality, or pipeline.

## Docs

- [`docs/tools.md`](docs/tools.md) — sponsor platforms, what each can do, source links
- [`docs/setup.md`](docs/setup.md) — step-by-step install instructions per tool
- [`docs/resources/`](docs/resources/) — original sponsor slides

## Requirements

- Python >=3.13

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Repo state

Still a scaffold — `main.py` is an unmodified PyCharm stub, `pyproject.toml` has no dependencies
yet. No source layout exists; nothing to preserve conventions from.

## Documentation style

- No prose, no explanation
- Just facts / step-by-step instructions
- Bullet points, not paragraphs
- As concise as possible
- Applies to all docs in this repo (`docs/*.md`, README, CLAUDE.md)

## Git

- Remote `origin` points to `git@github-personal:kowsercse/pgrn-lead-optimization.git`, using the
  `github-personal` SSH host alias (not the default `github.com` key, which is a different
  identity).
- Local `user.email` is set to `kowsercse@gmail.com` for this repo only (global git email is a
  work address).
