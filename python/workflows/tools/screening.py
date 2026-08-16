"""Stage 3 — screening library + docking: assemble candidates, dock, validate controls.

dock_library derives its Vina search box from the pocket residues map_interface_pocket
found (rather than needing the original bound ligand's coordinates), and lets Meeko
drop receptor heteroatoms (waters, glycans, the co-crystallized ligand) it can't
parameterize (`allow_bad_residues=True`) instead of requiring a hand-cleaned receptor.
"""

from io import StringIO

import numpy as np
from Bio.PDB import PDBParser
from proto_tools.entities.ligands import Ligands
from proto_tools.entities.structures import Structure
from proto_tools.tools.molecular_docking.vina import VinaDockingConfig, VinaDockingInput, VinaSearchBox, run_vina_docking

from conductor.ai.agents import tool
from workflows.config import load_config
from workflows.tools.common import load_structure_text, strip_heteroatoms

_MIN_BOX_SIZE_ANGSTROM = 20.0


@tool
def assemble_screening_library(known_ligands: dict) -> dict:
    """Assemble a screening library: config-driven candidate set + known-ligand positive controls.

    `known_ligands` is search_known_ligands output. The candidate set is read from
    `screening_library.candidate_smiles_file` in config.yaml (a .smi/.sdf file) —
    set that before running this stage.
    """
    cfg = load_config().screening_library
    if not cfg.candidate_smiles_file:
        raise ValueError(
            "screening_library.candidate_smiles_file is not set in config.yaml — point it "
            "at a .smi/.sdf virtual-screening candidate set before running this stage"
        )

    candidates = Ligands.from_file(cfg.candidate_smiles_file)
    compounds = [
        {"name": fragment.name or f"candidate_{i}", "smiles": fragment.smiles, "role": "candidate"}
        for i, fragment in enumerate(candidates.fragments)
    ]

    controls = [
        {"name": ligand.get("title") or ligand["query"], "smiles": ligand["smiles"], "role": "positive_control"}
        for ligand in known_ligands.get("known_ligands", [])
        if ligand.get("resolved") and ligand.get("smiles")
    ]

    return {
        "compounds": compounds + controls,
        "num_candidates": len(compounds),
        "num_positive_controls": len(controls),
    }


@tool
def dock_library(structure: dict, pocket: dict, library: dict) -> dict:
    """Dock a compound library against the pocket map_interface_pocket found.

    Search box is the padded bounding box of the pocket residues' CA atoms
    (padding + engine params from config.yaml's `docking` section).
    """
    cfg = load_config().docking
    pdb_text = load_structure_text(structure)
    model = PDBParser(QUIET=True).get_structure("receptor", StringIO(pdb_text))[0]

    pocket_keys = {(r["chain"], r["resnum"]) for r in pocket["pocket_residues"]}
    ca_coords = [
        atom.coord
        for chain in model
        for residue in chain
        if (chain.id, residue.id[1]) in pocket_keys
        for atom in residue
        if atom.get_name() == "CA"
    ]
    if not ca_coords:
        raise ValueError("no pocket-residue CA atoms found in the structure — check map_interface_pocket output")

    coords = np.asarray(ca_coords)
    padding = cfg.reference_ligand_padding_angstrom
    minima, maxima = coords.min(axis=0), coords.max(axis=0)
    center = tuple(((minima + maxima) / 2).tolist())
    size = tuple(max(float(v), _MIN_BOX_SIZE_ANGSTROM) for v in ((maxima - minima) + 2 * padding).tolist())

    receptor = Structure(structure=strip_heteroatoms(pdb_text))
    smiles = [compound["smiles"] for compound in library["compounds"] if compound.get("smiles")]

    output = run_vina_docking(
        VinaDockingInput(receptor=receptor, ligands=smiles, search_box=VinaSearchBox(center=center, size=size)),
        VinaDockingConfig(
            exhaustiveness=cfg.exhaustiveness,
            num_poses=cfg.num_poses,
            energy_range=cfg.energy_range,
            seed=cfg.seed,
            allow_bad_residues=True,
        ),
    )

    results = []
    for compound, ligand_result in zip(library["compounds"], output.results, strict=True):
        best_pose = ligand_result.poses[0] if ligand_result.poses else None
        results.append(
            {
                "name": compound.get("name"),
                "role": compound.get("role"),
                "smiles": ligand_result.smiles,
                "best_affinity_kcal_mol": best_pose.metrics.affinity if best_pose else None,
                "num_poses": len(ligand_result.poses),
                "warnings": ligand_result.warnings,
            }
        )
    results.sort(key=lambda r: (r["best_affinity_kcal_mol"] is None, r["best_affinity_kcal_mol"]))

    return {"search_box": {"center": center, "size": size}, "results": results}


@tool
def validate_positive_controls(docking_results: dict) -> dict:
    """Check whether known positive controls recovered a top-ranked affinity.

    A control "passes" if it ranks in the top `docking.positive_control_rank_threshold_pct`
    percent of the docked library by affinity. The screen is only trusted if every
    resolved positive control passes.
    """
    threshold_pct = load_config().docking.positive_control_rank_threshold_pct
    ranked = docking_results["results"]
    total = len(ranked)

    controls = []
    for rank, entry in enumerate(ranked, start=1):
        if entry.get("role") != "positive_control":
            continue
        percentile = 100.0 * rank / total if total else 100.0
        controls.append(
            {
                "name": entry.get("name"),
                "rank": rank,
                "percentile": percentile,
                "best_affinity_kcal_mol": entry.get("best_affinity_kcal_mol"),
                "passed": percentile <= threshold_pct,
            }
        )

    validated = bool(controls) and all(c["passed"] for c in controls)
    return {"validated": validated, "threshold_pct": threshold_pct, "controls": controls}
