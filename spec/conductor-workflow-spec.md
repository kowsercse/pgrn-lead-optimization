# PGRN–Sortilin screening — Conductor agent pipeline spec

Implements [`therapeutic-hypothesis.md`](therapeutic-hypothesis.md)'s "Computational
biologist review" flow as a Conductor agent pipeline, using the Conductor Python SDK.

## Scope

- In scope: agent topology — names, models, instructions, tool wiring, pipeline order
- In scope: Paperclip wired as an MCP tool (`mcp_tool()`) — see "MCP tool
  integration" below
- In scope: all 10 tool bodies — real implementations (proto-tools RCSB/Boltz2/
  Chai1/DSSP/PubChem/Vina, biopython, RDKit, Benchling REST) — live-verified
  against real PDB accessions (`6X48`/`6X4H`/`6X3L` — actual
  Sortilin-Progranulin co-crystal structures) except where noted in
  [`implementation-plan.md`](implementation-plan.md)'s Status section
  (`mkdssp` binary, GPU/Modal compute, Benchling tenant credentials)
- In scope: runtime parameters (target IDs, thresholds, engine/provider
  choices) are config-driven via `python/config.yaml` /
  `python/workflows/config.py`, not hardcoded in tool bodies
- Out of scope: the experimental hit/no-hit feedback loop back into screening
- Out of scope: deployment/serving config, Conductor task/workflow JSON authoring

## Dependency

- `conductor-python[agents]==2.0.0`
- Conductor server reachable via `CONDUCTOR_SERVER_URL` (local `main-conductor`, or
  Orkes Developer Edition)
- `CONDUCTOR_AGENT_LLM_MODEL` selects the LLM (defaults to `anthropic/claude-sonnet-4-6`)

## Agent topology

Sequential pipeline (`>>`), one agent per diagram stage:

| # | Agent | Tools (workflows/tools/ module) | Diagram stage |
| --- | --- | --- | --- |
| 1 | `literature_agent` | `mcp_tool` → Paperclip MCP server | Target validation |
| 2 | `structure_agent` | `fetch_pdb_structure`, `predict_complex_structure` (Boltz2/Chai1, not Biohub — see below), `score_structure_quality` (`structure.py`) | Structural modeling |
| 3 | `interface_agent` | `map_interface_pocket` (`interface.py`) | Interface mapping |
| 4 | `ligand_mining_agent` | `search_known_ligands` (`ligands.py`) | Ligand mining |
| 5 | `screening_agent` | `assemble_screening_library`, `dock_library`, `validate_positive_controls` (`screening.py`) | Library + docking (incl. validation gate) |
| 6 | `triage_agent` | `filter_hits` (`triage.py`) | Hit triage |
| 7 | `admet_agent` | `predict_admet` (`admet.py`) | ADMET profiling |
| 8 | `prioritization_agent` | `rank_and_handoff` (`prioritization.py`) | Prioritization |

- Decision points from the diagram (structure availability, docking-control
  validation) are delegated to each agent's own reasoning over its tool
  results — not hardcoded Python branching
- Feedback loop (prioritization → screening) is called out in
  `prioritization_agent`'s instructions as explicitly out of scope

## MCP tool integration

- **Paperclip**: hosted MCP server, already used for Claude Code (see
  `.mcp.json`) — `mcp_tool(server_url="https://paperclip.gxl.ai/mcp", ...)` on
  `literature_agent`, no worker process needed. Replaces the `search_paperclip`
  stub.
- **Biohub**: no hosted MCP server exists upstream (confirmed 15 Aug 2026 —
  REST API + `esm` SDK only, per `docs/tools.md`). Not worth standing up a
  local MCP server for this pipeline — would be called directly via its REST
  API/`esm` SDK if used (see note below).
- **Benchling**: hosted MCP server exists (`https://hackathon.mcp.bnchdev.org/mcp`)
  but is OAuth-redirect/interactive (per `docs/setup.md`) — doesn't fit a
  server-side Conductor `mcp_tool()` the way Paperclip's bearer-token auth
  does. `rank_and_handoff` instead uses Benchling's Apps + API OAuth2
  client-credentials REST flow directly.

## Note: `predict_complex_structure` uses Boltz2/Chai1, not Biohub

The original spec called for Biohub ESMFold2 (via the `esm` SDK) as the
co-folding fallback. Implemented instead with proto-tools' Boltz2/Chai1
wrappers (config-driven engine choice, `structure_prediction.engine` in
config.yaml) — proto-tools already has these ready to call, they handle
multi-chain complexes natively (ESMFold2 is more single-chain-oriented), and
it avoids requiring a separate `BIOHUB_API_KEY`. Biohub/ESMFold2 remains a
straightforward addition to the engine registry in
`workflows/tools/structure.py` if there's a reason to prefer it later.

## Open design questions

- Query thoroughness: `literature_agent` (Paperclip) and the Biohub-backed
  `predict_complex_structure` tool in `structure_agent` currently rely on a
  single LLM-issued query per run. May need agent instructions/strategy for
  broader, multi-query or iterative search (e.g. query reformulation,
  follow-up queries on weak results) rather than one-shot — revisit before
  implementation.

## File layout

- `python/workflows/pgrn_sortilin_agents.py` — agent definitions, pipeline
  wiring, `__main__` runner
- `python/workflows/config.py` + `python/config.yaml` — typed runtime config
  (target IDs, engine choices, thresholds), loaded by every tool module
- `python/workflows/tools/` — one module per pipeline stage: `structure.py`,
  `interface.py`, `ligands.py`, `screening.py`, `triage.py`, `admet.py`,
  `prioritization.py`, plus `common.py` for shared structure-loading helpers
