# Getting Started

## Requirements

- macOS or Linux (no Windows support)
- Python >=3.13, [`uv`](https://docs.astral.sh/uv/)
- Node.js + npm
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))

## Steps

1. Clone the repo
2. Copy `.env.example` to `.env`, fill in `ANTHROPIC_API_KEY`
3. `./nora setup` — downloads Temurin JDK 21 + Conductor server jar, installs python/ui deps
4. `./nora start` — starts the Conductor server, python worker, and UI dev server
5. Open the UI: http://localhost:5173
6. Conductor server: http://localhost:8080
7. `./nora stop` when done

See [`nora-tool-spec.md`](../spec/nora-tool-spec.md) for the full command
surface (`./nora {server,worker,ui} {start,stop,restart,status,logs}`).
