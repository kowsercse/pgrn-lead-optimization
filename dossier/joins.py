"""Cross-source joins — the findings no single database returns.

Any one query returns a list. The value is in the joins between sources:

  1. scaffold_match       a patent series' core against a structure's bound ligand,
                          yielding a receptor matched to the chemotype being scored
  2. holdout_disjointness one compound set subtracted from another on canonical
                          identifiers, yielding a validation set separated by date
  3. alias_resolution     series filed against pathway or phenotypic identifiers
                          rather than the molecular target
  4. record_vs_compound   activity-record counts reconciled against distinct compounds

All four are pure. Only `alias_resolution` reaches outward, and its lookup is injected.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from rdkit import Chem, RDLogger

from .store import Record

RDLogger.DisableLog("rdApp.*")  # unparseable input is data, not a program error


@dataclass(frozen=True)
class Disjointness:
    novel: set[str]      # holdout \ train — members absent from training
    overlap: set[str]    # train ∩ holdout — members present in both


def inchikey(smiles: str) -> str | None:
    """Canonical identity. Two spellings of one molecule must collapse to one key."""
    mol = Chem.MolFromSmiles(smiles)
    return Chem.MolToInchiKey(mol) if mol is not None else None


def _keys(smiles: Iterable[str]) -> set[str]:
    return {k for k in (inchikey(s) for s in smiles) if k is not None}


def holdout_disjointness(
    train: Iterable[str], holdout: Iterable[str]
) -> Disjointness:
    """Join 2. Both operands normalised to InChIKey before comparison, so a different
    SMILES traversal of the same molecule is not mistaken for a novel compound."""
    t, h = _keys(train), _keys(holdout)
    return Disjointness(novel=h - t, overlap=h & t)


def scaffold_match(series_core_smiles: str, ligand_smiles: str) -> bool:
    """Join 1. Is the series core contained in the ligand? Direction matters."""
    core = Chem.MolFromSmiles(series_core_smiles)
    ligand = Chem.MolFromSmiles(ligand_smiles)
    if core is None or ligand is None:
        return False
    return ligand.HasSubstructMatch(core)


def alias_resolution(
    target: str, *, lookup: Callable[[str], Sequence[str]]
) -> list[str]:
    """Join 3. Pathway and phenotypic identifiers, not only the molecular target.
    A lookup failure degrades to the target alone rather than taking the run down."""
    try:
        found = list(lookup(target))
    except Exception:
        found = []
    return sorted({target, *found})


def record_vs_compound(n_records: int, n_distinct: int) -> tuple[int, int, bool]:
    """Join 4. Reconcile the two counts. `conflated` is True when they differ, which
    is the normal case — the same molecule is measured in several assays. Reporting
    the record count as the compound count overstates the available matter."""
    if n_distinct > n_records:
        raise ValueError(
            f"distinct compounds ({n_distinct}) cannot exceed records ({n_records})"
        )
    return n_records, n_distinct, n_records != n_distinct


def _hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


def to_records(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    disjointness: Disjointness,
    scaffold_matched: bool,
    aliases: Sequence[str],
    counts: tuple[int, int, bool],
) -> list[Record]:
    """Persist one `join_result` row per join and return the dossier records."""
    n_records, n_distinct, conflated = counts
    findings = [
        ("holdout_disjointness",
         f"{len(disjointness.novel)} novel, {len(disjointness.overlap)} overlap",
         "holdout disjointness"),
        ("scaffold_match",
         "series core is present in the receptor ligand" if scaffold_matched
         else "series core is absent from the receptor ligand",
         "scaffold match"),
        ("alias_resolution", ", ".join(aliases), "target aliases searched"),
        ("record_vs_compound",
         f"{n_records} activity records over {n_distinct} distinct compounds"
         + (" — counts differ" if conflated else " — counts agree"),
         "record versus compound reconciliation"),
    ]

    conn.executemany(
        "INSERT INTO join_result (join_id, run_id, kind, result, grade) VALUES (?,?,?,?,?)",
        [(uuid.uuid4().hex, run_id, kind, result, "measured")
         for kind, result, _ in findings],
    )
    conn.commit()

    return [
        Record(run_id=run_id, scout="joins", claim=claim, value=result,
               grade="measured", query=f"join:{kind}", output_hash=_hash([kind, result]))
        for kind, result, claim in findings
    ]
