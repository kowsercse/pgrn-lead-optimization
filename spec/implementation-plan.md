# Implementation plan

Multi-stage plan for turning the Conductor pipeline
(`python/workflows/pgrn_sortilin_agents.py`) into a working PGRN-Sortilin
screening tool. All 10 tool bodies are now implemented (see Status below for
per-tool caveats); what's left is runtime validation against a live
Conductor server + LLM credential. See
[`conductor-workflow-spec.md`](conductor-workflow-spec.md) for agent
topology, [`therapeutic-hypothesis.md`](therapeutic-hypothesis.md) for the
underlying flow.

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
- Done: `assemble_screening_library` / `dock_library` / `validate_positive_controls`
  — proto-tools Vina docking, live-verified end-to-end against `6X48` (real
  affinities, e.g. -7.07 kcal/mol on a 4-compound smoke test). Search box is
  derived from `map_interface_pocket`'s residues (no reference-ligand
  coordinates needed). Receptor heteroatoms (waters, glycans, the
  co-crystallized ligand — including RCSB's "UNL" placeholder, which even
  `allow_bad_residues` can't parameterize) are stripped before docking
  (`workflows/tools/common.strip_heteroatoms`)
- Done: `filter_hits` — RDKit PAINS filtering + Butina scaffold-diversity
  clustering on Morgan fingerprints, live-verified
- Done: `predict_admet` — RDKit Lipinski Ro5 + QED proxy (no proto-tools
  ADMET tool exists), live-verified; pass/fail thresholds config-driven
- Done: `rank_and_handoff` — weighted composite ranking (docking affinity +
  QED + scaffold diversity), live-verified end-to-end; Benchling handoff
  uses the documented Apps + API OAuth2 client-credentials flow (real
  request shape, untested — no tenant credentials/schema IDs available here,
  gated off by default via `prioritization.benchling.enabled`)
- Done: runtime parameters (target IDs, thresholds, engine choices) moved to
  `python/config.yaml`, loaded via `python/workflows/config.py`
- All 10 pipeline tools now have real implementations (see per-tool caveats
  above: `mkdssp` binary missing locally, Boltz2/Chai1 need GPU/Modal
  compute, PubChem compound-numbering ambiguity, Benchling untested)

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

- [x] `assemble_screening_library` — candidate library (config-driven
  `.smi`/`.sdf` file) + known-ligand positive controls from Stage 2 (no
  decoys — the original hypothesis flow doesn't call for them, and a
  meaningful decoy set needs a real property-matched database we don't have)
- [x] `dock_library` — vina (proto-tools), search box from Stage 2's pocket
  residues
- [x] `validate_positive_controls` — rank/percentile check against
  `docking.positive_control_rank_threshold_pct`

## Stage 4 — Triage + ADMET

- [x] `filter_hits` — RDKit PAINS filter catalog + Butina clustering
  (`hit_triage.pains_filter`, `hit_triage.diversity_cluster_cutoff`, `hit_triage.top_n`)
- [x] `predict_admet` — RDKit descriptor-based proxy (Lipinski Ro5
  violations + QED); no proto-tools ADMET tool exists
  (`admet.lipinski_violations_max`, `admet.qed_min`)

## Stage 5 — Prioritization + runtime validation

- [x] `rank_and_handoff` — weighted composite rank (`prioritization.weights`,
  `prioritization.top_n`); Benchling handoff via Apps + API OAuth2
  client-credentials (`prioritization.benchling.*`, `BENCHLING_CLIENT_ID`/
  `BENCHLING_CLIENT_SECRET`), gated off (`enabled: false`) until a tenant
  schema/folder ID and credentials are available
- [x] Ran the full tool chain (fetch → interface → ligands → library →
  dock → triage → ADMET → rank) end-to-end in-process against `6X48` with a
  4-compound smoke library — every stage produced real, sane output
- [ ] Stand up a reachable Conductor server + LLM provider credential
- [ ] Run `literature_agent` (Paperclip MCP) live for the first time — first
  real runtime validation of the MCP wiring
- [ ] Run the full `pipeline` (Agent/AgentRuntime, not just the plain tool
  chain) end-to-end once a Conductor server + LLM credential are available

## Deferred

- Query thoroughness for `literature_agent`/`predict_complex_structure`
  (multi-query/iterative search) — see `conductor-workflow-spec.md`,
  "Open design questions"
- Experimental hit/no-hit feedback loop back into screening — explicitly
  out of scope per `conductor-workflow-spec.md`
