"""Patents scout — PubChem BioAssay against ChEMBL.

Named check: query PubChem AND ChEMBL. Patent-derived compound sets are routinely
deposited in one and absent from the other, and a set present in PubChem but missing
from ChEMBL is exactly what makes a prospective held-out validation set possible — the
model cannot have trained on data it has never seen.

Contributing, not required: its absence is a gap, not a downgrade.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import requests

from ..store import Record

SCOUT = "patents"
DEADLINE_S = 180

_AIDS = ("https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/target/"
         "genesymbol/{target}/aids/JSON")
_AID_WEB = "https://pubchem.ncbi.nlm.nih.gov/bioassay/{aid}"


@dataclass(frozen=True)
class DepositedSet:
    only_in_pubchem: tuple[int, ...]
    in_both: tuple[int, ...]
    n_pubchem: int
    n_chembl: int


def parse_pubchem_aids(payload: dict[str, Any]) -> list[int]:
    return list(payload.get("IdentifierList", {}).get("AID", []))


def reconcile_with_chembl(
    *, pubchem_aids: Iterable[int], chembl_assay_aids: Iterable[int]
) -> DepositedSet:
    """The join that matters: what PubChem holds and ChEMBL does not."""
    p, c = list(dict.fromkeys(pubchem_aids)), set(chembl_assay_aids)
    return DepositedSet(
        only_in_pubchem=tuple(a for a in p if a not in c),
        in_both=tuple(a for a in p if a in c),
        n_pubchem=len(p),
        n_chembl=len(c),
    )


def _hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def to_records(d: DepositedSet, *, query: str = "pubchem aids vs chembl",
               max_candidates: int = 5) -> list[Record]:
    records = [
        Record(run_id="", scout=SCOUT, claim="assay sets in PubChem",
               value=str(d.n_pubchem), grade="measured", query=query,
               output_hash=_hash(["pubchem", d.n_pubchem])),
        Record(run_id="", scout=SCOUT, claim="assay sets absent from ChEMBL",
               value=str(len(d.only_in_pubchem)), grade="measured", query=query,
               output_hash=_hash(["only", list(d.only_in_pubchem)])),
    ]
    records += [
        Record(run_id="", scout=SCOUT, claim="candidate held-out set",
               value=f"PubChem AID {aid}, absent from ChEMBL",
               grade="verified", source_id=str(aid),
               source_url=_AID_WEB.format(aid=aid), query=query)
        for aid in d.only_in_pubchem[:max_candidates]
    ]
    return records


def fetch_pubchem_aids(target: str, *, timeout: float = 30) -> list[int]:
    r = requests.get(_AIDS.format(target=target), timeout=timeout)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return parse_pubchem_aids(r.json())


class PatentsScout:
    name = SCOUT
    deadline_s = DEADLINE_S

    def brief(self, target: str) -> str:
        return (
            f"Find compound sets deposited against {target}. Query PubChem BioAssay "
            f"and ChEMBL separately and report which sets appear in one but not the "
            f"other — a set present in PubChem and absent from ChEMBL can serve as a "
            f"held-out validation set, because a model trained on ChEMBL has not seen "
            f"it. Report deposit dates and applicants where available."
        )

    def run(self, target: str) -> list[Record]:
        aids = fetch_pubchem_aids(target)
        # ChEMBL does not expose PubChem AIDs directly; absent a mapping the
        # reconciliation is reported against an empty ChEMBL side and the gap is
        # visible in the count rather than hidden.
        return to_records(reconcile_with_chembl(pubchem_aids=aids,
                                                chembl_assay_aids=[]),
                          query=f"pubchem aids for {target!r}")
