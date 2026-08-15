# Setup Instructions

## This project
1. `cd python`
2. `uv sync` — installs everything in `pyproject.toml`: `proto-tools`, `esm`
3. Run `modal setup` to link Modal compute
4. Get a Biohub API key, store as `BIOHUB_API_KEY` (see `biohub` skill)

## Proto — `proto-tools`
1. `pip install git+https://github.com/evo-design/proto-tools.git`

## Proto — `proto-language` (alternative to above)
1. `git clone https://github.com/evo-design/proto-language.git`
2. `cd proto-language`
3. `pip install -e .`

## Modal
1. `pip install modal`
2. `modal setup`

## Biohub Platform
1. Go to `biohub.ai`
2. Developer console → Sign up
3. Create API key

## Benchling — MCP
1. Log in at `https://hackathon.bnchdev.org` (Google Sign-In)
2. Add server URL to MCP client: `https://hackathon.mcp.bnchdev.org/mcp`
3. Authenticate via OAuth redirect

## Benchling — Apps + API
1. Log in at `https://hackathon.bnchdev.org`
2. Developer Console → Apps → Create
3. Copy `client_id` and `client_secret`
4. Call REST endpoints / subscribe to Events

## Benchling — AI
1. Log in at `https://hackathon.bnchdev.org`
2. Open agent via star icon
3. Ask question

## BenchFlow
1. `uv tool install --python 3.12 --upgrade benchflow`
2. Open `github.com/benchflow-ai/benchflow`
3. Follow README

## Sundial — Desktop
1. Download at `sundial.md/download`
2. Open folder with ⌘O

## Sundial — Web
1. Go to `sundial.md/templates`
2. Pick template

## Paperclip — Local CLI
1. `curl -fsSL https://paperclip.gxl.ai/install.sh | bash`
2. Sign in when prompted
3. `paperclip install` → select agent
4. Start new session, mention `/paperclip`

## Paperclip — Hosted MCP
1. Add server URL to MCP client: `https://paperclip.gxl.ai/mcp`
2. Complete browser sign-in
3. Keys at `paperclip.gxl.ai/keys`
4. Copy `.env.example` to `.env`, store key as `PAPERCLIP_API_KEY`
