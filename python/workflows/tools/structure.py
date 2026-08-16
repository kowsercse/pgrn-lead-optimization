"""Stage 1 — structural foundation: fetch/predict the PGRN-Sortilin complex, score its quality.

fetch_pdb_structure tries RCSB first (real Sortilin-Progranulin co-crystal structures exist,
e.g. 6X48/6X4H/6X3L). predict_complex_structure is the AI-cofolding fallback for targets with
no experimental structure. score_structure_quality runs DSSP on whichever structure is used —
mainly useful on the predicted-structure fallback path, since crystal structures are already
solved.
"""

from proto_tools.entities.structures import SingleChainSelection, Structure
from proto_tools.tools.database_retrieval.pdb.fetch_entry import (
    PdbFetchEntryConfig,
    PdbFetchEntryInput,
    run_pdb_fetch_entry,
)
from proto_tools.tools.database_retrieval.pdb.fetch_fasta import (
    PdbFetchFastaConfig,
    PdbFetchFastaInput,
    run_pdb_fetch_fasta,
)
from proto_tools.tools.structure_prediction.boltz2 import Boltz2Config, Boltz2Input, run_boltz2
from proto_tools.tools.structure_prediction.chai1 import Chai1Config, Chai1Input, run_chai1
from proto_tools.tools.structure_scoring.dssp import (
    DSSPSecondaryStructureConfig,
    DSSPSecondaryStructureInput,
    DSSPStructureInput,
    run_dssp_secondary_structure,
)

from conductor.ai.agents import tool
from workflows.config import load_config

# engine name -> (Input class, Config class, run function), all sharing the Boltz2Input-style
# `complexes: list[list[str]]` shape for a two-chain complex prediction
_STRUCTURE_PREDICTION_ENGINES = {
    "boltz2": (Boltz2Input, Boltz2Config, run_boltz2),
    "chai1": (Chai1Input, Chai1Config, run_chai1),
}


@tool
def fetch_pdb_structure(pdb_id: str) -> dict:
    """Fetch experimental structure metadata, chain sequences, and a coordinates
    file URL for a PDB accession (e.g. '6X48')."""
    entry = run_pdb_fetch_entry(PdbFetchEntryInput(pdb_id=pdb_id), PdbFetchEntryConfig())
    if not entry.title:
        return {"pdb_id": pdb_id.upper(), "found": False}

    fasta = run_pdb_fetch_fasta(PdbFetchFastaInput(pdb_id=pdb_id), PdbFetchFastaConfig())

    return {
        "pdb_id": pdb_id.upper(),
        "found": True,
        "title": entry.title,
        "method": entry.method,
        "resolution": entry.resolution,
        "chains": [chain.model_dump() for chain in fasta.chains],
        "structure_url": f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb",
    }


@tool
def predict_complex_structure(sequence_a: str, sequence_b: str) -> dict:
    """Co-fold two sequences into a predicted complex structure.

    Engine and MSA/sampling parameters come from config.yaml's `structure_prediction`
    section (default: Boltz2) — only exercised when fetch_pdb_structure finds no
    experimental structure for the target.
    """
    cfg = load_config().structure_prediction
    if cfg.engine not in _STRUCTURE_PREDICTION_ENGINES:
        raise ValueError(f"Unknown structure_prediction.engine {cfg.engine!r}; choices: {sorted(_STRUCTURE_PREDICTION_ENGINES)}")
    input_cls, config_cls, run_fn = _STRUCTURE_PREDICTION_ENGINES[cfg.engine]

    inputs = input_cls(complexes=[[sequence_a, sequence_b]])
    config = config_cls(
        use_msa=cfg.use_msa,
        recycling_steps=cfg.recycling_steps,
        sampling_steps=cfg.sampling_steps,
        diffusion_samples=cfg.diffusion_samples,
    )
    output = run_fn(inputs, config)
    structure = output.structures[0]  # Structure instance, one per input complex

    return {
        "engine": cfg.engine,
        "structure_pdb": structure.structure_pdb,
        "chain_ids": structure.get_chain_ids(),
        "metrics": dict(structure.metrics),
    }


@tool
def score_structure_quality(structure: dict) -> dict:
    """Score a structure/complex model's secondary-structure quality with DSSP.

    Expects `structure` to carry either `structure_url` (fetch_pdb_structure output)
    or `structure_pdb` (predict_complex_structure output), plus a `chains` list of
    chain IDs; falls back to config.yaml's `structure_quality.chains` when omitted.
    """
    source = structure.get("structure_url") or structure.get("structure_pdb")
    if not source:
        raise ValueError("structure must contain 'structure_url' or 'structure_pdb'")
    is_url = bool(structure.get("structure_url"))

    chain_ids = load_config().structure_quality.chains
    if not chain_ids:
        chain_ids = (Structure.from_url(source) if is_url else Structure(structure=source)).get_chain_ids()

    results = []
    for chain_id in chain_ids:
        base = Structure.from_url(source) if is_url else Structure(structure=source)
        dssp_input = DSSPSecondaryStructureInput(
            inputs=[DSSPStructureInput(structure=base, chain=SingleChainSelection(chain=chain_id))]
        )
        output = run_dssp_secondary_structure(dssp_input, DSSPSecondaryStructureConfig())
        metrics = output.results[0]
        results.append(
            {
                "chain_id": chain_id,
                "helix_pct": metrics.helix_pct,
                "sheet_pct": metrics.sheet_pct,
                "loop_pct": metrics.loop_pct,
            }
        )

    return {"per_chain": results}
