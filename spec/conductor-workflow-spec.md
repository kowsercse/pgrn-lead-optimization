# PGRN–Sortilin screening — Conductor agent pipeline spec

Implements [`therapeutic-hypothesis.md`](therapeutic-hypothesis.md)'s "Computational
biologist review" flow as a Conductor agent pipeline, using the Conductor Python SDK.

## Scope

- In scope: agent topology — names, models, instructions, tool wiring, pipeline order
- In scope: Paperclip wired as an MCP tool (`mcp_tool()`) — see "MCP tool
  integration" below
- Out of scope: remaining tool bodies (including Biohub) — stubs only
  (`raise NotImplementedError`), no real Biohub/PDB/PubChem/Vina/ADMET/
  Benchling integration
- Out of scope: the experimental hit/no-hit feedback loop back into screening
- Out of scope: deployment/serving config, Conductor task/workflow JSON authoring

## Dependency

- `conductor-python[agents]==2.0.0`
- Conductor server reachable via `CONDUCTOR_SERVER_URL` (local `main-conductor`, or
  Orkes Developer Edition)
- `CONDUCTOR_AGENT_LLM_MODEL` selects the LLM (defaults to `anthropic/claude-sonnet-4-6`)

## Agent topology

Sequential pipeline (`>>`), one agent per diagram stage:

| # | Agent | Tools (stub) | Diagram stage |
| --- | --- | --- | --- |
| 1 | `literature_agent` | `mcp_tool` → Paperclip MCP server | Target validation |
| 2 | `structure_agent` | `fetch_pdb_structure`, `predict_complex_structure` (Biohub API/`esm` SDK), `score_structure_quality` | Structural modeling |
| 3 | `interface_agent` | `map_interface_pocket` | Interface mapping |
| 4 | `ligand_mining_agent` | `search_known_ligands` | Ligand mining |
| 5 | `screening_agent` | `assemble_screening_library`, `dock_library`, `validate_positive_controls` | Library + docking (incl. validation gate) |
| 6 | `triage_agent` | `filter_hits` | Hit triage |
| 7 | `admet_agent` | `predict_admet` | ADMET profiling |
| 8 | `prioritization_agent` | `rank_and_handoff` | Prioritization |

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
  local MCP server for the barebone pipeline — called directly via its REST
  API/`esm` SDK instead, as the `predict_complex_structure` stub tool on
  `structure_agent`.

## Open design questions

- Query thoroughness: `literature_agent` (Paperclip) and the Biohub-backed
  `predict_complex_structure` tool in `structure_agent` currently rely on a
  single LLM-issued query per run. May need agent instructions/strategy for
  broader, multi-query or iterative search (e.g. query reformulation,
  follow-up queries on weak results) rather than one-shot — revisit before
  implementation.

## File layout

- `python/workflows/pgrn_sortilin_agents.py` — agent + tool definitions, pipeline
  wiring, `__main__` runner
