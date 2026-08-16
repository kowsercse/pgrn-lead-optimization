# pgrn-lead-optimization

Hackathon project for **re:AGENT**, 15–16 Aug 2026 (Stanford / Arc Institute).

Project direction is **not settled yet** — ask before assuming a target, modality, or pipeline.

## Repo layout

- [`python/`](python/) — Python code (`pyproject.toml`, `uv.lock`, `main.py`)
- [`docs/`](docs/) — project + tool documentation
- [`ui/`](ui/) — empty, reserved for a future UI
- [`spec/`](spec/) — spec docs for Claude

## Docs

- [`docs/tools.md`](docs/tools.md) — sponsor platforms, what each can do, source links
- [`docs/setup.md`](docs/setup.md) — step-by-step install instructions per tool
- [`docs/resources/`](docs/resources/) — original sponsor slides
- [`spec/therapeutic-hypothesis.md`](spec/therapeutic-hypothesis.md) — PGRN-Sortilin screening flow
- [`spec/conductor-workflow-spec.md`](spec/conductor-workflow-spec.md) — Conductor agent pipeline spec
- [`spec/implementation-plan.md`](spec/implementation-plan.md) — multi-stage plan for the remaining tools

## Requirements

- Python >=3.13

## Setup

```bash
cd python
uv sync
```

## Repo state

`python/main.py` is still an unmodified PyCharm stub. `ui/` is empty.
Real work lives in `python/workflows/pgrn_sortilin_agents.py` — a Conductor agent
pipeline for the PGRN-Sortilin screening hypothesis (see `spec/implementation-plan.md`
for what's implemented vs. stub).

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
