"""Shared helpers for workflows/tools/* — structure I/O used across multiple stages."""

from io import StringIO

import requests
from Bio.PDB import PDBIO, PDBParser, Select


def load_structure_text(structure: dict) -> str:
    """Return raw structure text from a fetch_pdb_structure/predict_complex_structure result."""
    if structure.get("structure_pdb"):
        return structure["structure_pdb"]
    url = structure.get("structure_url")
    if not url:
        raise ValueError("structure must contain 'structure_url' or 'structure_pdb'")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


class _PolymerOnly(Select):
    def accept_residue(self, residue) -> bool:
        return residue.id[0] == " "


def strip_heteroatoms(pdb_text: str) -> str:
    """Drop waters/glycans/co-crystallized ligands, keeping only polymer residues.

    Docking tools (e.g. Vina/Meeko) parameterize the receptor against polymer
    chemical templates only — heteroatoms with no template (including
    RCSB's "UNL" placeholder for unregistered ligands) abort preparation, and
    proto-tools' `allow_bad_residues` doesn't cover that case, so the
    receptor needs to be pre-cleaned instead.
    """
    model = PDBParser(QUIET=True).get_structure("receptor", StringIO(pdb_text))[0]
    io = PDBIO()
    io.set_structure(model)
    buffer = StringIO()
    io.save(buffer, select=_PolymerOnly())
    return buffer.getvalue()
