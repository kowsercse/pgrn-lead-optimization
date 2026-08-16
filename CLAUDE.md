# pgrn-lead-optimization

Hackathon project for **re:AGENT**, 15–16 Aug 2026 (Stanford / Arc Institute).

Project direction is **not settled yet** — ask before assuming a target, modality, or pipeline.

## Repo layout

- [`python/`](python/) — Python code (`pyproject.toml`, `uv.lock`, `main.py`)
- [`docs/`](docs/) — project + tool documentation
- [`ui/`](ui/) — React + Vite dashboard for the screening pipeline
- [`spec/`](spec/) — spec docs for Claude

## Docs

- [`docs/getting-started.md`](docs/getting-started.md) — requirements + step-by-step to run everything
- [`docs/tools.md`](docs/tools.md) — sponsor platforms, what each can do, source links
- [`docs/setup.md`](docs/setup.md) — step-by-step install instructions per tool
- [`docs/resources/`](docs/resources/) — original sponsor slides
- [`spec/therapeutic-hypothesis.md`](spec/therapeutic-hypothesis.md) — PGRN-Sortilin screening flow
- [`spec/conductor-workflow-spec.md`](spec/conductor-workflow-spec.md) — Conductor agent pipeline spec
- [`spec/implementation-plan.md`](spec/implementation-plan.md) — multi-stage tool implementation plan + status
- [`spec/nora-tool-spec.md`](spec/nora-tool-spec.md) — `nora` local dev process manager (Conductor server, worker, UI)
- [`spec/ui-conductor-client-spec.md`](spec/ui-conductor-client-spec.md) — UI's browser-side Conductor agent API client (no backend)

## Requirements

- Python >=3.13

## Setup

```bash
./nora setup   # downloads Temurin JDK 21 + Conductor server jar, uv sync, npm install
./nora start   # starts the Conductor server, python worker, and UI dev server
```

See [`spec/nora-tool-spec.md`](spec/nora-tool-spec.md) for the full command
surface (`./nora {server,worker,ui} {start,stop,restart,status,logs}`).
Requires `ANTHROPIC_API_KEY` set in `.env` for LLM-driven agent runs.

## Repo state

`python/main.py` is still an unmodified PyCharm stub. Real work lives in
`python/workflows/` — a Conductor agent pipeline (`pgrn_sortilin_agents.py`)
for the PGRN-Sortilin screening hypothesis, with all tool bodies implemented
in `python/workflows/tools/` and runtime parameters config-driven via
`python/config.yaml` (see `spec/implementation-plan.md` for per-tool
status/caveats). The worker (`python/workflows/worker.py`) has been run live
against a local Conductor server (via `nora`) and successfully registered
all tools; no LLM-driven agent run has happened yet (needs
`ANTHROPIC_API_KEY`).

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
