# `nora` — local dev process manager

One CLI to bootstrap and run this project's 3 local processes: the Conductor
OSS server, the Python agent worker, the UI dev server.

## Scope

- In scope: download + run Conductor OSS server (released jar, not built
  from source), download Temurin JDK 21, start/stop/restart/status/logs for
  server + worker + ui, one-shot `setup`
- Out of scope: Windows support, Docker, production hardening,
  HTTPS/auth, process supervision/auto-restart

## Confirmed facts (verified 16 Aug 2026)

- Conductor OSS ships a standalone Spring Boot jar via S3, not GitHub release
  assets: `https://conductor-server.s3.us-east-2.amazonaws.com/conductor-server-{VERSION}.jar`;
  `VERSION=latest` resolves directly (confirmed reachable, 465 MB). Matches
  the project's own bootstrap script
  (`~/orkes/conductor/main-conductor/conductor_server.sh`)
- Latest tagged release: `v3.32.1`
- Requires JDK 21+ (`conductor_server.sh` checks `java -version`)
- Default run — `java -jar conductor-server-<version>.jar --server.port=8080`
  — needs **no other config**; defaults to in-memory persistence. This is
  the "simplest configuration"
- Anthropic key wiring is already built into the jar:
  `conductor.ai.anthropic.api-key=${ANTHROPIC_API_KEY:}` in the server's
  `application.properties` — Spring Boot picks up the `ANTHROPIC_API_KEY` env
  var automatically. `nora` only needs to export it into the server
  subprocess's environment, no extra flag required
- Temurin JDK 21 downloads via Eclipse Adoptium API v3:
  `https://api.adoptium.net/v3/binary/latest/21/ga/{os}/{arch}/jdk/hotspot/normal/eclipse`
  → 307 redirect to a `.tar.gz` (mac/linux) or `.zip` (windows). Verified for
  `mac/aarch64` and `linux/x64` (currently resolves to `21.0.12+8`)
- `ui/` is no longer empty — already scaffolded (React 19 + Vite 7,
  `ui/package.json` has `dev`/`build`/`preview` npm scripts, `smiles-drawer`
  for rendering docked compounds). `nora ui` wires directly to these
  npm scripts
- No worker entrypoint exists yet — `pgrn_sortilin_agents.py`'s `__main__`
  does a one-shot `runtime.run(...)`, not a long-lived `runtime.serve(...)`.
  Adding one is part of this work (see Implementation notes)

## Design

### Language/location

- `./nora` — single executable script at repo root, Python 3 stdlib-only
  (`urllib`, `tarfile`, `subprocess`, `argparse`) — no third-party deps, so
  it runs before `uv sync` has ever happened. Shebang `#!/usr/bin/env python3`,
  `chmod +x`

### State layout

- `~/.nora/` — downloaded binaries, reusable across runs: `~/.nora/jdk-21/`,
  `~/.nora/conductor-server-<version>.jar`
- `.nora/` (repo root, gitignored) — this checkout's runtime state:
  `.nora/pids/{server,worker,ui}.pid`, `.nora/logs/{server,worker,ui}.log`

### Commands

- `./nora setup` — one-shot: download Temurin JDK 21 (skip if present),
  download the Conductor server jar (skip if present), `uv sync` under
  `python/`, `npm install` under `ui/` (skip with a message if
  `ui/package.json` is missing)
- `./nora server {start|stop|restart|status|logs}` — launches the downloaded
  JDK's `java -jar <conductor jar> --server.port=<port>` with
  `ANTHROPIC_API_KEY` (parsed from `.env`) exported into its environment;
  default port 8080, override via `--port`
- `./nora worker {start|stop|restart|status|logs}` — launches
  `uv run python -m workflows.worker` under `python/`, with
  `CONDUCTOR_SERVER_URL` pointed at the local server
- `./nora ui {start|stop|build|status|logs}` — `npm run dev` / `npm run
  build` under `ui/`; errors clearly if `ui/package.json` is missing
- `./nora start` / `./nora stop` / `./nora status` — all three, in order
  server → worker → ui (reverse order for stop)
- `./nora logs <server|worker|ui>` — tail the relevant log file
- Every long-lived process is backgrounded (`subprocess.Popen`, detached),
  PID written to `.nora/pids/*.pid`; `stop` reads the PID, sends SIGTERM,
  falls back to SIGKILL after a timeout; `status` checks PID liveness

### `.env` handling

- Add `ANTHROPIC_API_KEY=` placeholder to `.env.example` and `.env` (same
  pattern as the existing Paperclip/Biohub keys) — fill in the real value
  before `nora server start`
- `nora` parses `.env` itself (simple `KEY=VALUE` line parser, stdlib only)

## Implementation notes

- Add `python/workflows/worker.py` — thin entrypoint:
  `with AgentRuntime() as runtime: runtime.serve(pipeline)`, reading
  `CONDUCTOR_SERVER_URL` from the environment. Referenced by
  `nora worker start`
- `.gitignore`: add `.nora/`

## Non-goals

- No Windows support (Adoptium URL pattern would need a `.zip` + different
  extraction path; revisit if asked)
- No process supervision/auto-restart, no HTTPS, no auth in front of the
  local Conductor server — local dev tool only
