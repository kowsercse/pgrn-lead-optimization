"""Receptor selection — which structure the design work should use.

Not harmonisation. This links two *different* things: the chemical core a patent series
is built on, and the molecule bound in a candidate structure. If they match, that
structure holds something close to what the project would be working on, which can
outweigh a sharper picture of a site holding something unrelated.
"""
from __future__ import annotations

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")


def scaffold_match(series_core_smiles: str, ligand_smiles: str) -> bool:
    """Is the series core contained in the bound ligand? Direction matters: the core
    must sit inside the ligand, not the reverse."""
    core = Chem.MolFromSmiles(series_core_smiles)
    ligand = Chem.MolFromSmiles(ligand_smiles)
    if core is None or ligand is None:
        return False
    return ligand.HasSubstructMatch(core)
