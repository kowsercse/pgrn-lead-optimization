"""Stage 2a — interface mapping: locate the druggable pocket on the PGRN-Sortilin complex.

Hand-rolled (biopython neighbor search) — proto-tools has no interface/pocket-detection
wrapper. Prefers contacts to a co-crystallized ligand, since the real Sortilin-Progranulin
structures (6X48/6X4H/6X3L) each have one bound; falls back to inter-chain protein-protein
contacts for a ligand-free (e.g. predicted) complex.
"""

from io import StringIO

import requests
from Bio.PDB import NeighborSearch, PDBParser
from Bio.PDB.Polypeptide import is_aa

from conductor.ai.agents import tool
from workflows.config import load_config


def _load_structure_text(structure: dict) -> str:
    if structure.get("structure_pdb"):
        return structure["structure_pdb"]
    url = structure.get("structure_url")
    if not url:
        raise ValueError("structure must contain 'structure_url' or 'structure_pdb'")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


@tool
def map_interface_pocket(structure: dict) -> dict:
    """Identify PPI interface residues and the druggable pocket.

    `structure` is fetch_pdb_structure/predict_complex_structure output. Cutoffs
    and excluded residue names (e.g. waters) come from config.yaml's `interface`
    section.
    """
    cfg = load_config().interface
    cutoff = cfg.ligand_contact_cutoff_angstrom
    exclude = {name.upper() for name in cfg.exclude_resnames}

    parser = PDBParser(QUIET=True)
    model = parser.get_structure("complex", StringIO(_load_structure_text(structure)))[0]
    neighbor_search = NeighborSearch(list(model.get_atoms()))

    ligand_residues = [
        residue
        for chain in model
        for residue in chain
        if residue.id[0].startswith("H_") and residue.resname.upper() not in exclude
    ]

    if ligand_residues:
        contacts: set[tuple[str, int, str]] = set()
        for ligand in ligand_residues:
            for atom in ligand:
                for nearby_atom in neighbor_search.search(atom.coord, cutoff):
                    residue = nearby_atom.get_parent()
                    if residue.id[0] == " " and is_aa(residue):
                        contacts.add((residue.get_parent().id, residue.id[1], residue.resname))
        return {
            "method": "ligand_contact",
            "reference_ligands": sorted({ligand.resname for ligand in ligand_residues}),
            "pocket_residues": [{"chain": c, "resnum": n, "resname": r} for c, n, r in sorted(contacts)],
        }

    chain_ids = [chain.id for chain in model]
    if len(chain_ids) < 2:
        return {
            "method": "none",
            "pocket_residues": [],
            "note": "single chain, no bound ligand — cannot map an interface",
        }

    contacts = set()
    for chain in model:
        other_atoms = [atom for other in model if other.id != chain.id for atom in other.get_atoms()]
        other_ns = NeighborSearch(other_atoms)
        for residue in chain:
            if residue.id[0] != " " or not is_aa(residue):
                continue
            if any(other_ns.search(atom.coord, cutoff) for atom in residue):
                contacts.add((chain.id, residue.id[1], residue.resname))

    return {
        "method": "interchain_contact",
        "pocket_residues": [{"chain": c, "resnum": n, "resname": r} for c, n, r in sorted(contacts)],
    }
