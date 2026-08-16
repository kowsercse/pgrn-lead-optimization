"""Structures scout — RCSB PDB.

Named check: count entries whose bound ligand is drug-like separately from total
entries. A target can show dozens of depositions where only a handful have anything
worth designing against; the rest are apo, fragments, ions or crystallisation
additives.

Parsing is pure and tested offline. Only `fetch_*` touches the network.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import requests

from ..store import Record

# Target-agnostic thresholds. See SPEC.md THRESHOLDS.
DRUGLIKE_MW = 250.0
DRUGLIKE_HEAVY = 15

SCOUT = "structures"
DEADLINE_S = 180

_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
_ENTRY = "https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
_COMP = "https://data.rcsb.org/rest/v1/core/chemcomp/{het}"
_WEB = "https://www.rcsb.org/structure/{pdb_id}"


@dataclass(frozen=True)
class Ligand:
    het_code: str
    name: str
    mw: float
    heavy_atoms: int


@dataclass(frozen=True)
class StructureHit:
    pdb_id: str
    resolution: float | None
    method: str
    ligands: tuple[Ligand, ...] = ()


def is_druglike(ligand: Ligand) -> bool:
    return ligand.mw >= DRUGLIKE_MW and ligand.heavy_atoms >= DRUGLIKE_HEAVY


def parse_entry(entry: dict[str, Any], components: Sequence[dict[str, Any]]) -> StructureHit:
    resolutions = entry.get("rcsb_entry_info", {}).get("resolution_combined") or []
    methods = entry.get("exptl") or [{}]
    ligands = tuple(
        Ligand(
            het_code=c["chem_comp"]["id"],
            name=c["chem_comp"].get("name", ""),
            mw=float(c["chem_comp"].get("formula_weight") or 0.0),
            heavy_atoms=int(c.get("rcsb_chem_comp_info", {}).get("atom_count_heavy") or 0),
        )
        for c in components
    )
    return StructureHit(
        pdb_id=entry["rcsb_id"],
        resolution=float(resolutions[0]) if resolutions else None,
        method=methods[0].get("method", "UNKNOWN"),
        ligands=ligands,
    )


def _hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _describe(hit: StructureHit) -> str:
    res = f"{hit.resolution} A" if hit.resolution is not None else "no resolution"
    hets = ", ".join(l.het_code for l in hit.ligands if is_druglike(l))
    return f"PDB {hit.pdb_id}, {res}, {hit.method}, drug-like ligand: {hets}"


def to_records(hits: Sequence[StructureHit], *, query: str = "rcsb search") -> list[Record]:
    """Turn parsed hits into graded records. `run_id` is stamped by dispatch."""
    druglike = [h for h in hits if any(is_druglike(l) for l in h.ligands)]
    records: list[Record] = [
        Record(run_id="", scout=SCOUT, claim="total structures",
               value=str(len(hits)), grade="measured", query=query,
               output_hash=_hash([h.pdb_id for h in hits])),
        Record(run_id="", scout=SCOUT, claim="structures with a drug-like ligand",
               value=str(len(druglike)), grade="measured", query=query,
               output_hash=_hash([h.pdb_id for h in druglike])),
    ]
    records += [
        Record(run_id="", scout=SCOUT, claim="candidate structure",
               value=_describe(h), grade="verified",
               source_id=h.pdb_id, source_url=_WEB.format(pdb_id=h.pdb_id),
               query=query)
        for h in druglike
    ]
    return records


# --- network adapters (thin by design; the logic above is what is tested) ---

def fetch_pdb_ids(target: str, *, limit: int = 50, timeout: float = 30) -> list[str]:
    body = {
        "query": {"type": "terminal", "service": "full_text",
                  "parameters": {"value": target}},
        "return_type": "entry",
        "request_options": {"paginate": {"start": 0, "rows": limit}},
    }
    r = requests.post(_SEARCH, json=body, timeout=timeout)
    if r.status_code == 204:  # RCSB returns 204 for "no hits"
        return []
    r.raise_for_status()
    return [item["identifier"] for item in r.json().get("result_set", [])]


def fetch_hit(pdb_id: str, *, timeout: float = 30) -> StructureHit:
    entry = requests.get(_ENTRY.format(pdb_id=pdb_id), timeout=timeout)
    entry.raise_for_status()
    payload = entry.json()
    hets = payload.get("rcsb_entry_container_identifiers", {}).get("non_polymer_entity_ids") or []
    comps: list[dict[str, Any]] = []
    for het in payload.get("pdbx_entity_nonpoly", []) if hets else []:
        code = het.get("comp_id")
        if not code:
            continue
        c = requests.get(_COMP.format(het=code), timeout=timeout)
        if c.ok:
            comps.append(c.json())
    return parse_entry(payload, comps)


class StructuresScout:
    """Conforms to `dossier.dispatch.Scout`."""

    name = SCOUT
    deadline_s = DEADLINE_S

    def brief(self, target: str) -> str:
        return (
            f"Find experimentally determined structures of {target}. For each, report "
            f"the PDB identifier, resolution, experimental method, and the chemical "
            f"component identifiers of any bound non-polymer ligand. Count entries whose "
            f"bound ligand exceeds {DRUGLIKE_MW:.0f} Da and {DRUGLIKE_HEAVY} heavy atoms "
            f"separately from the total number of entries."
        )

    def run(self, target: str) -> list[Record]:
        ids = fetch_pdb_ids(target)
        hits = [fetch_hit(pdb_id) for pdb_id in ids]
        return to_records(hits, query=f"rcsb full_text={target!r} limit=50")
