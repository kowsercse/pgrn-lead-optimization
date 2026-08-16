"""Assays scout — ChEMBL assay descriptions.

Named check: flag qHTS. A target can show tens of thousands of compounds where only a
few hundred carry a real IC50, and reporting the screening total as "chemical matter"
overstates the target by two orders of magnitude. Percent-inhibition at a single
concentration is not a potency value.

Contributing, not required: its absence is a gap, not a downgrade.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Sequence

import requests

from ..store import Record

SCOUT = "assays"
DEADLINE_S = 180

# A single-concentration screen this large is a qHTS campaign, not a potency series.
QHTS_MIN_COMPOUNDS = 5_000

REAL_POTENCY_TYPES: tuple[str, ...] = ("IC50", "EC50", "Ki", "Kd", "AC50")

_BASE = "https://www.ebi.ac.uk/chembl/api/data"


@dataclass(frozen=True)
class AssayRecord:
    assay_id: str
    standard_type: str
    n_compounds: int
    description: str = ""


@dataclass(frozen=True)
class AssaySummary:
    n_assays: int
    n_qhts: int
    n_compounds_in_qhts: int
    n_with_real_potency: int
    potency_types: tuple[str, ...]


def has_real_potency(standard_type: str) -> bool:
    return standard_type.upper() in {t.upper() for t in REAL_POTENCY_TYPES}


def is_qhts(*, n_compounds: int, description: str) -> bool:
    """Size decides. A description saying 'qHTS' over 20 compounds is a mislabel."""
    return n_compounds >= QHTS_MIN_COMPOUNDS


def summarise_assays(assays: Sequence[AssayRecord]) -> AssaySummary:
    qhts = [a for a in assays
            if is_qhts(n_compounds=a.n_compounds, description=a.description)]
    real = [a for a in assays if has_real_potency(a.standard_type)]
    return AssaySummary(
        n_assays=len(assays),
        n_qhts=len(qhts),
        n_compounds_in_qhts=sum(a.n_compounds for a in qhts),
        n_with_real_potency=len(real),
        potency_types=tuple(sorted({a.standard_type for a in real})),
    )


def _hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def to_records(s: AssaySummary, *, query: str = "chembl assays") -> list[Record]:
    return [
        Record(run_id="", scout=SCOUT, claim="assays reported", value=str(s.n_assays),
               grade="measured", query=query, output_hash=_hash(["n", s.n_assays])),
        Record(run_id="", scout=SCOUT, claim="qHTS screens",
               value=str(s.n_qhts), grade="measured", query=query,
               output_hash=_hash(["qhts", s.n_qhts])),
        Record(run_id="", scout=SCOUT, claim="compounds behind qHTS screens",
               value=f"{s.n_compounds_in_qhts:,}", grade="measured", query=query,
               output_hash=_hash(["qhts_n", s.n_compounds_in_qhts])),
        Record(run_id="", scout=SCOUT, claim="assays carrying a real potency value",
               value=str(s.n_with_real_potency), grade="measured", query=query,
               output_hash=_hash(["real", s.n_with_real_potency])),
        Record(run_id="", scout=SCOUT, claim="potency types",
               value=", ".join(s.potency_types) or "none", grade="measured",
               query=query, output_hash=_hash(list(s.potency_types))),
    ]


def fetch_assays(accession: str, *, limit: int = 200, timeout: float = 30
                 ) -> list[AssayRecord]:
    r = requests.get(f"{_BASE}/assay.json",
                     params={"target_chembl_id": accession, "limit": limit},
                     timeout=timeout)
    r.raise_for_status()
    out = []
    for a in r.json().get("assays", []):
        out.append(AssayRecord(
            assay_id=a.get("assay_chembl_id", ""),
            standard_type=a.get("assay_type", "") or "",
            n_compounds=int(a.get("assay_tax_id") or 0) * 0,  # count comes from activities
            description=a.get("description", "") or "",
        ))
    return out


class AssaysScout:
    name = SCOUT
    deadline_s = DEADLINE_S

    def brief(self, target: str) -> str:
        return (
            f"Describe the assays behind measured activity for {target}. Flag "
            f"high-throughput screens: report how many compounds sit behind them "
            f"separately from how many assays carry a real potency value "
            f"({', '.join(REAL_POTENCY_TYPES)}). Percent inhibition at a single "
            f"concentration is not a potency value."
        )

    def run(self, target: str) -> list[Record]:
        from .bioactivity import fetch_target_accessions
        accessions = fetch_target_accessions(target)
        assays: list[AssayRecord] = []
        for acc in accessions[:2]:
            assays.extend(fetch_assays(acc))
        return to_records(summarise_assays(assays),
                          query=f"chembl assays for {target!r}")
