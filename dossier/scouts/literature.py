"""Literature scout — NCBI E-utilities.

Named check: search pathway and phenotypic aliases, not only the direct target. A
published series filed against a pathway or phenotypic identifier rather than the
molecular target is invisible to a target-only query, and that is precisely how a
relevant med-chem campaign gets missed.

Contributing, not required: its absence is a gap, not a downgrade.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Sequence

import requests

from ..store import Record

SCOUT = "literature"
DEADLINE_S = 180

_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_PUBMED_WEB = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

# Phenotypic and programme-level framings a target-only query never reaches.
_ANGLES = (
    "{t}",
    "{t} AND (inhibitor OR modulator OR antagonist)",
    "{t} AND (structure-activity OR medicinal chemistry)",
    "{t} AND (clinical trial OR phase)",
)


def alias_queries(target: str, *, aliases: Sequence[str] = ()) -> list[str]:
    """One query per angle per name. Deduplicated, order preserved."""
    names = list(dict.fromkeys([target, *aliases]))
    seen: dict[str, None] = {}
    for name in names:
        for angle in _ANGLES:
            seen.setdefault(angle.format(t=name), None)
    return list(seen)


def parse_esearch(payload: dict[str, Any]) -> tuple[list[str], int]:
    result = payload.get("esearchresult", {})
    try:
        total = int(result.get("count", 0))
    except (TypeError, ValueError):
        total = 0
    return list(result.get("idlist", [])), total


def parse_esummary(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    result = payload.get("result", {})
    out: list[tuple[str, str, str]] = []
    for uid in result.get("uids", []):
        item = result.get(uid, {})
        out.append((uid, item.get("title", ""), item.get("pubdate", "")))
    return out


def _hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def to_records(
    papers: Sequence[tuple[str, str, str]],
    *,
    total: int,
    queries: Sequence[str],
    max_cited: int = 5,
) -> list[Record]:
    records = [
        Record(run_id="", scout=SCOUT, claim="alias queries run",
               value=str(len(queries)), grade="measured",
               query="; ".join(queries)[:400], output_hash=_hash(list(queries))),
        Record(run_id="", scout=SCOUT, claim="publications found",
               value=str(total), grade="measured",
               query="; ".join(queries)[:400], output_hash=_hash(["total", total])),
    ]
    records += [
        Record(run_id="", scout=SCOUT, claim="publication",
               value=f"{title} ({pubdate})" if pubdate else title,
               grade="verified", source_id=pmid,
               source_url=_PUBMED_WEB.format(pmid=pmid),
               query=f"pubmed esummary {pmid}")
        for pmid, title, pubdate in papers[:max_cited]
    ]
    return records


def fetch_pmids(query: str, *, retmax: int = 10, timeout: float = 30
                ) -> tuple[list[str], int]:
    r = requests.get(f"{_EUTILS}/esearch.fcgi",
                     params={"db": "pubmed", "term": query, "retmax": retmax,
                             "retmode": "json"}, timeout=timeout)
    r.raise_for_status()
    return parse_esearch(r.json())


def fetch_summaries(pmids: Sequence[str], *, timeout: float = 30
                    ) -> list[tuple[str, str, str]]:
    if not pmids:
        return []
    r = requests.get(f"{_EUTILS}/esummary.fcgi",
                     params={"db": "pubmed", "id": ",".join(pmids),
                             "retmode": "json"}, timeout=timeout)
    r.raise_for_status()
    return parse_esummary(r.json())


class LiteratureScout:
    name = SCOUT
    deadline_s = DEADLINE_S

    def brief(self, target: str) -> str:
        return (
            f"Survey the literature on {target}. Search pathway and phenotypic "
            f"framings as well as the target name itself — a series filed against a "
            f"pathway identifier is invisible to a target-only query. Report mechanism, "
            f"disease link, and clinical outcomes including failures."
        )

    def run(self, target: str) -> list[Record]:
        queries = alias_queries(target)
        pmids: list[str] = []
        total = 0
        for q in queries:
            found, count = fetch_pmids(q, retmax=5)
            total = max(total, count)
            pmids.extend(p for p in found if p not in pmids)
        return to_records(fetch_summaries(pmids[:5]), total=total, queries=queries)
