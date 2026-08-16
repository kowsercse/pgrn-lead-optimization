# UI → Conductor agent API (browser client, no API server)

`ui/` calls the Conductor server's REST API directly from the browser to
start the `pgrn_sortilin_screening_pipeline` agent with a prompt and show
its output once complete — no backend of our own.

## Confirmed facts (verified 16 Aug 2026, live server)

- Conductor's server has **no CORS configuration anywhere in its codebase**
  — cross-origin requests get a flat 403 ("Invalid CORS request"). Not
  fixable via a server flag/property; would need a source change (out of
  scope — released jar, not built from source)
- Fix: Vite's built-in dev-server proxy (`ui/vite.config.js`, `server.proxy`)
  forwards `/api/*` to the Conductor server server-side — the browser only
  ever talks to its own origin (5173), so CORS never triggers. This is
  existing dev-server config, not a new server/process
- Start: `POST /api/workflow` — body
  `{"name": "<agent name>", "input": {"prompt": "...", "media": [], "session_id": "", "context": {}}}`,
  response is the plain-text execution ID. This is Conductor's standard
  workflow-start endpoint, not something agent-specific — works because the
  agent is pre-registered as a named workflow (the worker's `serve()` call
  registers it; see `python/workflows/worker.py`)
- Poll: `GET /api/workflow/{executionId}?includeTasks=false` — JSON with
  `status` (`RUNNING`/`COMPLETED`/`FAILED`/`TERMINATED`/`TIMED_OUT`),
  `output`, `reasonForIncompletion` on failure
- **Known limitation, not fixed here**: `literature_agent`'s Paperclip
  `mcp_tool()` fails with `401 Not authenticated` regardless of whether
  `PAPERCLIP_API_KEY` is set in the Conductor server's own process
  environment (tried — no effect) or in `.env`. `PUT /api/secrets/{key}`
  501s with "env-backed secrets are read-only", and the Python SDK's
  `_register_workflow_credentials` turned out to be in-memory
  Python-process-local state (unrelated to the server-side MCP call) — the
  actual resolution mechanism for `${VAR}` in an `mcp_tool()`'s `headers`
  wasn't identified. This is a **pre-existing pipeline issue**, not
  something the browser-vs-Python-SDK choice of *how* to start the workflow
  affects — a `runtime.run()` call would hit the same wall today. Revisit
  when literature_agent's output is actually needed end-to-end.

## Design

- `ui/src/conductor.js` — `startAgent(prompt)`, `pollUntilComplete(executionId, {onTick})`,
  `describeOutput(workflow)`. No dependencies beyond `fetch`.
- `ui/vite.config.js` — proxies `/api` to `VITE_CONDUCTOR_SERVER_URL`
  (default `http://localhost:8080`)
- `App.jsx` owns the chat message list; `Composer` calls back with the
  submitted prompt instead of just clearing itself; `ChatThread` renders
  real messages instead of the hardcoded mock

## Non-goals

- Not wiring `ResultsTable`/`MoleculeImage` to real per-compound data — the
  final agent output is LLM-generated prose/JSON of unknown-until-tested
  shape (no `ANTHROPIC_API_KEY` set yet to verify against), so mapping it
  into the compounds table would be guesswork. Revisit once a real run
  completes and the actual output shape is known.
- Production deployment (same-origin serving without Vite) is out of scope
  — this is a local dev tool, matches `nora`'s scope
