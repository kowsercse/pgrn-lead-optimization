# Implementation plan

Multi-stage plan for turning the barebone Conductor pipeline
(`python/workflows/pgrn_sortilin_agents.py`) into a working PGRN-Sortilin
screening tool. See [`conductor-workflow-spec.md`](conductor-workflow-spec.md)
for agent topology, [`therapeutic-hypothesis.md`](therapeutic-hypothesis.md)
for the underlying flow.

## Status

- Done: `fetch_pdb_structure` — proto-tools RCSB PDB entry + FASTA retrieval,
  live-verified against `6X48` and a not-found accession
- Done: `score_structure_quality` — proto-tools DSSP wrapper, live-verified up
  to dispatch; the local `mkdssp` binary isn't installed in this environment
  (proto-tools auto-provisions a `dssp_env` but still shells out to `mkdssp`),
  so the DSSP subprocess itself is untested here — install `mkdssp` to verify
- Done: `predict_complex_structure` — proto-tools Boltz2/Chai1 co-folding,
  engine selectable via `structure_prediction.engine` in config.yaml; needs
  GPU/Modal compute to actually run, untested at runtime
- Done: `literature_agent` wired to Paperclip's hosted MCP server — untested
  at runtime (no Conductor server/LLM credential exercised yet)
- Done: `map_interface_pocket` — biopython neighbor search, live-verified
  against `6X48`; ligand-vs-crystallization-artifact separation is
  config-driven (`interface.exclude_resnames`)
- Done: `search_known_ligands` — proto-tools PubChem lookup, live-verified;
  **known limitation** — generic paper compound numbering ("Compound 17")
  is ambiguous in PubChem's name index and can resolve to an unrelated
  paper's same-numbered compound (confirmed: "Compound 24" resolved to a
  Nav1.7 blocker, not the PGRN-Sortilin inhibitor). Prefer a SMILES/InChIKey
  from the source literature over the bare compound number when available.
- Done: runtime parameters (target IDs, thresholds, engine choices) moved to
  `python/config.yaml`, loaded via `python/workflows/config.py`
- Stub: all other tools (4 remaining)

## Stage 1 — Structural foundation

- [x] `fetch_pdb_structure` — RCSB entry + FASTA (proto-tools)
- [x] `score_structure_quality` — DSSP secondary-structure percentages
  (proto-tools `run_dssp_secondary_structure`); needs local `mkdssp` binary
- [x] `predict_complex_structure` — Boltz2/Chai1 co-folding (proto-tools),
  engine config-driven (`structure_prediction.engine`); only exercised when
  no PDB entry exists for the target

## Stage 2 — Interface + ligand mining

- [x] `map_interface_pocket` — bound-ligand contacts (biopython neighbor
  search, no existing proto-tools wrapper); falls back to inter-chain
  contacts when no ligand is bound (e.g. a predicted apo complex)
- [x] `search_known_ligands` — proto-tools `pubchem` lookup on
  `target.known_ligand_names`; see the compound-numbering caveat above

## Stage 3 — Screening library + docking

- [ ] `assemble_screening_library` — compile candidate library + positive
  controls (known ligands from Stage 2) + decoys
- [ ] `dock_library` — vina (proto-tools), dock against the Stage 2 pocket
- [ ] `validate_positive_controls` — re-dock known ligands, confirm expected
  pose/rank recovered before trusting the full screen

## Stage 4 — Triage + ADMET

- [ ] `filter_hits` — PAINS filtering + scaffold-diversity clustering on
  docking results
- [ ] `predict_admet` — no proto-tools ADMET tool identified yet; needs a
  source (RDKit descriptor-based proxy, or an external ADMET service) —
  open question, revisit at this stage

## Stage 5 — Prioritization + runtime validation

- [ ] `rank_and_handoff` — rank shortlist (score + ADMET + diversity);
  Benchling handoff needs API/MCP wiring (not yet done)
- [ ] Stand up a reachable Conductor server + LLM provider credential
- [ ] Run `literature_agent` (Paperclip MCP) live for the first time — first
  real runtime validation of the MCP wiring
- [ ] Run the full `pipeline` end-to-end once all tools are implemented

## Deferred

- Query thoroughness for `literature_agent`/`predict_complex_structure`
  (multi-query/iterative search) — see `conductor-workflow-spec.md`,
  "Open design questions"
- Experimental hit/no-hit feedback loop back into screening — explicitly
  out of scope per `conductor-workflow-spec.md`
