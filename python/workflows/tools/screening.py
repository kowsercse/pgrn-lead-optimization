"""Stage 3 — generative screening + docking, validate controls.

odesign_screening replaces the old static-library assemble_screening_library +
dock_library flow (spec/fixes_0.md): instead of docking every candidate in a
pre-assembled library, it proposes candidates over several generations via the
ODesign model, docking (Vina) only every `odesign.dock_every_n_generations`
generations against the pocket map_interface_pocket found — Vina's search box
is derived from the pocket residues (no reference-ligand coordinates needed),
and Meeko drops receptor heteroatoms it can't parameterize via a pre-cleaned
receptor (`strip_heteroatoms`) rather than a hand-rolled `allow_bad_residues`
workaround, since that doesn't cover RCSB's "UNL" placeholder ligand.

ODesign itself is not yet installed — `_odesign_generate` is a stub (see its
docstring). Everything else here (periodic docking, similarity-to-known-ligand
guidance, score combination) is real and independently testable once it's
plugged in.
"""

from io import StringIO

import numpy as np
from Bio.PDB import PDBParser
from proto_tools.entities.structures import Structure
from proto_tools.tools.molecular_docking.vina import VinaDockingConfig, VinaDockingInput, VinaSearchBox, run_vina_docking
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

from conductor.ai.agents import tool
from workflows.config import load_config
from workflows.tools.common import load_structure_text, strip_heteroatoms

_MIN_BOX_SIZE_ANGSTROM = 20.0
_MORGAN_GENERATOR = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


def _odesign_generate(seed_smiles: list[str], generation: int, population_size: int) -> list[dict]:
    """Propose `population_size` candidate ligands via the ODesign model.

    Not yet installed — this is a placeholder (spec/fixes_0.md). Real
    integration should call ODesign's generation API, seeded from
    `seed_smiles` (or guided by similarity to them), returning one dict per
    candidate with at least `smiles` and `model_score` (the model's own
    predicted binding-affinity/complementarity score, 0-1 higher-is-better,
    to match `ligand_similarity`'s scale).
    """
    raise NotImplementedError(
        "TODO: call the ODesign model's generation API (not yet installed) — "
        f"seed from {len(seed_smiles)} known ligand(s), generation {generation}, "
        f"population_size={population_size}; return [{{'smiles': ..., 'model_score': ...}}, ...]"
    )


def _vina_search_box(structure: dict, pocket: dict) -> tuple[tuple, tuple, str]:
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
    padding = load_config().docking.reference_ligand_padding_angstrom
    minima, maxima = coords.min(axis=0), coords.max(axis=0)
    center = tuple(((minima + maxima) / 2).tolist())
    size = tuple(max(float(v), _MIN_BOX_SIZE_ANGSTROM) for v in ((maxima - minima) + 2 * padding).tolist())
    return center, size, pdb_text


def _dock_smiles(structure: dict, pocket: dict, smiles_list: list[str]) -> list[float | None]:
    """Dock a batch of SMILES against the pocket; returns affinities in the same order as smiles_list.

    Positional, not keyed by the echoed SMILES: Vina/RDKit canonicalizes each
    ligand's SMILES before echoing it back (e.g. `CC1=C(C(=NO1)...)` comes
    back as `Cc1onc(...)`), so a dict keyed by the *returned* SMILES silently
    breaks any lookup by the original input string.
    """
    if not smiles_list:
        return []
    cfg = load_config().docking
    center, size, pdb_text = _vina_search_box(structure, pocket)
    receptor = Structure(structure=strip_heteroatoms(pdb_text))

    output = run_vina_docking(
        VinaDockingInput(receptor=receptor, ligands=smiles_list, search_box=VinaSearchBox(center=center, size=size)),
        VinaDockingConfig(
            exhaustiveness=cfg.exhaustiveness,
            num_poses=cfg.num_poses,
            energy_range=cfg.energy_range,
            seed=cfg.seed,
            allow_bad_residues=True,
        ),
    )
    return [
        (ligand_result.poses[0].metrics.affinity if ligand_result.poses else None) for ligand_result in output.results
    ]


def _normalize_affinity(affinity: float, best: float, worst: float) -> float:
    return max(0.0, min(1.0, (worst - affinity) / (worst - best)))


def _max_similarity(smiles: str, seed_smiles: list[str]) -> float:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return 0.0
    fp = _MORGAN_GENERATOR.GetFingerprint(mol)
    seed_fps = [_MORGAN_GENERATOR.GetFingerprint(seed_mol) for s in seed_smiles if (seed_mol := Chem.MolFromSmiles(s))]
    if not seed_fps:
        return 0.0
    return max(DataStructs.BulkTanimotoSimilarity(fp, seed_fps))


def _composite_score(model_score: float | None, affinity: float | None, similarity: float, weights: dict, cfg) -> float:
    components = {"ligand_similarity": similarity}
    if model_score is not None:
        components["model_score"] = model_score
    if affinity is not None:
        components["docking_score"] = _normalize_affinity(affinity, cfg.affinity_best_kcal_mol, cfg.affinity_worst_kcal_mol)
    total_weight = sum(weights.get(key, 0.0) for key in components)
    if total_weight == 0:
        return 0.0
    return sum(weights.get(key, 0.0) * value for key, value in components.items()) / total_weight


@tool
def odesign_screening(known_ligands: dict, pocket: dict, structure: dict, literature_seed_smiles: list[str] | None = None) -> dict:
    """Generate and dock candidate ligands via the ODesign model (config: `odesign.*`).

    Seeded from known_ligands (search_known_ligands's resolved compounds) plus
    any additional compounds `literature_seed_smiles` reports from
    literature_agent's findings. Docks every `odesign.dock_every_n_generations`
    generations against the pocket (Vina); combines ODesign's own predicted
    score, the docking score (when available), and similarity to the seed
    ligands into a single composite score per candidate.

    Returns the same `{"results": [...]}` shape as the old dock_library, so
    validate_positive_controls/filter_hits/predict_admet need no changes —
    each result still carries `smiles`/`role`/`best_affinity_kcal_mol`
    alongside the new `model_score`/`ligand_similarity`/`composite_score`/
    `generation` fields. Note: filter_hits currently drops any result with no
    `best_affinity_kcal_mol`, which only docked generations have — most
    candidates here come from non-docked generations, so revisit filter_hits
    to rank by composite_score with missing-docking handled gracefully.
    """
    cfg = load_config().odesign
    seeds = [
        ligand["smiles"] for ligand in known_ligands.get("known_ligands", []) if ligand.get("resolved") and ligand.get("smiles")
    ]
    seeds.extend(literature_seed_smiles or [])
    if not seeds:
        raise ValueError("no seed ligands available (search_known_ligands + literature_seed_smiles are both empty)")

    all_results = []
    for generation in range(cfg.num_generations):
        candidates = _odesign_generate(seeds, generation, cfg.population_size)
        docked = generation % cfg.dock_every_n_generations == 0
        affinities = _dock_smiles(structure, pocket, [c["smiles"] for c in candidates]) if docked else [None] * len(candidates)

        for candidate, affinity in zip(candidates, affinities, strict=True):
            smiles = candidate["smiles"]
            similarity = _max_similarity(smiles, seeds)
            all_results.append(
                {
                    "name": candidate.get("name") or f"gen{generation}_{smiles[:12]}",
                    "role": "candidate",
                    "smiles": smiles,
                    "generation": generation,
                    "model_score": candidate.get("model_score"),
                    "ligand_similarity": similarity,
                    "best_affinity_kcal_mol": affinity,
                    "composite_score": _composite_score(candidate.get("model_score"), affinity, similarity, cfg.score_weights, cfg),
                }
            )

    # Known ligands ride along as positive controls, same as the old assemble_screening_library.
    controls = [ligand for ligand in known_ligands.get("known_ligands", []) if ligand.get("resolved") and ligand.get("smiles")]
    control_affinities = _dock_smiles(structure, pocket, [c["smiles"] for c in controls])
    for ligand, affinity in zip(controls, control_affinities, strict=True):
        all_results.append(
            {
                "name": ligand.get("title") or ligand["query"],
                "role": "positive_control",
                "smiles": ligand["smiles"],
                "generation": None,
                "model_score": None,
                "ligand_similarity": 1.0,
                "best_affinity_kcal_mol": affinity,
                "composite_score": None,
            }
        )

    all_results.sort(key=lambda r: (r["composite_score"] is None, -(r["composite_score"] or 0)))
    return {
        "results": all_results,
        "num_generations": cfg.num_generations,
        "docked_generations": list(range(0, cfg.num_generations, cfg.dock_every_n_generations)),
    }


@tool
def validate_positive_controls(docking_results: dict) -> dict:
    """Check whether known positive controls recovered a top-ranked affinity.

    A control "passes" if it ranks in the top `docking.positive_control_rank_threshold_pct`
    percent of the docked library by affinity. The screen is only trusted if every
    resolved positive control passes.
    """
    threshold_pct = load_config().docking.positive_control_rank_threshold_pct
    ranked = [r for r in docking_results["results"] if r.get("best_affinity_kcal_mol") is not None]
    ranked.sort(key=lambda r: r["best_affinity_kcal_mol"])
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
