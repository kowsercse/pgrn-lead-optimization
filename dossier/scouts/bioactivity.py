"""Bioactivity scout — ChEMBL.

Named check: report **distinct compounds**, never activity records. The same molecule
is routinely measured in several assays, so the two counts differ by an order of
magnitude. A target that looks well-populated by record count can be thin by compound
count, and the dossier's third question depends on the difference.

Parsing and summarising are pure and tested offline. Only `fetch_*` touches the network.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import requests

from ..store import Record

SCOUT = "bioactivity"
DEADLINE_S = 180

_BASE = "https://www.ebi.ac.uk/chembl/api/data"
_WEB = "https://www.ebi.ac.uk/chembl/compound_report_card/{chembl_id}/"
_TARGET_WEB = "https://www.ebi.ac.uk/chembl/target_report_card/{chembl_id}/"


@dataclass(frozen=True)
class Activity:
    molecule_chembl_id: str
    pchembl_value: float | None
    standard_type: str
    assay_chembl_id: str


@dataclass(frozen=True)
class BioactivitySummary:
    n_records: int
    n_distinct_compounds: int
    n_with_pchembl: int
    assay_types: tuple[str, ...]
    pchembl_min: float | None = None
    pchembl_max: float | None = None
    pchembl_median: float | None = None
    target_accessions: tuple[str, ...] = ()


def pchembl_to_nm(pchembl: float) -> float:
    """pChEMBL is -log10(molar); express it as nanomolar."""
    return 10 ** (9 - pchembl)


def parse_activity(payload: dict[str, Any]) -> Activity:
    raw = payload.get("pchembl_value")
    return Activity(
        molecule_chembl_id=payload["molecule_chembl_id"],
        pchembl_value=float(raw) if raw not in (None, "") else None,
        standard_type=payload.get("standard_type", "UNKNOWN"),
        assay_chembl_id=payload.get("assay_chembl_id", ""),
    )


def summarise(
    activities: Sequence[Activity], *, target_accessions: Iterable[str] = ()
) -> BioactivitySummary:
    values = [a.pchembl_value for a in activities if a.pchembl_value is not None]
    return BioactivitySummary(
        n_records=len(activities),
        n_distinct_compounds=len({a.molecule_chembl_id for a in activities}),
        n_with_pchembl=len(values),
        assay_types=tuple(sorted({a.standard_type for a in activities})),
        pchembl_min=min(values) if values else None,
        pchembl_max=max(values) if values else None,
        pchembl_median=statistics.median(values) if values else None,
        target_accessions=tuple(target_accessions),
    )


def _hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def to_records(s: BioactivitySummary, *, query: str = "chembl activities") -> list[Record]:
    """`run_id` is stamped by dispatch."""
    records = [
        Record(run_id="", scout=SCOUT, claim="distinct compounds with measured activity",
               value=str(s.n_distinct_compounds), grade="measured", query=query,
               output_hash=_hash(["distinct", s.n_distinct_compounds])),
        Record(run_id="", scout=SCOUT, claim="activity records",
               value=str(s.n_records), grade="measured", query=query,
               output_hash=_hash(["records", s.n_records])),
        Record(run_id="", scout=SCOUT, claim="assay types",
               value=", ".join(s.assay_types) or "none", grade="measured", query=query,
               output_hash=_hash(list(s.assay_types))),
    ]
    if s.pchembl_median is not None:
        strongest = pchembl_to_nm(s.pchembl_max)
        weakest = pchembl_to_nm(s.pchembl_min)
        records.append(Record(
            run_id="", scout=SCOUT, claim="potency range",
            value=(f"{strongest:.3g} nM to {weakest:.3g} nM, "
                   f"median {pchembl_to_nm(s.pchembl_median):.3g} nM "
                   f"(n={s.n_with_pchembl} of {s.n_records} records)"),
            grade="measured", query=query,
            output_hash=_hash([s.pchembl_min, s.pchembl_max, s.pchembl_median])))
    records += [
        Record(run_id="", scout=SCOUT, claim="target accession",
               value=acc, grade="verified", source_id=acc,
               source_url=_TARGET_WEB.format(chembl_id=acc), query=query)
        for acc in s.target_accessions
    ]
    return records


# --- network adapters ----------------------------------------------------

def fetch_target_accessions(target: str, *, timeout: float = 30) -> list[str]:
    r = requests.get(f"{_BASE}/target/search.json", params={"q": target}, timeout=timeout)
    r.raise_for_status()
    return [t["target_chembl_id"] for t in r.json().get("targets", [])]


def fetch_activities(
    accession: str, *, limit: int = 1000, timeout: float = 30
) -> list[Activity]:
    out: list[Activity] = []
    url: str | None = f"{_BASE}/activity.json"
    params: dict[str, Any] | None = {"target_chembl_id": accession, "limit": 200}
    while url and len(out) < limit:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        body = r.json()
        out.extend(parse_activity(a) for a in body.get("activities", []))
        nxt = body.get("page_meta", {}).get("next")
        url = f"https://www.ebi.ac.uk{nxt}" if nxt else None
        params = None  # `next` already carries the query string
    return out[:limit]


class BioactivityScout:
    """Conforms to `dossier.dispatch.Scout`."""

    name = SCOUT
    deadline_s = DEADLINE_S

    def brief(self, target: str) -> str:
        return (
            f"Find measured bioactivity for {target}. Report the number of DISTINCT "
            f"compounds carrying a measured value, separately from the number of "
            f"activity records — the same molecule is routinely measured several times "
            f"and the two counts differ substantially. Report the potency range, the "
            f"median, and the assay types the values came from."
        )

    def run(self, target: str) -> list[Record]:
        accessions = fetch_target_accessions(target)
        activities: list[Activity] = []
        for acc in accessions[:3]:
            activities.extend(fetch_activities(acc))
        summary = summarise(activities, target_accessions=accessions[:3])
        return to_records(summary, query=f"chembl target.search={target!r} + activities")
