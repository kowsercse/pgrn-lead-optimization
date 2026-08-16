"""Stage 1 — structural foundation: fetch/predict the PGRN-Sortilin complex, score its quality.

fetch_pdb_structure tries RCSB first (real Sortilin-Progranulin co-crystal structures exist,
e.g. 6X48/6X4H/6X3L). predict_complex_structure is the AI-cofolding fallback for targets with
no experimental structure. score_structure_quality branches on which of the two produced the
structure: experimental structures score via resolution/R-free (crystallographic quality
signals), predicted structures score via the folding engine's own pLDDT-style confidence
metric — DSSP secondary-structure percentages aren't a meaningful quality signal for either
origin, so this tool no longer uses it (see spec/fixes_0.md).
"""

import requests
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


_RESOLUTION_BUCKETS = (
    (1.5, "excellent"),
    (2.5, "good"),
    (3.5, "moderate"),
)

# proto-tools' predicted-metrics field names differ per engine; try in this
# order (each engine always emits at least one of these — see their Metrics
# classes' metric_spec "availability" notes).
_PLDDT_FIELDS = ("complex_plddt", "avg_plddt", "confidence_score")


def _resolution_bucket(resolution: float) -> str:
    for cutoff, label in _RESOLUTION_BUCKETS:
        if resolution <= cutoff:
            return label
    return "poor"


def _plddt_bucket(plddt: float) -> str:
    # proto-tools' predicted-metrics fields are normalized 0-1 (not AlphaFold's
    # 0-100), so the standard pLDDT confidence bands are divided by 100 here.
    if plddt >= 0.9:
        return "very_high"
    if plddt >= 0.7:
        return "confident"
    if plddt >= 0.5:
        return "low"
    return "very_low"


def _fetch_r_free(pdb_id: str) -> float | None:
    """R-free isn't exposed by proto-tools' PDB entry wrapper — fetch it directly."""
    response = requests.get(f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}", timeout=30)
    response.raise_for_status()
    refine = response.json().get("refine") or [{}]
    return refine[0].get("ls_R_factor_R_free")


def _score_experimental_structure(structure: dict) -> dict:
    resolution = structure.get("resolution")
    r_free = _fetch_r_free(structure["pdb_id"]) if structure.get("pdb_id") else None
    return {
        "origin": "experimental",
        "resolution_angstrom": resolution,
        "resolution_quality": _resolution_bucket(resolution) if resolution is not None else None,
        "r_free": r_free,
    }


def _score_predicted_structure(structure: dict) -> dict:
    metrics = structure.get("metrics", {})
    plddt = next((metrics[field] for field in _PLDDT_FIELDS if metrics.get(field) is not None), None)
    return {
        "origin": "predicted",
        "engine": structure.get("engine"),
        "plddt": plddt,
        "plddt_quality": _plddt_bucket(plddt) if plddt is not None else None,
        "metrics": metrics,
    }


@tool
def score_structure_quality(structure: dict) -> dict:
    """Score a structure/complex model's quality.

    Branches on structure origin (spec/fixes_0.md): experimental structures
    (fetch_pdb_structure output) score via resolution + R-free; predicted
    structures (predict_complex_structure output) score via the folding
    engine's own pLDDT-style confidence metric.
    """
    if "engine" in structure:
        return _score_predicted_structure(structure)
    if structure.get("found") is False:
        raise ValueError(f"structure {structure.get('pdb_id')!r} was not found — nothing to score")
    return _score_experimental_structure(structure)
