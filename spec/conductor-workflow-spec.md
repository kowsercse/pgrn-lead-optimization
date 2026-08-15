# PGRN–Sortilin screening — Conductor agent pipeline spec

Implements [`therapeutic-hypothesis.md`](therapeutic-hypothesis.md)'s "Computational
biologist review" flow as a Conductor agent pipeline, using the Conductor Python SDK.

## Scope

- In scope: agent topology — names, models, instructions, tool wiring, pipeline order
- Out of scope: tool bodies — stubs only (`raise NotImplementedError`), no real
  Paperclip/PDB/PubChem/Vina/ADMET/Benchling integration
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
| 1 | `literature_agent` | `search_paperclip` | Target validation |
| 2 | `structure_agent` | `fetch_pdb_structure`, `predict_complex_structure`, `score_structure_quality` | Structural modeling |
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

## File layout

- `python/workflows/pgrn_sortilin_agents.py` — agent + tool definitions, pipeline
  wiring, `__main__` runner
