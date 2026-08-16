"""Harmonisation — making the sources agree about what is the same thing.

Five databases describe overlapping reality in incompatible ways. Before any count
means anything, three kinds of sameness have to be resolved:

  same molecule    pool_compounds     one molecule in two databases, written two ways,
                                      must be one entry — otherwise the target looks
                                      richer in chemical matter than it is
  same protein     alias_resolution   one protein under several names; work filed under
                                      a pathway or disease name is invisible to a search
                                      on the protein's own name
  same evidence    record_vs_compound one molecule measured several times is one
                                      molecule; reporting the measurement count
                                      overstates the available matter

This is not comparison for difference. Nothing here looks for what one source has and
another lacks — every source contributes, and harmonisation is what stops the same fact
being counted twice or missed entirely.

All three are pure. Only `alias_resolution` reaches outward, and its lookup is injected.
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


def inchikey(smiles: str) -> str | None:
    """Canonical identity. Two spellings of one molecule must collapse to one key."""
    mol = Chem.MolFromSmiles(smiles)
    return Chem.MolToInchiKey(mol) if mol is not None else None


def _keys(smiles: Iterable[str]) -> set[str]:
    return {k for k in (inchikey(s) for s in smiles) if k is not None}


def pool_compounds(*sources: Iterable[str]) -> set[str]:
    """Merge every source on canonical identity.

    All measured molecules are evidence of chemical matter, wherever they were
    deposited, so they are pooled rather than partitioned. Canonical identity is what
    stops the same molecule — reported by two databases under different SMILES — from
    being counted twice and flattering the target.
    """
    pooled: set[str] = set()
    for source in sources:
        pooled |= _keys(source)
    return pooled


def alias_resolution(
    target: str, *, lookup: Callable[[str], Sequence[str]]
) -> list[str]:
    """Pathway and phenotypic identifiers, not only the molecular target.
    A lookup failure degrades to the target alone rather than taking the run down."""
    try:
        found = list(lookup(target))
    except Exception:
        found = []
    return sorted({target, *found})


def record_vs_compound(n_records: int, n_distinct: int) -> tuple[int, int, bool]:
    """Reconcile the two counts. `conflated` is True when they differ, which
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
    pooled: set[str],
    aliases: Sequence[str],
    counts: tuple[int, int, bool],
) -> list[Record]:
    """Persist one `join_result` row per harmonisation and return the dossier records."""
    n_records, n_distinct, conflated = counts
    findings = [
        ("pooled_compounds",
         f"{len(pooled)} distinct molecules across all sources",
         "pooled chemical matter"),
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
