# PGRN–Sortilin screening — Conductor agent pipeline spec

Implements [`therapeutic-hypothesis.md`](therapeutic-hypothesis.md)'s "Computational
biologist review" flow as a Conductor agent pipeline, using the Conductor Python SDK.

## Scope

- In scope: agent topology — names, models, instructions, tool wiring, pipeline order
- In scope: Paperclip and Biohub wired as MCP tools (`mcp_tool()`), not custom
  stub functions — see "MCP tool integration" below
- Out of scope: remaining tool bodies — stubs only (`raise NotImplementedError`),
  no real PDB/PubChem/Vina/ADMET/Benchling integration
- Out of scope: the Biohub MCP server itself (not yet built)
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
| 2 | `structure_agent` | `fetch_pdb_structure`, `mcp_tool` → Biohub MCP server, `score_structure_quality` | Structural modeling |
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

Paperclip and Biohub are wired in as MCP tools (`mcp_tool()`, Conductor's
`ListMcpTools`/`CallMcpTool` system tasks), not custom `@tool` Python
functions — no worker process needed for either.

- **Paperclip**: hosted MCP server, already used for Claude Code (see
  `.mcp.json`) — `mcp_tool(server_url="https://paperclip.gxl.ai/mcp", ...)` on
  `literature_agent`. Replaces the `search_paperclip` stub.
- **Biohub**: no hosted MCP server exists upstream (REST + `esm` SDK only, per
  `docs/tools.md`). Requires standing up a local MCP server that wraps the
  `esm` SDK (ESMFold2/ESMC/ESM Atlas) and exposes it over MCP; `structure_agent`
  then points `mcp_tool(server_url="http://localhost:<port>/mcp", ...)` at it.
  Server itself is out of scope for the barebone pipeline — not yet built.

## Open design questions

- Query thoroughness: `literature_agent` (Paperclip) and the Biohub-backed
  tool in `structure_agent` currently rely on a single LLM-issued query per
  run. May need agent instructions/strategy for broader, multi-query or
  iterative search (e.g. query reformulation, follow-up queries on weak
  results) rather than one-shot — revisit before implementation.

## File layout

- `python/workflows/pgrn_sortilin_agents.py` — agent + tool definitions, pipeline
  wiring, `__main__` runner
