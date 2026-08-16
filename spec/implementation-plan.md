# Implementation plan

Multi-stage plan for turning the Conductor pipeline
(`python/workflows/pgrn_sortilin_agents.py`) into a working PGRN-Sortilin
screening tool. All 10 tool bodies are now implemented (see Status below for
per-tool caveats); what's left is runtime validation against a live
Conductor server + LLM credential. See
[`conductor-workflow-spec.md`](conductor-workflow-spec.md) for agent
topology, [`therapeutic-hypothesis.md`](therapeutic-hypothesis.md) for the
underlying flow.

## fixes_0.md (David Yang's feedback) — implemented

Both requests in [`fixes_0.md`](fixes_0.md) are done:

- `score_structure_quality` now branches on structure origin instead of
  always running DSSP — see Stage 1 below
- `assemble_screening_library` + `dock_library` replaced with a single
  `odesign_screening` tool (generative candidates, docked every N
  generations) — see Stage 3 below

**Known gap this introduces**: `filter_hits` drops any result with no
`best_affinity_kcal_mol` — that's fine for the old dock-everything flow
(every candidate had one), but most `odesign_screening` candidates come
from non-docked generations and have `best_affinity_kcal_mol: None`
(scored only by `composite_score`). Right now those get filtered out
before triage. Revisit `filter_hits` to rank by `composite_score` with
missing-docking handled gracefully — not done here since it wasn't part
of the fixes_0.md ask.

## Status

- Done: `fetch_pdb_structure` — proto-tools RCSB PDB entry + FASTA retrieval,
  live-verified against `6X48` and a not-found accession
- Done: `score_structure_quality` — branches by structure origin
  (spec/fixes_0.md): experimental structures score via resolution + R-free
  (R-free fetched directly from RCSB's REST API — not exposed by
  proto-tools' entry wrapper, confirmed via `6X48`: resolution 2.9 Å,
  R-free 0.2524); predicted structures score via the folding engine's own
  pLDDT-style metric (`complex_plddt`/`avg_plddt`/`confidence_score`,
  whichever the engine provides). No longer uses DSSP — dropped the
  `mkdssp`-binary dependency entirely.
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
- Done: `odesign_screening` / `validate_positive_controls` — generative
  screening (spec/fixes_0.md) replacing the old static-library assemble+dock
  flow. Docks every `odesign.dock_every_n_generations` generations (Vina),
  combining ODesign's own model score, the docking score, and similarity to
  known-ligand seeds into a composite score. Search box is derived from
  `map_interface_pocket`'s residues (no reference-ligand coordinates
  needed); receptor heteroatoms (waters, glycans, the co-crystallized
  ligand — including RCSB's "UNL" placeholder, which even
  `allow_bad_residues` can't parameterize) are stripped before docking
  (`workflows/tools/common.strip_heteroatoms`). ODesign generation itself
  (`_odesign_generate`) is a stub — not yet installed; everything else
  (periodic docking, similarity scoring, composite scoring) is live-verified
  against `6X48` with a monkey-patched generator. **Found and fixed a real
  bug during that verification**: Vina/RDKit canonicalizes each ligand's
  SMILES before echoing it back (e.g. `CC1=C(C(=NO1)...)` → `Cc1onc(...)`),
  so keying results by the *returned* SMILES silently drops any lookup by
  the *original* input string — fixed by matching positionally instead
  (same approach the old `dock_library` already used, just not carried
  forward when this was rewritten)
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
  above: ODesign generation not yet installed, Boltz2/Chai1 need GPU/Modal
  compute, PubChem compound-numbering ambiguity, Benchling untested)

## Stage 1 — Structural foundation

- [x] `fetch_pdb_structure` — RCSB entry + FASTA (proto-tools)
- [x] `score_structure_quality` — branches by structure origin: resolution +
  R-free for experimental structures, pLDDT-style confidence for predicted
  ones (spec/fixes_0.md)
- [x] `predict_complex_structure` — Boltz2/Chai1 co-folding (proto-tools),
  engine config-driven (`structure_prediction.engine`); only exercised when
  no PDB entry exists for the target

## Stage 2 — Interface + ligand mining

- [x] `map_interface_pocket` — bound-ligand contacts (biopython neighbor
  search, no existing proto-tools wrapper); falls back to inter-chain
  contacts when no ligand is bound (e.g. a predicted apo complex)
- [x] `search_known_ligands` — proto-tools `pubchem` lookup on
  `target.known_ligand_names`; see the compound-numbering caveat above

## Stage 3 — Generative screening + docking

- [x] `odesign_screening` — generates candidates over `odesign.num_generations`
  generations (ODesign model call is a stub, not yet installed), docking
  every `odesign.dock_every_n_generations` (vina, proto-tools) against
  Stage 2's pocket; known-ligand positive controls from Stage 2 ride along,
  docked every run (spec/fixes_0.md — replaces the old
  assemble_screening_library + dock_library)
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
- [x] Stand up a reachable Conductor server — done via `./nora server start`
  (see [`nora-tool-spec.md`](nora-tool-spec.md)); no LLM credential set yet
  (`ANTHROPIC_API_KEY` still blank in `.env`)
- [x] `python/workflows/worker.py` (`AgentRuntime().serve(pipeline)`) live
  against that server — all 11 tools across all 8 agents registered and
  polled correctly, first real runtime validation of the Conductor wiring
  (not just in-process Python calls)
- [ ] Run `literature_agent` (Paperclip MCP) live for the first time —
  blocked on `ANTHROPIC_API_KEY`; worker registration alone doesn't exercise
  the LLM-driven agent loop
- [ ] Run the full `pipeline` end-to-end via `runtime.run(...)` (an actual
  agent conversation, not just worker registration) once
  `ANTHROPIC_API_KEY` is set

## Deferred

- Query thoroughness for `literature_agent`/`predict_complex_structure`
  (multi-query/iterative search) — see `conductor-workflow-spec.md`,
  "Open design questions"
- Experimental hit/no-hit feedback loop back into screening — explicitly
  out of scope per `conductor-workflow-spec.md`
